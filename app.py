from io import BytesIO
from pathlib import Path
import os
import re
import hmac
from datetime import datetime
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from dotenv import load_dotenv
from openpyxl import Workbook, load_workbook

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from opportunity import OPPORTUNITY_CONFIG, compute_headroom_scores

try:
    import numpy as np
    from scipy.optimize import curve_fit
except Exception:
    np = None
    curve_fit = None

base_dir_env = os.getenv('APP_BASE_DIR')
BASE_DIR = Path(base_dir_env) if base_dir_env else Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / 'pwc reports' / 'outputs' / 'python_output_all.csv'
LOGO_PATH = BASE_DIR / 'porsche_logo.png'

st.set_page_config(page_title='Intelligence Console', layout='wide')

load_dotenv()

def _load_auth_users() -> dict:
    raw_users = os.getenv('APP_AUTH_USERS', '').strip()
    if raw_users:
        users = {}
        for item in raw_users.split(','):
            item = item.strip()
            if not item or ':' not in item:
                continue
            username, password = item.split(':', 1)
            username = username.strip()
            password = password.strip()
            if username and password:
                users[username] = password
        return users

    single_user = os.getenv('APP_AUTH_USER', '').strip()
    single_pass = os.getenv('APP_AUTH_PASSWORD', '').strip()
    return {single_user: single_pass} if single_user and single_pass else {}


def _verify_credentials(username: str, password: str, users: dict) -> bool:
    if not username or not password:
        return False
    stored = users.get(username, '')
    return hmac.compare_digest(password, stored)


def _render_auth_header():
    if LOGO_PATH.exists():
        cols = st.columns([1, 2, 1])
        with cols[1]:
            st.image(str(LOGO_PATH), width=260)
    st.markdown(
        """
        <div style="text-align:center; margin-top: 6px;">
          <div style="font-size: 28px; font-weight: 700;">Authentication Required</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def require_auth():
    users = _load_auth_users()
    if not users:
        st.error(
            'Authentication is not configured. Set APP_AUTH_USERS (user:pass,...) '
            'or APP_AUTH_USER and APP_AUTH_PASSWORD in the environment.'
        )
        st.stop()

    if st.session_state.get('authenticated'):
        with st.sidebar:
            if LOGO_PATH.exists():
                st.image(str(LOGO_PATH), width=200)
            st.caption(f"Signed in as {st.session_state.get('auth_user', 'user')}")
            if st.button('Logout'):
                st.session_state['authenticated'] = False
                st.session_state['auth_user'] = None
                st.rerun()
        return

    _render_auth_header()
    left, center, right = st.columns([1, 2, 1])
    with center:
        with st.form('login_form'):
            username = st.text_input('Username')
            password = st.text_input('Password', type='password')
            submitted = st.form_submit_button('Sign in')
    if submitted:
        if _verify_credentials(username, password, users):
            st.session_state['authenticated'] = True
            st.session_state['auth_user'] = username
            st.success('Authenticated.')
            st.rerun()
        else:
            st.error('Invalid username or password.')
    st.stop()


require_auth()

@st.cache_data
def load_data(csv_path: Path, mtime: float):
    df = pd.read_csv(csv_path, low_memory=False)
    return normalize_data(df)


def normalize_data(df: pd.DataFrame) -> pd.DataFrame:
    df['report_date'] = pd.to_datetime(df.get('report_date'), errors='coerce')
    if 'Date' in df.columns:
        date_series = df['Date']
        if pd.api.types.is_datetime64_any_dtype(date_series):
            df['Date'] = date_series
        else:
            date_str = date_series.astype(str).str.strip()
            date_str = date_str.str.replace(r'\.0$', '', regex=True)
            date_ymd = date_str.where(date_str.str.match(r'^\d{8}$', na=False))
            parsed = pd.to_datetime(date_ymd, format='%Y%m%d', errors='coerce')
            parsed_fallback = pd.to_datetime(date_str, errors='coerce')
            df['Date'] = parsed.fillna(parsed_fallback)
    df['report_week'] = df.get('report_week', pd.Series(dtype=str)).astype(str).str.strip()
    report_week_clean = df['report_week'].replace({'nan': '', 'None': ''}).fillna('')
    report_week_clean = report_week_clean.str.upper().str.replace(' ', '', regex=False)

    report_date = df['report_date']
    iso = report_date.dt.isocalendar()
    iso_year = iso['year']
    iso_week = iso['week']

    week_match = report_week_clean.str.extract(r'CW(\d{1,2})', expand=False)
    week_num = pd.to_numeric(week_match, errors='coerce')

    df['report_cw'] = week_num
    df['report_cw_year'] = pd.Series(pd.NA, index=df.index, dtype='Int64')
    date_has_week = report_date.notna()
    df.loc[date_has_week, 'report_cw'] = df.loc[date_has_week, 'report_cw'].fillna(iso_week)
    df.loc[date_has_week, 'report_cw_year'] = iso_year.where(date_has_week)

    df['report_week_key'] = pd.Series(pd.NA, index=df.index, dtype='string')
    has_cw = df['report_cw'].notna() & df['report_cw_year'].notna()
    df.loc[has_cw, 'report_week_key'] = (
        df.loc[has_cw, 'report_cw_year'].astype(int).astype(str)
        + '-CW'
        + df.loc[has_cw, 'report_cw'].astype(int).astype(str).str.zfill(2)
    )
    df['report_week_sort'] = pd.Series(pd.NA, index=df.index, dtype='Int64')
    df.loc[has_cw, 'report_week_sort'] = (
        df.loc[has_cw, 'report_cw_year'].astype(int) * 100
        + df.loc[has_cw, 'report_cw'].astype(int)
    )

    if 'Date' in df.columns:
        date_base = df['Date']
        valid_date = date_base.notna()
        date_iso = date_base.dt.isocalendar()
        date_week = date_iso['week']
        date_year = date_iso['year']
        df['calendar_week'] = df.get('calendar_week', pd.Series(dtype=object))
        df.loc[valid_date, 'calendar_week'] = (
            date_year[valid_date].astype(int).astype(str)
            + '-CW'
            + date_week[valid_date].astype(int).astype(str).str.zfill(2)
        )
        df['calendar_week_sort'] = df.get('calendar_week_sort', pd.Series(dtype='Int64'))
        df.loc[valid_date, 'calendar_week_sort'] = (
            date_year[valid_date].astype(int) * 100
            + date_week[valid_date].astype(int)
        )

        week_start = date_base - pd.to_timedelta(date_base.dt.weekday, unit='D')
        week_end = week_start + pd.Timedelta(days=6)

        def _format_range(start, end):
            return f'{start.strftime("%B")} {start.day} - {end.strftime("%B")} {end.day}'

        df['week_text'] = df.get('week_text', pd.Series(dtype=object))
        df.loc[valid_date, 'week_text'] = [
            _format_range(start, end)
            for start, end in zip(week_start[valid_date], week_end[valid_date])
        ]

        unique_starts = sorted(week_start[valid_date].dropna().unique())
        week_index = {start: idx + 1 for idx, start in enumerate(unique_starts)}
        df['week_relative'] = df.get('week_relative', pd.Series(dtype=object))
        df.loc[valid_date, 'week_relative'] = (
            'BW '
            + week_start[valid_date].map(week_index).astype(int).astype(str)
        )
    for col in ['Media Spend', 'Number of Sessions', 'DCFS', 'Forms Submission Started', 'Impressions']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def get_calendar_week_options(df_in: pd.DataFrame) -> list:
    if 'calendar_week' not in df_in.columns:
        return []
    if 'calendar_week_sort' in df_in.columns:
        tmp = df_in[['calendar_week', 'calendar_week_sort']].dropna()
        if not tmp.empty:
            return (
                tmp.sort_values('calendar_week_sort')
                .drop_duplicates('calendar_week')['calendar_week']
                .tolist()
            )
    return sorted(df_in['calendar_week'].dropna().unique())


_DATE_RE = re.compile(r'^(\d{8})_')
_CW_RE = re.compile(r'\bCW\s*\d+\b', re.IGNORECASE)


def _parse_date_prefix(filename: str) -> Optional[str]:
    match = _DATE_RE.match(filename)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), '%d%m%Y').strftime('%Y-%m-%d')
    except ValueError:
        return None


def _parse_report_week(text: str) -> str:
    match = _CW_RE.search(text or '')
    return match.group(0).replace(' ', '') if match else ''


def _find_python_output_sheet(wb):
    for name in wb.sheetnames:
        if re.search(r'python output', name, re.IGNORECASE):
            return name
    return None


@st.cache_data
def load_excel_python_output(file_bytes: bytes, filename: str) -> pd.DataFrame:
    wb = load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
    sheet_name = _find_python_output_sheet(wb)
    if not sheet_name:
        wb.close()
        raise ValueError('Python Output sheet not found.')
    ws = wb[sheet_name]

    rows = []
    for row in ws.iter_rows(values_only=True):
        if any(cell is not None and cell != '' for cell in row):
            rows.append(row)
    wb.close()

    if not rows:
        raise ValueError('Python Output sheet is empty.')

    header = [str(col).strip() if col is not None else '' for col in rows[0]]
    report_date = _parse_date_prefix(filename)
    report_week = _parse_report_week(filename)
    source_file = filename

    out_rows = []
    for row in rows[1:]:
        values = [row[idx] if idx < len(row) else None for idx in range(len(header))]
        out_rows.append([report_date, report_week, source_file] + values)

    df = pd.DataFrame(out_rows, columns=['report_date', 'report_week', 'source_file'] + header)
    return normalize_data(df)


def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Python Output (cleaned)')
    return output.getvalue()


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


def _run_headroom_report(summary: dict) -> str:
    if OpenAI is None:
        return 'LLM client not available. Install openai package.'
    client = OpenAI()
    prompt = (
        'Write a short, tight headroom report (max 8 sentences). '
        'DCFS means Dealer Contact Form Submissions. '
        'Include: 1) the idea of headroom, 2) how the numbers are derived, '
        '3) how to use it strategically. Use plain language for marketers. '
        'Do not include any extra sections or headings.\n\n'
        f'Headroom summary:\n{summary}\n'
    )
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': prompt}],
    )
    return response.choices[0].message.content


def _run_scale_report(summary: dict) -> str:
    if OpenAI is None:
        return 'LLM client not available. Install openai package.'
    client = OpenAI()
    prompt = (
        'Write a short, tight scale report (max 8 sentences). '
        'DCFS means Dealer Contact Form Submissions. '
        'Include: 1) the idea of scale, 2) how the numbers are derived, '
        '3) how to use it strategically. Use plain language for marketers. '
        'Do not include any extra sections or headings.\n\n'
        f'Scale summary:\n{summary}\n'
    )
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': prompt}],
    )
    return response.choices[0].message.content


def _run_spend_distribution_report(summary: dict) -> str:
    if OpenAI is None:
        return 'LLM client not available. Install openai package.'
    client = OpenAI()
    prompt = (
        'Write a short, tight spend distribution report (max 8 sentences). '
        's50 is the saturation point captured from the media response curve. '
        'Explain exactly what is shown on the plot: the recent spend bars, the spend '
        'distribution boxplots, and the color-based zone classification. '
        'Use plain language for marketers. Do not add extra sections or headings.\n\n'
        f'Spend distribution summary:\n{summary}\n'
    )
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': prompt}],
    )
    return response.choices[0].message.content


def _run_predictability_report(summary: dict) -> str:
    if OpenAI is None:
        return 'LLM client not available. Install openai package.'
    client = OpenAI()
    prompt = (
        'Write a short, tight predictability report (max 8 sentences). '
        'CPL is cost per lead. Explain exactly what is shown on the plot: '
        'volatility bars by group and the LOW/MED/HIGH/VERY_HIGH thresholds. '
        'Use plain language for marketers. Do not add extra sections or headings.\n\n'
        f'Predictability summary:\n{summary}\n'
    )
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': prompt}],
    )
    return response.choices[0].message.content


def _run_opportunity_report(summary: dict) -> str:
    if OpenAI is None:
        return 'LLM client not available. Install openai package.'
    client = OpenAI()
    prompt = (
        'Write a short, tight opportunity score report (max 8 sentences). '
        'Explain exactly what is shown on the plot: average opportunity score by group '
        'and the 0–100 scale. Use plain language for marketers. '
        'Do not add extra sections or headings.\n\n'
        f'Opportunity summary:\n{summary}\n'
    )
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': prompt}],
    )
    return response.choices[0].message.content


def _run_final_conclusion(reports: dict) -> str:
    if OpenAI is None:
        return 'LLM client not available. Install openai package.'
    client = OpenAI()
    prompt = (
        'Using the reports below, write a concise conclusion and budget allocation strategy '
        'to win the incentive deal. Be specific about prioritization and guardrails. '
        'Do not invent metrics or data. Use plain language for marketers. '
        'Output two short paragraphs labeled "Conclusion" and "Strategy".\n\n'
        f'Reports:\n{reports}\n'
    )
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': prompt}],
    )
    return response.choices[0].message.content

with st.sidebar:
    st.header('Data Ingestion')
    uploaded_excel = st.file_uploader(
        'Upload weekly Excel (Python Output sheet)',
        type=['xlsx'],
    )

data_source_label = f'CSV: {CSV_PATH.name}'
if uploaded_excel is not None:
    try:
        df = load_excel_python_output(uploaded_excel.getvalue(), uploaded_excel.name)
        data_source_label = f'Uploaded Excel: {uploaded_excel.name}'
    except Exception as exc:
        st.error(f'Unable to read the uploaded Excel file: {exc}')
        st.stop()
else:
    st.info('Upload a weekly Excel file to load the dashboard.')
    st.stop()

with st.sidebar.expander('Data diagnostics'):
    if 'Date' in df.columns:
        st.write('Date min:', df['Date'].min())
        st.write('Date max:', df['Date'].max())
    if 'calendar_week' in df.columns:
        week_list = get_calendar_week_options(df)
        st.write('Calendar weeks:', week_list[:5], '...', week_list[-5:])
        st.write('Total weeks:', len(week_list))

st.title('Intelligence Console')
st.caption(f'Data source: {data_source_label}')

numeric_cols = df.select_dtypes(include='number').columns.tolist()
numeric_cols = [col for col in numeric_cols if col not in {'Date'}]

categorical_cols = [
    col for col in [
        'Market', 'Model', 'Ad Type', 'Channel', 'Platform', 'Activation Group',
        'Campaign', 'calendar_week', 'week_relative', 'week_text', 'report_week'
    ]
    if col in df.columns
]

dual_selections = {}
dual_breakdown_dim = None
dual_aggregate = False
dual_aggregate_dims = {}
dual_left_kpi = None
dual_right_kpi = None

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


def compute_dynamic_s50(df_in):
    if np is None or curve_fit is None:
        return {}
    group_cols = [col for col in ['Market', 'Channel', 'Model'] if col in df_in.columns]
    if not group_cols:
        return {}
    curve_df = df_in.copy()
    curve_df['Media Spend'] = pd.to_numeric(curve_df['Media Spend'], errors='coerce')
    curve_df['DCFS'] = pd.to_numeric(curve_df['DCFS'], errors='coerce')
    curve_df = curve_df[(curve_df['Media Spend'] > 0) & (curve_df['DCFS'] >= 0)]
    if curve_df.empty:
        return {}
    s50_map = {}
    for key, group in curve_df.groupby(group_cols, dropna=False):
        a, b = fit_saturation(group['Media Spend'], group['DCFS'])
        if b is None or pd.isna(b) or b <= 0:
            continue
        s50_map[key] = float(b)
    return s50_map


with st.sidebar:
    page = st.radio(
        'Page',
        ['Overview', 'Risk Analysis', 'Market CPL', 'Market Report - Excel Export', 'KPI vs Investment'],
        horizontal=True,
    )
    if page == 'Overview':
        st.header('Plot Filters')
        st.caption('All includes every value. Use Aggregate to combine into one series.')
        dimension_candidates = [
            ('Market', 'Market'),
            ('Model', 'Model'),
            ('Campaign', 'Campaign'),
            ('Channel', 'Channel'),
            ('Platform', 'Platform'),
            ('Activation Group', 'Activation Group'),
        ]
        for label, col in dimension_candidates:
            if col in df.columns:
                options = ['All'] + sorted(df[col].dropna().unique())
                select_col, agg_col = st.columns([3, 1], vertical_alignment='center')
                with select_col:
                    dual_selections[col] = st.multiselect(f'{label}', options, default=['All'])
                with agg_col:
                    dual_aggregate_dims[col] = st.checkbox('Aggregate', value=True, key=f'agg_{col}')

        breakdown_dims = [
            col
            for col, selections in dual_selections.items()
            if selections and not dual_aggregate_dims.get(col, False)
        ]
        dual_breakdown_dim = breakdown_dims

        base_kpis = numeric_cols.copy()
        extra_kpis = [
            'Cost per Lead (Forms Submission Started)',
            'Cost per Lead (DCFS)',
            'CPM',
        ]
        kpi_choices = [k for k in base_kpis if k not in extra_kpis] + extra_kpis
        dual_left_kpi = st.selectbox('Left axis KPI', kpi_choices, index=0)
        compare_kpis = st.checkbox('Compare (add right axis)', value=False)
        if compare_kpis:
            dual_right_kpi = st.selectbox('Right axis KPI', kpi_choices, index=min(7, len(kpi_choices) - 1))
        else:
            dual_right_kpi = None

        metric = None
        agg_func = None
        filtered = df
        model_df = None
        market = None
        campaign = None
        top_n = None
        export_market = None
        export_weeks = None
    elif page == 'Market CPL':
        st.header('Filters')
        if 'Model' not in df.columns:
            st.warning('Model column not found in the dataset.')
            st.stop()

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

        metric = None
        agg_func = None
        top_n = None
        export_market = None
        export_weeks = None
    elif page == 'Market Report - Excel Export':
        st.header('Filters')
        if 'Market' not in df.columns:
            st.warning('Market column not found in the dataset.')
            st.stop()
        export_market = st.selectbox('Market', sorted(df['Market'].dropna().unique()))
        campaign_options = ['All']
        if 'Campaign' in df.columns:
            campaign_options += sorted(df['Campaign'].dropna().unique())
        export_campaign = st.selectbox('Campaign', campaign_options)
        date_mode = st.radio('Filter by', ['Weeks', 'Date range'], horizontal=True)
        week_options = get_calendar_week_options(df)
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
    elif page == 'Risk Analysis':
        market_options = ['All'] + sorted(df['Market'].dropna().unique()) if 'Market' in df.columns else ['All']
        channel_options = ['All'] + sorted(df['Channel'].dropna().unique()) if 'Channel' in df.columns else ['All']
        model_options = ['All'] + sorted(df['Model'].dropna().unique()) if 'Model' in df.columns else ['All']
        campaign_options = ['All'] + sorted(df['Campaign'].dropna().unique()) if 'Campaign' in df.columns else ['All']

        headroom_high_input = st.number_input(
            'Headroom high threshold',
            min_value=0.01,
            max_value=5.0,
            value=float(OPPORTUNITY_CONFIG['headroom_high']),
            step=0.01,
            format='%.2f',
        )
        recent_periods_input = st.number_input(
            'Recent periods',
            min_value=1,
            max_value=52,
            value=int(OPPORTUNITY_CONFIG['recent_cpl_periods']),
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
        opp_market = st.selectbox('Market', market_options)
        opp_channel = st.selectbox('Channel', channel_options)
        opp_model = st.selectbox('Model', model_options)
        opp_campaign = st.selectbox('Campaign', campaign_options)
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

if page == 'Risk Analysis':
    st.subheader('Risk Analysis')
    with st.popover('What is this?'):
        st.write(
            'This page scores markets/channels/models for opportunity and risk using recent '
            'performance and spend efficiency. It combines headroom, scale, curve position, '
            'and predictability into one opportunity score.'
        )
        st.write(
            'How to use it:\n'
            '1. Set thresholds in the left panel (or keep defaults).\n'
            '2. Filter by Market/Channel/Model if you want a narrower view.\n'
            '3. Review each step section to see how the score is built.\n'
            '4. Use the LLM report for a plain‑language summary.'
        )

    st.subheader('Efficiency headroom')
    config_override = dict(OPPORTUNITY_CONFIG)
    config_override['headroom_high'] = float(headroom_high_input)
    config_override['recent_cpl_periods'] = int(recent_periods_input)
    config_override['recent_scale_periods'] = int(recent_periods_input)
    config_override['recent_curve_periods'] = int(recent_periods_input)
    config_override['growth_ratio_max'] = float(growth_ratio_max_input)
    config_override['mid_ratio_max'] = float(mid_ratio_max_input)
    df_input = df.copy()
    if opp_market != 'All':
        df_input = df_input[df_input['Market'] == opp_market]
    if opp_channel != 'All':
        df_input = df_input[df_input['Channel'] == opp_channel]
    if opp_model != 'All':
        df_input = df_input[df_input['Model'] == opp_model]
    if opp_campaign != 'All':
        df_input = df_input[df_input['Campaign'] == opp_campaign]

    if np is None or curve_fit is None:
        st.info('Install scipy to enable dynamic s50 curve fitting.')
    else:
        s50_map = compute_dynamic_s50(df_input)
        if s50_map:
            group_cols = [col for col in ['Market', 'Channel', 'Model'] if col in df_input.columns]
            if group_cols:
                df_input = df_input.copy()
                df_input['s50_spend'] = (
                    df_input[group_cols]
                    .apply(lambda r: s50_map.get(tuple(r.tolist())), axis=1)
                )

    results, missing = compute_headroom_scores(df_input, config_override)
    if missing:
        st.warning(f'Missing required columns: {", ".join(missing)}')
        st.stop()
    if results.empty:
        st.warning('No data available to compute headroom.')
        st.stop()

    st.subheader('LLM report')
    st.caption('LLM insights (wireframe)')
    if st.button('Generate LLM Report (Markdown)'):
        st.info('Coming soon...')

    st.subheader('Headroom by group')
    with st.popover('What is this?'):
        st.write(
            'Compares current CPL vs. a benchmark to show efficiency headroom by group. '
            'Higher headroom % means more room to improve efficiency.'
        )
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
            if st.button('Generate headroom report', key='headroom_report'):
                st.info('Coming soon...')

        st.subheader('Scale')
        with st.popover('What is this?'):
            st.write(
                'Measures scalable volume using average DCFS over the most recent periods, '
                'then ranks it within the channel. Higher scores mean this group is already '
                'performing strongly on volume and has more headroom to scale investment.'
            )
        scale_df = plot_df.dropna(subset=['scale_score'])
        if scale_df.empty:
            st.info('No scale score data for the current filters.')
        else:
            scale_df = scale_df.copy()
            scale_df['scale_score'] = pd.to_numeric(scale_df['scale_score'], errors='coerce')
            scale_df = scale_df.dropna(subset=['scale_score'])
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
            if st.button('Generate scale report', key='scale_report'):
                st.info('Coming soon...')

        st.subheader('Media response curve')
        with st.popover('What is this?'):
            st.write(
                'Plots Media Spend vs. DCFS to visualize response curves and fitted saturation trends. '
                'Used to infer growth vs. saturation.'
            )
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
                fit_rows = []
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
                        fit_rows.append({
                            'group': group_label,
                            'A': a,
                            'B': b,
                            'points': len(group),
                        })
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
                if fit_rows:
                    st.subheader('Media response fit parameters (A, B)')
                    st.dataframe(pd.DataFrame(fit_rows).sort_values('A', ascending=False))

        st.subheader('Spend distribution')
        with st.popover('What is this?'):
            st.write(
                'Compares recent spend to s50 benchmarks and shows spend distributions by group '
                'to classify growth/mid/saturated zones.'
            )
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

            zone_colors = {
                'GROWTH': '#2ca02c',
                'MID': '#f2c744',
                'SATURATED': '#d62728',
                'UNKNOWN': '#9e9e9e',
            }
            zones_by_group = {}
            for group in groups:
                spend_recent = recent_map.get(group)
                s50_spend = s50_map.get(group)
                if spend_recent is None or s50_spend is None or s50_spend <= 0:
                    zones_by_group[group] = 'UNKNOWN'
                    continue
                ratio = spend_recent / s50_spend
                growth_ratio_max = float(growth_ratio_max_input)
                mid_ratio_max = float(mid_ratio_max_input)
                if ratio <= growth_ratio_max:
                    zones_by_group[group] = 'GROWTH'
                elif ratio <= mid_ratio_max:
                    zones_by_group[group] = 'MID'
                else:
                    zones_by_group[group] = 'SATURATED'

            fig = go.Figure()
            for zone, color in zone_colors.items():
                zone_groups = [g for g in groups if zones_by_group.get(g) == zone]
                if not zone_groups:
                    continue
                zone_custom = [
                    [recent_map.get(g), s50_map.get(g)]
                    for g in zone_groups
                ]
                fig.add_trace(
                    go.Bar(
                        x=zone_groups,
                        y=[recent_map.get(g) for g in zone_groups],
                        marker=dict(color=color, opacity=0.5),
                        name=f'Recent spend ({zone})',
                        customdata=zone_custom,
                        hovertemplate=(
                            'Group: %{x}<br>'
                            'Current spend: %{customdata[0]:,.2f}<br>'
                            'Saturation point: %{customdata[1]:,.2f}<extra></extra>'
                        ),
                    )
                )
            for group in groups:
                group_mask = curve_plot[group_by] == group if group_by else pd.Series([True] * len(curve_plot))
                y_vals = curve_plot.loc[group_mask, 'Media Spend']
                if y_vals.empty:
                    continue
                zone = zones_by_group.get(group, 'UNKNOWN')
                fig.add_trace(
                    go.Box(
                        x=[group] * len(y_vals),
                        y=y_vals,
                        boxpoints=False,
                        marker=dict(color='rgba(0,0,0,0)'),
                        line=dict(color='#444444'),
                        name=f'{group} ({zone})',
                        showlegend=False,
                    )
                )
            if group_order:
                fig.update_xaxes(categoryorder='array', categoryarray=group_order)
            fig.update_layout(yaxis_title='Media Spend')
            st.plotly_chart(fig, use_container_width=True)
            if st.button('Generate spend distribution report', key='spend_distribution_report'):
                st.info('Coming soon...')

        st.subheader('Predictability')
        with st.popover('What is this?'):
            st.write(
                'Shows CPL volatility (IQR/median) and the resulting predictability tier. '
                'Higher volatility means less predictable performance.'
            )
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
                if st.button('Generate predictability report', key='predictability_report'):
                    st.info('Coming soon...')

        st.subheader('Opportunity score')
        with st.popover('What is this?'):
            st.write(
                'Combines headroom, scale, and curve scores minus volatility penalties into a '
                '0–100 opportunity score.'
            )
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
            if st.button('Generate opportunity score report', key='opportunity_report'):
                st.info('Coming soon...')

        st.subheader('Conclusion and budget strategy')
        st.caption('LLM conclusion (wireframe)')
        if st.button('Generate final conclusion', key='final_conclusion'):
            st.info('Coming soon...')

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

    week_options = get_calendar_week_options(df)
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

if page == 'Market Report - Excel Export':
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
    st.subheader('Market Report - Excel Export')
    st.caption('Exports the same stacked tables as the shared PCL Excel file.')

    workbook = build_close_gap_workbook(export_df, export_market, week_label)
    st.download_button(
        'Download Excel',
        data=workbook,
        file_name=f'Close_the_Gap_{export_market}_2025.xlsx',
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

if page == 'Overview':
    st.subheader('KPI chart')
    with st.popover('What is this?'):
        st.write(
            'This page shows how your key performance indicators (KPIs) change by calendar week. '
            'Use the filters to pick which data you want to include, and the chart will update.'
        )
        st.write(
            'How to use it (beginner-friendly):\n'
            '1. Start with everything aggregated (default). This gives one clean line per KPI.\n'
            '2. Pick a KPI on the left axis (for example, Media Spend or DCFS).\n'
            '3. If you want to compare two KPIs, turn on Compare and pick a right-axis KPI.\n'
            '4. To focus on a subset, use the dropdowns. Select specific values instead of All.\n'
            '5. To split the line by a dimension, uncheck Aggregate next to that dropdown.'
        )
    dual_base = df.copy()
    breakdown_dims = dual_breakdown_dim or []

    for col, selections in dual_selections.items():
        if not selections:
            continue
        if 'All' in selections:
            continue
        value_selections = [s for s in selections if s != 'All']
        if value_selections:
            dual_base = dual_base[dual_base[col].isin(value_selections)]

    if dual_base.empty:
        st.warning('No data available for the selected filters.')
        st.stop()

    left_kpi = dual_left_kpi or (numeric_cols[0] if numeric_cols else None)
    right_kpi = dual_right_kpi

    group_cols = ['calendar_week'] + breakdown_dims

    agg_spec = {}
    for col in numeric_cols:
        if col in dual_base.columns:
            agg_spec[col] = 'sum'

    weekly = dual_base.groupby(group_cols, dropna=False).agg(agg_spec).reset_index()

    def _compute_kpi(frame, label):
        if label in frame.columns:
            return frame[label]
        if label == 'Cost per Lead (Forms Submission Started)':
            return frame.apply(lambda r: _safe_ratio(r['Media Spend'], r['Forms Submission Started']), axis=1)
        if label == 'Cost per Lead (DCFS)':
            return frame.apply(lambda r: _safe_ratio(r['Media Spend'], r['DCFS']), axis=1)
        if label == 'CPM':
            if 'Impressions' not in frame.columns:
                return pd.Series([None] * len(frame))
            return frame.apply(
                lambda r: (_safe_ratio(r['Media Spend'], r['Impressions']) or 0) * 1000
                if _safe_ratio(r['Media Spend'], r['Impressions']) is not None
                else None,
                axis=1,
            )
        return pd.Series([None] * len(frame))

    weekly['left_kpi'] = _compute_kpi(weekly, left_kpi)
    if right_kpi:
        weekly['right_kpi'] = _compute_kpi(weekly, right_kpi)

    week_order = get_calendar_week_options(dual_base)
    fig = make_subplots(specs=[[{"secondary_y": bool(right_kpi)}]])

    if breakdown_dims:
        palette = px.colors.qualitative.Plotly
        for idx, (key, group) in enumerate(weekly.groupby(breakdown_dims, dropna=False)):
            color = palette[idx % len(palette)]
            if isinstance(key, tuple):
                parts = [str(part) if part not in [None, ''] else 'Not specified' for part in key]
                name = ' | '.join(parts)
            else:
                name = str(key) if key not in [None, ''] else 'Not specified'
            fig.add_trace(
                go.Scatter(
                    x=group['calendar_week'],
                    y=group['left_kpi'],
                    mode='lines+markers',
                    name=f'{name} — {left_kpi}',
                    line=dict(color=color),
                ),
                secondary_y=False,
            )
            if right_kpi:
                fig.add_trace(
                    go.Scatter(
                        x=group['calendar_week'],
                        y=group['right_kpi'],
                        mode='lines+markers',
                        name=f'{name} — {right_kpi}',
                        line=dict(color=color, dash='dash'),
                    ),
                    secondary_y=True,
                )
    else:
        fig.add_trace(
            go.Scatter(
                x=weekly['calendar_week'],
                y=weekly['left_kpi'],
                mode='lines+markers',
                name=left_kpi,
            ),
            secondary_y=False,
        )
        if right_kpi:
            fig.add_trace(
                go.Scatter(
                    x=weekly['calendar_week'],
                    y=weekly['right_kpi'],
                    mode='lines+markers',
                    name=right_kpi,
                    line=dict(dash='dash'),
                ),
                secondary_y=True,
            )
    fig.update_layout(
        height=420,
        xaxis=dict(categoryorder='array', categoryarray=week_order),
        legend_title_text='KPI',
    )
    fig.update_yaxes(title_text=left_kpi, secondary_y=False)
    if right_kpi:
        fig.update_yaxes(title_text=right_kpi, secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)
