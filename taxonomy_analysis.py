from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


PLACEHOLDER_VALUES = {
    "",
    "-",
    "mixed",
    "not used",
    "other",
    "unknown",
    "n/a",
    "na",
    "null",
    "none",
}

DESIGN_SMELL_TOKENS = [
    "string only",
    "mixed",
    "not used",
    "other",
]


@dataclass(frozen=True)
class DimensionConfig:
    description: str
    applies_to: str
    current_or_future_default: str = "Current-State"


DIMENSION_CONFIG: dict[str, DimensionConfig] = {
    "Channel": DimensionConfig("Primary media channel", "All"),
    "Sub Channel": DimensionConfig("More specific channel routing beneath Channel", "All"),
    "Local Channel": DimensionConfig("Operational channel grouping used by local planning teams", "All"),
    "Local Channel TACT": DimensionConfig("Template-driven local tactical routing label", "All"),
    "Reporting Channel": DimensionConfig("Reporting-facing rollup of channel behavior", "All"),
    "Buying Platform": DimensionConfig("Execution platform used to buy media", "All"),
    "Buying Tactic": DimensionConfig("Broad buying mechanism such as programmatic vs non-programmatic", "All"),
    "Buying Mode": DimensionConfig("Inventory trading mode", "Display, iVideo, CTV, Programmatic"),
    "Planning Principle": DimensionConfig("Planning/funnel principle intended to guide setup", "All"),
    "KPI Objective": DimensionConfig("Primary outcome objective", "All"),
    "Format": DimensionConfig("Ad format or inventory unit type", "All"),
    "Format Mix": DimensionConfig("Aggregated or mixed format state", "All"),
    "Dimensions": DimensionConfig("Ad size / duration / unit specification", "Display, Social, Video, CTV"),
    "Dimensions Mix": DimensionConfig("Aggregated or mixed dimension state", "Display, Social, Video, CTV"),
    "Audience Segment": DimensionConfig("Audience definition selected for delivery", "Social, Display, Programmatic, Video"),
    "Targeting": DimensionConfig("Targeting method or targeting source", "Social, Display, Programmatic, Search"),
    "Demographic": DimensionConfig("Demographic targeting layer", "All"),
    "Device": DimensionConfig("Device target or delivery context", "All"),
    "Language": DimensionConfig("Language targeting", "All"),
    "Match Type": DimensionConfig("Search keyword match behavior", "Paid Search"),
    "Keyword Type / Messaging": DimensionConfig("Search keyword/message classification", "Paid Search"),
    "Buying Type": DimensionConfig("Commercial pricing method", "All"),
    "Supplier": DimensionConfig("Supplier / media owner / platform supplier", "All"),
    "Vendor": DimensionConfig("Vendor field likely overlapping with Supplier", "All"),
}


KEY_DIMENSIONS = list(DIMENSION_CONFIG.keys())

CHANNEL_DRIVER_CANDIDATES = [
    "Channel",
    "Local Channel",
    "Reporting Channel",
]


def normalize_value(value: Any) -> str:
    if pd.isna(value):
        return "<<NULL>>"
    text = str(value).strip()
    return text if text else "<<NULL>>"


def is_placeholder(value: str) -> bool:
    value_norm = value.strip().lower()
    if value == "<<NULL>>":
        return True
    return value_norm in PLACEHOLDER_VALUES


def contains_design_smell(value: str) -> bool:
    value_norm = value.strip().lower()
    return any(token in value_norm for token in DESIGN_SMELL_TOKENS)


def get_channel_driver_col(df: pd.DataFrame) -> str | None:
    for col in CHANNEL_DRIVER_CANDIDATES:
        if col in df.columns:
            return col
    return None


def load_taxonomy_data(path: Path, sheet_name: str = "Taxonomy Outputs") -> pd.DataFrame:
    if sheet_name == "Taxonomy Outputs":
        df = pd.read_excel(path, sheet_name=sheet_name, header=8)
        unnamed_cols = [col for col in df.columns if str(col).startswith("Unnamed:")]
        if unnamed_cols:
            df = df.drop(columns=unnamed_cols, errors="ignore")
        df = df.dropna(how="all").reset_index(drop=True)
        return df
    return pd.read_excel(path, sheet_name=sheet_name)


def classify_value(dimension: str, value: str, usage_count: int, usage_prop: float) -> tuple[str, str, str]:
    lower = value.lower()
    if value == "<<NULL>>" or is_placeholder(value):
        return (
            "Reporting-only placeholder",
            "Convert to reporting-only derived state",
            "Placeholder or blank-like value should not be selectable by default.",
        )
    if contains_design_smell(value):
        return (
            "Design-smell workaround",
            "Remove or redesign field logic",
            "Value looks like a workaround created by taxonomy design rather than a business concept.",
        )
    if dimension in {"Match Type", "Keyword Type / Messaging"} and usage_prop < 0.01:
        return (
            "Valid niche value",
            "Keep with search-only restriction",
            "Low-volume value but channel-specific and potentially strategically important.",
        )
    if usage_prop < 0.002:
        return (
            "Valid niche value",
            "Needs stakeholder sign-off before removal",
            "Rarely used; could be niche or legacy. Review with channel owner before removing.",
        )
    if "mixed" in lower:
        return (
            "Too broad",
            "Remove from input and derive in reporting",
            "Mixed is not mutually exclusive and weakens governance.",
        )
    if "other" in lower:
        return (
            "Ambiguous",
            "Remove or replace with controlled vocabulary",
            "Catch-all bucket reduces analytical value and governance.",
        )
    return (
        "Valid core value",
        "Keep",
        "Used enough and appears to represent a meaningful business option.",
    )


def _channel_usage(df: pd.DataFrame, dimension: str) -> pd.DataFrame:
    channel_col = get_channel_driver_col(df)
    if channel_col is None:
        subset = df[[dimension]].copy()
        subset["Channel Driver"] = "ALL_ROWS"
    else:
        subset = df[[channel_col, dimension]].copy()
        subset = subset.rename(columns={channel_col: "Channel Driver"})
    subset["Channel Driver"] = subset["Channel Driver"].map(normalize_value)
    subset[dimension] = subset[dimension].map(normalize_value)
    usage = (
        subset.groupby(["Channel Driver", dimension], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["Channel Driver", "count"], ascending=[True, False])
    )
    return usage


def analyze_dimensions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dimension_rows: list[dict[str, Any]] = []
    value_rows: list[dict[str, Any]] = []
    total_rows = len(df)
    channel_driver_col = get_channel_driver_col(df)

    for dimension in KEY_DIMENSIONS:
        if dimension not in df.columns:
            continue
        series = df[dimension].map(normalize_value)
        value_counts = series.value_counts(dropna=False)
        unique_count = int(series.nunique(dropna=False))
        placeholder_count = int(sum(count for value, count in value_counts.items() if is_placeholder(str(value))))
        placeholder_prop = placeholder_count / total_rows if total_rows else 0.0
        top_values = value_counts.head(10)
        channel_usage = _channel_usage(df, dimension)
        channel_count = int(
            channel_usage[channel_usage[dimension].map(lambda x: not is_placeholder(str(x)))]["Channel Driver"].nunique()
        )

        problems: list[str] = []
        severity = "Low"
        recommendation = "Keep as is"
        current_future = DIMENSION_CONFIG[dimension].current_or_future_default
        rationale_bits: list[str] = []
        risks = ""
        open_questions = ""

        if placeholder_prop > 0.2:
            problems.append("Placeholder / bad fallback value")
            severity = "High" if severity in {"Low", "Medium"} else severity
            rationale_bits.append(f"Placeholder-style values account for {placeholder_prop:.1%} of rows.")
        if unique_count > 40:
            problems.append("Too many values")
            severity = "High" if severity == "Low" else severity
            rationale_bits.append(f"{unique_count} unique values creates a long dropdown and weakens control.")
        if dimension in {"Match Type", "Keyword Type / Messaging"} and channel_count > 1:
            problems.append("Irrelevant cross-channel usage")
            severity = "Critical"
            recommendation = "Make conditional"
            channel_context = channel_driver_col or "available channel grouping"
            rationale_bits.append(
                f"Search-specific concept appears across multiple values of {channel_context} and should be hidden elsewhere."
            )
        if dimension in {"Format Mix", "Dimensions Mix"}:
            problems.append("Reporting-only value used as input")
            severity = "High" if severity != "Critical" else severity
            recommendation = "Convert to reporting-only derived state"
            rationale_bits.append("Mix fields largely encode aggregation states rather than user decisions.")
        if dimension in {"Supplier", "Vendor"}:
            problems.append("Redundant with another field")
            severity = "Medium" if severity == "Low" else severity
            recommendation = "Merge with another field"
            rationale_bits.append("Supplier and Vendor appear to capture near-duplicate platform/entity concepts.")
        if dimension == "Buying Mode":
            problems.append("Irrelevant cross-channel usage")
            severity = "High" if severity != "Critical" else severity
            recommendation = "Make conditional"
            rationale_bits.append("Almost all rows are Not Used; field should likely only appear for programmatic/open-inventory cases.")
        if dimension == "Local Channel TACT":
            problems.append("Free-text risk")
            problems.append("Design smell")
            severity = "High" if severity != "Critical" else severity
            recommendation = "Move to future-state redesign"
            rationale_bits.append("Values like 'String Only' look like workflow workarounds rather than business taxonomy.")
            current_future = "Future-State"
        if dimension in {"Audience Segment", "Targeting"}:
            rationale_bits.append("Field is strategically important but too broad and may need channel-specific vocabularies.")
            if recommendation == "Keep as is":
                recommendation = "Restrict values"
                severity = "Medium" if severity == "Low" else severity
        if dimension == "Planning Principle":
            rationale_bits.append("Contains conceptually overlapping funnel states; should drive conditional validation.")
            if recommendation == "Keep as is":
                recommendation = "Restrict values"
                severity = "Medium" if severity == "Low" else severity
        if dimension == "Buying Platform":
            rationale_bits.append("Should be tightly filtered by channel / sub-channel rather than globally available.")
            recommendation = "Make conditional"
            severity = "High" if severity == "Low" else severity
        if not problems:
            problems = ["None material"]
            rationale_bits.append("No major hygiene issue detected from first-pass usage and naming review.")

        if "Design smell" in problems:
            risks = "Likely reflects workaround-driven legacy structure; removal needs owner sign-off."
        elif dimension in {"Supplier", "Vendor", "Local Channel", "Reporting Channel"}:
            risks = "Historical reporting and mappings may depend on current duplication."
        elif dimension in {"Format Mix", "Dimensions Mix"}:
            risks = "Removing from input may require report and template updates."

        if dimension in {"Audience Segment", "Targeting", "Planning Principle"}:
            open_questions = "Which stakeholders rely on current granularity for channel planning or reporting?"
        elif dimension in {"Buying Platform", "Sub Channel"}:
            open_questions = "Which current validation logic already exists in PlanIT, and where are exceptions needed?"
        elif dimension == "Local Channel TACT":
            open_questions = "Is this field only present to satisfy string/template generation rules?"

        cfg = DIMENSION_CONFIG[dimension]
        dimension_rows.append({
            "Dimension Name": dimension,
            "Description / inferred business meaning": cfg.description,
            "Applies To Channels": cfg.applies_to,
            "Current Values": ", ".join(map(str, top_values.index[:8])),
            "Observed Usage": f"{unique_count} unique values; placeholders {placeholder_prop:.1%}",
            "Governance Problem Type": "; ".join(problems),
            "Severity": severity,
            "Recommendation": recommendation,
            "Recommended Future Validation Logic": proposed_logic_for_dimension(dimension),
            "Rationale": " ".join(rationale_bits),
            "Current-State or Future-State": current_future,
            "Risks / Dependencies": risks,
            "Open Questions": open_questions,
        })

        for value, count in value_counts.items():
            usage_prop = float(count / total_rows) if total_rows else 0.0
            classification, value_reco, reason = classify_value(dimension, str(value), int(count), usage_prop)
            channel_context = (
                ", ".join(
                    channel_usage[channel_usage[dimension] == value]
                    .sort_values("count", ascending=False)["Channel Driver"]
                    .head(4)
                    .astype(str)
                    .tolist()
                )
                if not channel_usage.empty
                else ""
            )
            value_rows.append({
                "Dimension": dimension,
                "Value": value,
                "Usage count / proportion": f"{int(count)} ({usage_prop:.1%})",
                "Channel context if inferable": channel_context,
                "Classification": classification,
                "Recommendation": value_reco,
                "Reason": reason,
            })

    return pd.DataFrame(dimension_rows), pd.DataFrame(value_rows)


def proposed_logic_for_dimension(dimension: str) -> str:
    mapping = {
        "Buying Platform": "Filter by Channel and Sub Channel; hide irrelevant platforms.",
        "Match Type": "Visible and mandatory only when Channel = Paid Search.",
        "Keyword Type / Messaging": "Visible only when Channel = Paid Search; otherwise null.",
        "Buying Mode": "Visible only for programmatic/open inventory contexts.",
        "Format Mix": "Derived in reporting only; not selectable.",
        "Dimensions Mix": "Derived in reporting only; not selectable.",
        "Audience Segment": "Allowed values should vary by Social / Programmatic / Display.",
        "Targeting": "Restrict by channel and separate source vs method if retained.",
    }
    return mapping.get(dimension, "Review for channel-aware filtering where applicable.")


def proposed_validation_rules(df: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "Driver Field": "Channel",
            "Driver Value": "Paid Search",
            "Controlled Field": "Buying Platform",
            "Allowed Values": "Google Ads; Microsoft Ads; Bing; search-approved engines only",
            "Logic Type": "Allowed values filter",
            "Reason": "Search channel should not expose social, DSP, or direct-buy platforms.",
            "Confidence": "High",
        },
        {
            "Driver Field": "Channel",
            "Driver Value": "Paid Search",
            "Controlled Field": "Match Type",
            "Allowed Values": "ALL; Exact; Broad; Phrase; Dynamic Search Ads",
            "Logic Type": "Field visibility condition",
            "Reason": "Search-specific concept; should be hidden elsewhere.",
            "Confidence": "High",
        },
        {
            "Driver Field": "Channel",
            "Driver Value": "!= Paid Search",
            "Controlled Field": "Match Type",
            "Allowed Values": "NULL only",
            "Logic Type": "Forbidden-if condition",
            "Reason": "Current workbook shows search concepts leaking into non-search rows.",
            "Confidence": "High",
        },
        {
            "Driver Field": "Channel",
            "Driver Value": "!= Paid Search",
            "Controlled Field": "Keyword Type / Messaging",
            "Allowed Values": "NULL only",
            "Logic Type": "Forbidden-if condition",
            "Reason": "Keyword messaging is search-only and placeholder states should not be used elsewhere.",
            "Confidence": "High",
        },
        {
            "Driver Field": "Channel",
            "Driver Value": "Paid Social",
            "Controlled Field": "Buying Platform",
            "Allowed Values": "Facebook Business Manager; LinkedIn Ads; Pinterest Ads; Reddit Ads; TikTok; social-approved platforms",
            "Logic Type": "Allowed values filter",
            "Reason": "Social should not present search or direct-buy platform lists.",
            "Confidence": "High",
        },
        {
            "Driver Field": "Channel",
            "Driver Value": "Display / iVideo / Connected TV (CTV)",
            "Controlled Field": "Buying Platform",
            "Allowed Values": "Google - DV360; The Trade Desk; Amazon DSP; Direct Buy; channel-specific approved vendors",
            "Logic Type": "Allowed values filter",
            "Reason": "Programmatic and direct inventory require a different platform vocabulary.",
            "Confidence": "Medium",
        },
        {
            "Driver Field": "Buying Platform",
            "Driver Value": "Direct Buy",
            "Controlled Field": "Buying Mode",
            "Allowed Values": "NULL or direct-buy specific value only",
            "Logic Type": "Field visibility condition",
            "Reason": "Programmatic open inventory mode is not meaningful for direct-buy rows.",
            "Confidence": "Medium",
        },
        {
            "Driver Field": "Channel",
            "Driver Value": "Paid Search",
            "Controlled Field": "Format / Dimensions",
            "Allowed Values": "Search-specific values only; no generic display sizes",
            "Logic Type": "Allowed values filter",
            "Reason": "Search rows currently contain placeholder format constructs rather than meaningful search values.",
            "Confidence": "Medium",
        },
        {
            "Driver Field": "Sub Channel",
            "Driver Value": "Programmatic - Display / Video / Audio",
            "Controlled Field": "Buying Mode",
            "Allowed Values": "Programmatic Open Inventory and other approved programmatic modes",
            "Logic Type": "Mandatory-if condition",
            "Reason": "Trading mode matters only in applicable programmatic contexts.",
            "Confidence": "Medium",
        },
        {
            "Driver Field": "Planning Principle",
            "Driver Value": "Awareness",
            "Controlled Field": "KPI Objective",
            "Allowed Values": "Awareness; Video Views; Reach-type objectives",
            "Logic Type": "Allowed values filter",
            "Reason": "Funnel principle should constrain valid KPI choices.",
            "Confidence": "Medium",
        },
    ]
    return pd.DataFrame(rows)


def missing_dimensions() -> pd.DataFrame:
    rows = [
        {
            "Proposed Dimension Name": "Audience Source / Data Source",
            "Business Need": "Differentiate 1P CRM, Tealium/CDP, platform-native, partner, contextual and modeled audiences.",
            "Example Values": "Tealium; CRM; Pixel retargeting; Platform native interest; 2P; 3P; Contextual",
            "Applies To": "Social, Programmatic, Display, Video",
            "Why current taxonomy fails": "Current Targeting and Audience Segment fields mix source and tactic in one place.",
            "Whether current-state feasible or future-state only": "Current-State feasible",
        },
        {
            "Proposed Dimension Name": "Targeting Method",
            "Business Need": "Separate targeting method from audience source for reporting and governance.",
            "Example Values": "Interest; In-market; Retargeting; Keyword; Contextual; Lookalike; Demographic",
            "Applies To": "Search, Social, Programmatic, Display",
            "Why current taxonomy fails": "Targeting field currently bundles incompatible concepts.",
            "Whether current-state feasible or future-state only": "Current-State feasible",
        },
        {
            "Proposed Dimension Name": "Funnel Stage",
            "Business Need": "Create a cleaner normalized funnel lens distinct from planning principle and KPI objective.",
            "Example Values": "Awareness; Consideration; Conversion",
            "Applies To": "All",
            "Why current taxonomy fails": "Planning Principle values are too numerous and partially overlapping.",
            "Whether current-state feasible or future-state only": "Future-State",
        },
        {
            "Proposed Dimension Name": "Creative / Message Family",
            "Business Need": "Support reporting on message strategy and model-specific creative architecture.",
            "Example Values": "Brand; Model; Offer; Aftersales; Launch; Tactical",
            "Applies To": "All paid media",
            "Why current taxonomy fails": "Keyword Type / Messaging is search-biased and cannot serve all channels.",
            "Whether current-state feasible or future-state only": "Future-State",
        },
        {
            "Proposed Dimension Name": "Inventory Logic",
            "Business Need": "Distinguish direct buy, PMP, open exchange, reservation, auction and retail media structures.",
            "Example Values": "Open Exchange; PMP; PG; Direct IO; Retail sponsored",
            "Applies To": "Programmatic, Display, CTV, Retail media",
            "Why current taxonomy fails": "Buying Mode is too narrow and mostly filled with placeholders.",
            "Whether current-state feasible or future-state only": "Current-State feasible",
        },
    ]
    return pd.DataFrame(rows)


def current_state_recommendations() -> pd.DataFrame:
    rows = [
        {"Priority": 1, "Recommendation": "Remove placeholder values such as Mixed, Not Used, Other, Unknown and blanks from input dropdowns wherever possible.", "Why it matters": "These values dominate several fields and are degrading governance immediately."},
        {"Priority": 2, "Recommendation": "Make Match Type and Keyword Type / Messaging search-only conditional fields.", "Why it matters": "They are currently leaking into non-search rows and creating invalid taxonomy states."},
        {"Priority": 3, "Recommendation": "Restrict Buying Platform by Channel and Sub Channel.", "Why it matters": "Platform dropdowns should be channel-aware to stop invalid combinations at source."},
        {"Priority": 4, "Recommendation": "Convert Format Mix and Dimensions Mix into reporting-only derived states.", "Why it matters": "These are aggregation outputs masquerading as input choices."},
        {"Priority": 5, "Recommendation": "Split Targeting into source and method, or at minimum tighten allowed values by channel.", "Why it matters": "Current values mix audience source, targeting method and operational workarounds."},
        {"Priority": 6, "Recommendation": "Review Supplier and Vendor for consolidation into a single governed entity field.", "Why it matters": "Duplication increases maintenance and inconsistency risk."},
    ]
    return pd.DataFrame(rows)


def future_state_recommendations() -> pd.DataFrame:
    rows = [
        {"Priority": 1, "Recommendation": "Redesign taxonomy by channel family rather than forcing one globally generic set of dropdowns.", "Why it matters": "Search, Social and Programmatic require different governed concepts."},
        {"Priority": 2, "Recommendation": "Replace Local Channel TACT workaround structures with proper object-level taxonomy and string-generation logic.", "Why it matters": "Fields containing 'String Only' are design smells, not business taxonomy."},
        {"Priority": 3, "Recommendation": "Introduce a normalized funnel-stage model separate from campaign planning and reporting objectives.", "Why it matters": "Current fields partially duplicate and conflict with each other."},
        {"Priority": 4, "Recommendation": "Move message strategy, audience source and targeting method into separately governed dimensions.", "Why it matters": "Current field overload limits analytical usability."},
    ]
    return pd.DataFrame(rows)


def stakeholder_questions() -> pd.DataFrame:
    rows = [
        {"Stakeholder": "Laura / analytics owners", "Question / sign-off need": "Which dimensions are required for reporting and modelling today versus desirable in future state?"},
        {"Stakeholder": "Chloe / PlanIT taxonomy owners", "Question / sign-off need": "Which conditional validation rules are technically feasible without breaking historical templates?"},
        {"Stakeholder": "Sam Tait / governance owners", "Question / sign-off need": "Which placeholder values are mandated today due to workflow constraints rather than business need?"},
        {"Stakeholder": "Channel leads", "Question / sign-off need": "Which rare values are strategically important and must survive consolidation?"},
        {"Stakeholder": "Local markets", "Question / sign-off need": "Which fields currently force users into workaround values just to complete planning flows?"},
    ]
    return pd.DataFrame(rows)


def executive_summary(dimension_df: pd.DataFrame, value_df: pd.DataFrame) -> dict[str, Any]:
    critical = int((dimension_df["Severity"] == "Critical").sum())
    high = int((dimension_df["Severity"] == "High").sum())
    placeholders = int(value_df["Classification"].eq("Reporting-only placeholder").sum())
    smells = int(value_df["Classification"].eq("Design-smell workaround").sum())
    summary = {
        "critical_dimensions": critical,
        "high_dimensions": high,
        "placeholder_values": placeholders,
        "design_smell_values": smells,
        "headline": (
            "The taxonomy is over-generic across channels, placeholder-heavy in several input fields, "
            "and still carrying workflow workarounds as if they were legitimate business structure."
        ),
        "practical_priority": (
            "Biggest immediate gains come from removing placeholder input values, making search fields conditional, "
            "and tightening Buying Platform / Targeting rules by channel."
        ),
    }
    return summary


def grouped_findings(dimension_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    def filt(pattern: str) -> pd.DataFrame:
        return dimension_df[dimension_df["Governance Problem Type"].str.contains(pattern, case=False, na=False)]

    return {
        "excessive_dropdown_complexity": filt("Too many values"),
        "irrelevant_cross_channel_values": filt("Irrelevant cross-channel usage"),
        "missing_dimensions": missing_dimensions(),
        "bad_fallback_values": filt("Placeholder / bad fallback value"),
        "weak_validation_logic": dimension_df[dimension_df["Recommendation"].isin(["Make conditional", "Restrict values", "Convert to reporting-only derived state"])],
        "future_state_structural_issues": dimension_df[dimension_df["Current-State or Future-State"] == "Future-State"],
    }


def build_taxonomy_analysis(df: pd.DataFrame) -> dict[str, Any]:
    dimension_df, value_df = analyze_dimensions(df)
    result = {
        "executive_summary": executive_summary(dimension_df, value_df),
        "dimension_review": dimension_df.sort_values(["Severity", "Dimension Name"], ascending=[True, True]),
        "value_review": value_df,
        "validation_rules": proposed_validation_rules(df),
        "missing_dimensions": missing_dimensions(),
        "current_state": current_state_recommendations(),
        "future_state": future_state_recommendations(),
        "stakeholder_questions": stakeholder_questions(),
        "appendix": pd.DataFrame(
            [
                {
                    "Assumption / note": "Analysis is provisional and based on the workbook Data sheet only.",
                    "Impact": "Confidence on governance issues is strong; confidence on owner intent is lower until template logic and stakeholder requirements are supplied.",
                },
                {
                    "Assumption / note": "Placeholder values are treated as invalid input by default.",
                    "Impact": "Some values may require owner confirmation if they are genuinely used for workflow gating.",
                },
                {
                    "Assumption / note": "Workaround-looking values are flagged as design smells rather than accepted business structure.",
                    "Impact": "Future-state recommendations may challenge existing string-generation logic.",
                },
            ]
        ),
        "grouped_findings": grouped_findings(dimension_df),
    }
    return result
