# Close the Gap  
## Budget Allocation Report - Risk-Aware + Reverse-Funnel Blend  

---

## Scope  

This allocation covers 14 markets: PCA, PCGB, PCH, PCL, PD, PIB Por, PIB Spa, PIT, PKO, PNO, POF, PPL, PTW and TRK.

Included activity:
- Paid Search and Paid Social  
- Cayenne, Macan, Panamera, Taycan and mixed range  
- Panamera & Cayenne Close the Gap  
- Winning BEV Close the Gap  

All modelling is based on weekly performance data.

Total available budget: **EUR 80,000**

---

## Core Concepts Behind the Allocation  

### 1. Spend Response  

Each market has a response curve that estimates how additional budget translates into incremental DCFS.

At low spend levels, incremental gains are strong.  
As spend increases, gains begin to flatten.  

This curve allows us to identify where incremental investment still produces meaningful return.

---

### 2. Scale  

Scale reflects how large and active a market currently is.

It is derived from recent DCFS volume:
- Markets are ranked within their channel.
- Rankings are converted into percentile scores.
- Scores are normalised between 0 and 1 for weighting.

Scale matters because larger, active markets can usually absorb incremental budget more reliably.

In this scenario:
- **HeadroomStrength = 0.00**
- **ScaleStrength = 1.00**

Only scale influences driver allocation.

---

### 3. Risk-Aware Allocation  

The allocation first blends:
- Pure spend optimisation  
- Scale-based steering  

The blend is controlled by:

**ConstraintStrength = 0.50**

This means:
- 50% optimisation logic  
- 50% scale logic  

Minimum spend per market is enforced (EUR 500 each).  
No maximum caps are applied.

This produces a **risk-aware allocation** (both unconstrained and constrained).

---

## Reverse-Funnel Blend  

In addition to the risk-aware allocation, a strategic overlay is introduced.

The reverse-funnel split represents a predefined target share per market.  

The final blended allocation is calculated as:

> x_blend = (1 - lambda) x risk_allocation + lambda x reverse_funnel_split  

Where:

**ReverseFunnelBlend (lambda) = 0.90**

This means:
- 90% strategic target split  
- 10% optimisation logic  

lambda = 0 -> pure optimisation  
lambda = 1 -> fully enforce strategic split  

Blending is applied separately to unconstrained and constrained allocations.

---

## Key Parameters  

| Parameter | Value |
|------------|--------|
| Total Budget | EUR 80,000 |
| Headroom Strength | 0.00 |
| Scale Strength | 1.00 |
| Constraint Strength | 0.50 |
| ReverseFunnelBlend (lambda) | 0.90 |
| Minimum Spend | EUR 500 per market |
| Maximum Caps | Not applied |
| Markets Modelled | 14 |

---

## Performance Comparison  

| Scenario | Total DCFS |
|------------|-------------|
| Pure Optimisation (Unconstrained) | 149.10 |
| Risk-Aware (Constrained) | 130.27 |
| Blended (Unconstrained) | 93.02 |
| Blended (Constrained) | 84.56 |

Observations:

- Pure optimisation heavily concentrates in TRK.  
- Risk-aware allocation reduces extreme concentration.  
- Reverse-funnel blend significantly shifts capital toward strategic targets.  
- Higher strategic weight (lambda = 0.90) reduces short-term DCFS but increases structural alignment.

---

## Allocation Overview by Scenario  

### Risk-Aware (Constrained)

Largest allocations:
- TRK: EUR 25,101 (31.38%)
- PKO: EUR 12,508 (15.64%)
- PIT: EUR 10,771 (13.46%)

All markets receive minimum EUR 500.

---

### Reverse-Funnel Blend (Constrained)

Largest allocations shift toward:
- PCGB: EUR 16,587 (20.73%)
- PD: EUR 13,923 (17.40%)
- PKO: EUR 10,251 (12.81%)
- POF: EUR 7,592 (9.49%)

TRK reduces significantly under strategic blend:
- EUR 4,742 (5.93%)

---

## Interpretation  

Three distinct allocation logics are visible:

**1. Pure Optimisation**  
Maximises DCFS but concentrates heavily in one market (TRK).

**2. Risk-Aware Blend (50/50)**  
Balances optimisation and scale.  
Reduces extreme exposure while preserving performance.

**3. Reverse-Funnel Blend (lambda = 0.90)**  
Strongly enforces strategic split.  
Materially redistributes budget toward predefined group targets.  
Short-term DCFS decreases, but structural alignment increases.

---

## Strategic Takeaway  

The model allows controlled movement along a spectrum:

- From performance-maximising  
- To risk-aware  
- To strategy-enforced  

The ReverseFunnelBlend parameter is the primary lever controlling that shift.

At lambda = 0.90, allocation prioritises strategic distribution over pure incremental return, while still retaining a small optimisation anchor.

This creates flexibility:  
short-term performance and long-term structural objectives can be actively balanced rather than chosen in isolation.
