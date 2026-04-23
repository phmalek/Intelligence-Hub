# Budget Setting Sankey: Design Note

## Objective

Create a defensible Sankey-style budget flow for discussion with stakeholders.

This is not intended to claim final budget shares.
It is intended to show the correct **decision logic** and where the current model needs adjustment.

## Core flow

1. Start with total budget envelope
2. Split into:
   - `Always On / Core`
   - `Highlight Activations`
3. Classify `Highlight Activations` into:
   - `Upper Funnel Highlight`
   - `Lower Funnel Highlight`

## Key logic to show

- `Highlight` is not the same thing as `Upper Funnel`
- launch activity can contain both upper- and lower-funnel components
- current highlight logic starts from digital impressions needed to drive sessions
- that baseline should be adjusted upward for:
  - offline / non-digital contribution to sessions
  - broader sales influence beyond OGS / website-touch journeys
- highlight activity should also be credited for session / click contribution that reduces the burden on Always On lower funnel
- non-trackable allocation remains a sensitivity assumption and should be shown as such

## Fixed factors from current discussion

- offline / non-digital upweight reference: `18.7%` of 2025 Tier 1 investment
- OGS reference: `13.6%` of total sales in 2025

## Intent of the diagram

The diagram should make four points clearly:

1. budget should not be split into `Always On` vs `Highlight` and then assume highlight is purely upper funnel
2. highlight needs a second classification into upper vs lower funnel
3. current sessions/impressions logic likely understates highlight because it excludes offline and non-website influence
4. highlight should receive credit for helping generate sessions that would otherwise be attributed entirely to Always On
