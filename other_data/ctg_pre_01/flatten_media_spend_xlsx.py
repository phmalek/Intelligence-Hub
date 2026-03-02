#!/usr/bin/env python3
"""
Flatten the media spend Excel into a raw CSV with no filtering.

Reads sheet1 from:
  x Full Data SCHEMATIC 27 Feb 2026 14 24 15_Ali data request.xlsx

Outputs:
  other_data/ctg_pre_01/media_spend_flat.csv
"""
from __future__ import annotations

import csv
import pathlib
import zipfile
import xml.etree.ElementTree as ET


def _col_letter(cell_ref: str) -> str:
    out = []
    for ch in cell_ref:
        if ch.isdigit():
            break
        out.append(ch)
    return "".join(out)


def _parse_shared_strings(zf: zipfile.ZipFile):
    try:
        xml = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(xml)
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings = []
    for si in root.findall("x:si", ns):
        text_parts = [t.text or "" for t in si.findall(".//x:t", ns)]
        strings.append("".join(text_parts))
    return strings


def _parse_sheet(zf: zipfile.ZipFile, shared_strings):
    xml = zf.read("xl/worksheets/sheet1.xml")
    root = ET.fromstring(xml)
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows = []
    for row in root.findall("x:sheetData/x:row", ns):
        cells = {}
        for c in row.findall("x:c", ns):
            ref = c.attrib.get("r")
            if not ref:
                continue
            col = _col_letter(ref)
            cell_type = c.attrib.get("t")
            v = c.find("x:v", ns)
            if v is None:
                continue
            val = v.text
            if cell_type == "s":
                try:
                    val = shared_strings[int(val)]
                except Exception:
                    pass
            cells[col] = val
        rows.append(cells)
    return rows


def main():
    base = pathlib.Path("other_data/ctg_pre_01")
    xlsx_path = base / "x Full Data SCHEMATIC 27 Feb 2026 14 24 15_Ali data request.xlsx"
    if not xlsx_path.exists():
        raise SystemExit(f"Missing file: {xlsx_path}")

    with zipfile.ZipFile(xlsx_path, "r") as zf:
        shared_strings = _parse_shared_strings(zf)
        sheet_rows = _parse_sheet(zf, shared_strings)

    if not sheet_rows:
        raise SystemExit("No rows found in sheet1.")

    # Determine all columns present in sheet, keep column letters as fallback
    all_cols = set()
    for row in sheet_rows:
        all_cols.update(row.keys())
    columns = []
    header = sheet_rows[0] if sheet_rows else {}
    for col in sorted(all_cols):
        val = header.get(col)
        col_name = str(val).strip() if val not in (None, "") else col
        columns.append((col, col_name))

    output_path = base / "media_spend_flat.csv"
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([name for _, name in columns])
        for row in sheet_rows[1:]:
            writer.writerow([row.get(col, "") for col, _ in columns])

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
