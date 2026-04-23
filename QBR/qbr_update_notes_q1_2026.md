# QBR Update Notes: Q1 2026

## Scope

This note is written to be transferred into [Porsche QBR_21st April 2026.pptx](/c:/Users/ali/repos/porsche/QBR/Porsche%20QBR_21st%20April%202026.pptx).

It does **not** update the deck directly.

It gives:

- recommended traffic-light status for relevant projects
- transfer-ready slide copy in the same `Goal / Current Status / Next Steps` structure
- two draft data-expansion slides for the `slides 31 / 32` request

## Important note on the deck version

The local `.pptx` currently contains **9 actual slides** only.

The colleague note referring to `slides 31, 32` appears to relate to a longer or newer version of the deck. For now, the two extra data-slide drafts are included below as additional content blocks that can be inserted wherever needed.

---

## 1. Traffic Light Board: Recommended Updates

Use these statuses on slide 1.

| Topic | Recommended Status | Why |
|---|---|---|
| Budget Setting Guidelines | Amber | Good progress and clearer shared understanding with PWC, but the model still needs challenge and refinement before it is stable enough for market use. |
| UTMs | Amber | Rollout is live across most markets and enablement has been delivered, but platform-level green-light status is still uneven and automated audit is still being scoped. |
| Clean & Accurate Data | Amber | Compliance is improving and weekly audit distribution is running, but campaign and placement quality is not yet at target and remediation is still in progress. |
| Taxonomy Hygiene Audit | Amber | Governance methodology and first-pass analysis are in place, but recommendation set and sign-off logic are still being developed. |
| CTG Reporting Automation | Amber | Briefing and automation scoping are underway, but no completed production solution yet. |
| Quarterly Business Review | Green | Deck structure now exists and Q1 content can be populated; this cadence is now established. |

---

## 2. Slide-Ready Copy

## Slide 2: Budget Setting Guidelines

### Recommended traffic light

Amber

### Goal

Strengthen budget-setting logic so that market planning is explicit, evidence-led, and easier to explain across `Always On`, `Highlight`, and funnel roles.

### Current Status

- Several working sessions with PWC completed.
- Main issue now appears to be interpretation and classification rather than the entire reverse-funnel logic being fundamentally wrong.
- Key clarification: `Highlight` should not automatically be treated as equivalent to `Upper Funnel`.
- Initial challenge points have been documented around:
  - OGS-led planning base being too narrow for full-funnel planning
  - potential overlap between upper- and lower-funnel session logic
  - platform-level upper-funnel weighting assumptions being too coarse
- A Sankey-style decision layer has been added in the app to make the budget split and funnel interpretation more explicit.

### Next Steps

- Align internal view on how `Highlight`, `Always On`, `Upper Funnel`, and `Lower Funnel` should be classified.
- Use the Sankey decision layer as a translation tool on top of the reverse funnel, not as a replacement for the workbook.
- Request underlying PWC notebooks / logic where needed to complete a fuller technical assessment.
- Convert the agreed logic into a market-ready planning view once assumptions are locked.

### Optional one-line update for the slide

`Q1 focused on clarifying the reverse-funnel interpretation and making budget-allocation assumptions more explicit; further refinement is now needed before wider rollout.`

---

## Slide 6: UTMs

### Recommended traffic light

Amber

### Goal

Ensure all relevant campaigns are live with the new UTM framework and that rollout status can be tracked clearly by market and platform.

### Current Status

- New UTM framework is live across the majority of markets.
- Jan / Feb manual audit completed.
- Five enablement sessions delivered for PHD markets.
- Two enablement sessions supported with Porsche local offices.
- A market/platform status view has been built to show where there is explicit green-light confirmation.
- Current explicit platform-level green lights confirmed from source material:
  - France: `Google`, `Meta`
  - MENA: scoped correctly due to no active PME campaigns

### Next Steps

- Move from manual monitoring to a more systematic audit process.
- Continue market follow-up to confirm exact platform readiness, not just market-level status.
- Keep `green light` classification strict and evidence-based.
- Expand client-facing status reporting with clearer `ready / in progress / blocked` states by market.

### Optional one-line update for the slide

`UTM rollout is now live across most markets, with manual audit and enablement completed in Q1; focus now shifts to tighter monitoring and explicit market/platform readiness tracking.`

---

## Slide 6: Clean & Accurate Data

### Recommended traffic light

Amber

### Goal

Deliver clean and accurate media data end to end, with consistent campaign and placement compliance and clearer visibility of issues requiring remediation.

### Current Status

- Weekly audit output continues to be distributed to PHD Global and local markets.
- Campaign spend compliance is at `91.3%`.
- Placement spend compliance is at `94.3%`.
- Campaign compliance is at `100%` except for MENA and Taiwan, which are currently reducing the average.
- Remediation work is in progress.
- An Intelligence Console is live in the app to make the data more usable, including:
  - filterable views by market, model, channel, platform, and activation group
  - KPI and trend views
  - efficiency headroom analysis
  - exportable reporting tables

### Next Steps

- Close remaining remediation gaps, especially where campaign or placement quality is still dragging compliance below target.
- Improve translation from audit output into usable decision-support views for markets and PAG.
- Continue maturing the Intelligence Console as the working layer for data review, issue visibility, and performance interrogation.

### Optional one-line update for the slide

`Q1 combined weekly audit discipline with a first working intelligence layer, improving visibility of data quality, performance, and remediation needs.`

---

## Slide 7: Taxonomy Hygiene Audit

### Recommended traffic light

Amber

### Goal

Improve taxonomy quality, consistency, and governance so PlanIT inputs become tighter, more relevant, more channel-aware, and more useful for reporting and modelling.

### Current Status

- Taxonomy hygiene has been framed as a governance-design task rather than a reporting exercise.
- First analysis layer has been built in the app using the `Taxonomy Outputs` sheet.
- Current methodology focuses on:
  - removing or restricting placeholder values such as `Mixed`, `Other`, `Not used`, `Unknown`, `N/A`
  - treating workaround-driven values as design smells rather than legitimate structure
  - pushing more channel-specific validation logic
  - identifying missing dimensions and over-generic fields
- Initial output structure now includes:
  - executive summary
  - main findings
  - dimension review
  - value review
  - proposed validation rules
  - missing-dimension view
  - current-state vs future-state recommendations

### Next Steps

- Tighten the implemented rule set into explicit, dashboard-ready hygiene checks.
- Review logic with wider team and collect additional business rules.
- Convert agreed rules into a cleaner implementation tracker and dashboard logic.
- Separate current-state feasible changes from future-state redesign for PlanIT owners.

### Optional one-line update for the slide

`Q1 established the taxonomy hygiene framework and first analysis layer; next step is to convert this into explicit rules and owner-ready recommendations.`

---

## Slide 7: CTG Reporting Automation

### Recommended traffic light

Amber

### Goal

Automate CTG tracking and reporting workflows to reduce manual handling, improve consistency, and speed up campaign reporting.

### Current Status

- CTG campaign briefing is in progress.
- Automation brief has been received by Credera.
- Review of campaign brief and automated reporting / tracking approach is underway.

### Next Steps

- Finalise scope between business need and reporting logic.
- Confirm which outputs should become operational dashboards vs periodic exports.
- Move from briefing into implementation planning once the logic and ownership are locked.

### Optional one-line update for the slide

`CTG automation moved from idea to scoped brief in Q1; the next phase is translating that brief into a concrete reporting and workflow solution.`

---

## Slide 9: Quarterly Business Review

### Recommended traffic light

Green

### Goal

Use the QBR as the structured quarterly forum to review progress, surface issues, align on priorities, and set the next-quarter outlook across the media governance agenda.

### Current Status

- QBR cadence is now established.
- Q1 deck can now reflect tangible progress across UTM rollout, data quality, taxonomy hygiene, budget setting, and governance tooling.
- Content is now strong enough to show both delivery progress and where more alignment is still needed.

### Next Steps

- Use the QBR not just as a status deck, but as a working governance checkpoint.
- Keep the top slide as a genuine traffic-light summary and use project slides to show the operational detail.
- Expand data slides in future versions so progress is visible both at initiative level and at operational-detail level.

### Optional one-line update for the slide

`This QBR now serves as the quarterly governance checkpoint across rollout, data quality, taxonomy, and planning logic, rather than a simple status review.`

---

## 3. Draft Additional Data Slides

These are the two draft `data slides` that can be inserted later if the longer deck version is used.

## Draft Slide 31: Data Foundation Progress

### Slide title

`DATA FOUNDATION PROGRESS`

### Suggested subtitle

`Q1 2026 focused on making media data more compliant, more visible, and more usable for governance and decision-making`

### Left block: UTM rollout

**Headline**

`UTM rollout now live across most markets`

**Body**

- Manual Jan / Feb audit completed
- 5 PHD enablement sessions delivered
- 2 Porsche local enablement sessions supported
- Platform-level green-light status now being tracked explicitly

### Middle block: Clean & accurate data

**Headline**

`Audit discipline now paired with operational visibility`

**Body**

- Weekly audit output distributed to global and local teams
- Campaign spend compliance: `91.3%`
- Placement spend compliance: `94.3%`
- Remediation still required in selected markets

### Right block: Intelligence layer

**Headline**

`First working intelligence layer now live`

**Body**

- Filterable by market, model, channel, platform, activation group
- KPI and trend views available
- Headroom analysis added for efficiency review
- Export tables available for working use

### Footer line

`Q2 focus: close remediation gaps, reduce manual monitoring, and improve decision-usefulness of the data layer.`

---

## Draft Slide 32: Governance Logic and Planning Layer

### Slide title

`GOVERNANCE LOGIC AND PLANNING LAYER`

### Suggested subtitle

`Q1 moved several workstreams from raw reporting into more explicit governance and decision-support logic`

### Left block: Taxonomy hygiene

**Headline**

`Taxonomy work reframed as governance design`

**Body**

- Focus shifted from describing taxonomy to improving it
- Placeholder values treated critically
- Channel-specific validation logic prioritised
- Current-state and future-state changes separated

### Middle block: Budget setting

**Headline**

`Budget-setting debate now clearer and more explicit`

**Body**

- Main issue is now classification and interpretation, not just model error
- `Highlight` and `Upper Funnel` need to be treated separately
- Key assumptions have been surfaced for challenge and planning discussion
- Decision layer created to make budget logic easier to explain

### Right block: Why this matters

**Headline**

`Shift from reporting outputs to controlled logic`

**Body**

- Better governance
- Cleaner planning inputs
- More transparent decision-making
- Stronger basis for market rollout

### Footer line

`Q2 focus: convert the current logic into owner-ready rules, cleaner market guidance, and more stable dashboard implementation.`

---

## 4. Optional Speaker Framing

If you want a consistent verbal line across these slides:

`Q1 was less about launching entirely new workstreams and more about making several existing ones usable: clearer rollout status on UTMs, tighter control over data quality, a more governance-led taxonomy view, and a more explicit planning layer around budget setting.`
