# Taxonomy Hygiene Analysis: Instruction and Methodology

## Purpose

This work is a **taxonomy hygiene and governance analysis** for Porsche / Omnicom PlanIT taxonomy.

It is **not** a traditional reporting exercise.

The purpose is to produce an instruction back to the PlanIT / taxonomy owners on what should be:

- kept
- removed
- restricted
- added
- made conditional
- flagged as missing from the current taxonomy structure

The goal is to make the available dropdown values in PlanIT:

- tighter
- more relevant
- more channel-aware
- more useful for reporting
- more useful for modelling
- more useful for governance

## Business problem

The current taxonomy contains:

- overly long option lists
- values that are irrelevant to the channel context
- dimensions applied globally even where they should only apply to specific channels
- placeholder and workaround values that weaken data quality

This creates:

- poor governance
- inconsistent user selection
- weak downstream reporting
- avoidable clean-up effort
- reduced analytical value for modelling and intelligence work

## Core framing

This analysis must be treated as **taxonomy governance design**, not descriptive reporting.

That means:

- do not just summarise value counts
- do not just state what exists
- evaluate what should exist
- identify what should not exist
- identify what is missing
- propose validation logic
- separate current-state feasible changes from future-state redesign

## Key interpretation rules

### 1. Clean input, flexible reporting

Selectable taxonomy values should be:

- specific
- meaningful
- mutually understandable
- channel-relevant
- useful downstream for reporting and modelling

Values such as:

- `Mixed`
- `Not used`
- `Other`
- `Unknown`
- `N/A`
- blank-like placeholders

should be treated as **invalid input taxonomy values by default**, unless there is strong evidence that they are intentionally required for governance.

In most cases, these should be recommended as:

- reporting-only derived states
- data quality flags
- aggregation placeholders

not selectable inputs.

### 2. Workarounds are design smells

Whenever a field or value exists mainly because the current taxonomy design forced users into a bad workaround, it should **not** be treated as legitimate business structure.

It should be explicitly flagged as a **design smell**.

### 3. Channel-specific logic matters

Dimensions should be assessed for whether they are truly relevant to:

- Search
- Social
- Programmatic
- Display
- Inventory ads
- Video
- CTV
- other relevant media types

Examples:

- `Match Type` should usually be Search-only
- `Keyword Type / Messaging` should usually be Search-only
- audience or targeting-source logic is more relevant for Social and Programmatic
- buying-platform options should depend on channel / sub-channel

### 4. Fewer values is generally better, if governance is preserved

Shorter dropdowns are preferred, but values should not be removed blindly.

For every value or dimension considered for removal or consolidation, assess:

- is it unused or weakly used?
- is it rare but strategically important?
- is it redundant?
- is it better represented in another field?
- is it better collapsed into a higher-level category?

### 5. Missing dimensions matter as much as bad ones

Some business concepts may matter operationally and analytically but are not cleanly captured in the taxonomy.

Examples may include:

- audience source
- targeting source
- targeting method
- Tealium / CDP usage
- funnel stage
- creative or message family
- format family
- inventory logic

These should be recommended as:

- new dimensions
- revised dimensions
- future-state improvements

### 6. Respect current-state vs future-state

Recommendations must be split into:

#### Current-state feasible

Changes likely possible without major structural breakage, such as:

- removing bad values
- restricting dropdowns
- adding missing values
- clarifying names
- making fields conditional
- preventing reporting placeholders from being selectable

#### Future-state structural

Larger redesign ideas, such as:

- different taxonomies by channel
- revised hierarchy across planning levels
- moving dimensions to different object levels
- deeper redesign of mapping logic

## Diagnostic lenses

All dimensions and values should be assessed through these lenses:

1. Relevance
2. Specificity
3. Mutual exclusivity
4. Downstream analytical value
5. Operational usability
6. Governance enforceability
7. Historical compatibility

## Patterns to flag aggressively

The following should be treated critically:

1. Placeholder or fallback values:
   - `Mixed`
   - `Not used`
   - `Unknown`
   - `Other`
   - `N/A`
   - blank-like placeholders

2. Search-specific fields appearing across non-search channels

3. Social / targeting concepts not being captured properly

4. Long dropdowns with weakly differentiated values

5. Multiple values that are effectively synonyms

6. Fields that appear mandatory but are not meaningful in some channels

7. Places where users are likely forced to select nonsense values just to complete workflow

8. Fields that try to capture multiple concepts in one place

9. Granularity that does not match real platform decision-making

## Required output structure

The analysis should be presented in this order:

1. Executive Summary
2. Main Findings
3. Dimension Review Table
4. Value Review Table
5. Proposed Validation Rules
6. Missing Dimensions / Additions
7. Current-State Recommendations
8. Future-State Recommendations
9. Stakeholder Questions / Sign-off Needs
10. Appendices

## Output style

The output should be:

- precise
- practical
- highly structured
- recommendation-led
- explicit about uncertainty where evidence is weak

It should not be fluffy and should not just restate the data.

## Data source used in the app page

The current app page implementation uses:

- workbook: `Copy of VWG Taxonomy Output v1.3 8 Apr 2026 11 30 07.xlsx`
- tab: `Taxonomy Outputs`

If additional tabs or external mappings are later required, the analysis should be expanded with those sources explicitly.
