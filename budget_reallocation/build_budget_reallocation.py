from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
PERFORMANCE_PATH = BASE_DIR / 'pwc reports' / 'outputs' / 'python_output_all.csv'
ACTIVITY_SIGNALS_PATH = BASE_DIR / 'market_activities' / 'market_activity_weekly_signals.csv'
OUT_DIR = BASE_DIR / 'budget_reallocation'
WEEKLY_PERFORMANCE_OUT = OUT_DIR / 'weekly_market_performance.csv'
MARKET_SUMMARY_OUT = OUT_DIR / 'market_performance_summary.csv'
RECOMMENDATIONS_OUT = OUT_DIR / 'budget_reallocation_recommendations.csv'
REPORT_OUT = OUT_DIR / 'budget_reallocation_final_report.md'


def normalize_market(value):
    if value is None or pd.isna(value):
        return ''
    text = str(value or '').strip()
    lookup = re.sub(r'\s+', ' ', text).upper()
    if lookup in {'', 'NAN', 'NONE'}:
        return ''
    if lookup == 'PIB SPA':
        return 'PIB SPA'
    if lookup == 'PIB POR':
        return 'PIB POR'
    return lookup


def normalize_model_family(value):
    text = str(value or '').strip().lower()
    if 'macan' in text:
        return 'Macan'
    if 'cayenne' in text:
        return 'Cayenne'
    if 'taycan' in text:
        return 'Taycan'
    if 'panamera' in text:
        return 'Panamera'
    if 'range' in text:
        return 'Range'
    return 'Unknown'


def activity_model_family(value):
    text = str(value or '').strip().lower()
    if 'macan' in text:
        return 'Macan'
    if 'cayenne' in text:
        return 'Cayenne'
    return 'Unknown'


def parse_date_column(series):
    as_text = series.astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    ymd = pd.to_datetime(as_text.where(as_text.str.match(r'^\d{8}$', na=False)), format='%Y%m%d', errors='coerce')
    fallback = pd.to_datetime(as_text, errors='coerce')
    return ymd.fillna(fallback)


def plain_ratio(numerator, denominator):
    return numerator / denominator if denominator and denominator > 0 else None


def pct_change(new, old):
    if old is None or pd.isna(old) or old == 0:
        return None
    if new is None or pd.isna(new):
        return None
    return (new - old) / old


def trend_label(value, positive='improving', negative='declining'):
    if value is None or pd.isna(value):
        return 'not enough history'
    if value >= 0.15:
        return positive
    if value <= -0.15:
        return negative
    return 'stable'


def load_weekly_performance():
    usecols = [
        'Market',
        'Model',
        'Date',
        'Channel',
        'Media Spend',
        'Number of Sessions',
        'DCFS',
        'Forms Submission Started',
        'Impressions',
    ]
    df = pd.read_csv(PERFORMANCE_PATH, usecols=usecols, low_memory=False)
    df['market'] = df['Market'].apply(normalize_market)
    df['model_family'] = df['Model'].apply(normalize_model_family)
    df['date'] = parse_date_column(df['Date'])
    df = df[df['market'].ne('') & df['model_family'].isin(['Macan', 'Cayenne'])]
    df = df[df['date'].notna()]
    df['week_start'] = df['date'] - pd.to_timedelta(df['date'].dt.weekday, unit='D')
    for col in ['Media Spend', 'Number of Sessions', 'DCFS', 'Forms Submission Started', 'Impressions']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    weekly = (
        df.groupby(['market', 'model_family', 'week_start'], dropna=False)
        .agg({
            'Media Spend': 'sum',
            'Number of Sessions': 'sum',
            'DCFS': 'sum',
            'Forms Submission Started': 'sum',
            'Impressions': 'sum',
        })
        .reset_index()
        .rename(columns={
            'Media Spend': 'spend',
            'Number of Sessions': 'sessions',
            'Forms Submission Started': 'forms_started',
            'Impressions': 'impressions',
        })
    )
    weekly['cpl_dcfs'] = weekly.apply(lambda r: plain_ratio(r['spend'], r['DCFS']), axis=1)
    weekly['visit_to_lead_rate'] = weekly.apply(lambda r: plain_ratio(r['DCFS'], r['sessions']), axis=1)
    return weekly.sort_values(['market', 'model_family', 'week_start'])


def summarize_performance(weekly):
    rows = []
    market_median_cpl = weekly[weekly['DCFS'] > 0]['cpl_dcfs'].median()
    market_median_vtl = weekly[weekly['sessions'] > 0]['visit_to_lead_rate'].median()

    for (market, model), group in weekly.groupby(['market', 'model_family'], dropna=False):
        group = group.sort_values('week_start')
        active = group[(group['spend'] > 0) | (group['sessions'] > 0) | (group['DCFS'] > 0)]
        if active.empty:
            continue
        recent = active.tail(4)
        previous = active.iloc[:-4].tail(4)
        recent_spend = recent['spend'].sum()
        recent_sessions = recent['sessions'].sum()
        recent_dcfs = recent['DCFS'].sum()
        previous_spend = previous['spend'].sum() if not previous.empty else None
        previous_dcfs = previous['DCFS'].sum() if not previous.empty else None
        recent_cpl = plain_ratio(recent_spend, recent_dcfs)
        recent_vtl = plain_ratio(recent_dcfs, recent_sessions)
        dcfs_trend = pct_change(recent_dcfs, previous_dcfs)
        spend_trend = pct_change(recent_spend, previous_spend)

        efficient = recent_cpl is not None and market_median_cpl and recent_cpl <= market_median_cpl
        high_response = recent_vtl is not None and market_median_vtl and recent_vtl >= market_median_vtl
        growing = dcfs_trend is not None and dcfs_trend >= 0.15
        spend_up_response_flat = spend_trend is not None and spend_trend >= 0.15 and (dcfs_trend is None or dcfs_trend <= 0.05)

        if recent_spend < 1000 or len(recent) < 2:
            performance_bucket = 'Watch'
            performance_direction = 'Keep small test budget'
        elif recent_dcfs == 0 and recent_spend > 0:
            performance_bucket = 'Reduce'
            performance_direction = 'Reduce flexible budget'
        elif efficient and (growing or high_response):
            performance_bucket = 'Scale'
            performance_direction = 'Increase budget'
        elif spend_up_response_flat and not efficient:
            performance_bucket = 'Reduce'
            performance_direction = 'Reduce flexible budget'
        elif recent_sessions > 0 and recent_dcfs < 3:
            performance_bucket = 'Fix'
            performance_direction = 'Keep budget modest and fix conversion'
        elif efficient:
            performance_bucket = 'Protect'
            performance_direction = 'Maintain budget'
        else:
            performance_bucket = 'Fix'
            performance_direction = 'Review setup before scaling'

        if performance_bucket == 'Scale':
            reason = (
                f"{market} / {model}: recent spend is producing dealer contact forms efficiently "
                f"and response is {trend_label(dcfs_trend, 'growing', 'falling')}."
            )
        elif performance_bucket == 'Reduce':
            reason = (
                f"{market} / {model}: recent spend is not translating into enough dealer contact forms, "
                f"so flexible budget should be challenged."
            )
        elif performance_bucket == 'Fix':
            reason = (
                f"{market} / {model}: there is some demand signal, but conversion or efficiency is not strong enough to scale yet."
            )
        elif performance_bucket == 'Protect':
            reason = (
                f"{market} / {model}: performance is efficient enough to maintain, but the latest evidence is not a clear scale signal."
            )
        else:
            reason = f"{market} / {model}: recent evidence is limited, so keep this on watch rather than making a large move."

        rows.append({
            'market': market,
            'model_family': model,
            'latest_week_start': active['week_start'].max().date().isoformat(),
            'recent_spend': round(recent_spend, 2),
            'recent_sessions': int(recent_sessions),
            'recent_dcfs': int(recent_dcfs),
            'recent_cpl_dcfs': round(recent_cpl, 2) if recent_cpl is not None else None,
            'recent_visit_to_lead_rate': round(recent_vtl, 4) if recent_vtl is not None else None,
            'dcfs_trend_vs_previous_4w': round(dcfs_trend, 4) if dcfs_trend is not None else None,
            'spend_trend_vs_previous_4w': round(spend_trend, 4) if spend_trend is not None else None,
            'performance_bucket': performance_bucket,
            'performance_direction': performance_direction,
            'performance_reason': reason,
        })
    return pd.DataFrame(rows).sort_values(['performance_bucket', 'market', 'model_family'])


def load_activity_summary():
    signals = pd.read_csv(ACTIVITY_SIGNALS_PATH)
    signals['market'] = signals['market'].apply(normalize_market)
    signals['model_family'] = signals['model'].apply(activity_model_family)
    future = signals[signals['model_family'].isin(['Macan', 'Cayenne'])].copy()
    priority_actions = [
        'Harvest local upper-funnel demand',
        'CTG filling local gap',
        'Coordinated support',
        'Potential CTG whitespace',
        'Validate data before optimisation',
    ]
    rows = []
    for (market, model), group in future.groupby(['market', 'model_family'], dropna=False):
        counts = group['recommended_action'].value_counts().to_dict()
        bucket_counts = group['planning_bucket'].value_counts().to_dict()
        top_action = next((a for a in priority_actions if counts.get(a, 0) > 0), group['recommended_action'].mode().iloc[0])
        rows.append({
            'market': market,
            'model_family': model,
            'activity_top_signal': top_action,
            'activity_scale_weeks': int(bucket_counts.get('Scale', 0)),
            'activity_fix_weeks': int(bucket_counts.get('Fix', 0)),
            'activity_watch_weeks': int(bucket_counts.get('Watch', 0)),
            'activity_protect_weeks': int(bucket_counts.get('Protect', 0)),
            'harvest_weeks': int(counts.get('Harvest local upper-funnel demand', 0)),
            'gap_fill_weeks': int(counts.get('CTG filling local gap', 0)),
            'validate_weeks': int(counts.get('Validate data before optimisation', 0)),
            'activity_reason_sample': group['recommendation_reason'].dropna().astype(str).head(1).iloc[0],
        })
    return pd.DataFrame(rows)


def final_recommendation(perf_bucket, activity_signal, validate_weeks):
    if validate_weeks > 0:
        return 'Watch'
    if perf_bucket == 'Scale' and activity_signal in {'Harvest local upper-funnel demand', 'CTG filling local gap'}:
        return 'Increase'
    if perf_bucket == 'Scale':
        return 'Protect'
    if perf_bucket == 'Protect' and activity_signal == 'Harvest local upper-funnel demand':
        return 'Increase'
    if perf_bucket == 'Reduce' and activity_signal not in {'Harvest local upper-funnel demand', 'CTG filling local gap'}:
        return 'Reduce'
    if perf_bucket == 'Fix':
        return 'Fix'
    if activity_signal == 'Potential CTG whitespace':
        return 'Test'
    return 'Protect'


def final_reason(row):
    market = row['market']
    model = row['model_family']
    rec = row['final_budget_action']
    if rec == 'Increase':
        return (
            f"Increase {market} / {model}: observed performance is strong enough to support more pressure, "
            f"and the activity layer shows {row['activity_top_signal'].lower()}."
        )
    if rec == 'Reduce':
        return (
            f"Reduce {market} / {model}: recent spend is not producing enough dealer response and the activity layer does not show a strong reason to protect CTG."
        )
    if rec == 'Fix':
        return (
            f"Fix {market} / {model}: there is some opportunity, but performance needs channel, creative, or conversion work before scaling."
        )
    if rec == 'Test':
        return (
            f"Test {market} / {model}: local activity is visible but CTG has whitespace, so use a controlled test rather than a large shift."
        )
    if rec == 'Watch':
        return (
            f"Watch {market} / {model}: validate the activity or performance evidence before making a budget move."
        )
    return (
        f"Protect {market} / {model}: keep budget stable because performance or activity context supports presence, but not a large increase."
    )


def build_recommendations(performance_summary, activity_summary):
    combined = performance_summary.merge(activity_summary, on=['market', 'model_family'], how='outer')
    combined = combined[combined['market'].fillna('').astype(str).str.strip().ne('')]
    combined['performance_bucket'] = combined['performance_bucket'].fillna('Watch')
    combined['performance_direction'] = combined['performance_direction'].fillna('Keep small test budget')
    combined['activity_top_signal'] = combined['activity_top_signal'].fillna('No market activity signal')
    for col in ['activity_scale_weeks', 'activity_fix_weeks', 'activity_watch_weeks', 'activity_protect_weeks', 'harvest_weeks', 'gap_fill_weeks', 'validate_weeks']:
        combined[col] = pd.to_numeric(combined[col], errors='coerce').fillna(0).astype(int)
    combined['final_budget_action'] = combined.apply(
        lambda r: final_recommendation(r['performance_bucket'], r['activity_top_signal'], r['validate_weeks']),
        axis=1,
    )
    no_observed_performance = combined['recent_spend'].isna() & combined['recent_dcfs'].isna()
    activity_present = combined['activity_top_signal'].ne('No market activity signal')
    combined.loc[no_observed_performance & activity_present & combined['final_budget_action'].eq('Protect'), 'final_budget_action'] = 'Test'
    combined.loc[
        combined['performance_bucket'].eq('Reduce')
        & combined['activity_top_signal'].isin(['Harvest local upper-funnel demand', 'CTG filling local gap'])
        & combined['final_budget_action'].eq('Protect'),
        'final_budget_action',
    ] = 'Fix'
    action_rank = {'Increase': 1, 'Protect': 2, 'Test': 3, 'Fix': 4, 'Watch': 5, 'Reduce': 6}
    combined['final_reason'] = combined.apply(final_reason, axis=1)
    combined['action_rank'] = combined['final_budget_action'].map(action_rank).fillna(9)
    return combined.sort_values(['action_rank', 'market', 'model_family']).drop(columns=['action_rank'])


def build_report(recommendations):
    actions = recommendations['final_budget_action'].value_counts().to_dict()

    def action_table():
        lines = ['| Action | Market/model rows |', '|---|---:|']
        for action, count in actions.items():
            lines.append(f'| {action} | {count} |')
        return '\n'.join(lines)

    def examples(action, limit=8):
        rows = recommendations[recommendations['final_budget_action'] == action].head(limit)
        if rows.empty:
            return '- None in current cut.'
        return '\n'.join(f"- {r.final_reason}" for r in rows.itertuples())

    return f"""# Budget Reallocation - Final Workflow Output

## What This Adds

This completes the practical workflow after the market activity layer:

1. Observe recent market performance.
2. Classify each market/model into plain planning buckets.
3. Overlay known market activity.
4. Recommend whether to increase, protect, test, fix, watch, or reduce budget.

The point is explainability. The recommendation does not say "score = 78"; it says why a strategist should move or hold budget.

## Final Budget Action Counts

{action_table()}

## Increase Candidates

{examples('Increase')}

## Protect Candidates

{examples('Protect')}

## Test Candidates

{examples('Test')}

## Fix Candidates

{examples('Fix')}

## Watch Candidates

{examples('Watch')}

## Reduce Candidates

{examples('Reduce')}

## How To Explain This To Debs

The console now separates the budget conversation into two questions:

- **Is the market responding?** This comes from observed spend, sessions, dealer contact forms, CPL, and recent trend.
- **Is CTG adding something useful?** This comes from whether local market activity is absent, upper-funnel only, already lower-funnel, or incomplete.

The budget move only becomes convincing when both questions are answered together.

## Draft Final Email

Subject: CTG weekly optimisation - market activity and performance layer

Hi Debs,

I have now connected the market activity timeline to observed weekly performance so the Intelligence Console can support a more practical budget reallocation conversation.

The workflow now looks at recent market response first: spend, sessions, dealer contact forms, CPL, and recent trend. It then overlays Nico's market activity view to understand whether CTG is filling a gap, harvesting local demand, duplicating activity, or needs validation because the local data is incomplete.

The output is deliberately explainable. Each market/model gets a plain budget action: increase, protect, test, fix, watch, or reduce. The recommendation includes the reason, so we can say things like "increase because performance is responding and CTG is harvesting local upper-funnel activity" rather than asking the client to trust a black-box score.

This gives us a clearer position against a pure dashboard view: we are not just reporting activity, we are turning activity and performance into weekly planning decisions.

Thanks,  
Ali

## Draft Team Message

Final workflow update: the CTG activity layer is now connected to observed weekly performance. The output gives each market/model a plain budget action - increase, protect, test, fix, watch, or reduce - with a reason based on both recent response and local market activity context. This should make the optimisation story much easier to explain than a score-based ranking.
"""


def main():
    OUT_DIR.mkdir(exist_ok=True)
    weekly = load_weekly_performance()
    performance_summary = summarize_performance(weekly)
    activity_summary = load_activity_summary()
    recommendations = build_recommendations(performance_summary, activity_summary)

    weekly.to_csv(WEEKLY_PERFORMANCE_OUT, index=False)
    performance_summary.to_csv(MARKET_SUMMARY_OUT, index=False)
    recommendations.to_csv(RECOMMENDATIONS_OUT, index=False)
    REPORT_OUT.write_text(build_report(recommendations), encoding='utf-8')

    print(f'Wrote {WEEKLY_PERFORMANCE_OUT} ({len(weekly)} rows)')
    print(f'Wrote {MARKET_SUMMARY_OUT} ({len(performance_summary)} rows)')
    print(f'Wrote {RECOMMENDATIONS_OUT} ({len(recommendations)} rows)')
    print(f'Wrote {REPORT_OUT}')


if __name__ == '__main__':
    main()
