import ast

import pandas as pd


def parse_budget_split_input(raw_text: str) -> pd.DataFrame:
    text = (raw_text or "").strip()
    if not text:
        return pd.DataFrame(columns=["Market", "budget_amount", "budget_share"])

    try:
        parsed = ast.literal_eval(text)
    except Exception as exc:
        raise ValueError(f"Unable to parse budget split input: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Budget split input must be a dictionary of Market -> budget.")

    rows = []
    for market, amount in parsed.items():
        market_key = str(market).strip()
        if not market_key:
            continue
        try:
            budget_amount = float(amount)
        except Exception as exc:
            raise ValueError(f"Budget for {market_key} is not numeric.") from exc
        if budget_amount < 0:
            raise ValueError(f"Budget for {market_key} must be non-negative.")
        rows.append({"Market": market_key, "budget_amount": budget_amount})

    budget_df = pd.DataFrame(rows)
    if budget_df.empty:
        return pd.DataFrame(columns=["Market", "budget_amount", "budget_share"])

    total_budget = float(budget_df["budget_amount"].sum())
    if total_budget <= 0:
        raise ValueError("Budget split total must be greater than zero.")

    budget_df["budget_share"] = budget_df["budget_amount"] / total_budget
    return budget_df


def calculate_cost_kpi_adjustment(actual_value: float, benchmark_value: float) -> float | None:
    if actual_value is None or benchmark_value is None or benchmark_value <= 0:
        return None
    delta = (benchmark_value - actual_value) / benchmark_value
    if delta < 0:
        return max(delta, -0.5)
    if delta <= 0.10:
        return 0.0
    return min(delta - 0.10, 0.5)


def build_weighted_fee_table(
    budget_df: pd.DataFrame,
    forecast_kpi: float,
    benchmark_value: float,
    bah_fee: float,
    fte_fee: float,
) -> tuple[pd.DataFrame, dict]:
    if budget_df.empty:
        return pd.DataFrame(), {}

    adjustment = calculate_cost_kpi_adjustment(forecast_kpi, benchmark_value)
    variable_bah = 0.5 * bah_fee
    variable_fte = 0.2 * fte_fee
    variable_fee = variable_bah + variable_fte
    fixed_fee = (bah_fee + fte_fee) - variable_fee

    weighted_df = budget_df.copy()
    weighted_df["forecast_kpi"] = forecast_kpi
    weighted_df["benchmark_kpi"] = benchmark_value
    weighted_df["adjustment"] = adjustment
    weighted_df["variable_fee_base"] = weighted_df["budget_share"] * variable_fee
    weighted_df["fixed_fee_base"] = weighted_df["budget_share"] * fixed_fee
    weighted_df["bah_variable_base"] = weighted_df["budget_share"] * variable_bah
    weighted_df["fte_variable_base"] = weighted_df["budget_share"] * variable_fte
    weighted_df["bah_adjustment"] = weighted_df["bah_variable_base"] * adjustment
    weighted_df["fte_adjustment"] = weighted_df["fte_variable_base"] * adjustment
    weighted_df["final_fee"] = (
        weighted_df["fixed_fee_base"] + weighted_df["variable_fee_base"] * (1 + adjustment)
    )

    summary = {
        "total_budget": float(weighted_df["budget_amount"].sum()),
        "weighted_adjustment": adjustment,
        "bah_adjustment_total": float(weighted_df["bah_adjustment"].sum()),
        "fte_adjustment_total": float(weighted_df["fte_adjustment"].sum()),
        "final_fee_total": float(weighted_df["final_fee"].sum()),
        "budget_coverage_markets": int(len(weighted_df)),
    }
    return weighted_df, summary


def compute_weighted_market_percentiles(
    points_df: pd.DataFrame,
    budget_df: pd.DataFrame,
    percentiles: list[float],
) -> dict[float, float]:
    if points_df.empty or budget_df.empty or "Market" not in points_df.columns:
        return {}

    working_points = points_df[["Market", "kpi_value"]].copy()
    working_points["Market"] = working_points["Market"].astype(str)
    working_points["kpi_value"] = pd.to_numeric(working_points["kpi_value"], errors="coerce")
    working_points = working_points.dropna(subset=["kpi_value"])
    if working_points.empty:
        return {}

    working_budget = budget_df[["Market", "budget_amount"]].copy()
    working_budget["Market"] = working_budget["Market"].astype(str)
    working_budget = working_budget[working_budget["Market"].isin(working_points["Market"].unique())]
    if working_budget.empty:
        return {}

    working_budget["budget_share"] = working_budget["budget_amount"] / working_budget["budget_amount"].sum()
    market_quantiles = (
        working_points.groupby("Market", dropna=False)["kpi_value"]
        .quantile(percentiles)
        .unstack()
        .reset_index()
    )
    merged = working_budget.merge(market_quantiles, on="Market", how="inner")
    if merged.empty:
        return {}

    weighted = {}
    for percentile in percentiles:
        if percentile not in merged.columns:
            continue
        values = pd.to_numeric(merged[percentile], errors="coerce")
        mask = values.notna()
        if not mask.any():
            continue
        shares = merged.loc[mask, "budget_share"]
        shares = shares / shares.sum()
        weighted[percentile] = float((values.loc[mask] * shares).sum())
    return weighted
