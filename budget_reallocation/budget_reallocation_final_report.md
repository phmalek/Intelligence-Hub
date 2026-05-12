# Budget Reallocation - Final Workflow Output

## What This Adds

This completes the practical workflow after the market activity layer:

1. Observe recent market performance.
2. Classify each market/model into plain planning buckets.
3. Overlay known market activity.
4. Recommend whether to increase, protect, test, fix, watch, or reduce budget.

The point is explainability. The recommendation does not say "score = 78"; it says why a strategist should move or hold budget.

## Final Budget Action Counts

| Action | Market/model rows |
|---|---:|
| Fix | 14 |
| Test | 10 |
| Increase | 3 |
| Watch | 3 |
| Protect | 2 |
| Reduce | 2 |

## Increase Candidates

- Increase PIB POR / Macan: observed performance is strong enough to support more pressure, and the activity layer shows ctg filling local gap.
- Increase PIT / Macan: observed performance is strong enough to support more pressure, and the activity layer shows harvest local upper-funnel demand.
- Increase TRK / Macan: observed performance is strong enough to support more pressure, and the activity layer shows harvest local upper-funnel demand.

## Protect Candidates

- Protect CZ / Macan: keep budget stable because performance or activity context supports presence, but not a large increase.
- Protect PCNA / Cayenne: keep budget stable because performance or activity context supports presence, but not a large increase.

## Test Candidates

- Test PBR / Cayenne: local activity is visible but CTG has whitespace, so use a controlled test rather than a large shift.
- Test PBR / Macan: local activity is visible but CTG has whitespace, so use a controlled test rather than a large shift.
- Test PCH / Cayenne: local activity is visible but CTG has whitespace, so use a controlled test rather than a large shift.
- Test PCNA / Macan: local activity is visible but CTG has whitespace, so use a controlled test rather than a large shift.
- Test PIB POR / Cayenne: local activity is visible but CTG has whitespace, so use a controlled test rather than a large shift.
- Test PKO / Macan: local activity is visible but CTG has whitespace, so use a controlled test rather than a large shift.
- Test PNO / Cayenne: local activity is visible but CTG has whitespace, so use a controlled test rather than a large shift.
- Test POF / Cayenne: local activity is visible but CTG has whitespace, so use a controlled test rather than a large shift.

## Fix Candidates

- Fix PCA / Cayenne: there is some opportunity, but performance needs channel, creative, or conversion work before scaling.
- Fix PCA / Macan: there is some opportunity, but performance needs channel, creative, or conversion work before scaling.
- Fix PCGB / Macan: there is some opportunity, but performance needs channel, creative, or conversion work before scaling.
- Fix PCL / Cayenne: there is some opportunity, but performance needs channel, creative, or conversion work before scaling.
- Fix PCL / Macan: there is some opportunity, but performance needs channel, creative, or conversion work before scaling.
- Fix PD / Cayenne: there is some opportunity, but performance needs channel, creative, or conversion work before scaling.
- Fix PD / Macan: there is some opportunity, but performance needs channel, creative, or conversion work before scaling.
- Fix PIB SPA / Cayenne: there is some opportunity, but performance needs channel, creative, or conversion work before scaling.

## Watch Candidates

- Watch PCGB / Cayenne: validate the activity or performance evidence before making a budget move.
- Watch PKO / Cayenne: validate the activity or performance evidence before making a budget move.
- Watch PTW / Cayenne: validate the activity or performance evidence before making a budget move.

## Reduce Candidates

- Reduce GREC / Macan: recent spend is not producing enough dealer response and the activity layer does not show a strong reason to protect CTG.
- Reduce PCH / Macan: recent spend is not producing enough dealer response and the activity layer does not show a strong reason to protect CTG.

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
