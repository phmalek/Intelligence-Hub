Implement a SIMPLE, AUDITABLE bonus/malus pipeline using 4 precomputed factors.
Do NOT recompute headroom/scale/spend_position/volatility. They are inputs.

GOAL
- For each (market, channel, carline): classify eligibility and compute a simple opportunity score.
- Aggregate to one portfolio score + portfolio index.
- Map index to a bonus/malus payout with deadband and +/-50% cap.
- Output an audit trail that explains every step.

INPUT
DataFrame df with ONE row per (market, channel, carline) and columns:
- market: str
- channel: str
- carline: str
- headroom_score: int in [0..100]
- scale_score: int in [0..100]          # percentile within channel based on recent DCFS
- spend_position_score: int in [0..100] # Growth=100, Mid=50, Saturated=0, Unknown=50 (already computed)
- spend_zone: str in {"GROWTH","MID","SATURATED","UNKNOWN"} (already computed)
- volatility_tier: str in {"LOW","MED","HIGH","VERY_HIGH"} (already computed)

CONFIG (constants; put in a dict/dataclass)
- deadband = 0.05               # +/-5% no payout zone
- cap = 0.50                    # +/-50% payout cap
- target_index = 1.00
- score_weights:
  - w_headroom = 0.50
  - w_spendpos = 0.30
  - w_scale = 0.20
- eligibility_rules:
  - EXCLUDED if volatility_tier == "VERY_HIGH"
  - ELIGIBLE if volatility_tier in {"LOW","MED"} AND spend_zone != "SATURATED"
  - CAPPED otherwise (i.e., volatility_tier == "HIGH" OR spend_zone in {"MID","SATURATED","UNKNOWN"} )
- capped_weight_multiplier = 0.50   # CAPPED rows count half as much in weighting
- excluded_weight_multiplier = 0.00

OUTPUTS
1) combo-level df_out: same keys + these columns
- eligibility: "ELIGIBLE"|"CAPPED"|"EXCLUDED"
- opportunity_score: float in [0..100]
- base_weight: float
- adj_weight: float
- norm_weight: float
- contribution: float
- audit: dict (json-serializable)

2) portfolio summary dict:
- portfolio_score: float
- portfolio_index: float
- payout_factor: float in [-0.50..+0.50]
- audit_portfolio: dict

STEP-BY-STEP (must be followed exactly, and each step logged in audit)

STEP 1 — Eligibility classification
For each row:
- if volatility_tier == "VERY_HIGH": eligibility="EXCLUDED"
- else if volatility_tier in {"LOW","MED"} and spend_zone != "SATURATED": eligibility="ELIGIBLE"
- else: eligibility="CAPPED"
Store in audit: volatility_tier, spend_zone, eligibility_reason.

STEP 2 — Compute opportunity_score (simple weighted average)
opportunity_score = w_headroom*headroom_score + w_spendpos*spend_position_score + w_scale*scale_score
Clamp to [0,100].
Store in audit: weights, inputs, computed score.

STEP 3 — Compute base_weight from scale_score
base_weight = scale_score
(Yes: scale_score is already a percentile proxy; we use it as a simple weight.)
Store in audit.

STEP 4 — Apply eligibility multipliers to get adj_weight
- if eligibility=="ELIGIBLE": adj_weight = base_weight * 1.0
- if eligibility=="CAPPED":   adj_weight = base_weight * capped_weight_multiplier
- if eligibility=="EXCLUDED": adj_weight = base_weight * excluded_weight_multiplier  # => 0
Store in audit: multiplier used.

STEP 5 — Normalize weights
total_adj_weight = sum(adj_weight)
If total_adj_weight == 0:
- portfolio_score=100.0
- portfolio_index=1.0
- payout_factor=0.0
- return outputs with audit_portfolio explaining "no eligible volume"
Else for each row:
- norm_weight = adj_weight / total_adj_weight
- contribution = norm_weight * opportunity_score
Store in audit.

STEP 6 — Portfolio aggregation
portfolio_score = sum(contribution)        # 0..100
portfolio_index = portfolio_score / 100.0  # around 1.0
Store in audit_portfolio.

STEP 7 — Map portfolio_index to bonus/malus payout_factor
delta = portfolio_index - target_index

If abs(delta) <= deadband:
- payout_factor = 0.0
Else:
- effective_delta = delta - sign(delta)*deadband
- slope = cap / (1.0 - deadband)   # so delta=+1 maps to +cap after deadband removal
- payout_factor = clamp(slope*effective_delta, -cap, +cap)

Store in audit_portfolio: delta, effective_delta, slope, deadband, cap, payout_factor.

IMPLEMENTATION REQUIREMENTS
- Provide function: run_bonus_malus(df, config) -> (df_out, portfolio_summary)
- Must be deterministic (no randomness).
- Must create an audit dict per row with all intermediate values and reasons.
- Must create a portfolio audit dict.
- Include 3 minimal tests using tiny synthetic dataframes:
  1) all VERY_HIGH volatility => payout 0
  2) mix of ELIGIBLE + CAPPED => payout computed
  3) deadband check (index close to 1.0 => payout 0)

Keep the code short, readable, with type hints and docstrings.
