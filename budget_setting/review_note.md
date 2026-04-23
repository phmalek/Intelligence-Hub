# Review Note: Reverse Funnel Light Budget Logic

## Purpose

This note explains what the current workbook is doing, how that maps to the concerns raised in `comment.md`, and where the logic appears defensible versus where it likely breaks.

It is written to be standalone and self-contained.

## Important file caveat

There is a mismatch between the saved workbook and the description in `comment.md`.

- In the saved file, the `RFL` tab itself appears empty.
- In the saved file, the `Share Of MAL-Budget` tab contains raw lead-level data rather than the summary budget calculations described in the comment.
- The actual summary calculation layer is visible on the `Pivots` tab.
- The `Pivots` tab contains many formulas pointing back to `RFL!D136:P163`, which strongly suggests the live Excel workbook may contain unsaved `RFL` calculations that are not currently present in the file on disk.

Because of that, the analysis below is based on:

- the boss comment in [comment.md](/c:/Users/ali/repos/porsche/budget_setting/comment.md)
- the saved workbook values and formulas visible on the `Pivots` tab
- the supporting summary tabs such as `2026_03_03_OGS`

Despite the tab mismatch, the saved workbook still supports the substance of the boss comment.

## Executive summary

The boss’s concerns are valid.

The current model appears to do three things:

1. It anchors the reverse funnel on `Online Generated Sales` rather than on the broader universe of influenced sales.
2. It calculates upper-funnel budget from impressions and sessions in a way that likely understates the true upper-funnel requirement.
3. It calculates lower-funnel budget as if all required sessions need to be bought by lower-funnel media, while also calculating a separate upper-funnel budget that itself should contribute to sessions. That creates a real risk of double counting.

The result is a model that is internally coherent in a narrow attribution sense, but likely too conservative for upper funnel and conceptually inconsistent when lower and upper funnel budgets are combined.

## What the model is trying to do

At a high level, the workbook is trying to reverse engineer media budget from sales targets.

The intended chain appears to be:

1. Start from a sales target.
2. Convert sales into required online-generated sales.
3. Convert online-generated sales into required DCFS.
4. Convert DCFS into required sessions.
5. Price those sessions using paid-session cost and/or impression cost.
6. Convert the result into lower-funnel and upper-funnel budget requirements.

This is the basic reverse-funnel concept described in the comment.

## Where the key logic sits in the workbook

Although the comment references the `RFL` and `Share Of MAL-Budget` tabs, the saved workbook exposes the most important calculation outputs on the `Pivots` tab.

Key visible references:

- `Pivots` row 6 pulls sales targets from `RFL!D136:P136`
- `Pivots` row 7 pulls focus-model sales targets from `RFL!D137:P137`
- `Pivots` row 8 pulls focus-model shares from `RFL!D138:P138`
- `Pivots` rows 10 to 33 pull most of the reverse-funnel outputs from `RFL!D140:P163`

So even though the saved `RFL` sheet is empty, the workbook structure confirms that the reverse-funnel outputs were intended to flow from `RFL` into `Pivots`.

## Part 1: Why the boss says the model is anchored on OGS

This is the most important conceptual issue.

The model uses `Online Generated Sales` as the base for the reverse funnel, rather than total sales or total influenced sales.

Evidence:

- On `2026_03_03_OGS`, total sales are shown as `Q6 = 85,393`
- On the same tab, OGS are shown as `Q12 = 11,626`
- Therefore `Share of OGS` is `Q14 = 0.13614699097115687`

This means only 13.6% of total sales are being treated as online-generated sales.

That directly matches the boss comment:

`All of the RFL calculations are based on Online Generated Sales – 13.6% of total sales in 2025.`

That interpretation is confirmed again on `Pivots`:

- `Y10 = 12,491.894862576557`
- `Z10 = 0.13614699097115687`
- `Y10 = Y7 * Z10`

In plain English:

- the model starts from focus-model sales target `Y7 = 91,753`
- then multiplies by the OGS share of `13.6%`
- that produces the number of sales it expects to be addressable through the attributable online funnel

This is exactly why your boss says the model is too narrow for upper-funnel planning.

### Why this matters

If upper funnel is supposed to help create demand across the broader sales journey, then anchoring the budget model only on the share of sales that are formally classified as OGS will understate need.

The boss’s reasoning is:

- many sales journeys are influenced by media and by the website even if they do not remain attributable all the way to an OGS outcome
- therefore a reverse funnel built only on OGS measures only the attributable tail, not the full influenced opportunity

That is a fair criticism.

## Part 2: How the model gets from OGS to paid-media-driven sales

The next narrowing step is the paid-media share within OGS.

On `2026_03_03_OGS`:

- `Q20 = 3,579` for `Paid Media`
- `Q21 = 6,787` for `Organic / Direct`
- `Q12 = 11,626` total OGS
- `Q24 = 0.30784448649578533` is the paid-media share of OGS

So the model assumes that only 30.8% of OGS are paid-media-driven.

That is then combined with the OGS share of total sales:

- OGS share of total sales = `Q14 = 13.614699097115687%`
- paid-media share of OGS = `Q24 = 30.784448649578533%`
- paid-media share of total sales = `Q13 = 4.1912100523462115%`

This is visible on `Pivots` as well:

- `Y13 = 0.041912100523462115`

That directly supports the boss comment:

`Within the OGS, 31% are directly attributed to paid media. This means that in total Porsche can attribute 4.2% of car sales to digital paid media.`

That statement is mathematically correct based on the workbook.

## Part 3: The reverse-funnel path visible in the workbook

The model then turns those attributed sales into downstream requirements.

Using the sample-market totals on `Pivots`:

1. Focus sales target
   - `Y7 = 91,753`

2. OGS among those sales
   - `Y10 = 12,491.894862576557`

3. Paid OGS share
   - `Y11 = 3,845.5609593292193`

4. DCFS to sale rate
   - `Y25 = 0.075546174142480216`

5. Required DCFS
   - `Y26 = 101,806.90161957069`

6. Session to DCFS rate
   - `Y28 = 0.0011002933341384732`

7. Required paid sessions
   - `Y29 = 92,527,054.796060577`

8. Cost per paid session
   - `Y17 = 0.5252525252525253`

9. Required lower-funnel budget
   - `Y31 = 48,600,069.185809597`

This is the core lower-funnel reverse-funnel chain.

### Interpretation

This logic is internally coherent if your goal is:

`How much lower-funnel paid media spend is required to produce the paid sessions needed to generate the attributable paid-media sales?`

But that is a much narrower question than:

`How much media investment is required to support overall demand creation and sales delivery?`

That distinction is the heart of the disagreement.

## Part 4: Why the boss says upper funnel is likely undervalued

The upper-funnel logic uses a different route.

Instead of using cost per paid session, it uses impressions and impression cost.

On `Pivots`:

- `Y46 = 3,442,898,678.7` impressions in 2025
- `Y47 = 14,378,777.610363638` cost for those impressions
- `Y52 = 141,785,103` total sessions
- `Y54 = 24.282513507078384` average impressions per session
- `Y56 = 0.004176358049488957` average cost per impression

Then it applies those ratios to future required sessions:

- `AN41 = 188,827,993.2551035` required sessions
- `AN44 = 24.282513507078384` required impressions per session
- `AN46 = 4,585,218,296.7315569` required impressions
- `AN45 = 0.004176358049488957` cost per impression
- `AN47 = 19,149,513.342218883` required budget for highlight activations

So the model’s upper-funnel budget requirement is approximately `19.15m`.

### Why the boss questions this

The boss comment argues that this upper-funnel output is too low because:

1. It is based only on the sessions required by the attributable online funnel.
2. It excludes the effect of non-digital media that may also be driving website sessions.
3. It may be understating the impression pool or misclassifying what counts as upper funnel.

The workbook supports those concerns.

### The specific “16%” intuition

If you compare upper-funnel budget to total required budget in the forecast case:

- Upper funnel = `AN47 = 19.15m`
- Total required budget = `AN48 = 123.34m`
- So upper funnel is about `15.5%` of required budget

That is presumably the basis of the boss’s “16% of media budget” concern.

In formula terms:

- `AN48 = AN43 + AN47`
- where `AN43` is always-on lower funnel
- and `AN47` is upper funnel / highlight

So the boss is not wrong: the model is effectively producing an upper-funnel share around the mid-teens relative to the recommended spend stack.

### Another way the workbook expresses this

As a share of the estimated total MAL budget:

- `AN52 = 360.246m` estimated MAL budget
- `AN54 = 5.3156767995466571%` share of MAL budget for highlight

That is even smaller.

So regardless of which denominator is used, upper funnel comes out low.

## Part 5: What rows 46, 47 and 52 are doing

The boss specifically references these mechanics in the comment. That interpretation is correct.

### Row 46: upper-funnel-like impressions base

`Pivots` row 46 contains the 2025 impression volumes used in the calculation.

- total sample = `Y46 = 3.4429bn`

This is the numerator for impressions per session.

### Row 47: corresponding costs

`Pivots` row 47 contains the cost associated with those impressions.

- total sample = `Y47 = 14.3788m`

This is the numerator for cost per impression.

### Row 52: total sessions

`Pivots` row 52 combines:

- paid media sessions `Y50 = 43,056,700`
- organic/direct sessions `Y51 = 98,728,403`
- total sessions `Y52 = 141,785,103`

That directly matches the boss comment that the model considers paid media plus organic/direct sessions in the upper-funnel logic.

### What this means

The workbook is effectively saying:

- upper funnel drives all site sessions
- therefore we can estimate upper-funnel requirement from impressions per session and cost per impression

This logic is not unreasonable on its own.

The problem is what happens when it is combined with the lower-funnel logic.

## Part 6: Why the boss says lower funnel is overstated

This is the strongest technical criticism in the note.

The model calculates lower funnel as if all required sessions needed for DCFS are lower-funnel paid sessions.

Evidence:

- required DCFS: `Y26 = 101,806.90161957069`
- session-to-DCFS rate: `Y28 = 0.0011002933341384732`
- therefore required paid sessions: `Y29 = 92,527,054.796060577`
- priced at cost per paid session `Y17 = 0.5252525252525253`
- giving lower-funnel required budget `Y31 = 48.60m`

The issue is that upper-funnel media also drives sessions.

The workbook separately assumes that upper funnel drives total sessions, then prices an upper-funnel budget on top.

So the model is doing both of these:

1. charging lower funnel for all session needs required for DCFS
2. charging upper funnel based on total session generation logic

That is exactly why your boss says:

`the always-on budget is inflated as it assumes that all sessions needed to deliver DCFS would be lower funnel`

That criticism is well supported by the workbook.

## Part 7: Why the boss says there is double counting

This follows directly from the point above.

The lower-funnel budget is based on paid sessions.
The upper-funnel budget is based on impressions that are assumed to drive sessions.

If the same eventual session outcomes are being funded once through lower-funnel CPS and again through upper-funnel impressions, then the combined budget stack is not cleanly partitioned.

In other words, the model needs a clear answer to this question:

`Which sessions are caused by upper funnel, and which sessions still need to be bought by lower funnel?`

Right now the structure suggests:

- lower funnel is credited with all required sessions for DCFS
- upper funnel is also priced off session generation mechanics

That is not clean separation.

This is why the boss writes:

`I also feel that we are double-counting paid media sessions – as the cost of media is in both the upper and the lower budget calculations. There should be a clear way of differentiating within the model.`

That statement is justified.

## Part 8: Which parts of the model are defensible

Not everything in the workbook is wrong.

The following ideas are methodologically reasonable:

### 1. Starting from targets and back-solving requirements

This is a sound planning approach.

If you know the target sales volume and the conversion chain, then back-solving the required lead and session volume is a valid framework.

### 2. Using observed rates rather than arbitrary assumptions

The model uses actual observed ratios such as:

- OGS share
- paid-media share of OGS
- DCFS to sale rate
- session to DCFS rate
- impressions per session
- CPI and CPS

That is better than purely assumption-driven planning.

### 3. Separating session-based and impression-based planning concepts

There is value in distinguishing:

- lower-funnel efficiency economics via CPS
- upper-funnel reach economics via CPI and impression/session relationships

Conceptually, that is the right direction.

## Part 9: Where the model likely breaks

These are the most important weaknesses.

### 1. It confuses attributable sales with influenced sales

This is the biggest issue.

Upper funnel should not usually be sized only to the share of sales that remain attributable as OGS.

That creates an artificially low demand base.

### 2. It does not clearly distinguish session ownership between funnels

If upper funnel generates some sessions, lower funnel should not be budgeted as if it must buy them all.

### 3. It likely understates non-digital drivers of sessions

The boss notes that offline media also contributes to website demand, but the impression base only captures tracked digital impressions.

If true, then the impression-to-session ratio is incomplete and could bias the upper-funnel estimate downwards.

### 4. The split of upper-funnel impressions and costs may need checking

The boss specifically flags:

- total impressions served in GB in 2025: around `731m`
- total cost around `4.5m`
- PWC upper-funnel slice used in the workbook: around `318m` impressions and `1m` cost

That is exactly the kind of ratio check that should be validated. If the impression classification or cost allocation is off, upper-funnel budget will be distorted.

### 5. The model does not represent synergy between upper and lower funnel

The boss’s point is strategically correct:

- upper funnel does not just create sessions directly
- it can also increase the efficiency of lower-funnel conversion

The current structure is too linear to capture that.

## Part 10: A simple way to explain the disagreement to stakeholders

The cleanest way to explain the issue is:

`The model is valid as an attribution-based media efficiency model, but not yet as a full-funnel commercial investment model.`

Why:

- it measures the attributable online path well enough
- but it underscopes the broader role of upper funnel in creating demand and improving lower-funnel effectiveness

That distinction is important because it avoids saying the whole model is wrong.
It is more precise to say the model is answering a narrower question than the business actually needs.

## Part 11: Recommended challenge points back to PWC

These are the strongest challenge points to raise.

### 1. Clarify the base sales universe

Ask:

`Why is upper-funnel need being anchored on OGS rather than on all sales journeys influenced by media and/or web touchpoints?`

This is the central challenge.

### 2. Separate session contribution by funnel

Ask:

`How does the model avoid charging lower funnel for sessions that are generated by upper-funnel activity?`

This addresses the inflation / double-counting issue directly.

### 3. Validate the upper-funnel impression and cost base

Ask:

`Which channels, placements and costs are included in row 46 and row 47, and what was excluded as lower funnel?`

This is especially important because upper-funnel budget is very sensitive to:

- impressions per session
- cost per impression

### 4. Adjust for offline contribution

Ask:

`How is offline media’s contribution to sessions handled if the impression base only captures digital?`

Without an adjustment, upper funnel is likely understated.

### 5. Clarify whether the objective is attribution planning or total commercial planning

Ask:

`Is this model intended to budget the attributable digital funnel only, or to inform total full-funnel media investment?`

If the latter, then the current logic is too narrow.

## Part 12: Bottom-line judgement

Bottom line:

- The boss has correctly understood the model’s logic.
- The boss is correct that the model is anchored on OGS and therefore likely underestimates upper-funnel need.
- The boss is correct that the current lower-funnel logic appears to over-allocate session generation to always-on paid media.
- The boss is correct that the model structure creates a real risk of double counting between upper-funnel and lower-funnel media.

My overall assessment is:

`The current workbook is analytically tidy but commercially incomplete.`

It appears fit for:

- reverse engineering attributable digital performance
- producing a narrow efficiency-based budget recommendation

It does not yet appear fit for:

- setting a robust full-funnel upper-funnel budget
- cleanly partitioning the role of upper versus lower funnel
- reflecting the broader influence of media beyond the attributable online sales path

## Appendix: Key workbook numbers referenced

From `2026_03_03_OGS`:

- total sales: `Q6 = 85,393`
- OGS: `Q12 = 11,626`
- OGS share: `Q14 = 13.614699097115687%`
- paid media OGS: `Q20 = 3,579`
- paid media share of OGS: `Q24 = 30.784448649578533%`

From `Pivots`:

- paid media share of total sales: `Y13 = 4.1912100523462115%`
- focus sales target: `Y7 = 91,753`
- OGS sales implied: `Y10 = 12,491.894862576557`
- paid OGS implied: `Y11 = 3,845.5609593292193`
- required DCFS: `Y26 = 101,806.90161957069`
- required paid sessions: `Y29 = 92,527,054.796060577`
- lower-funnel required budget: `Y31 = 48,600,069.185809597`
- 2025 impressions base: `Y46 = 3,442,898,678.7`
- 2025 cost base: `Y47 = 14,378,777.610363638`
- total sessions base: `Y52 = 141,785,103`
- average impressions per session: `Y54 = 24.282513507078384`
- average cost per impression: `Y56 = 0.004176358049488957`
- upper-funnel budget: `AN47 = 19,149,513.342218883`
- total required budget: `AN48 = 123,343,635.94685405`
