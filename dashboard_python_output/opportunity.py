from __future__ import annotations

import pandas as pd

OPPORTUNITY_CONFIG = {
    'min_weeks_required': 6,
    'min_total_spend': 5000,
    'min_total_dcfs': 30,
    'headroom_high': 0.30,
    'headroom_med': 0.15,
    'recent_cpl_periods': 3,
    'recent_scale_periods': 4,
    'recent_curve_periods': 4,
    'growth_ratio_max': 0.60,
    'mid_ratio_max': 1.10,
    'min_curve_points': 8,
    'min_curve_dcfs': 50,
    'min_spend_range_ratio': 2.0,
    'vol_low': 0.40,
    'vol_med': 0.50,
    'vol_high': 0.60,
}


def _select_time_col(df_in):
    for col in ['Date', 'report_date', 'calendar_week']:
        if col in df_in.columns:
            return col
    return None


def _safe_quantile(series, q):
    if series is None or series.empty:
        return None
    value = series.quantile(q)
    if pd.isna(value):
        return None
    return float(value)


def _find_column(df_in, name):
    target = name.lower()
    for col in df_in.columns:
        if col.lower() == target:
            return col
    return None


def _lookup_benchmark(series, key):
    try:
        value = series.loc[key]
    except KeyError:
        return None
    if pd.isna(value):
        return None
    return float(value)


def _compute_benchmarks(valid_df):
    p25_group = valid_df.groupby(['Market', 'Channel', 'Model'], dropna=False)['cpl'].quantile(0.25)
    p25_market_channel = valid_df.groupby(['Market', 'Channel'], dropna=False)['cpl'].quantile(0.25)
    p25_channel = valid_df.groupby(['Channel'], dropna=False)['cpl'].quantile(0.25)
    return p25_group, p25_market_channel, p25_channel


def compute_headroom_scores(df_in, config):
    required_cols = ['Market', 'Channel', 'Model', 'Media Spend', 'DCFS']
    missing = [col for col in required_cols if col not in df_in.columns]
    if missing:
        return pd.DataFrame(), missing

    data = df_in.copy()
    data['Media Spend'] = pd.to_numeric(data['Media Spend'], errors='coerce')
    data['DCFS'] = pd.to_numeric(data['DCFS'], errors='coerce')

    valid = data[(data['Media Spend'] > 0) & (data['DCFS'] > 0)].copy()
    valid['cpl'] = valid['Media Spend'] / valid['DCFS']

    p25_group, p25_market_channel, p25_channel = _compute_benchmarks(valid)

    time_col = _select_time_col(data)
    s50_col = _find_column(data, 's50_spend')
    rows = []
    grouped = data.groupby(['Market', 'Channel', 'Model'], dropna=False)

    for (market, channel, model), group in grouped:
        group_sorted = group.sort_values(time_col) if time_col and time_col in group.columns else group
        n_weeks = len(group)
        total_spend = group['Media Spend'].sum(skipna=True)
        total_dcfs = group['DCFS'].sum(skipna=True)

        valid_group = group[(group['Media Spend'] > 0) & (group['DCFS'] > 0)].copy()
        valid_group['cpl'] = valid_group['Media Spend'] / valid_group['DCFS']
        if time_col and time_col in valid_group.columns:
            valid_group = valid_group.sort_values(time_col)

        recent = valid_group.tail(int(config.get('recent_cpl_periods', 3)))
        current_cpl = _safe_quantile(recent['cpl'], 0.5) if not recent.empty else None

        recent4 = group_sorted.tail(int(config.get('recent_scale_periods', 4)))
        avg_dcfs_recent = recent4['DCFS'].mean(skipna=True) if not recent4.empty else None
        avg_spend_recent = recent4['Media Spend'].mean(skipna=True) if not recent4.empty else None
        scale_proxy = float(avg_dcfs_recent) if avg_dcfs_recent is not None and pd.notna(avg_dcfs_recent) else None

        vol_rows = group[(group['Media Spend'] > 0) & (group['DCFS'] > 0)].copy()
        vol_rows['cpl'] = vol_rows['Media Spend'] / vol_rows['DCFS']
        vol_values = vol_rows['cpl'].dropna()
        volatility = None
        vol_tier = 'UNKNOWN'
        predictability_penalty = None
        vol_notes = []
        if not vol_values.empty:
            q1 = vol_values.quantile(0.25)
            q3 = vol_values.quantile(0.75)
            denom = q3 + q1
            if denom == 0:
                volatility = 1.0
                vol_notes.append('zero_denominator_forced_volatility')
            else:
                volatility = float((q3 - q1) / denom)
            vol_low = float(config.get('vol_low', 0.40))
            vol_med = float(config.get('vol_med', 0.50))
            vol_high = float(config.get('vol_high', 0.60))
            if volatility <= vol_low:
                vol_tier = 'LOW'
                predictability_penalty = 0
            elif volatility <= vol_med:
                vol_tier = 'MED'
                predictability_penalty = 10
            elif volatility <= vol_high:
                vol_tier = 'HIGH'
                predictability_penalty = 25
            else:
                vol_tier = 'VERY_HIGH'
                predictability_penalty = 40
        else:
            vol_notes.append('no_valid_cpl')

        benchmark = _lookup_benchmark(p25_group, (market, channel, model))
        benchmark_source = 'market_channel_model'
        if benchmark is None:
            benchmark = _lookup_benchmark(p25_market_channel, (market, channel))
            benchmark_source = 'market_channel'
        if benchmark is None:
            benchmark = _lookup_benchmark(p25_channel, channel)
            benchmark_source = 'channel'
        if benchmark is None:
            benchmark_source = 'missing'

        headroom = None
        headroom_clamped = None
        headroom_score = None
        headroom_tier = None
        if current_cpl is not None and benchmark and benchmark > 0:
            headroom = (current_cpl - benchmark) / benchmark
            headroom_clamped = max(-1, min(3, headroom))
            if headroom_clamped <= 0:
                headroom_score = 0.0
                headroom_tier = 'NONE'
            else:
                headroom_score = min(100.0, headroom_clamped / config['headroom_high'] * 100.0)
                if headroom_clamped >= config['headroom_high']:
                    headroom_tier = 'HIGH'
                elif headroom_clamped >= config['headroom_med']:
                    headroom_tier = 'MED'
                else:
                    headroom_tier = 'LOW'

        gate_passed = True
        gate_reasons = []
        if n_weeks < config['min_weeks_required']:
            gate_passed = False
            gate_reasons.append('min_weeks_required')
        if total_spend < config['min_total_spend']:
            gate_passed = False
            gate_reasons.append('min_total_spend')
        if total_dcfs < config['min_total_dcfs']:
            gate_passed = False
            gate_reasons.append('min_total_dcfs')

        curve_notes = []
        spend_recent = None
        k_used = 0
        s50_spend = None
        ratio = None
        curve_zone_raw = 'UNKNOWN'
        curve_score_raw = 50.0
        curve_zone = 'UNKNOWN'
        curve_score = 50.0
        curve_worthy = True
        curve_worthiness_notes = []
        growth_ratio_max = float(config.get('growth_ratio_max', 0.60))
        mid_ratio_max = float(config.get('mid_ratio_max', 1.10))

        spend_positive = group_sorted[group_sorted['Media Spend'] > 0]
        recent_k = int(config.get('recent_curve_periods', 4))
        recent_spend = spend_positive.tail(recent_k)
        if len(recent_spend) >= 2:
            spend_recent = recent_spend['Media Spend'].mean(skipna=True)
            k_used = len(recent_spend)
        else:
            if len(spend_positive) > 0:
                spend_recent = spend_positive['Media Spend'].median(skipna=True)
                curve_notes.append('fallback_median_all_periods')
            else:
                curve_notes.append('no_positive_spend')

        if s50_col and s50_col in group.columns:
            s50_series = group[s50_col].dropna()
            if not s50_series.empty:
                s50_spend = float(s50_series.iloc[0])
        if s50_col is None:
            curve_notes.append('missing_s50_column')
        elif s50_spend is None or s50_spend <= 0:
            curve_notes.append('invalid_s50_spend')
        elif spend_recent is None or pd.isna(spend_recent):
            curve_notes.append('missing_spend_recent')
        else:
            ratio = spend_recent / s50_spend
            if ratio <= growth_ratio_max:
                curve_zone_raw = 'GROWTH'
                curve_score_raw = 100.0
            elif ratio <= mid_ratio_max:
                curve_zone_raw = 'MID'
                curve_score_raw = 50.0
            else:
                curve_zone_raw = 'SATURATED'
                curve_score_raw = 0.0

        spend_points = int(len(spend_positive))
        spend_min = spend_positive['Media Spend'].min() if spend_points else None
        spend_max = spend_positive['Media Spend'].max() if spend_points else None
        spend_range_ratio = None
        if spend_min is not None and spend_min > 0 and spend_max is not None:
            spend_range_ratio = spend_max / spend_min

        if spend_points < int(config.get('min_curve_points', 8)):
            curve_worthy = False
            curve_worthiness_notes.append('insufficient_spend_points')
        if total_dcfs < float(config.get('min_curve_dcfs', 50)):
            curve_worthy = False
            curve_worthiness_notes.append('insufficient_total_dcfs')
        if spend_range_ratio is not None and spend_range_ratio < float(config.get('min_spend_range_ratio', 2.0)):
            curve_worthy = False
            curve_worthiness_notes.append('low_spend_range')
        if s50_spend is not None and s50_spend > 0 and spend_max is not None:
            if spend_max < s50_spend * growth_ratio_max:
                curve_worthy = False
                curve_worthiness_notes.append('max_spend_below_growth_ratio')

        if s50_spend is None and curve_worthy:
            curve_notes.append('missing_s50_spend')

        if not gate_passed:
            curve_notes.append('gate_failed')
        else:
            curve_zone = curve_zone_raw
            curve_score = curve_score_raw

        if curve_zone == 'UNKNOWN':
            curve_zone = 'GROWTH'
            curve_score = 100.0
            curve_notes.append('unknown_forced_growth')
        if not curve_worthy and s50_spend is None:
            curve_zone = 'GROWTH'
            curve_score = 100.0
            curve_notes.append('curve_not_worthy_forced_growth')

        audit = {
            'n_weeks': int(n_weeks),
            'total_spend': float(total_spend) if pd.notna(total_spend) else None,
            'total_dcfs': float(total_dcfs) if pd.notna(total_dcfs) else None,
            'current_cpl': current_cpl,
            'benchmark_cpl_p25': benchmark,
            'benchmark_source': benchmark_source,
            'headroom_raw': headroom,
            'headroom_clamped': headroom_clamped,
            'headroom_tier': headroom_tier,
            'headroom_score': headroom_score,
            'avg_dcfs_recent': float(avg_dcfs_recent) if avg_dcfs_recent is not None and pd.notna(avg_dcfs_recent) else None,
            'avg_spend_recent': float(avg_spend_recent) if avg_spend_recent is not None and pd.notna(avg_spend_recent) else None,
            'scale_proxy': scale_proxy,
            'volatility': volatility,
            'vol_tier': vol_tier,
            'predictability_penalty': predictability_penalty,
            'vol_notes': vol_notes,
            'spend_recent': float(spend_recent) if spend_recent is not None and pd.notna(spend_recent) else None,
            'k_used': int(k_used) if k_used else 0,
            's50_spend': s50_spend,
            'curve_ratio': float(ratio) if ratio is not None and pd.notna(ratio) else None,
            'curve_zone_raw': curve_zone_raw,
            'curve_score_raw': curve_score_raw,
            'curve_zone': curve_zone,
            'curve_score': curve_score,
            'curve_worthy': curve_worthy,
            'curve_worthiness_notes': curve_worthiness_notes,
            'curve_thresholds': {
                'growth_ratio_max': growth_ratio_max,
                'mid_ratio_max': mid_ratio_max,
            },
            'curve_notes': curve_notes,
            'gate_passed': gate_passed,
            'gate_reasons': gate_reasons,
        }

        rows.append({
            'Market': market,
            'Channel': channel,
            'Model': model,
            'current_cpl': current_cpl,
            'benchmark_cpl_p25': benchmark,
            'benchmark_source': benchmark_source,
            'headroom': headroom_clamped,
            'headroom_score': headroom_score,
            'headroom_tier': headroom_tier,
            'avg_dcfs_recent': avg_dcfs_recent,
            'avg_spend_recent': avg_spend_recent,
            'scale_proxy': scale_proxy,
            'scale_score': None,
            'scale_dist_n': None,
            'scale_dist_p25': None,
            'scale_dist_p50': None,
            'scale_dist_p75': None,
            'volatility': volatility,
            'vol_tier': vol_tier,
            'predictability_penalty': predictability_penalty,
            'spend_recent': spend_recent,
            'k_used': k_used,
            's50_spend': s50_spend,
            'curve_ratio': ratio,
            'curve_zone_raw': curve_zone_raw,
            'curve_score_raw': curve_score_raw,
            'curve_zone': curve_zone,
            'curve_score': curve_score,
            'curve_worthy': curve_worthy,
            'curve_worthiness_notes': ', '.join(curve_worthiness_notes) if curve_worthiness_notes else None,
            'gate_passed': gate_passed,
            'gate_reasons': ', '.join(gate_reasons) if gate_reasons else None,
            'audit': audit,
        })

    result_df = pd.DataFrame(rows)
    if result_df.empty:
        return result_df, []

    eligible = result_df[(result_df['gate_passed']) & result_df['scale_proxy'].notna()].copy()
    if not eligible.empty:
        for channel, channel_df in eligible.groupby('Channel', dropna=False):
            series = channel_df['scale_proxy']
            dist_n = int(series.count())
            dist_p25 = _safe_quantile(series, 0.25)
            dist_p50 = _safe_quantile(series, 0.50)
            dist_p75 = _safe_quantile(series, 0.75)
            ranks = series.rank(pct=True) * 100
            for idx, score in ranks.items():
                result_df.at[idx, 'scale_score'] = float(score)
                result_df.at[idx, 'scale_dist_n'] = dist_n
                result_df.at[idx, 'scale_dist_p25'] = dist_p25
                result_df.at[idx, 'scale_dist_p50'] = dist_p50
                result_df.at[idx, 'scale_dist_p75'] = dist_p75
                audit = result_df.at[idx, 'audit']
                if isinstance(audit, dict):
                    audit.update({
                        'scale_score': float(score),
                        'scale_dist_n': dist_n,
                        'scale_dist_p25': dist_p25,
                        'scale_dist_p50': dist_p50,
                        'scale_dist_p75': dist_p75,
                    })
                    result_df.at[idx, 'audit'] = audit

    headroom_component = result_df['headroom_score'].fillna(0.0)
    scale_component = result_df['scale_score'].fillna(0.0)
    curve_component = result_df['curve_score'].fillna(0.0)
    penalty_component = result_df['predictability_penalty'].fillna(0.0)
    raw_opportunity_score = (
        0.45 * headroom_component
        + 0.25 * scale_component
        + 0.30 * curve_component
    )
    opportunity_score = (raw_opportunity_score - penalty_component).clip(lower=0.0, upper=100.0)
    result_df['raw_opportunity_score'] = raw_opportunity_score
    result_df['opportunity_score'] = opportunity_score

    def _score_to_tier(score):
        if score is None or pd.isna(score):
            return 'NONE'
        if score >= 70:
            return 'HIGH'
        if score >= 40:
            return 'MEDIUM'
        if score >= 15:
            return 'LOW'
        return 'NONE'

    result_df['opportunity_tier'] = result_df['opportunity_score'].apply(_score_to_tier)

    def _apply_overrides(row):
        tier = row.get('opportunity_tier', 'NONE')
        audit_notes = []
        if row.get('vol_tier') == 'VERY_HIGH':
            audit_notes.append('override_volatility_very_high')
            return 'NONE', audit_notes
        if row.get('curve_zone') == 'SATURATED' and tier in {'HIGH', 'MEDIUM'}:
            audit_notes.append('override_curve_saturated')
            tier = 'LOW'
        if row.get('headroom_tier') == 'NONE' and tier == 'HIGH':
            audit_notes.append('override_headroom_none')
            tier = 'MEDIUM'
        return tier, audit_notes

    override_notes = []
    final_tiers = []
    for _, row in result_df.iterrows():
        tier, notes = _apply_overrides(row)
        final_tiers.append(tier)
        override_notes.append(notes)
    result_df['opportunity_tier'] = final_tiers
    result_df['tier_override_notes'] = [
        ', '.join(notes) if notes else None for notes in override_notes
    ]

    for idx, row in result_df.iterrows():
        audit = row.get('audit')
        if isinstance(audit, dict):
            audit.update({
                'raw_opportunity_score': row['raw_opportunity_score'],
                'opportunity_score': row['opportunity_score'],
                'opportunity_tier': row['opportunity_tier'],
                'tier_override_notes': row['tier_override_notes'],
            })
            result_df.at[idx, 'audit'] = audit

    return result_df, []
