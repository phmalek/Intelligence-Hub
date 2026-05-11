# CTG Market Activity Integration - Day 1 Output

## What Was Delivered Today

- Converted Nico's market activity workbook into three machine-readable interim files:
  - `market_activities/local_activity_normalized.csv`
  - `market_activities/ctg_timeline_normalized.csv`
  - `market_activities/market_activity_weekly_signals.csv`
- Added a first `CTG Market Activity` page to the Intelligence Console.
- Built the first weekly decision signals for gap-filling, harvesting, duplication checks, and potential CTG whitespace.

## Initial Findings

- Local survey coverage currently contains **64 activity rows** across **17 markets**.
- **61 rows** have enough date/channel detail to use directly in weekly optimisation.
- **3 rows** need follow-up before they should influence decisions.
- CTG planning contributes **131 market/model/channel timeline rows** from the `Media Mix` / `Zeitstrahl` logic.
- The weekly signal layer currently contains **1516 market-model-week rows**.

## Decision Signal Counts

| Signal | Rows |
|---|---:|
| Potential CTG whitespace | 832 |
| CTG filling local gap | 296 |
| Harvest local upper-funnel demand | 284 |
| Coordinated support | 58 |
| Validate data before optimisation | 46 |

## Interesting Examples To Discuss

### CTG Filling Local Gaps

- PCA / Cayenne E3 II / week 2026-04-27: CTG `META Inventory Ads`, local `none`
- PCA / Cayenne E4 / week 2026-04-27: CTG `Google Ads`, local `none`
- PCGB / Cayenne E4 / week 2026-04-27: CTG `Google Ads`, local `none`
- PCGB / Macan BEV / week 2026-04-27: CTG `Google Ads, Google Inventory Ads, META Inventory Ads`, local `none`
- PIB POR / Cayenne E4 / week 2026-04-27: CTG `Google Ads`, local `none`
- PIB POR / Macan BEV / week 2026-04-27: CTG `Google Ads, META Inventory Ads`, local `none`
- PIT / Cayenne E3 II / week 2026-04-27: CTG `Google Ads, META Inventory Ads`, local `none`
- PKO / Cayenne E3 II / week 2026-04-27: CTG `Google Ads, Google Inventory Ads, META Inventory Ads`, local `none`

### Harvesting Local Upper-Funnel Demand

- PCA / Macan BEV / week 2026-04-27: CTG `Google Ads, META Inventory Ads`, local `Programmatic`
- PCL / Cayenne E3 II / week 2026-04-27: CTG `Google Ads, Google Inventory Ads, META Inventory Ads`, local `Programmatic, Search, Social`
- PCL / Cayenne E4 / week 2026-04-27: CTG `Google Ads`, local `CTV, DOOH, Other Online Channel, Programmatic, Search, Social`
- PCL / Macan BEV / week 2026-04-27: CTG `Google Ads, Google Inventory Ads, META Inventory Ads`, local `Programmatic, Search, Social`
- PD / Cayenne E3 II / week 2026-04-27: CTG `Google Ads, META Inventory Ads`, local `Programmatic, Search`
- PD / Cayenne E4 / week 2026-04-27: CTG `Google Ads`, local `Programmatic, Search`
- PD / Macan BEV / week 2026-04-27: CTG `Google Ads, META Inventory Ads`, local `Programmatic, Search, Social`
- PIB SPA / Cayenne E4 / week 2026-04-27: CTG `Google Ads`, local `CTV, Other Online Channel, Programmatic, Search, Social, YouTube`

### Duplication Checks

- None identified in current cut.

## Data Quality Notes

- `PCGB` is not yet usable as a local activity input: the survey row has no start date, end date, channel, budget, or KPI.
- Market channels need normalization before final scoring. Examples include `SEM`, `SEA`, `YouTube & CTV`, `Other Online Channel`, and marketplace-specific entries.
- Budgets are not yet comparable because they mix currencies and free text (`200K`, `CHF 380'000.-`, etc.). Day 1 uses presence/timing/channel signals, not budget weighting.
- `Zeitstrahl nach Markt` is the right planning view for stakeholders; the app should use a structured weekly version of it underneath.

## Draft Email To Debs

Subject: CTG market activity layer - Day 1 progress

Hi Debs,

I have started turning Nico's market activity timeline into a structured optimisation layer for the Intelligence Console.

The first version now converts the workbook into weekly market/model signals showing where CTG is filling local gaps, where we can harvest demand from local upper-funnel activity, and where we need to check for duplication before upweighting. I have also added a separate CTG Market Activity page in the app so this stays clean and does not interfere with the existing optimisation views.

The main Day 1 finding is that the data is already good enough to drive directional weekly recommendations, especially from the timeline view, but some fields still need clean-up before we should weight budget decisions from it. PCGB is the clearest missing market data point at the moment.

Tomorrow I will tighten the channel taxonomy and connect these market activity signals more directly to the weekly optimisation logic.

Thanks,  
Ali

## Draft Team Message

Quick update on the CTG market activity work: I have converted Nico's timeline into a first weekly signal layer for the Intelligence Console. It now flags where CTG fills a local market gap, where CTG search/inventory can harvest demand from local upper-funnel activity, and where there is a possible duplication risk. First app page is in place under `CTG Market Activity`; next step is channel taxonomy clean-up and tying the signals into optimisation priority.

## Suggested Nico Follow-Up

Hi Nico,

I have started using the `Zeitstrahl nach Markt` view as the basis for a weekly optimisation overlay in the Intelligence Console.

The structure is useful. The main thing I need next is completion/validation for missing or partial market rows, especially PCGB, plus confirmation that the channel labels in the survey can be grouped into search, social, programmatic, video/CTV, and other local channels for optimisation purposes.

Thanks,  
Ali
