# CTG Market Activity Integration - Day 2 Output

## What Changed Today

- Tightened the channel taxonomy so local market labels and CTG labels map into a common planning language.
- Added confidence handling so incomplete market rows are not treated as reliable optimisation evidence.
- Added `budget_direction`, `planning_bucket`, and `recommendation_reason` to the weekly signal table.
- Updated the app layer to support more explainable recommendations rather than only counts.

## New Files / Updated Outputs

- `market_activities/channel_taxonomy_day2.csv`
- `market_activities/local_activity_normalized.csv`
- `market_activities/ctg_timeline_normalized.csv`
- `market_activities/market_activity_weekly_signals.csv`
- `market_activities/market_activity_day2_report.md`

## Day 2 Data Summary

- Local activity rows: **64**
- CTG timeline rows: **131**
- Weekly signal rows: **1516**
- Channel taxonomy mappings: **19**
- Local rows needing follow-up: **3**

## Planning Buckets

| Planning Bucket | Rows |
|---|---:|
| Fix | 832 |
| Scale | 580 |
| Protect | 58 |
| Watch | 46 |

## Budget Directions

| Budget Direction | Rows |
|---|---:|
| Review for CTG test | 832 |
| Protect or upweight CTG | 296 |
| Upweight CTG lower-funnel | 284 |
| Coordinate with market | 58 |
| Validate before moving budget | 46 |

## Signal Counts

| Signal | Rows |
|---|---:|
| Potential CTG whitespace | 832 |
| CTG filling local gap | 296 |
| Harvest local upper-funnel demand | 284 |
| Coordinated support | 58 |
| Validate data before optimisation | 46 |

## Confidence Counts

| Confidence | Rows |
|---|---:|
| High | 1470 |
| Low | 46 |

## Channel Taxonomy Summary

- Brand Days: upper_funnel, 1 raw label(s)
- Branded Content: upper_funnel, 1 raw label(s)
- CTV: upper_funnel, 1 raw label(s)
- Cinemas: upper_funnel, 2 raw label(s)
- DOOH: upper_funnel, 1 raw label(s)
- Display: lower_funnel, 1 raw label(s)
- Google Ads: lower_funnel, 1 raw label(s)
- Google Inventory Ads: lower_funnel, 1 raw label(s)
- META Inventory Ads: lower_funnel, 1 raw label(s)
- Other Online Channel: upper_funnel, 1 raw label(s)
- Paid Social: upper_funnel, 1 raw label(s)
- Programmatic: upper_funnel, 1 raw label(s)
- Retail Marketplace: lower_funnel, 2 raw label(s)
- Search: lower_funnel, 1 raw label(s)
- Social: upper_funnel, 1 raw label(s)
- Streaming TV: upper_funnel, 1 raw label(s)
- YouTube: upper_funnel, 1 raw label(s)

## Strong Examples For Discussion

### Scale / Harvest

- PCA / Macan BEV in week 2026-04-27: local activity is creating demand (Programmatic) and CTG has lower-funnel capture live (Google Ads, META Inventory Ads).
- PCL / Cayenne E3 II in week 2026-04-27: local activity is creating demand (Programmatic, Search, Social) and CTG has lower-funnel capture live (Google Ads, Google Inventory Ads, META Inventory Ads).
- PCL / Cayenne E4 in week 2026-04-27: local activity is creating demand (CTV, DOOH, Other Online Channel, Programmatic, Search, Social) and CTG has lower-funnel capture live (Google Ads).
- PCL / Macan BEV in week 2026-04-27: local activity is creating demand (Programmatic, Search, Social) and CTG has lower-funnel capture live (Google Ads, Google Inventory Ads, META Inventory Ads).
- PD / Cayenne E3 II in week 2026-04-27: local activity is creating demand (Programmatic, Search) and CTG has lower-funnel capture live (Google Ads, META Inventory Ads).
- PD / Cayenne E4 in week 2026-04-27: local activity is creating demand (Programmatic, Search) and CTG has lower-funnel capture live (Google Ads).

### Protect Or Upweight CTG Gap-Fill

- PCA / Cayenne E3 II in week 2026-04-27: CTG is active (META Inventory Ads) where no confirmed local activity is planned.
- PCA / Cayenne E4 in week 2026-04-27: CTG is active (Google Ads) where no confirmed local activity is planned.
- PCGB / Cayenne E4 in week 2026-04-27: CTG is active (Google Ads) where no confirmed local activity is planned.
- PCGB / Macan BEV in week 2026-04-27: CTG is active (Google Ads, Google Inventory Ads, META Inventory Ads) where no confirmed local activity is planned.
- PIB POR / Cayenne E4 in week 2026-04-27: CTG is active (Google Ads) where no confirmed local activity is planned.
- PIB POR / Macan BEV in week 2026-04-27: CTG is active (Google Ads, META Inventory Ads) where no confirmed local activity is planned.

### Validate Before Optimisation

- PCGB / Cayenne E3 II in week 2026-04-27: validate local plan data before reallocating; current local activity fields are incomplete.
- PTW / Cayenne E3 II in week 2026-04-27: validate local plan data before reallocating; current local activity fields are incomplete.
- PCGB / Cayenne E3 II in week 2026-05-04: validate local plan data before reallocating; current local activity fields are incomplete.
- PKO / Cayenne E4 in week 2026-05-04: validate local plan data before reallocating; current local activity fields are incomplete.
- PTW / Cayenne E3 II in week 2026-05-04: validate local plan data before reallocating; current local activity fields are incomplete.
- PCGB / Cayenne E3 II in week 2026-05-11: validate local plan data before reallocating; current local activity fields are incomplete.

## Follow-Up Needed

The main governance improvement today is that incomplete local market data now gets flagged rather than silently treated as absence of local activity.

Rows still needing validation:

| Market | Model | Activity | Data Quality | Confidence |
|---|---|---|---|---|
| PTW | Cayenne E3 II | always-on | needs_follow_up | Medium |
| PCGB | Cayenne E3 II | Always on | needs_follow_up | Low |
| PKO | Cayenne E4 | TEST | needs_follow_up | Low |

## Draft Email To Debs

Subject: CTG market activity layer - Day 2 progress

Hi Debs,

Today I tightened the market activity layer so the Intelligence Console is moving from a timeline view into a more explainable optimisation input.

The main improvement is that market and CTG activity are now being translated into common planning language: whether the activity is upper-funnel, lower-funnel, full-funnel, or incomplete. The weekly output now includes a recommended budget direction, a planning bucket, and a plain-English reason for each market/model/week. This means we can explain not just that a market is flagged, but why it should be protected, upweighted, reviewed, or validated before budget moves.

I have also added confidence handling. Incomplete market rows are now flagged as validation items rather than being treated as true gaps. This is important for PCGB-style cases where missing local activity data could otherwise create a misleading CTG opportunity.

Next, I would connect these planning buckets to recent performance so that the final recommendation combines both sides: where the market is active and where the media is actually responding.

Thanks,  
Ali

## Draft Team Message

Day 2 update on CTG market activity: the timeline is now mapped into common planning language and weekly rows have explainable budget directions. The app can now show whether a signal is a scale, protect, fix, reduce, or watch case, plus the plain reason behind it. I also added confidence handling so incomplete market data is not mistaken for a genuine gap.

## Suggested Nico Follow-Up

Hi Nico,

I have now mapped the survey and CTG timeline channels into a common taxonomy so we can use the timeline as a weekly optimisation input.

Could you help validate the remaining incomplete rows, especially where date/channel/budget is missing? The most important point is to avoid treating missing market data as a confirmed absence of market activity.

Thanks,  
Ali
