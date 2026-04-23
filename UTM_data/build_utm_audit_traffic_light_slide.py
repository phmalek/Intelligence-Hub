from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import shutil

import pythoncom
import win32com.client


BASE_DIR = Path(__file__).resolve().parent
INPUT_PPTX = BASE_DIR / "PAG_UTM_Monthly Audit_26.pptx"
OUTPUT_PPTX = BASE_DIR / "PAG_UTM_Monthly Audit_26_with_traffic_light.pptx"
CSV_PATH = BASE_DIR / "Porsche_UTM Adoption Notes_Feb2026.csv"
OUTPUT_MD = BASE_DIR / "utm_audit_traffic_light_logic.md"

ppLayoutBlank = 12
msoTextOrientationHorizontal = 1
msoShapeRoundedRectangle = 5
msoShapeOval = 9
ppAlignLeft = 1
ppAlignCenter = 2

BLACK = 0
WHITE = 16777215
TEXT = WHITE
MUTED = 14604762
ROW_PURPLE = 5382969
PILL_PURPLE = 13326221
GREEN = 1150565
AMBER = 41458
RED = 255
GREY = 8421504


@dataclass
class MarketStatus:
    code: str
    name: str
    category: str
    readout: str


RULE_DEFINITIONS = {
    "New concept fully implemented": "All relevant Planit IDs with start date before the report are found in GA4.",
    "New concept partially implemented": "Some Planit IDs are found in GA4 / One.Reporting, but coverage is incomplete or mixed.",
    "Other concept implemented": "Placements appear live in reporting, but not on the new UTM concept consistently enough to count as compliant.",
    "Campaign not live / not yet measurable": "No live campaigns expected, or current downstream visibility does not allow a valid compliance check.",
}


def normalize_name(code: str, name: str) -> str:
    name = (name or "").strip()
    if name:
        return name
    fallback = {
        "PAP": "PAP",
        "PLA": "PLA",
        "PSG": "PSG",
        "PCEE": "PCEE",
        "PME": "MENA",
    }
    return fallback.get(code, code)


def classify_row(row: dict[str, str]) -> MarketStatus:
    code = (row.get("Market Code") or "").strip()
    name = normalize_name(code, row.get("Market Name") or "")
    status = (row.get("Status") or "").strip()
    issues = (row.get("Issues Identified") or "").strip()
    observations = (row.get("Observations") or "").strip()
    notes = " ".join(part for part in [status, observations, issues] if part).lower()

    if "no tacticals currently planned" in notes:
        category = "Campaign not live / not yet measurable"
        readout = "No tacticals currently planned; no live UTM requirement to audit."
    elif "validation currently not possible" in notes:
        category = "Campaign not live / not yet measurable"
        readout = "Validation blocked because downstream ingestion is not available."
    elif any(
        phrase in notes for phrase in [
            "partially implemented",
            "partial utm implementation",
            "limited compliance",
            "limited visibility",
            "very limited adoption",
            "not fully implemented",
            "mostly compliant",
            "fully aligned",
        ]
    ):
        category = "New concept partially implemented"
        readout = status.rstrip(".") + "."
    elif any(
        phrase in notes for phrase in [
            "search always-on 2026 campaigns are live",
            "no fully compliant channels identified",
            "no planit usage identified",
            "no ga4 visibility",
        ]
    ):
        category = "Other concept implemented"
        readout = status.rstrip(".") + "."
    else:
        category = "New concept partially implemented"
        readout = status.rstrip(".") + "." if status else "Mixed implementation state requiring market follow-up."

    return MarketStatus(code=code, name=name, category=category, readout=readout)


def load_market_statuses() -> list[MarketStatus]:
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    statuses = [classify_row(row) for row in rows]
    order = {
        "New concept fully implemented": 0,
        "New concept partially implemented": 1,
        "Other concept implemented": 2,
        "Campaign not live / not yet measurable": 3,
    }
    ordered_codes = [
        "PCNA", "PCL", "PCGB", "PCH", "PIB", "PNO", "POF", "PPL",
        "PAP", "PCA", "PKO", "PLA", "PME", "PSG", "PTW", "PCEE",
    ]
    by_code = {s.code: s for s in statuses}
    return [by_code[code] for code in ordered_codes if code in by_code]


def add_textbox(slide, left, top, width, height, text, size, color, bold=False, align=ppAlignLeft, italic=False):
    shape = slide.Shapes.AddTextbox(msoTextOrientationHorizontal, left, top, width, height)
    tr = shape.TextFrame.TextRange
    tr.Text = text
    tr.Font.Name = "Porsche Next TT"
    tr.Font.Size = size
    tr.Font.Bold = -1 if bold else 0
    tr.Font.Italic = -1 if italic else 0
    tr.Font.Color.RGB = color
    shape.TextFrame.MarginLeft = 0
    shape.TextFrame.MarginRight = 0
    shape.TextFrame.MarginTop = 0
    shape.TextFrame.MarginBottom = 0
    tr.ParagraphFormat.Alignment = align
    return shape


def add_rect(slide, left, top, width, height, fill, line=WHITE, rounded=False):
    shape_type = msoShapeRoundedRectangle if rounded else 1
    shape = slide.Shapes.AddShape(shape_type, left, top, width, height)
    shape.Fill.ForeColor.RGB = fill
    if line is None:
        shape.Line.Visible = 0
    else:
        shape.Line.ForeColor.RGB = line
        shape.Line.Weight = 1
    return shape


def add_circle(slide, left, top, size, fill):
    shape = slide.Shapes.AddShape(msoShapeOval, left, top, size, size)
    shape.Fill.ForeColor.RGB = fill
    shape.Line.ForeColor.RGB = fill
    return shape


def build_slide(slide, statuses: list[MarketStatus]) -> None:
    add_rect(slide, 0, 0, 960, 540, BLACK, None, False)

    add_textbox(slide, 25, 18, 900, 34, "Audit Results: Market traffic-light status using agreed UTM compliance logic", 20, WHITE, True)
    pill = add_rect(slide, 837.6, 9.5, 144.1, 23.3, PILL_PURPLE, WHITE, True)
    pill.Adjustments.Item(1) if False else None
    add_textbox(slide, 852, 13, 116, 14, "As of 28th Feb 2026", 10, WHITE, True, ppAlignCenter)

    add_rect(slide, 33.4, 84.9, 892.7, 2.0, PILL_PURPLE, PILL_PURPLE, False)
    add_rect(slide, 33.4, 495.0, 892.7, 2.0, PILL_PURPLE, PILL_PURPLE, False)

    headers = [
        ("Market", 56, 96, 90),
        ("New UTM Concept\nImplemented", 229, 95, 150),
        ("New Concept Partially\nImplemented", 430, 95, 170),
        ("Other Concept\nImplemented", 642, 95, 130),
        ("No Live\nCampaigns", 817, 95, 95),
    ]
    for text, left, top, width in headers:
        add_textbox(slide, left, top, width, 24, text, 10, WHITE, False, ppAlignCenter)

    row_tops = [
        129.4, 153.7, 174.9, 196.2, 217.9, 240.6, 261.3, 283.7,
        305.9, 327.6, 349.3, 371.1, 392.4, 415.1, 436.6, 459.0,
    ]
    for top in row_tops[::2]:
        add_rect(slide, 33.4, top, 892.7, 15.0, ROW_PURPLE, ROW_PURPLE, False)

    x_positions = {
        "New UTM Concept Implemented": 301.0,
        "New concept partially implemented": 503.0,
        "Other concept implemented": 705.0,
        "Campaign not live / not yet measurable": 881.0,
    }
    category_color = {
        "New UTM Concept Implemented": GREEN,
        "New concept partially implemented": AMBER,
        "Other concept implemented": RED,
        "Campaign not live / not yet measurable": WHITE,
    }
    display_label = {
        "New concept fully implemented": "New UTM Concept Implemented",
        "New concept partially implemented": "New concept partially implemented",
        "Other concept implemented": "Other concept implemented",
        "Campaign not live / not yet measurable": "Campaign not live / not yet measurable",
    }
    all_cols = list(x_positions.keys())

    for idx, status in enumerate(statuses):
        y = row_tops[idx]
        add_textbox(slide, 41, y - 1, 95, 14, status.code, 11, WHITE, True)
        selected = display_label[status.category]
        for col in all_cols:
            circ = slide.Shapes.AddShape(msoShapeOval, x_positions[col], y - 0.6, 11.3, 11.3)
            if col == selected and selected != "Campaign not live / not yet measurable":
                circ.Fill.ForeColor.RGB = category_color[col]
                circ.Line.ForeColor.RGB = category_color[col]
            else:
                circ.Fill.ForeColor.RGB = BLACK
                circ.Line.ForeColor.RGB = WHITE if col == selected else GREY
            circ.Line.Weight = 1.8 if col == selected else 0.6

    legend_y = 512.4
    legend_items = [
        ("New UTM Concept Implemented", GREEN, 164.6, 179.5),
        ("New Concept Partially Implemented", AMBER, 338.8, 354.4),
        ("Other Concept Implemented", RED, 514.6, 528.4),
        ("No Live Campaigns", WHITE, 657.9, 673.7),
    ]
    for label, color, cx, tx in legend_items:
        circ = slide.Shapes.AddShape(msoShapeOval, cx, legend_y, 11.3, 11.3)
        if color == WHITE:
            circ.Fill.ForeColor.RGB = BLACK
            circ.Line.ForeColor.RGB = WHITE
        else:
            circ.Fill.ForeColor.RGB = color
            circ.Line.ForeColor.RGB = color
        circ.Line.Weight = 1.8 if color == WHITE else 1.2
        add_textbox(slide, tx, 512.0, 155, 12.1, label, 9, WHITE, False, ppAlignLeft, italic=True)


def write_logic_md(statuses: list[MarketStatus]) -> None:
    lines = [
        "# UTM Audit Traffic-Light Logic",
        "",
        "Source files:",
        f"- `{CSV_PATH.name}`",
        f"- `{INPUT_PPTX.name}`",
        "",
        "Applied audit rules:",
        "",
        "- `New concept fully implemented`: all relevant Planit IDs with start date before the report are found in GA4.",
        "- `New concept partially implemented`: some Planit IDs are found in GA4 / One.Reporting, but coverage is incomplete or mixed.",
        "- `Other concept implemented`: placements appear live in reporting, but not on the new UTM concept consistently enough to count as compliant.",
        "- `Campaign not live / not yet measurable`: no live campaigns expected, or current downstream visibility does not allow a valid compliance check.",
        "",
        "## Market classification",
        "",
        "| Market | Classification | Readout |",
        "|---|---|---|",
    ]
    for status in statuses:
        lines.append(f"| {status.name} | {status.category} | {status.readout} |")
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    statuses = load_market_statuses()
    shutil.copyfile(INPUT_PPTX, OUTPUT_PPTX)

    pythoncom.CoInitialize()
    app = win32com.client.Dispatch("PowerPoint.Application")
    app.Visible = 1
    pres = app.Presentations.Open(str(OUTPUT_PPTX), WithWindow=False)

    slide = pres.Slides.Add(pres.Slides.Count + 1, ppLayoutBlank)
    build_slide(slide, statuses)

    pres.Save()
    pres.Close()
    app.Quit()
    pythoncom.CoUninitialize()

    write_logic_md(statuses)
    print(f"Saved {OUTPUT_PPTX}")
    print(f"Saved {OUTPUT_MD}")


if __name__ == "__main__":
    main()
