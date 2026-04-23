from pathlib import Path
import shutil

import pythoncom
import win32com.client


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "Weekly Status Meetings 2026.pptx"
OUTPUT_PATH = BASE_DIR / "utm_status_market_greenlights_template.pptx"

TEXT = 0x111111
MUTED = 0x626262
RED = 0xF40437
GREEN = 0x2D7D46
AMBER = 0xB26E12
WHITE = 0xFFFFFF
LIGHT = 0xF3F1EE
LINE = 0xD7D2CC


PAGE_1 = [
    ("Australia", "None confirmed yet", "In progress. Fix UTM mismatches and missing placements by 21 Apr."),
    ("Portugal", "None confirmed yet", "No response. Escalation required; DV360 missing from GA4 and 1R."),
    ("UK", "None confirmed yet", "In progress. Fix non-Hive campaigns and resolve builder issue."),
    ("MENA", "Scoped out correctly", "Resolved. No active PME campaigns at present."),
    ("South Korea", "None confirmed yet", "Blocked. Ingestion feasibility must be confirmed first."),
    ("France", "Google, Meta", "In progress. Platforms implemented; March validation needed to close."),
]

PAGE_2 = [
    ("Switzerland", "None confirmed yet", "In progress. Placement IDs reused across multiple UTMs."),
    ("Poland", "None confirmed yet", "In progress. Missing placement IDs; Social still on old UTMs."),
    ("Norway", "None confirmed yet", "Needs setup. No Planit schematic exists for Always On."),
    ("PCEE", "None confirmed yet", "In progress. Package-level UTMs still being remapped."),
    ("LATAM", "None confirmed yet", "Clarifying. DV360 routed via CM360 autotagging."),
]


def set_text(shape, text, size=None, bold=None, color=None, font="Porsche Next TT"):
    if not shape.HasTextFrame:
        return
    tr = shape.TextFrame.TextRange
    tr.Text = text
    tr.Font.Name = font
    if size is not None:
        tr.Font.Size = size
    if bold is not None:
        tr.Font.Bold = -1 if bold else 0
    if color is not None:
        tr.Font.Color.RGB = color
    shape.TextFrame.MarginLeft = 0
    shape.TextFrame.MarginRight = 0
    shape.TextFrame.MarginTop = 0
    shape.TextFrame.MarginBottom = 0


def add_textbox(slide, left, top, width, height, text, size, color, bold=False, font="Porsche Next TT"):
    shape = slide.Shapes.AddTextbox(1, left, top, width, height)
    set_text(shape, text, size=size, bold=bold, color=color, font=font)
    return shape


def add_rect(slide, left, top, width, height, fill, line=None, rounded=False):
    shape_type = 5 if rounded else 1
    shape = slide.Shapes.AddShape(shape_type, left, top, width, height)
    shape.Fill.ForeColor.RGB = fill
    if line is None:
        shape.Line.Visible = 0
    else:
        shape.Line.ForeColor.RGB = line
        shape.Line.Weight = 1
    return shape


def format_title_slide(slide):
    set_text(slide.Shapes(1), "UTM status by market", size=30, bold=True, color=TEXT)
    set_text(slide.Shapes(2), "Platforms already cleared for use", size=18, bold=False, color=RED)

    add_textbox(slide, 196, 396, 569, 56, "Only explicit green lights are marked as green.\nAll other platforms remain subject to validation or market confirmation.", 16, MUTED)


def clear_slide_2_content(slide):
    # Keep background, top title placeholder and footer band.
    while slide.Shapes.Count > 4:
        slide.Shapes(slide.Shapes.Count).Delete()


def build_market_table(slide, title_text, rows):
    set_text(slide.Shapes(2), title_text, size=24, bold=True, color=TEXT)
    slide.Shapes(2).Left = 34
    slide.Shapes(2).Top = 34
    slide.Shapes(2).Width = 892
    slide.Shapes(2).Height = 40

    add_textbox(slide, 34, 86, 270, 18, "MARKET", 12, RED, bold=True)
    add_textbox(slide, 320, 86, 220, 18, "PLATFORMS WITH GREEN LIGHT", 12, RED, bold=True)
    add_textbox(slide, 560, 86, 360, 18, "STATUS / NEXT STEP", 12, RED, bold=True)

    top = 114
    row_h = 62
    gap = 8
    for idx, (market, green, note) in enumerate(rows):
        y = top + idx * (row_h + gap)
        add_rect(slide, 24, y, 912, row_h, WHITE, LINE, rounded=False)
        add_textbox(slide, 38, y + 16, 250, 22, market, 18, TEXT, bold=True)
        color = GREEN if green != "None confirmed yet" else AMBER
        add_textbox(slide, 320, y + 12, 220, 28, green, 15, color, bold=True)
        add_textbox(slide, 560, y + 10, 350, 34, note, 13, TEXT)


def prepare_slide_3(slide):
    # Remove "Thank You" and add a clean content canvas.
    while slide.Shapes.Count > 2:
        slide.Shapes(slide.Shapes.Count).Delete()
    add_rect(slide, 0, 0, 960, 18, RED, None, rounded=False)
    add_rect(slide, 0, 511.3, 959.5, 28.7, RED, None, rounded=False)
    add_rect(slide, 0, 18, 960, 493, LIGHT, None, rounded=False)


def main():
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Missing template: {TEMPLATE_PATH}")

    shutil.copyfile(TEMPLATE_PATH, OUTPUT_PATH)

    pythoncom.CoInitialize()
    ppt = win32com.client.Dispatch("PowerPoint.Application")
    ppt.Visible = 1

    pres = ppt.Presentations.Open(str(OUTPUT_PATH), WithWindow=False)

    format_title_slide(pres.Slides(1))
    clear_slide_2_content(pres.Slides(2))
    build_market_table(pres.Slides(2), "Confirmed green lights: Australia to France", PAGE_1)

    prepare_slide_3(pres.Slides(3))
    build_market_table(pres.Slides(3), "Confirmed green lights: Switzerland to LATAM", PAGE_2)

    pres.Save()
    pres.Close()
    ppt.Quit()
    pythoncom.CoUninitialize()
    print(f"Saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
