from pathlib import Path

import pythoncom
import win32com.client


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "reverse_funnel_x_bev_v3.pptx"
BG_IMAGE_PATH = BASE_DIR / "background_reference.jpg"


BG = 0x101010
SURFACE = 0x171717
SURFACE_2 = 0x1F1F1F
TEXT = 0xF3F3F3
MUTED = 0xA6A6A6
LINE = 0x3A3A3A
ACCENT = 0x67D7FF
ACCENT_2 = 0xFFCC33

PP_LAYOUT_BLANK = 12
MSO_TEXT_ORIENTATION_HORIZONTAL = 1
MSO_SHAPE_RECTANGLE = 1
MSO_SHAPE_ROUNDED_RECTANGLE = 5
MSO_SHAPE_OVAL = 9
MSO_SHAPE_ARC = 25
MSO_ANCHOR_CENTER = 2
MSO_ANCHOR_MIDDLE = 3
MSO_ARROWHEAD_TRIANGLE = 2


def style_text_range(text_range, size, color, bold=False, font_name="Aptos"):
    text_range.Font.Name = font_name
    text_range.Font.Size = size
    text_range.Font.Bold = -1 if bold else 0
    text_range.Font.Color.RGB = color


def set_bg(slide):
    slide.FollowMasterBackground = 0
    slide.Background.Fill.Solid()
    slide.Background.Fill.ForeColor.RGB = BG


def add_textbox(
    slide,
    left,
    top,
    width,
    height,
    text,
    size,
    color,
    bold=False,
    font_name="Aptos",
    margin=0,
):
    shape = slide.Shapes.AddTextbox(
        MSO_TEXT_ORIENTATION_HORIZONTAL,
        left,
        top,
        width,
        height,
    )
    frame = shape.TextFrame
    frame.TextRange.Text = text
    frame.MarginLeft = margin
    frame.MarginRight = margin
    frame.MarginTop = margin
    frame.MarginBottom = margin
    frame.WordWrap = -1
    style_text_range(frame.TextRange, size, color, bold=bold, font_name=font_name)
    return shape


def add_line(slide, x1, y1, x2, y2, color=LINE, weight=1.5, begin_arrow=False, end_arrow=False):
    line = slide.Shapes.AddLine(x1, y1, x2, y2)
    line.Line.ForeColor.RGB = color
    line.Line.Weight = weight
    if begin_arrow:
        line.Line.BeginArrowheadStyle = MSO_ARROWHEAD_TRIANGLE
    if end_arrow:
        line.Line.EndArrowheadStyle = MSO_ARROWHEAD_TRIANGLE
    return line


def add_rect(slide, left, top, width, height, fill, line_color=None, rounded=True):
    shape_type = MSO_SHAPE_ROUNDED_RECTANGLE if rounded else MSO_SHAPE_RECTANGLE
    shape = slide.Shapes.AddShape(shape_type, left, top, width, height)
    shape.Fill.ForeColor.RGB = fill
    if line_color is None:
        shape.Line.Visible = 0
    else:
        shape.Line.ForeColor.RGB = line_color
        shape.Line.Weight = 1
    return shape


def add_picture(slide, path, left, top, width, height):
    return slide.Shapes.AddPicture(str(path), 0, -1, left, top, width, height)


def add_overlay(slide, left, top, width, height, fill, transparency):
    shape = add_rect(slide, left, top, width, height, fill, None, rounded=False)
    shape.Fill.Transparency = transparency
    return shape


def add_stage(slide, left, top, width, height, title, note=None):
    add_rect(slide, left, top, width, height, SURFACE_2, LINE, rounded=True)
    add_textbox(slide, left + 22, top + 14, width - 44, 24, title, 19, TEXT, bold=True)
    if note:
        add_textbox(slide, left + 22, top + 42, width - 44, 18, note, 10, MUTED)


def add_chip(slide, left, top, width, text, fill, line_color, text_color):
    add_rect(slide, left, top, width, 24, fill, line_color, rounded=True)
    add_textbox(slide, left + 10, top + 4, width - 20, 14, text, 10, text_color, bold=True)


def add_footer(slide):
    add_textbox(
        slide,
        360,
        516,
        240,
        12,
        "Confidential - Not for Public Consumption or Distribution",
        8,
        0x4E4E4E,
    )


def build_slide_1(slide):
    set_bg(slide)

    if BG_IMAGE_PATH.exists():
        add_picture(slide, BG_IMAGE_PATH, 318, 0, 720, 540)
        add_overlay(slide, 0, 0, 960, 540, BG, 0.34)
        add_overlay(slide, 0, 0, 520, 540, BG, 0.08)
        add_overlay(slide, 470, 0, 490, 540, 0x0B0B0B, 0.42)

    add_textbox(slide, 44, 28, 380, 22, "REVERSE FUNNEL x BEV", 14, ACCENT, bold=True)
    add_textbox(
        slide,
        44,
        52,
        420,
        88,
        "FROM MEDIA PLANNING\nTO OUTCOME ENGINEERING",
        28,
        TEXT,
        bold=True,
    )
    add_textbox(
        slide,
        44,
        122,
        320,
        36,
        "Reverse Funnel turns demand into a controllable system",
        14,
        MUTED,
    )

    add_chip(slide, 44, 172, 112, "TRACEABLE", SURFACE, LINE, TEXT)
    add_chip(slide, 164, 172, 130, "OBSERVED DATA", SURFACE, LINE, TEXT)
    add_chip(slide, 302, 172, 124, "REALLOCATION", SURFACE, LINE, TEXT)

    flow_left = 74
    flow_top = 222
    flow_width = 346
    stage_height = 42
    stage_gap = 16
    stage_titles = [
        ("SALES TARGET", "Start from decision outcome"),
        ("REQUIRED LEADS (DCFS)", "Backsolve the demand requirement"),
        ("SESSIONS", "Translate leads into traffic volume"),
        ("MEDIA SPEND", "Price the traffic requirement"),
    ]

    for idx, (title, note) in enumerate(stage_titles):
        top = flow_top + idx * (stage_height + stage_gap)
        add_stage(slide, flow_left, top, flow_width, stage_height, title, note)
        if idx < len(stage_titles) - 1:
            center_x = flow_left + (flow_width / 2)
            add_line(
                slide,
                center_x,
                top + stage_height,
                center_x,
                top + stage_height + stage_gap - 2,
                color=ACCENT,
                weight=2,
                end_arrow=True,
            )

    channels_top = flow_top + 4 * (stage_height + stage_gap)
    add_textbox(slide, flow_left, channels_top - 20, 120, 14, "CHANNEL ALLOCATION", 10, MUTED, bold=True)
    chip_y = channels_top
    chip_specs = [
        (flow_left, 100, "SEARCH"),
        (flow_left + 116, 114, "INVENTORY"),
        (flow_left + 246, 96, "SOCIAL"),
    ]
    for left, width, label in chip_specs:
        add_rect(slide, left, chip_y, width, 30, BG, ACCENT, rounded=True)
        add_textbox(slide, left + 12, chip_y + 7, width - 24, 16, label, 12, TEXT, bold=True)

    add_line(slide, flow_left + 100, chip_y + 15, flow_left + 116, chip_y + 15, color=ACCENT, weight=1.5, begin_arrow=True, end_arrow=True)
    add_line(slide, flow_left + 230, chip_y + 15, flow_left + 246, chip_y + 15, color=ACCENT, weight=1.5, begin_arrow=True, end_arrow=True)
    add_textbox(slide, flow_left, chip_y + 36, 200, 14, "Budget shifts to the strongest marginal return", 10, MUTED)

    right_left = 504
    add_textbox(slide, right_left, 74, 260, 18, "WHY THIS IS DIFFERENT", 11, MUTED, bold=True)
    add_rect(slide, right_left, 100, 266, 330, SURFACE, LINE, rounded=True)
    add_textbox(slide, right_left + 24, 124, 190, 20, "Closed-loop optimisation", 18, TEXT, bold=True)
    add_textbox(
        slide,
        right_left + 24,
        154,
        182,
        48,
        "Observed performance continuously updates lead needs, session volume and spend.",
        12,
        MUTED,
    )

    chart_left = right_left + 24
    chart_top = 222
    chart_w = 206
    chart_h = 124
    add_line(slide, chart_left, chart_top + chart_h, chart_left + chart_w, chart_top + chart_h, color=LINE, weight=1)
    add_line(slide, chart_left, chart_top + chart_h, chart_left, chart_top, color=LINE, weight=1)
    add_textbox(slide, chart_left - 2, chart_top - 18, 90, 14, "Marginal return", 9, MUTED)
    add_textbox(slide, chart_left + chart_w - 12, chart_top + chart_h + 6, 40, 14, "Spend", 9, MUTED)
    points = [
        (chart_left + 12, chart_top + 18),
        (chart_left + 54, chart_top + 34),
        (chart_left + 96, chart_top + 54),
        (chart_left + 140, chart_top + 76),
        (chart_left + 188, chart_top + 96),
    ]
    for start, end in zip(points, points[1:]):
        add_line(slide, start[0], start[1], end[0], end[1], color=ACCENT_2, weight=2.25)
    add_line(slide, chart_left + 154, chart_top + 18, chart_left + 154, chart_top + 110, color=ACCENT, weight=1.5, end_arrow=True)
    add_textbox(slide, chart_left + 162, chart_top + 44, 70, 14, "Headroom", 10, MUTED)

    alloc_left = right_left + 24
    alloc_top = 376
    add_textbox(slide, alloc_left, alloc_top - 18, 130, 14, "Dynamic reallocation", 10, MUTED)
    labels = ["SEARCH", "INVENTORY", "SOCIAL"]
    before = [64, 92, 78]
    after = [108, 70, 56]
    for idx, label in enumerate(labels):
        y = alloc_top + idx * 32
        add_textbox(slide, alloc_left, y - 1, 70, 14, label, 10, TEXT, bold=True)
        base_left = alloc_left + 84
        add_rect(slide, base_left, y, before[idx], 10, 0x4A4A4A, None, rounded=False)
        add_rect(slide, base_left, y, after[idx], 10, ACCENT, None, rounded=False)

    add_textbox(slide, 44, 486, 360, 24, "Every EUR is traceable to sales impact", 15, ACCENT_2, bold=True)
    add_footer(slide)


def build_slide_2(slide):
    set_bg(slide)

    if BG_IMAGE_PATH.exists():
        add_picture(slide, BG_IMAGE_PATH, 520, 12, 500, 375)
        add_overlay(slide, 0, 0, 960, 540, BG, 0.24)
        add_overlay(slide, 608, 0, 352, 540, 0x0C0C0C, 0.50)

    add_textbox(slide, 44, 32, 520, 32, "REVERSE FUNNEL OPERATING LOGIC", 25, TEXT, bold=True)
    add_textbox(slide, 44, 64, 420, 20, "Decision engine, not media plan", 13, MUTED)

    left = 44
    top = 108
    col_gap = 24
    box_w = 266
    box_h = 84

    blocks = [
        ("01", "START FROM SALES", "Budget derived from targets, not guesses"),
        ("02", "FIND THE GAP", "Quantify inefficiencies across the funnel"),
        ("03", "REALLOCATE", "Shift spend to highest marginal return"),
        ("04", "SCALE SYSTEM", "Codified learnings across markets"),
    ]

    positions = [
        (left, top),
        (left + box_w + col_gap, top),
        (left, top + box_h + 18),
        (left + box_w + col_gap, top + box_h + 18),
    ]

    for (num, title, body), (x, y) in zip(blocks, positions):
        add_rect(slide, x, y, box_w, box_h, SURFACE, LINE, rounded=True)
        add_textbox(slide, x + 18, y + 14, 28, 18, num, 12, ACCENT, bold=True)
        add_textbox(slide, x + 54, y + 14, 180, 18, title, 13, TEXT, bold=True)
        add_textbox(slide, x + 18, y + 42, box_w - 36, 24, body, 12, MUTED)

    output_y = top + 2 * (box_h + 18)
    output_w = box_w * 2 + col_gap
    add_rect(slide, left, output_y, output_w, 92, SURFACE_2, ACCENT, rounded=True)
    add_textbox(slide, left + 18, output_y + 16, 48, 18, "05", 12, ACCENT_2, bold=True)
    add_textbox(slide, left + 54, output_y + 14, 220, 18, "OUTPUT", 14, TEXT, bold=True)
    add_textbox(slide, left + 18, output_y + 44, 280, 18, "Always-on decision engine", 20, TEXT, bold=True)
    add_textbox(slide, left + 316, output_y + 44, 190, 18, "Target in. Allocation out.", 12, MUTED)

    right_left = 660
    add_textbox(slide, right_left, 116, 180, 16, "ALLOCATION VIEW", 10, MUTED, bold=True)

    chart_left = right_left
    chart_top = 144
    chart_w = 220
    chart_h = 126
    add_line(slide, chart_left, chart_top + chart_h, chart_left + chart_w, chart_top + chart_h, color=LINE, weight=1)
    add_line(slide, chart_left, chart_top + chart_h, chart_left, chart_top, color=LINE, weight=1)
    add_textbox(slide, chart_left - 2, chart_top - 18, 100, 14, "Marginal return", 9, MUTED)
    add_textbox(slide, chart_left + chart_w - 12, chart_top + chart_h + 6, 44, 14, "Spend", 9, MUTED)
    points = [
        (chart_left + 14, chart_top + 22),
        (chart_left + 60, chart_top + 40),
        (chart_left + 112, chart_top + 66),
        (chart_left + 166, chart_top + 88),
        (chart_left + 204, chart_top + 102),
    ]
    for start, end in zip(points, points[1:]):
        add_line(slide, start[0], start[1], end[0], end[1], color=ACCENT_2, weight=2.25)
    add_line(slide, chart_left + 172, chart_top + 18, chart_left + 172, chart_top + 108, color=ACCENT, weight=1.5, end_arrow=True)
    add_textbox(slide, chart_left + 180, chart_top + 46, 66, 14, "Headroom", 10, MUTED)

    bars_top = 324
    add_textbox(slide, right_left, bars_top - 22, 160, 14, "Budget shift by channel", 10, MUTED)
    labels = ["SEARCH", "INVENTORY", "SOCIAL"]
    before = [76, 102, 68]
    after = [122, 78, 52]
    for idx, label in enumerate(labels):
        y = bars_top + idx * 40
        add_textbox(slide, right_left, y - 1, 84, 14, label, 10, TEXT, bold=True)
        x0 = right_left + 96
        add_rect(slide, x0, y, before[idx], 12, 0x494949, None, rounded=False)
        add_rect(slide, x0, y, after[idx], 12, ACCENT, None, rounded=False)

    add_textbox(slide, right_left, 458, 220, 16, "Reallocate before channels saturate", 11, ACCENT_2, bold=True)
    add_footer(slide)


def main():
    pythoncom.CoInitialize()
    powerpoint = win32com.client.Dispatch("PowerPoint.Application")
    powerpoint.Visible = 1

    presentation = powerpoint.Presentations.Add()
    presentation.PageSetup.SlideWidth = 960
    presentation.PageSetup.SlideHeight = 540

    slide1 = presentation.Slides.Add(1, PP_LAYOUT_BLANK)
    build_slide_1(slide1)

    slide2 = presentation.Slides.Add(2, PP_LAYOUT_BLANK)
    build_slide_2(slide2)

    presentation.SaveAs(str(OUTPUT_PATH))
    presentation.Close()
    powerpoint.Quit()
    pythoncom.CoUninitialize()

    print(f"Saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
