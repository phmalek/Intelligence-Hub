from io import BytesIO
from pathlib import Path
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from openpyxl import Workbook

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from opportunity import OPPORTUNITY_CONFIG, compute_headroom_scores
except ImportError:
    from dashboard_python_output.opportunity import OPPORTUNITY_CONFIG, compute_headroom_scores

try:
    import numpy as np
    from scipy.optimize import curve_fit
except Exception:
    np = None
    curve_fit = None

BASE_DIR = Path('/home/ali/repos/porsche')
CSV_PATH = BASE_DIR / 'pwc reports' / 'outputs' / 'python_output_all.csv'
S50_LOOKUP_PATH = BASE_DIR / 'pwc reports' / 'outputs' / 's50_spend_lookup.csv'

st.set_page_config(page_title='Python Output Dashboard', layout='wide')

load_dotenv()

@st.cache_data
def load_data(csv_path: Path, mtime: float):
    df = pd.read_csv(csv_path, low_memory=False)
    df['report_date'] = pd.to_datetime(df.get('report_date'), errors='coerce')
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'].astype(str), format='%Y%m%d', errors='coerce')
    df['report_week'] = df.get('report_week', pd.Series(dtype=str)).astype(str).str.strip()
    for col in ['Media Spend', 'Number of Sessions', 'DCFS', 'Forms Submission Started']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


@st.cache_data
def load_s50_lookup(csv_path: Path, mtime: float):
    if not csv_path.exists():
        return pd.DataFrame(), []
    lookup = pd.read_csv(csv_path, low_memory=False)
    if 's50_spend' not in lookup.columns or 'Market' not in lookup.columns:
        return pd.DataFrame(), []
    lookup['s50_spend'] = pd.to_numeric(lookup['s50_spend'], errors='coerce')

    join_cols = ['Market']
    if 'Channel' in lookup.columns:
        join_cols.append('Channel')
    if 'Model' in lookup.columns:
        join_cols.append('Model')

    lookup = lookup[join_cols + ['s50_spend']].copy()
    return lookup, join_cols


def _pdf_escape(text: str) -> str:
    sanitized = text.encode('latin-1', errors='replace').decode('latin-1')
    return sanitized.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _text_to_pdf_bytes(text: str) -> bytes:
    # Minimal PDF writer for plain text output.
    lines = text.splitlines() or ['']
    lines_per_page = 50
    pages = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]

    objects = []
    xref_positions = []
    buffer = []

    def add_obj(obj_str: str):
        xref_positions.append(sum(len(s.encode('latin-1')) for s in buffer))
        buffer.append(obj_str)

    buffer.append('%PDF-1.4\n')
    add_obj('1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
    kids = ' '.join([f'{3 + i * 2} 0 R' for i in range(len(pages))])
    add_obj(f'2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>\nendobj\n')

    for idx, page_lines in enumerate(pages):
        content_stream = 'BT\n/F1 11 Tf\n72 740 Td\n'
        for line in page_lines:
            content_stream += f'({_pdf_escape(line)}) Tj\n0 -14 Td\n'
        content_stream += 'ET\n'
        content_bytes = content_stream.encode('latin-1')
        obj_num = 3 + idx * 2
        add_obj(
            f'{obj_num} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
            f'/Contents {obj_num + 1} 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n'
        )
        add_obj(
            f'{obj_num + 1} 0 obj\n<< /Length {len(content_bytes)} >>\nstream\n'
            f'{content_stream}endstream\nendobj\n'
        )

    add_obj('5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n')

    xref_start = sum(len(s.encode('latin-1')) for s in buffer)
    xref = ['xref\n0 {}\n'.format(len(xref_positions) + 1), '0000000000 65535 f \n']
    for pos in xref_positions:
        xref.append(f'{pos:010d} 00000 n \n')
    buffer.append(''.join(xref))
    buffer.append(
        f'trailer\n<< /Size {len(xref_positions) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n'
    )
    return ''.join(buffer).encode('latin-1')


def _build_step_payload(results: pd.DataFrame) -> dict:
    payload = {}
    payload['rows'] = len(results)
    payload['gate_passed_rate'] = float(results['gate_passed'].mean()) if 'gate_passed' in results else None
    payload['headroom'] = results['headroom_score'].describe().to_dict() if 'headroom_score' in results else {}
    payload['headroom_tier_counts'] = (
        results['headroom_tier'].value_counts().to_dict() if 'headroom_tier' in results else {}
    )
    payload['scale_score'] = results['scale_score'].describe().to_dict() if 'scale_score' in results else {}
    payload['curve_zone_counts'] = (
        results['curve_zone'].value_counts().to_dict() if 'curve_zone' in results else {}
    )
    payload['volatility'] = results['volatility'].describe().to_dict() if 'volatility' in results else {}
    payload['vol_tier_counts'] = (
        results['vol_tier'].value_counts().to_dict() if 'vol_tier' in results else {}
    )
    payload['opportunity_score'] = (
        results['opportunity_score'].describe().to_dict() if 'opportunity_score' in results else {}
    )
    payload['opportunity_tier_counts'] = (
        results['opportunity_tier'].value_counts().to_dict() if 'opportunity_tier' in results else {}
    )
    return payload


def _run_llm_report(step_payload: dict, step_text: str, final_text: str, progress=None) -> str:
    if OpenAI is None:
        return 'LLM client not available. Install openai package.'
    client = OpenAI()
    outputs = []
    total_steps = len(step_payload) + 1
    completed = 0
    for step_name, content in step_payload.items():
        prompt = (
            f'You are the analyst for {step_name}. Explain this step in simple language for marketers, '
            f'use the provided stats and the step definition.\n\n'
            f'Step definition:\n{step_text}\n\n'
            f'Stats:\n{content}\n'
        )
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
        )
        outputs.append(f'## {step_name}\n{response.choices[0].message.content}')
        completed += 1
        if progress:
            progress.progress(completed / total_steps, text=f'Completed {step_name}')

    synthesis_prompt = (
        'You are the final reporting agent. Use the step summaries below to write a clear, '
        'non-technical report with a short executive summary, key findings per step, '
        'and a concise conclusion.\n\n'
        f'Step summaries:\n{chr(10).join(outputs)}\n\n'
        f'Final reporting guidance:\n{final_text}\n'
    )
    completed += 1
    if progress:
        progress.progress(completed / total_steps, text='Final report synthesis')
    final_response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': synthesis_prompt}],
    )
    report = '\n'.join(outputs) + '\n\n# Final Report\n' + final_response.choices[0].message.content
    return report

df = load_data(CSV_PATH, CSV_PATH.stat().st_mtime)
s50_lookup, s50_join_cols = load_s50_lookup(
    S50_LOOKUP_PATH, S50_LOOKUP_PATH.stat().st_mtime if S50_LOOKUP_PATH.exists() else 0
)
if not s50_lookup.empty and s50_join_cols:
    df = df.merge(s50_lookup, on=s50_join_cols, how='left', suffixes=('', '_lookup'))
    if 's50_spend_lookup' in df.columns:
        df['s50_spend'] = df['s50_spend_lookup']
        df = df.drop(columns=['s50_spend_lookup'])

st.title('Python Output Dashboard')

numeric_cols = df.select_dtypes(include='number').columns.tolist()
numeric_cols = [col for col in numeric_cols if col not in {'Date'}]

categorical_cols = [
    col for col in [
        'Market', 'Model', 'Ad Type', 'Channel', 'Platform', 'Activation Group',
        'Campaign', 'calendar_week', 'week_relative', 'week_text', 'report_week'
    ]
    if col in df.columns
]

def _label_value(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 'not specified'
    if isinstance(value, str):
        text = value.strip()
        return text if text else 'not specified'
    return str(value)


def _safe_ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _aggregate_metrics(df_in):
    media = df_in['Media Spend'].sum()
    visits = df_in['Number of Sessions'].sum()
    forms = df_in['Forms Submission Started'].sum()
    dcfs = df_in['DCFS'].sum()
    v2l = _safe_ratio(dcfs, visits)
    return media, visits, forms, dcfs, v2l


def _add_section_header(rows, market, model, week_label):
    rows.append(['Markets', market, None, None, None, None])
    if model is not None:
        rows.append(['Models', model, None, None, None, None])
    rows.append(['calendar_week', week_label, None, None, None, None])
    rows.append([None, None, None, None, None, None])
    rows.append(['Row Labels', 'Media Spend', 'Vists (Sessions)', 'Forms Started', 'DCFS', 'Visits to Lead CR'])


def _add_channel_section(rows, df_in):
    base = df_in.copy()
    for col in ['Channel', 'Platform', 'Activation Group']:
        base[col] = base[col].apply(_label_value)

    grouped = (
        base.groupby(['Channel', 'Platform', 'Activation Group'], dropna=False)
        .agg({
            'Media Spend': 'sum',
            'Number of Sessions': 'sum',
            'Forms Submission Started': 'sum',
            'DCFS': 'sum',
        })
        .reset_index()
    )
    grouped['Visits to Lead CR'] = grouped.apply(
        lambda r: _safe_ratio(r['DCFS'], r['Number of Sessions']), axis=1
    )

    def sort_key(value):
        text = str(value).strip()
        return (text.lower() == 'not specified', text)

    channels = sorted(grouped['Channel'].unique(), key=sort_key)
    for channel in channels:
        rows.append([channel, None, None, None, None, None])
        channel_df = grouped[grouped['Channel'] == channel]
        platforms = sorted(channel_df['Platform'].unique(), key=sort_key)
        for platform in platforms:
            rows.append([platform, None, None, None, None, None])
            platform_df = channel_df[channel_df['Platform'] == platform]
            activations = sorted(platform_df['Activation Group'].unique(), key=sort_key)
            for activation in activations:
                row = platform_df[platform_df['Activation Group'] == activation].iloc[0]
                rows.append([
                    activation,
                    row['Media Spend'],
                    row['Number of Sessions'],
                    row['Forms Submission Started'],
                    row['DCFS'],
                    row['Visits to Lead CR'],
                ])

    total = _aggregate_metrics(base)
    rows.append(['Grand Total', *total])


def _add_model_summary(rows, df_in):
    base = df_in.copy()
    base['Model'] = base['Model'].apply(_label_value)
    grouped = (
        base.groupby('Model', dropna=False)
        .agg({
            'Media Spend': 'sum',
            'Number of Sessions': 'sum',
            'Forms Submission Started': 'sum',
            'DCFS': 'sum',
        })
        .reset_index()
    )
    grouped['Visits to Lead CR'] = grouped.apply(
        lambda r: _safe_ratio(r['DCFS'], r['Number of Sessions']), axis=1
    )

    for _, row in grouped.sort_values('Model').iterrows():
        rows.append([
            row['Model'],
            row['Media Spend'],
            row['Number of Sessions'],
            row['Forms Submission Started'],
            row['DCFS'],
            row['Visits to Lead CR'],
        ])

    total = _aggregate_metrics(base)
    rows.append(['Grand Total', *total])


def build_close_gap_workbook(df_in, market, week_label):
    rows = []
    _add_section_header(rows, market, 'All', week_label)
    _add_channel_section(rows, df_in)
    rows.append([None, None, None, None, None, None])
    rows.append([None, None, None, None, None, None])

    _add_section_header(rows, market, None, week_label)
    _add_model_summary(rows, df_in)
    rows.append([None, None, None, None, None, None])
    rows.append([None, None, None, None, None, None])

    for model in sorted(df_in['Model'].dropna().unique()):
        model_df = df_in[df_in['Model'] == model]
        _add_section_header(rows, market, model, week_label)
        _add_channel_section(rows, model_df)
        rows.append([None, None, None, None, None, None])
        rows.append([None, None, None, None, None, None])

    wb = Workbook()
    ws = wb.active
    ws.title = 'Sheet1'
    for row in rows:
        ws.append(row)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def _saturation_curve(x, a, b):
    return a * x / (b + x)


def fit_saturation(x, y):
    if np is None or curve_fit is None:
        return None, None
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y) & (x >= 0)
    x = x[mask]
    y = y[mask]
    if len(x) < 3:
        return None, None
    a0 = max(y.max(), 1.0)
    b0 = max(np.median(x), 1.0)
    try:
        params, _ = curve_fit(
            _saturation_curve,
            x,
            y,
            p0=[a0, b0],
            bounds=([0.0, 0.0], [np.inf, np.inf]),
            maxfev=20000,
        )
        return params[0], params[1]
    except Exception:
        return None, None


with st.sidebar:
    page = st.radio(
        'Page',
        ['Overview', 'Market CPL', 'Opportunity Headroom', 'Close the Gap Export', 'KPI vs Investment'],
        horizontal=True,
    )
    st.header('Filters')
    if page == 'Overview':
        metric = st.selectbox('Metric', numeric_cols)
        agg_func = st.selectbox('Aggregate', ['sum', 'mean', 'median'])
    else:
        metric = None
        agg_func = None

    if page in {'Overview', 'Market CPL'}:
        if 'Model' not in df.columns:
            st.warning('Model column not found in the dataset.')
            st.stop()

        if page == 'Overview':
            if 'Market' not in df.columns:
                st.warning('Market column not found in the dataset.')
                st.stop()
            market_options = ['All'] + sorted(df['Market'].dropna().unique())
            market = st.selectbox('Market', market_options)
            base_df = df if market == 'All' else df[df['Market'] == market]
        else:
            market = None
            base_df = df

        model_options = ['All'] + sorted(base_df['Model'].dropna().unique())
        if not model_options:
            st.warning('No models available for the selected filters.')
            st.stop()
        model = st.selectbox('Model', model_options)
        model_df = base_df if model == 'All' else base_df[base_df['Model'] == model]

        campaign_options = []
        if 'Campaign' in model_df.columns:
            campaign_options = ['All'] + sorted(model_df['Campaign'].dropna().unique())
        campaign = st.selectbox('Campaign', campaign_options) if campaign_options else None

        filtered = model_df
        if campaign and campaign != 'All':
            filtered = filtered[filtered['Campaign'] == campaign]

        if filtered.empty:
            st.warning('No data available for the current filters.')
            st.stop()

        if page == 'Overview':
            top_n = st.slider('Top N series', 5, 30, 10)
        else:
            top_n = None
        export_market = None
        export_weeks = None
    elif page == 'Close the Gap Export':
        if 'Market' not in df.columns:
            st.warning('Market column not found in the dataset.')
            st.stop()
        export_market = st.selectbox('Market', sorted(df['Market'].dropna().unique()))
        campaign_options = ['All']
        if 'Campaign' in df.columns:
            campaign_options += sorted(df['Campaign'].dropna().unique())
        export_campaign = st.selectbox('Campaign', campaign_options)
        date_mode = st.radio('Filter by', ['Weeks', 'Date range'], horizontal=True)
        week_options = sorted(df['calendar_week'].dropna().unique()) if 'calendar_week' in df.columns else []
        week_choices = ['All'] + week_options
        export_weeks = st.multiselect('Weeks', week_choices, default=['All'], disabled=date_mode == 'Date range')
        export_dates = None
        date_col = None
        if date_mode == 'Date range':
            date_col = 'Date' if 'Date' in df.columns else 'report_date'
            if date_col not in df.columns:
                st.warning('No date column found for date range filtering.')
                st.stop()
            date_series = pd.to_datetime(df[date_col], errors='coerce')
            min_date = date_series.min()
            max_date = date_series.max()
            if pd.isna(min_date) or pd.isna(max_date):
                st.warning('Date column has no valid values.')
                st.stop()
            export_dates = st.date_input(
                'Date range',
                value=(min_date.date(), max_date.date()),
                min_value=min_date.date(),
                max_value=max_date.date(),
            )
        filtered = None
        model_df = None
        market = None
        campaign = None
        top_n = None
        kpi_filters = None
    elif page == 'Opportunity Headroom':
        market_options = ['All'] + sorted(df['Market'].dropna().unique()) if 'Market' in df.columns else ['All']
        channel_options = ['All'] + sorted(df['Channel'].dropna().unique()) if 'Channel' in df.columns else ['All']
        model_options = ['All'] + sorted(df['Model'].dropna().unique()) if 'Model' in df.columns else ['All']

        headroom_high_input = st.number_input(
            'Headroom high threshold',
            min_value=0.01,
            max_value=5.0,
            value=float(OPPORTUNITY_CONFIG['headroom_high']),
            step=0.01,
            format='%.2f',
        )
        recent_cpl_periods_input = st.number_input(
            'Recent CPL periods',
            min_value=1,
            max_value=52,
            value=int(OPPORTUNITY_CONFIG['recent_cpl_periods']),
            step=1,
        )
        recent_scale_periods_input = st.number_input(
            'Recent scale periods',
            min_value=1,
            max_value=52,
            value=int(OPPORTUNITY_CONFIG['recent_scale_periods']),
            step=1,
        )
        recent_curve_periods_input = st.number_input(
            'Recent curve periods',
            min_value=1,
            max_value=52,
            value=int(OPPORTUNITY_CONFIG['recent_curve_periods']),
            step=1,
        )
        growth_ratio_max_input = st.number_input(
            'Growth ratio max',
            min_value=0.01,
            max_value=5.0,
            value=float(OPPORTUNITY_CONFIG['growth_ratio_max']),
            step=0.01,
            format='%.2f',
        )
        mid_ratio_max_input = st.number_input(
            'Mid ratio max',
            min_value=0.01,
            max_value=5.0,
            value=float(OPPORTUNITY_CONFIG['mid_ratio_max']),
            step=0.01,
            format='%.2f',
        )
        curve_group_candidates = [col for col in ['calendar_week', 'Date', 'report_date'] if col in df.columns]
        curve_group_by = (
            st.selectbox('Curve group by', curve_group_candidates) if curve_group_candidates else None
        )
        group_by_candidates = [col for col in ['Market', 'Channel', 'Model'] if col in df.columns]
        group_by = st.selectbox('Group plots by', group_by_candidates, index=0) if group_by_candidates else None
        uploaded_s50 = st.file_uploader('Upload s50 lookup CSV', type=['csv'])
        opp_market = st.selectbox('Market', market_options)
        opp_channel = st.selectbox('Channel', channel_options)
        opp_model = st.selectbox('Model', model_options)
        filtered = None
        model_df = None
        market = None
        campaign = None
        top_n = None
        kpi_filters = None
    elif page == 'KPI vs Investment':
        if 'Market' not in df.columns:
            st.warning('Market column not found in the dataset.')
            st.stop()
        kpi_market = st.selectbox('Market', ['All'] + sorted(df['Market'].dropna().unique()))
        kpi_channels = []
        if 'Channel' in df.columns:
            channel_choices = ['All'] + sorted(df['Channel'].dropna().unique())
            kpi_channels = st.multiselect('Channels', channel_choices, default=['All'])
        kpi_campaigns = []
        if 'Campaign' in df.columns:
            campaign_choices = ['All'] + sorted(df['Campaign'].dropna().unique())
            kpi_campaigns = st.multiselect('Campaigns', campaign_choices, default=['All'])
        kpi_platforms = []
        if 'Platform' in df.columns:
            platform_choices = ['All'] + sorted(df['Platform'].dropna().unique())
            kpi_platforms = st.multiselect('Platforms', platform_choices, default=['All'])
        kpi_models = []
        if 'Model' in df.columns:
            model_choices = ['All'] + sorted(df['Model'].dropna().unique())
            kpi_models = st.multiselect('Models', model_choices, default=['All'])
        kpi_activations = []
        if 'Activation Group' in df.columns:
            activation_choices = ['All'] + sorted(df['Activation Group'].dropna().unique())
            kpi_activations = st.multiselect('Activation Groups', activation_choices, default=['All'])

        kpi_options = [
            'Visits (Sessions)',
            'Dealer Contract Form Submissions',
            'DCFS',
            'Sessions to DCFS Conversion Rate',
            'Cost per Lead (Forms Submission Started)',
            'Cost per Lead (DCFS)',
        ]
        kpi_choice = st.selectbox('KPI', kpi_options)

        color_candidates = [None]
        for col in ['Channel', 'Campaign', 'Platform', 'Model', 'Activation Group']:
            if col in df.columns:
                color_candidates.append(col)
        color_by = st.selectbox('Color by', color_candidates, format_func=lambda x: x or 'None')

        group_candidates = []
        for col in ['calendar_week', 'Date', 'report_date']:
            if col in df.columns:
                group_candidates.append(col)
        group_by = st.selectbox('Group by', group_candidates) if group_candidates else None

        kpi_filters = {
            'market': kpi_market,
            'channels': kpi_channels,
            'campaigns': kpi_campaigns,
            'platforms': kpi_platforms,
            'models': kpi_models,
            'activations': kpi_activations,
            'kpi': kpi_choice,
            'color_by': color_by,
            'group_by': group_by,
        }
        filtered = None
        model_df = None
        market = None
        campaign = None
        top_n = None

if page == 'Opportunity Headroom':
    st.subheader('Efficiency headroom (Step 1)')
    config_override = dict(OPPORTUNITY_CONFIG)
    config_override['headroom_high'] = float(headroom_high_input)
    config_override['recent_cpl_periods'] = int(recent_cpl_periods_input)
    config_override['recent_scale_periods'] = int(recent_scale_periods_input)
    config_override['recent_curve_periods'] = int(recent_curve_periods_input)
    config_override['growth_ratio_max'] = float(growth_ratio_max_input)
    config_override['mid_ratio_max'] = float(mid_ratio_max_input)
    df_input = df.copy()
    if uploaded_s50 is not None:
        try:
            upload_df = pd.read_csv(uploaded_s50)
            if 's50_spend' in upload_df.columns and 'Market' in upload_df.columns:
                join_cols = ['Market']
                if 'Channel' in upload_df.columns:
                    join_cols.append('Channel')
                if 'Model' in upload_df.columns:
                    join_cols.append('Model')
                upload_df['s50_spend'] = pd.to_numeric(upload_df['s50_spend'], errors='coerce')
                upload_df = upload_df[join_cols + ['s50_spend']].copy()
                df_input = df_input.merge(upload_df, on=join_cols, how='left', suffixes=('', '_upload'))
                if 's50_spend_upload' in df_input.columns:
                    df_input['s50_spend'] = df_input['s50_spend_upload']
                    df_input = df_input.drop(columns=['s50_spend_upload'])
            else:
                st.warning('s50 upload needs at least Market and s50_spend columns.')
        except Exception:
            st.warning('Unable to read the uploaded s50 CSV.')

    if opp_market != 'All':
        df_input = df_input[df_input['Market'] == opp_market]
    if opp_channel != 'All':
        df_input = df_input[df_input['Channel'] == opp_channel]
    if opp_model != 'All':
        df_input = df_input[df_input['Model'] == opp_model]

    results, missing = compute_headroom_scores(df_input, config_override)
    if missing:
        st.warning(f'Missing required columns: {", ".join(missing)}')
        st.stop()
    if results.empty:
        st.warning('No data available to compute headroom.')
        st.stop()

    st.subheader('LLM report')
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        st.warning('OPENAI_API_KEY is not set in .env.')
    else:
        step_definitions = {
            'Step 0 — Data sufficiency gate': (
                'If n_weeks < min_weeks_required OR total_spend < min_total_spend OR '
                'total_dcfs < min_total_dcfs => tier NONE and score 0.'
            ),
            'Step 1 — Efficiency headroom': (
                'current_cpl = median CPL of most recent 3 valid periods. '
                'benchmark_cpl_p25 = 25th percentile with fallbacks. '
                'headroom = (current_cpl - benchmark) / benchmark; clamp; score from headroom.'
            ),
            'Step 2 — Scalable volume': (
                'avg_dcfs_recent = mean DCFS over most recent 4 periods. '
                'scale_score = percentile rank within channel.'
            ),
            'Step 3 — Curve position': (
                'spend_recent vs s50_spend ratio defines GROWTH/MID/SATURATED; curve_score 100/50/0.'
            ),
            'Step 4 — Predictability penalty (volatility)': (
                'volatility = (q3 - q1) / (q3 + q1) on CPL; tiered to penalties.'
            ),
            'Step 5 — Opportunity score aggregation': (
                'raw = 0.45*headroom_score + 0.25*scale_score + 0.30*curve_score; '
                'opportunity_score = clamp(raw - predictability_penalty, 0, 100).'
            ),
            'Step 6 — Opportunity tier mapping': (
                'Score thresholds: >=70 HIGH, >=40 MEDIUM, >=15 LOW, else NONE. '
                'Overrides: SATURATED => max LOW; headroom NONE => max MEDIUM; VERY_HIGH volatility => NONE.'
            ),
        }
        final_guidance = (
            'Write for non-technical marketers: short sentences, explain why scores change, '
            'call out top opportunities and risks. Avoid formulas unless necessary.'
        )
        if st.button('Generate LLM Report (Markdown)'):
            with st.spinner('Generating report...'):
                progress = st.progress(0, text='Starting report...')
                payload = _build_step_payload(results)
                report_text = _run_llm_report(payload, step_definitions, final_guidance, progress=progress)
                progress.progress(1.0, text='Report ready')
                st.markdown(report_text)
                st.download_button(
                    'Download report (Markdown)',
                    data=report_text,
                    file_name='opportunity_report.md',
                    mime='text/markdown',
                )

    st.subheader('Cost per lead distribution')
    cpl_df = df_input.copy()
    cpl_df['Media Spend'] = pd.to_numeric(cpl_df['Media Spend'], errors='coerce')
    cpl_df['DCFS'] = pd.to_numeric(cpl_df['DCFS'], errors='coerce')
    cpl_df = cpl_df[(cpl_df['Media Spend'] > 0) & (cpl_df['DCFS'] > 0)]
    cpl_df['cpl'] = cpl_df['Media Spend'] / cpl_df['DCFS']
    if cpl_df.empty:
        st.info('No CPL data available for the current filters.')
    else:
        if group_by:
            cpl_df['group'] = cpl_df[group_by]
        else:
            cpl_df['group'] = 'All'
        cpl_order = (
            cpl_df.groupby('group', dropna=False)['cpl']
            .median()
            .sort_values(ascending=False)
            .index.tolist()
        )
        fig = px.box(
            cpl_df,
            x='group',
            y='cpl',
            points=False,
            labels={'group': group_by or 'Group', 'cpl': 'CPL'},
        )
        fig.update_xaxes(categoryorder='array', categoryarray=cpl_order)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader('Headroom by group')
    base_df = results[results['gate_passed']].copy()
    base_df = base_df.dropna(subset=['headroom', 'scale_score'])
    if base_df.empty:
        st.info('No headroom data for the current filters.')
    else:
        if group_by:
            agg_df = (
                base_df.groupby(group_by, dropna=False)
                .agg(
                    headroom_pct=('headroom', lambda s: float((s * 100).mean())),
                    scale_score=('scale_score', 'mean'),
                    curve_score=('curve_score', 'mean'),
                    spend_recent=('spend_recent', 'mean'),
                )
                .reset_index()
                .rename(columns={group_by: 'group'})
            )
        else:
            agg_df = pd.DataFrame({
                'group': ['All'],
                'headroom_pct': [(base_df['headroom'] * 100).mean()],
                'scale_score': [base_df['scale_score'].mean()],
                'curve_score': [base_df['curve_score'].mean()],
                'spend_recent': [base_df['spend_recent'].mean()],
            })
        group_order = (
            agg_df.sort_values('headroom_pct', ascending=False)['group'].tolist()
            if 'headroom_pct' in agg_df.columns
            else agg_df['group'].tolist()
        )
        palette = px.colors.qualitative.Safe
        group_color_map = {
            group: palette[idx % len(palette)] for idx, group in enumerate(group_order)
        }
        plot_df = agg_df.dropna(subset=['headroom_pct'])
        if plot_df.empty:
            st.info('No headroom data for the current filters.')
        else:
            high_pct = float(headroom_high_input) * 100
            med_pct = float(OPPORTUNITY_CONFIG['headroom_med']) * 100
            plot_df['tier'] = 'LOW'
            plot_df.loc[plot_df['headroom_pct'] >= med_pct, 'tier'] = 'MED'
            plot_df.loc[plot_df['headroom_pct'] >= high_pct, 'tier'] = 'HIGH'
            fig = px.bar(
                plot_df.sort_values('headroom_pct', ascending=False),
                x='group',
                y='headroom_pct',
                text='tier',
                color='group',
                labels={'headroom_pct': 'Headroom %', 'group': group_by or 'Group'},
                color_discrete_map=group_color_map,
            )
            fig.update_xaxes(categoryorder='array', categoryarray=group_order)
            fig.update_traces(
                texttemplate='%{text}',
                textposition='outside',
            )
            threshold_pct = float(headroom_high_input) * 100
            fig.add_hline(
                y=threshold_pct,
                line_dash='dash',
                line_color='orange',
                annotation_text=f'High threshold ({threshold_pct:.0f}%)',
                annotation_position='top left',
            )
            fig.update_yaxes(title_text='Headroom %')
            st.plotly_chart(fig, use_container_width=True)

        st.subheader('Scale (Step 2) by group')
        scale_df = plot_df.dropna(subset=['scale_score'])
        if scale_df.empty:
            st.info('No scale score data for the current filters.')
        else:
            fig = px.bar(
                scale_df.sort_values('scale_score', ascending=False),
                x='group',
                y='scale_score',
                text='scale_score',
                color='group',
                labels={'scale_score': 'Scale score (0–100)', 'group': group_by or 'Group'},
                color_discrete_map=group_color_map,
            )
            fig.update_xaxes(categoryorder='array', categoryarray=group_order)
            fig.update_traces(
                texttemplate='%{text:.0f}',
                textposition='outside',
            )
            fig.add_hline(
                y=75,
                line_dash='dash',
                line_color='orange',
                annotation_text='Top quartile (75th pct)',
                annotation_position='top left',
            )
            fig.update_yaxes(title_text='Scale score (0–100)', range=[0, 110])
            st.plotly_chart(fig, use_container_width=True)

        st.subheader('Predictability (Step 4) by group')
        vol_df = base_df.dropna(subset=['volatility'])
        if vol_df.empty:
            st.info('No volatility data for the current filters.')
        else:
            if group_by:
                vol_agg = (
                    vol_df.groupby(group_by, dropna=False)
                    .agg(
                        volatility=('volatility', 'median'),
                        predictability_penalty=('predictability_penalty', 'mean'),
                    )
                    .reset_index()
                    .rename(columns={group_by: 'group'})
                )
            else:
                vol_agg = vol_df.assign(group='All').agg(
                    volatility=('volatility', 'median'),
                    predictability_penalty=('predictability_penalty', 'mean'),
                ).to_frame().T
            vol_agg = vol_agg.dropna(subset=['volatility'])
            if vol_agg.empty:
                st.info('No volatility data for the current filters.')
            else:
                vol_low = float(OPPORTUNITY_CONFIG['vol_low'])
                vol_med = float(OPPORTUNITY_CONFIG['vol_med'])
                vol_high = float(OPPORTUNITY_CONFIG['vol_high'])
                vol_agg['vol_tier'] = 'VERY_HIGH'
                vol_agg.loc[vol_agg['volatility'] <= vol_high, 'vol_tier'] = 'HIGH'
                vol_agg.loc[vol_agg['volatility'] <= vol_med, 'vol_tier'] = 'MED'
                vol_agg.loc[vol_agg['volatility'] <= vol_low, 'vol_tier'] = 'LOW'
                fig = px.bar(
                    vol_agg.sort_values('volatility', ascending=False),
                    x='group',
                    y='volatility',
                    color='vol_tier',
                    labels={'volatility': 'Volatility (IQR / median)', 'group': group_by or 'Group'},
                    color_discrete_map={
                        'LOW': '#2ca02c',
                        'MED': '#f2c744',
                        'HIGH': '#ff7f0e',
                        'VERY_HIGH': '#d62728',
                    },
                )
                fig.update_xaxes(categoryorder='array', categoryarray=group_order)
                fig.add_hline(y=vol_low, line_dash='dash', line_color='#2ca02c', annotation_text='LOW')
                fig.add_hline(y=vol_med, line_dash='dash', line_color='#f2c744', annotation_text='MED')
                fig.add_hline(y=vol_high, line_dash='dash', line_color='#ff7f0e', annotation_text='HIGH')
                fig.update_yaxes(title_text='Volatility (IQR / median)')
                st.plotly_chart(fig, use_container_width=True)

        st.subheader('Opportunity score (Step 5) by group')
        opp_df = base_df.dropna(subset=['opportunity_score'])
        if opp_df.empty:
            st.info('No opportunity score data for the current filters.')
        else:
            if group_by:
                opp_agg = (
                    opp_df.groupby(group_by, dropna=False)['opportunity_score']
                    .mean()
                    .reset_index()
                    .rename(columns={group_by: 'group'})
                )
            else:
                opp_agg = pd.DataFrame({'group': ['All'], 'opportunity_score': [opp_df['opportunity_score'].mean()]})
            fig = px.bar(
                opp_agg.sort_values('opportunity_score', ascending=False),
                x='group',
                y='opportunity_score',
                text='opportunity_score',
                labels={'opportunity_score': 'Opportunity score (0–100)', 'group': group_by or 'Group'},
            )
            fig.update_xaxes(categoryorder='array', categoryarray=group_order)
            fig.update_traces(texttemplate='%{text:.0f}', textposition='outside')
            fig.update_yaxes(title_text='Opportunity score (0–100)', range=[0, 110])
            st.plotly_chart(fig, use_container_width=True)


        st.subheader('Media response curve (Step 3)')
        curve_data = df.copy()
        if opp_market != 'All':
            curve_data = curve_data[curve_data['Market'] == opp_market]
        if opp_channel != 'All':
            curve_data = curve_data[curve_data['Channel'] == opp_channel]
        if opp_model != 'All':
            curve_data = curve_data[curve_data['Model'] == opp_model]
        curve_data['Media Spend'] = pd.to_numeric(curve_data['Media Spend'], errors='coerce')
        curve_data['DCFS'] = pd.to_numeric(curve_data['DCFS'], errors='coerce')
        curve_data = curve_data[(curve_data['Media Spend'] > 0) & (curve_data['DCFS'] >= 0)]
        if curve_data.empty:
            st.info('No spend/DCFS data available for the current filters.')
        else:
            time_col = curve_group_by
            if not time_col:
                st.info('No time column available for curve aggregation.')
            else:
                worth_map = {}
                if group_by:
                    worth_map = (
                        results.groupby(group_by, dropna=False)['curve_worthy']
                        .max()
                        .rename_axis('group')
                        .to_dict()
                    )
                plot_df = (
                    curve_data.groupby([time_col, group_by], dropna=False)
                    .agg({'Media Spend': 'sum', 'DCFS': 'sum'})
                    .reset_index()
                )
                curve_fig = px.scatter(
                    plot_df,
                    x='Media Spend',
                    y='DCFS',
                    color=group_by,
                    labels={'Media Spend': 'Media Spend', 'DCFS': 'DCFS', group_by: group_by},
                    color_discrete_map=group_color_map if group_order else None,
                )
                color_map = {}
                for trace in curve_fig.data:
                    color_map[str(trace.name)] = trace.marker.color
                    if worth_map and not worth_map.get(str(trace.name), False):
                        trace.marker.color = '#9e9e9e'
                        trace.marker.opacity = 0.6
                if np is None or curve_fit is None:
                    st.info('Install scipy to enable curve fitting for Ax/(b+x).')
                else:
                    for group_key, group in plot_df.groupby(group_by, dropna=False):
                        group_label = str(group_key)
                        if worth_map and not worth_map.get(group_label, False):
                            continue
                        a, b = fit_saturation(group['Media Spend'], group['DCFS'])
                        if a is None or b is None:
                            continue
                        x_fit = np.linspace(group['Media Spend'].min(), group['Media Spend'].max(), 100)
                        y_fit = _saturation_curve(x_fit, a, b)
                        curve_fig.add_trace(
                            go.Scatter(
                                x=x_fit,
                                y=y_fit,
                                mode='lines',
                                name=f'{group_label} fit',
                                line=dict(dash='solid', color=color_map.get(group_label)),
                                showlegend=True,
                            )
                        )
                st.plotly_chart(curve_fig, use_container_width=True)

        st.subheader('Spend distribution by group (Step 3)')
        curve_plot = curve_data.copy()
        if curve_plot.empty or results.empty:
            st.info('No spend data available for the current filters.')
        else:
            if group_by:
                recent_map = (
                    results.groupby(group_by, dropna=False)['spend_recent']
                    .mean()
                    .rename_axis('group')
                    .to_dict()
                )
                s50_map = (
                    results.groupby(group_by, dropna=False)['s50_spend']
                    .mean()
                    .rename_axis('group')
                    .to_dict()
                )
            else:
                recent_map = {'All': results['spend_recent'].mean()}
                s50_map = {'All': results['s50_spend'].mean()}
            groups = [g for g in group_order if g in recent_map] if group_order else list(recent_map.keys())

            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=groups,
                    y=[recent_map.get(g) for g in groups],
                    marker=dict(color='#39ff14', opacity=0.35),
                    name='Recent spend',
                )
            )
            zone_colors = {
                'GROWTH': '#2ca02c',
                'MID': '#f2c744',
                'SATURATED': '#d62728',
                'UNKNOWN': '#9e9e9e',
            }
            for group in groups:
                group_mask = curve_plot[group_by] == group if group_by else pd.Series([True] * len(curve_plot))
                y_vals = curve_plot.loc[group_mask, 'Media Spend']
                if y_vals.empty:
                    continue
                spend_recent = recent_map.get(group)
                s50_spend = s50_map.get(group)
                zone = 'GROWTH'
                if spend_recent is None or s50_spend is None or s50_spend <= 0:
                    zone = 'UNKNOWN'
                else:
                    ratio = spend_recent / s50_spend
                    growth_ratio_max = float(growth_ratio_max_input)
                    mid_ratio_max = float(mid_ratio_max_input)
                    if ratio <= growth_ratio_max:
                        zone = 'GROWTH'
                    elif ratio <= mid_ratio_max:
                        zone = 'MID'
                    else:
                        zone = 'SATURATED'
                fig.add_trace(
                    go.Box(
                        x=[group] * len(y_vals),
                        y=y_vals,
                        boxpoints=False,
                        marker=dict(color='rgba(0,0,0,0)'),
                        line=dict(color=zone_colors.get(zone, '#9e9e9e')),
                        name=f'{group} ({zone})',
                        showlegend=False,
                    )
                )
            if group_order:
                fig.update_xaxes(categoryorder='array', categoryarray=group_order)
            fig.update_layout(yaxis_title='Media Spend')
            st.plotly_chart(fig, use_container_width=True)

    st.caption('Headroom is based on median CPL of the most recent 3 valid periods vs. historical P25 CPL.')

    display_cols = [
        'Market',
        'Channel',
        'Model',
        'current_cpl',
        'benchmark_cpl_p25',
        'benchmark_source',
        'headroom',
        'headroom_score',
        'headroom_tier',
        'avg_dcfs_recent',
        'avg_spend_recent',
        'scale_score',
        'scale_dist_n',
        'scale_dist_p25',
        'scale_dist_p50',
        'scale_dist_p75',
        'volatility',
        'vol_tier',
        'predictability_penalty',
        'raw_opportunity_score',
        'opportunity_score',
        'opportunity_tier',
        'tier_override_notes',
        'spend_recent',
        'k_used',
        's50_spend',
        'curve_ratio',
        'curve_zone_raw',
        'curve_score_raw',
        'curve_zone',
        'curve_score',
        'curve_worthy',
        'curve_worthiness_notes',
        'gate_passed',
        'gate_reasons',
        'audit',
    ]
    display_cols = [col for col in display_cols if col in results.columns]
    st.dataframe(results[display_cols].sort_values(['headroom_score'], ascending=False), use_container_width=True)
    st.download_button(
        'Download headroom results (CSV)',
        data=results.to_csv(index=False),
        file_name='opportunity_headroom_step1.csv',
        mime='text/csv',
    )
    st.stop()

if page == 'Market CPL':
    st.subheader('Average KPI by market')
    if 'Market' not in df.columns:
        st.warning('Market column not found in the dataset.')
        st.stop()
    required = {
        'media': 'Media Spend',
        'sessions': 'Number of Sessions',
        'dcfs': 'DCFS',
        'forms': 'Forms Submission Started',
    }
    for key, col in required.items():
        if col not in df.columns:
            required[key] = None

    week_options = sorted(df['calendar_week'].dropna().unique()) if 'calendar_week' in df.columns else []
    week_choices = ['All'] + week_options
    selected_weeks = st.multiselect('Weeks', week_choices, default=['All'])

    market_options = sorted(df['Market'].dropna().unique())
    market_choices = ['All'] + market_options
    selected_markets = st.multiselect('Markets', market_choices, default=['All'])

    channel_options = sorted(df['Channel'].dropna().unique()) if 'Channel' in df.columns else []
    channel_choices = ['All'] + channel_options
    selected_channels = st.multiselect('Channels', channel_choices, default=['All'])

    kpi_options = [
        'Media Invest',
        'Visits (Sessions)',
        'Dealer Contract Form Submissions',
        'DCFS',
        'Sessions to DCFS Conversion Rate',
        'Cost per Lead (Forms Submission Started)',
        'Cost per Lead (DCFS)',
        'Cost per Lead (both)',
    ]
    kpi_choice = st.selectbox('KPI', kpi_options)

    kpi_df = model_df.copy()
    if campaign and campaign != 'All':
        kpi_df = kpi_df[kpi_df['Campaign'] == campaign]
    if selected_weeks and 'All' not in selected_weeks:
        kpi_df = kpi_df[kpi_df['calendar_week'].isin(selected_weeks)]
    if selected_markets and 'All' not in selected_markets:
        kpi_df = kpi_df[kpi_df['Market'].isin(selected_markets)]
    if selected_channels and 'All' not in selected_channels and 'Channel' in kpi_df.columns:
        kpi_df = kpi_df[kpi_df['Channel'].isin(selected_channels)]

    if kpi_df.empty:
        st.warning('No data available for the selected weeks/markets.')
        st.stop()

    weekly_base = (
        kpi_df.groupby(['Market', 'calendar_week'], dropna=False)
        .agg({
            'Media Spend': 'sum',
            'Number of Sessions': 'sum',
            'DCFS': 'sum',
            'Forms Submission Started': 'sum',
        })
        .reset_index()
    )

    def safe_ratio(num, denom):
        return num / denom if denom else None

    if kpi_choice == 'Media Invest':
        weekly_base['kpi_value'] = weekly_base['Media Spend']
    elif kpi_choice == 'Visits (Sessions)':
        weekly_base['kpi_value'] = weekly_base['Number of Sessions']
    elif kpi_choice == 'Dealer Contract Form Submissions':
        weekly_base['kpi_value'] = weekly_base['Forms Submission Started']
    elif kpi_choice == 'DCFS':
        weekly_base['kpi_value'] = weekly_base['DCFS']
    elif kpi_choice == 'Sessions to DCFS Conversion Rate':
        weekly_base['kpi_value'] = weekly_base.apply(
            lambda r: safe_ratio(r['DCFS'], r['Number of Sessions']), axis=1
        )
    elif kpi_choice == 'Cost per Lead (Forms Submission Started)':
        weekly_base['kpi_value'] = weekly_base.apply(
            lambda r: safe_ratio(r['Media Spend'], r['Forms Submission Started']), axis=1
        )
    elif kpi_choice == 'Cost per Lead (DCFS)':
        weekly_base['kpi_value'] = weekly_base.apply(
            lambda r: safe_ratio(r['Media Spend'], r['DCFS']), axis=1
        )
    else:
        weekly_cpl_forms = weekly_base.copy()
        weekly_cpl_forms['kpi'] = 'CPL (Forms Submission Started)'
        weekly_cpl_forms['kpi_value'] = weekly_cpl_forms.apply(
            lambda r: safe_ratio(r['Media Spend'], r['Forms Submission Started']), axis=1
        )
        weekly_cpl_dcfs = weekly_base.copy()
        weekly_cpl_dcfs['kpi'] = 'CPL (DCFS)'
        weekly_cpl_dcfs['kpi_value'] = weekly_cpl_dcfs.apply(
            lambda r: safe_ratio(r['Media Spend'], r['DCFS']), axis=1
        )
        weekly_base = pd.concat([weekly_cpl_forms, weekly_cpl_dcfs], ignore_index=True)

    if kpi_choice == 'Cost per Lead (both)':
        avg_kpi = (
            weekly_base.groupby(['Market', 'kpi'], dropna=False)['kpi_value']
            .mean()
            .reset_index()
            .sort_values('kpi_value', ascending=False)
        )
    else:
        avg_kpi = (
            weekly_base.groupby('Market', dropna=False)['kpi_value']
            .mean()
            .reset_index()
            .sort_values('kpi_value', ascending=False)
        )
    weekly_base['week'] = weekly_base['calendar_week']

    st.subheader('Average + volatility (box plot)')
    if kpi_choice == 'Cost per Lead (both)':
        box_fig = px.box(
            weekly_base,
            x='Market',
            y='kpi_value',
            facet_col='kpi',
            points=False,
            labels={'kpi_value': kpi_choice, 'Market': 'Market'},
        )
        scatter_fig = px.strip(
            weekly_base,
            x='Market',
            y='kpi_value',
            color='week',
            facet_col='kpi',
        )
    else:
        box_fig = px.box(
            weekly_base,
            x='Market',
            y='kpi_value',
            points=False,
            labels={'kpi_value': kpi_choice, 'Market': 'Market'},
        )
        scatter_fig = px.strip(
            weekly_base,
            x='Market',
            y='kpi_value',
            color='week',
        )

    for trace in scatter_fig.data:
        trace.marker.size = 6
        trace.marker.opacity = 0.6
        box_fig.add_trace(trace)

    box_fig.update_layout(height=520, boxmode='overlay')
    st.plotly_chart(box_fig, use_container_width=True)

    st.subheader('KPI summary table (avg + volatility)')
    if kpi_choice == 'Cost per Lead (both)':
        summary_table = (
            weekly_base.groupby(['Market', 'kpi'], dropna=False)['kpi_value']
            .agg(avg_kpi='mean', volatility='std', weeks='count')
            .reset_index()
            .sort_values(['kpi', 'avg_kpi'], ascending=[True, False])
        )
        summary_table = summary_table.rename(columns={
            'avg_kpi': 'CPL average',
            'volatility': 'CPL volatility',
        })
    else:
        summary_table = (
            weekly_base.groupby('Market', dropna=False)['kpi_value']
            .agg(avg_kpi='mean', volatility='std', weeks='count')
            .reset_index()
            .sort_values('avg_kpi', ascending=False)
        )
        summary_table = summary_table.rename(columns={
            'avg_kpi': f'{kpi_choice} average',
            'volatility': f'{kpi_choice} volatility',
        })

    st.dataframe(summary_table)
    st.download_button(
        'Download KPI summary (CSV)',
        data=summary_table.to_csv(index=False),
        file_name='market_kpi_summary.csv',
        mime='text/csv',
    )

    st.subheader('All KPI summary table (avg + volatility)')
    full_weekly = (
        kpi_df.groupby(['Market', 'calendar_week'], dropna=False)
        .agg({
            'Media Spend': 'sum',
            'Number of Sessions': 'sum',
            'DCFS': 'sum',
            'Forms Submission Started': 'sum',
        })
        .reset_index()
    )

    full_weekly['Media Invest'] = full_weekly['Media Spend']
    full_weekly['Visits (Sessions)'] = full_weekly['Number of Sessions']
    full_weekly['Dealer Contract Form Submissions'] = full_weekly['Forms Submission Started']
    full_weekly['DCFS'] = full_weekly['DCFS']
    full_weekly['Sessions to DCFS Conversion Rate'] = full_weekly.apply(
        lambda r: safe_ratio(r['DCFS'], r['Number of Sessions']), axis=1
    )
    full_weekly['Cost per Lead (Forms Submission Started)'] = full_weekly.apply(
        lambda r: safe_ratio(r['Media Spend'], r['Forms Submission Started']), axis=1
    )
    full_weekly['Cost per Lead (DCFS)'] = full_weekly.apply(
        lambda r: safe_ratio(r['Media Spend'], r['DCFS']), axis=1
    )

    long_cols = [
        'Media Invest',
        'Visits (Sessions)',
        'Dealer Contract Form Submissions',
        'DCFS',
        'Sessions to DCFS Conversion Rate',
        'Cost per Lead (Forms Submission Started)',
        'Cost per Lead (DCFS)',
    ]
    long_kpis = full_weekly.melt(
        id_vars=['Market', 'calendar_week'],
        value_vars=long_cols,
        var_name='KPI',
        value_name='kpi_value',
    )
    all_kpi_summary = (
        long_kpis.groupby(['Market', 'KPI'], dropna=False)['kpi_value']
        .agg(avg='mean', volatility='std')
        .reset_index()
    )
    wide = all_kpi_summary.pivot(index='Market', columns='KPI')
    wide.columns = [f'{kpi} {stat}' for stat, kpi in wide.columns]
    wide = wide.reset_index()

    st.dataframe(wide)
    st.download_button(
        'Download all KPI summary (CSV)',
        data=wide.to_csv(index=False),
        file_name='market_kpi_summary_all.csv',
        mime='text/csv',
    )
    st.stop()

if page == 'Close the Gap Export':
    required_cols = [
        'Market',
        'Model',
        'Channel',
        'Platform',
        'Activation Group',
        'Media Spend',
        'Number of Sessions',
        'Forms Submission Started',
        'DCFS',
        'calendar_week',
    ]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        st.warning(f'Missing required columns: {", ".join(missing)}')
        st.stop()

    export_df = df[df['Market'] == export_market].copy()
    if export_campaign != 'All' and 'Campaign' in export_df.columns:
        export_df = export_df[export_df['Campaign'] == export_campaign]
    if date_mode == 'Date range':
        date_col = 'Date' if 'Date' in export_df.columns else 'report_date'
        export_df[date_col] = pd.to_datetime(export_df[date_col], errors='coerce')
        if not export_dates or len(export_dates) != 2:
            st.warning('Select a start and end date.')
            st.stop()
        start_date, end_date = export_dates
        export_df = export_df[
            (export_df[date_col] >= pd.Timestamp(start_date))
            & (export_df[date_col] <= pd.Timestamp(end_date))
        ]
    elif export_weeks and 'All' not in export_weeks:
        export_df = export_df[export_df['calendar_week'].isin(export_weeks)]

    if export_df.empty:
        st.warning('No data available for the selected market/weeks.')
        st.stop()

    if date_mode == 'Date range':
        week_label = f'{export_dates[0]} to {export_dates[1]}'
    else:
        week_label = 'All' if not export_weeks or 'All' in export_weeks else ', '.join(export_weeks)
    st.subheader('Close the Gap Export')
    st.caption('Exports the same stacked tables as the shared PCL Excel file.')

    workbook = build_close_gap_workbook(export_df, export_market, week_label)
    st.download_button(
        'Download Excel',
        data=workbook,
        file_name=f'Porsche_Close_the_Gap_{export_market}_2025.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    st.stop()

if page == 'KPI vs Investment':
    required_cols = [
        'Media Spend',
        'Number of Sessions',
        'Forms Submission Started',
        'DCFS',
    ]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        st.warning(f'Missing required columns: {", ".join(missing)}')
        st.stop()

    data = df.copy()
    if kpi_filters['market'] != 'All':
        data = data[data['Market'] == kpi_filters['market']]
    if kpi_filters['channels'] and 'All' not in kpi_filters['channels']:
        data = data[data['Channel'].isin(kpi_filters['channels'])]
    if kpi_filters['campaigns'] and 'All' not in kpi_filters['campaigns']:
        data = data[data['Campaign'].isin(kpi_filters['campaigns'])]
    if kpi_filters['platforms'] and 'All' not in kpi_filters['platforms']:
        data = data[data['Platform'].isin(kpi_filters['platforms'])]
    if kpi_filters['models'] and 'All' not in kpi_filters['models']:
        data = data[data['Model'].isin(kpi_filters['models'])]
    if kpi_filters['activations'] and 'All' not in kpi_filters['activations']:
        data = data[data['Activation Group'].isin(kpi_filters['activations'])]

    if data.empty:
        st.warning('No data available for the selected filters.')
        st.stop()

    group_by = kpi_filters['group_by']
    if not group_by:
        st.warning('No grouping column available for the selected dataset.')
        st.stop()

    agg = (
        data.groupby(group_by, dropna=False)
        .agg({
            'Media Spend': 'sum',
            'Number of Sessions': 'sum',
            'Forms Submission Started': 'sum',
            'DCFS': 'sum',
        })
        .reset_index()
    )
    if kpi_filters['kpi'] == 'Visits (Sessions)':
        agg['kpi_value'] = agg['Number of Sessions']
    elif kpi_filters['kpi'] == 'Dealer Contract Form Submissions':
        agg['kpi_value'] = agg['Forms Submission Started']
    elif kpi_filters['kpi'] == 'DCFS':
        agg['kpi_value'] = agg['DCFS']
    elif kpi_filters['kpi'] == 'Sessions to DCFS Conversion Rate':
        agg['kpi_value'] = agg.apply(lambda r: _safe_ratio(r['DCFS'], r['Number of Sessions']), axis=1)
    elif kpi_filters['kpi'] == 'Cost per Lead (Forms Submission Started)':
        agg['kpi_value'] = agg.apply(
            lambda r: _safe_ratio(r['Media Spend'], r['Forms Submission Started']), axis=1
        )
    elif kpi_filters['kpi'] == 'Cost per Lead (DCFS)':
        agg['kpi_value'] = agg.apply(lambda r: _safe_ratio(r['Media Spend'], r['DCFS']), axis=1)
    else:
        agg['kpi_value'] = None

    color_by = kpi_filters['color_by']
    if color_by:
        color_map = (
            data.groupby([group_by, color_by], dropna=False)
            .agg({
                'Media Spend': 'sum',
                'Number of Sessions': 'sum',
                'Forms Submission Started': 'sum',
                'DCFS': 'sum',
            })
            .reset_index()
        )
        if kpi_filters['kpi'] == 'Visits (Sessions)':
            color_map['kpi_value'] = color_map['Number of Sessions']
        elif kpi_filters['kpi'] == 'Dealer Contract Form Submissions':
            color_map['kpi_value'] = color_map['Forms Submission Started']
        elif kpi_filters['kpi'] == 'DCFS':
            color_map['kpi_value'] = color_map['DCFS']
        elif kpi_filters['kpi'] == 'Sessions to DCFS Conversion Rate':
            color_map['kpi_value'] = color_map.apply(
                lambda r: _safe_ratio(r['DCFS'], r['Number of Sessions']), axis=1
            )
        elif kpi_filters['kpi'] == 'Cost per Lead (Forms Submission Started)':
            color_map['kpi_value'] = color_map.apply(
                lambda r: _safe_ratio(r['Media Spend'], r['Forms Submission Started']), axis=1
            )
        elif kpi_filters['kpi'] == 'Cost per Lead (DCFS)':
            color_map['kpi_value'] = color_map.apply(
                lambda r: _safe_ratio(r['Media Spend'], r['DCFS']), axis=1
            )
        plot_df = color_map
    else:
        plot_df = agg

    st.subheader('KPI vs investment')
    fig = px.scatter(
        plot_df,
        x='Media Spend',
        y='kpi_value',
        color=color_by,
        hover_name=group_by,
        labels={'Media Spend': 'Media Spend', 'kpi_value': kpi_filters['kpi'], group_by: group_by},
    )
    fig.update_layout(height=520)

    fit_rows = []
    if np is None or curve_fit is None:
        st.info('Install scipy to enable curve fitting for Ax/(b+x).')
    else:
        if color_by:
            for key, group in plot_df.groupby(color_by, dropna=False):
                a, b = fit_saturation(group['Media Spend'], group['kpi_value'])
                if a is None or b is None:
                    continue
                fit_rows.append({color_by: key, 'A': a, 'B': b, 'points': len(group)})
                x_fit = np.linspace(group['Media Spend'].min(), group['Media Spend'].max(), 100)
                y_fit = _saturation_curve(x_fit, a, b)
                fig.add_trace(
                    go.Scatter(
                        x=x_fit,
                        y=y_fit,
                        mode='lines',
                        name=f'{key} fit',
                        line=dict(dash='solid'),
                        showlegend=True,
                    )
                )
        else:
            a, b = fit_saturation(plot_df['Media Spend'], plot_df['kpi_value'])
            if a is not None and b is not None:
                fit_rows.append({'A': a, 'B': b, 'points': len(plot_df)})
                x_fit = np.linspace(plot_df['Media Spend'].min(), plot_df['Media Spend'].max(), 100)
                y_fit = _saturation_curve(x_fit, a, b)
                fig.add_trace(
                    go.Scatter(
                        x=x_fit,
                        y=y_fit,
                        mode='lines',
                        name='Fit',
                        line=dict(dash='solid'),
                        showlegend=True,
                    )
                )
    st.plotly_chart(fig, use_container_width=True)

    if fit_rows:
        st.subheader('Saturation fit parameters')
        st.dataframe(pd.DataFrame(fit_rows))

    st.subheader('Aggregated data')
    st.dataframe(plot_df)
    st.stop()

x_axis = 'calendar_week'
platform_col = 'Platform' if 'Platform' in filtered.columns else None

platform_group = [x_axis, platform_col] if platform_col else [x_axis]
platform_agg = (
    filtered.groupby(platform_group, dropna=False)[metric]
    .agg(agg_func)
    .reset_index()
)

total_agg = (
    filtered.groupby([x_axis], dropna=False)[metric]
    .agg(agg_func)
    .reset_index()
)

st.subheader(f'{metric} by platform | {market} | {model}')
if platform_col:
    top_platforms = (
        platform_agg.groupby(platform_col, dropna=False)[metric]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .index
        .tolist()
    )
    plot_platform = platform_agg[platform_agg[platform_col].isin(top_platforms)]
    line_fig = px.line(
        plot_platform,
        x=x_axis,
        y=metric,
        color=platform_col,
        markers=True,
        labels={x_axis: 'Date' if x_axis == 'Date' else 'Calendar Week', metric: metric},
    )
    line_fig.update_layout(height=450, legend_title_text=platform_col)
    st.plotly_chart(line_fig, use_container_width=True)
else:
    st.info('Platform column not available in this dataset.')

st.subheader(f'Total (all platforms) | {market} | {model}')
total_fig = px.line(
    total_agg,
    x=x_axis,
    y=metric,
    markers=True,
    labels={x_axis: 'Date' if x_axis == 'Date' else 'Calendar Week', metric: metric},
)
total_fig.update_layout(height=300)
st.plotly_chart(total_fig, use_container_width=True)

st.subheader('Platform totals')
if platform_col:
    totals_table = (
        platform_agg.groupby(platform_col, dropna=False)[metric]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    st.dataframe(totals_table)
else:
    st.dataframe(total_agg)

st.subheader('KPI trends')

kpi_options = [
    'Media Invest',
    'Visits (Sessions)',
    'Dealer Contract Form Submissions',
    'Sessions to DCFS Conversion Rate',
    'Cost per Lead',
    'Lead to Sales Rate',
]
kpi = st.selectbox('KPI', kpi_options)
series_mode = st.selectbox('Series', ['Total (all platforms)', 'By platform'])

required_cols = {
    'media': 'Media Spend',
    'sessions': 'Number of Sessions',
    'dcfs': 'DCFS',
    'forms': 'Forms Submission Started',
}

for key, col in required_cols.items():
    if col not in filtered.columns:
        required_cols[key] = None

sales_col = 'Sales (OGR)' if 'Sales (OGR)' in filtered.columns else None

group_cols = [x_axis]
if series_mode == 'By platform' and platform_col:
    group_cols.append(platform_col)

base = (
    filtered.groupby(group_cols, dropna=False)
    .agg({
        'Media Spend': 'sum',
        'Number of Sessions': 'sum',
        'DCFS': 'sum',
        'Forms Submission Started': 'sum',
        **({sales_col: 'sum'} if sales_col else {}),
    })
    .reset_index()
)

def safe_ratio(numerator, denominator):
    return numerator / denominator if denominator and denominator != 0 else None

if kpi == 'Media Invest':
    base['kpi_value'] = base['Media Spend']
elif kpi == 'Visits (Sessions)':
    base['kpi_value'] = base['Number of Sessions']
elif kpi == 'Dealer Contract Form Submissions':
    base['kpi_value'] = base['Forms Submission Started']
elif kpi == 'Sessions to DCFS Conversion Rate':
    base['kpi_value'] = base.apply(lambda r: safe_ratio(r['DCFS'], r['Number of Sessions']), axis=1)
elif kpi == 'Cost per Lead':
    base['kpi_value'] = base.apply(lambda r: safe_ratio(r['Media Spend'], r['Forms Submission Started']), axis=1)
elif kpi == 'Lead to Sales Rate':
    if sales_col:
        base['kpi_value'] = base.apply(lambda r: safe_ratio(r[sales_col], r['Forms Submission Started']), axis=1)
    else:
        base['kpi_value'] = None

if series_mode == 'By platform' and platform_col:
    kpi_fig = px.line(
        base,
        x=x_axis,
        y='kpi_value',
        color=platform_col,
        markers=True,
        labels={x_axis: 'Date' if x_axis == 'Date' else 'Calendar Week', 'kpi_value': kpi},
    )
    kpi_fig.update_layout(height=420, legend_title_text=platform_col)
else:
    kpi_fig = px.line(
        base,
        x=x_axis,
        y='kpi_value',
        markers=True,
        labels={x_axis: 'Date' if x_axis == 'Date' else 'Calendar Week', 'kpi_value': kpi},
    )
    kpi_fig.update_layout(height=320)

st.plotly_chart(kpi_fig, use_container_width=True)

st.subheader('KPI summary table')

kpi_groupby = st.multiselect(
    'KPI group by',
    categorical_cols,
    default=['Market', 'Model', 'Channel', 'Platform', 'Activation Group'],
)


def safe_div(numerator, denominator):
    return numerator / denominator if denominator and denominator != 0 else None


def compute_kpis(df_in, groupby_cols):
    group_cols = groupby_cols if groupby_cols else []
    grouped = df_in.groupby(group_cols, dropna=False) if group_cols else [((), df_in)]

    rows = []
    for key, data in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(group_cols, key)) if group_cols else {}

        media_invest = data['Media Spend'].sum() if 'Media Spend' in data else None
        visits = data['Number of Sessions'].sum() if 'Number of Sessions' in data else None
        dcfs = data['DCFS'].sum() if 'DCFS' in data else None
        forms = data['Forms Submission Started'].sum() if 'Forms Submission Started' in data else None

        row['Media Invest'] = media_invest
        row['Visits (Sessions)'] = visits
        row['Dealer Contract Form Submissions'] = forms
        row['Sessions to DCFS Conversion Rate'] = safe_div(dcfs, visits)
        row['Cost per Lead'] = safe_div(media_invest, forms)

        if 'Sales (OGR)' in data:
            sales = data['Sales (OGR)'].sum()
            row['Lead to Sales Rate'] = safe_div(sales, forms)
            if 'Date' in data:
                aug_mask = data['Date'].dt.strftime('%Y-%m') == '2025-08'
                row["Sales (OGR) as of Aug'25"] = data.loc[aug_mask, 'Sales (OGR)'].sum()
            else:
                row["Sales (OGR) as of Aug'25"] = None
        else:
            row['Lead to Sales Rate'] = None
            row["Sales (OGR) as of Aug'25"] = None

        rows.append(row)

    return pd.DataFrame(rows)


kpi_table = compute_kpis(filtered, kpi_groupby)
st.dataframe(kpi_table)
