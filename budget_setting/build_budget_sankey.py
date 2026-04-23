from pathlib import Path

import pythoncom
import win32com.client


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "budget_setting_sankey_v1.pptx"

BG = 0xF5F1EB
TEXT = 0x141414
MUTED = 0x6B6B6B
RED = 0xF40437
NAVY = 0x22313F
BLUE = 0x5392C5
GREEN = 0x5C8B5A
AMBER = 0xC69214
GREY = 0xD7D1C9
WHITE = 0xFFFFFF

PP_LAYOUT_BLANK = 12
MSO_TEXT_ORIENTATION_HORIZONTAL = 1
MSO_SHAPE_RECTANGLE = 1
MSO_SHAPE_ROUNDED_RECTANGLE = 5
MSO_SHAPE_CHEVRON = 52
MSO_SHAPE_DOWN_ARROW = 36


def add_textbox(slide, left, top, width, height, text, size, color, bold=False, font="Porsche Next TT"):
    shape = slide.Shapes.AddTextbox(MSO_TEXT_ORIENTATION_HORIZONTAL, left, top, width, height)
    tr = shape.TextFrame.TextRange
    tr.Text = text
    tr.Font.Name = font
    tr.Font.Size = size
    tr.Font.Bold = -1 if bold else 0
    tr.Font.Color.RGB = color
    shape.TextFrame.MarginLeft = 0
    shape.TextFrame.MarginRight = 0
    shape.TextFrame.MarginTop = 0
    shape.TextFrame.MarginBottom = 0
    return shape


def add_rect(slide, left, top, width, height, fill, line=None, rounded=False):
    shape_type = MSO_SHAPE_ROUNDED_RECTANGLE if rounded else MSO_SHAPE_RECTANGLE
    shape = slide.Shapes.AddShape(shape_type, left, top, width, height)
    shape.Fill.ForeColor.RGB = fill
    if line is None:
        shape.Line.Visible = 0
    else:
        shape.Line.ForeColor.RGB = line
        shape.Line.Weight = 1
    return shape


def add_chevron(slide, left, top, width, height, fill):
    shape = slide.Shapes.AddShape(MSO_SHAPE_CHEVRON, left, top, width, height)
    shape.Fill.ForeColor.RGB = fill
    shape.Line.Visible = 0
    return shape


def add_arrow(slide, left, top, width, height, fill):
    shape = slide.Shapes.AddShape(MSO_SHAPE_DOWN_ARROW, left, top, width, height)
    shape.Fill.ForeColor.RGB = fill
    shape.Line.Visible = 0
    return shape


def build_slide(slide):
    slide.FollowMasterBackground = 0
    slide.Background.Fill.Solid()
    slide.Background.Fill.ForeColor.RGB = BG

    add_rect(slide, 0, 0, 960, 18, RED)
    add_textbox(slide, 40, 30, 300, 18, "BUDGET SETTING", 14, RED, bold=True)
    add_textbox(slide, 40, 54, 760, 30, "SANKEY VIEW: FROM BUDGET ENVELOPE TO UPPER / LOWER FUNNEL ALLOCATION", 24, TEXT, bold=True)
    add_textbox(slide, 40, 86, 770, 18, "Defensible flow for stakeholder discussion. Diagram shows logic, not final fixed shares.", 11, MUTED)

    # Left source
    add_rect(slide, 38, 184, 160, 118, NAVY, None, rounded=True)
    add_textbox(slide, 60, 214, 118, 22, "TOTAL BUDGET", 20, WHITE, bold=True)
    add_textbox(slide, 60, 244, 118, 18, "Starting envelope", 12, WHITE)

    # Middle split
    add_chevron(slide, 212, 198, 150, 44, BLUE)
    add_textbox(slide, 234, 209, 108, 18, "ALWAYS ON / CORE", 15, WHITE, bold=True)
    add_chevron(slide, 212, 244, 150, 44, RED)
    add_textbox(slide, 232, 255, 116, 18, "HIGHLIGHT ACTIVATIONS", 14, WHITE, bold=True)

    # Right split for highlight
    add_chevron(slide, 384, 222, 152, 38, AMBER)
    add_textbox(slide, 406, 231, 110, 18, "CLASSIFY HIGHLIGHT", 15, WHITE, bold=True)

    add_chevron(slide, 564, 176, 164, 44, GREEN)
    add_textbox(slide, 592, 186, 118, 18, "UPPER FUNNEL HIGHLIGHT", 14, WHITE, bold=True)
    add_chevron(slide, 564, 242, 164, 44, BLUE)
    add_textbox(slide, 592, 252, 118, 18, "LOWER FUNNEL HIGHLIGHT", 14, WHITE, bold=True)

    # Always on destination block
    add_rect(slide, 564, 330, 164, 58, NAVY, None, rounded=True)
    add_textbox(slide, 586, 345, 126, 18, "ALWAYS ON LOWER\nFUNNEL / CORE", 15, WHITE, bold=True)

    # Flow credit arrow from upper highlight to AO
    add_arrow(slide, 638, 288, 22, 38, RED)
    add_textbox(slide, 676, 288, 210, 34, "Credit highlight with click / session contribution to AO burden", 11, RED, bold=True)

    # Assumption / adjustment blocks
    add_rect(slide, 754, 154, 170, 56, WHITE, GREY, rounded=True)
    add_textbox(slide, 768, 166, 140, 16, "Baseline highlight calc", 12, RED, bold=True)
    add_textbox(slide, 768, 184, 142, 20, "Digital impressions -> sessions -> budget", 11, TEXT)

    add_rect(slide, 754, 220, 170, 52, WHITE, GREY, rounded=True)
    add_textbox(slide, 768, 232, 138, 16, "Upweight 1", 12, RED, bold=True)
    add_textbox(slide, 768, 248, 146, 18, "Offline / non-digital factor\n(+18.7% Tier 1 ref.)", 11, TEXT)

    add_rect(slide, 754, 282, 170, 56, WHITE, GREY, rounded=True)
    add_textbox(slide, 768, 294, 138, 16, "Upweight 2", 12, RED, bold=True)
    add_textbox(slide, 768, 310, 150, 20, "Beyond OGS / website-touch sales\n(OGS ref. 13.6%)", 11, TEXT)

    add_rect(slide, 754, 348, 170, 52, WHITE, GREY, rounded=True)
    add_textbox(slide, 768, 360, 138, 16, "Sensitivity", 12, RED, bold=True)
    add_textbox(slide, 768, 376, 146, 18, "Non-trackable allocation is estimate only", 11, TEXT)

    # Clarifier panel
    add_rect(slide, 40, 420, 684, 78, WHITE, GREY, rounded=True)
    add_textbox(slide, 58, 434, 170, 16, "Critical classification point", 12, RED, bold=True)
    add_textbox(
        slide,
        58,
        454,
        646,
        34,
        "Highlight is not automatically all upper funnel. In market planning, model launches may contain both upper-funnel demand creation and lower-funnel conversion support.",
        14,
        TEXT,
    )

    add_textbox(slide, 744, 438, 180, 18, "Interpretation", 12, RED, bold=True)
    add_textbox(
        slide,
        744,
        458,
        176,
        32,
        "Shift budget logic from a simple AO vs Highlight split to a classified funnel-aware flow.",
        12,
        TEXT,
    )


def main():
    pythoncom.CoInitialize()
    ppt = win32com.client.Dispatch("PowerPoint.Application")
    ppt.Visible = 1

    pres = ppt.Presentations.Add()
    pres.PageSetup.SlideWidth = 960
    pres.PageSetup.SlideHeight = 540

    slide = pres.Slides.Add(1, PP_LAYOUT_BLANK)
    build_slide(slide)

    pres.SaveAs(str(OUTPUT_PATH))
    pres.Close()
    ppt.Quit()
    pythoncom.CoUninitialize()
    print(f"Saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
