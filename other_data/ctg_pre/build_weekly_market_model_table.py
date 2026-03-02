#!/usr/bin/env python3
"""
Build a combined weekly table from Excel files in other_data/ctg_pre.

Expected filename pattern:
  <kpi>_<model>_<market>.xlsx (e.g., icc_dcfs_cayenne_canada.xlsx)

Sheet structure (sheet 1 / index 0):
  - Header row contains week labels across columns (YYYY-WW).
  - Data rows contain a channel name in column A and values across week columns.

Output:
  Wide CSV with columns: market, model, channel, week,
  icc_dcfs, model_dcfs, finder_dcfs, dcfs, spend
"""
from __future__ import annotations

import argparse
import csv
import math
import pathlib
import re
import zipfile
import xml.etree.ElementTree as ET


WEEK_RE = re.compile(r"^\d{4}-\d{2}$")


def _col_letter(cell_ref: str) -> str:
    return re.sub(r"\d", "", cell_ref)


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


def _parse_filename(path: pathlib.Path):
    stem = path.stem
    # pattern: kpi_model_market (kpi has known prefixes, model can contain underscores)
    kpi_prefixes = ["icc_dcfs", "model_dcfs", "finder_dcfs", "spend"]
    for kpi in kpi_prefixes:
        prefix = f"{kpi}_"
        if stem.startswith(prefix):
            remainder = stem[len(prefix):]
            parts = remainder.split("_")
            if len(parts) < 2:
                return None, None, None
            market = parts[-1].upper()
            model = "_".join(parts[:-1]).lower()
            return kpi, model, market
    return None, None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        default="other_data/ctg_pre",
        help="Directory containing Excel files.",
    )
    parser.add_argument(
        "--output",
        default="other_data/ctg_pre/weekly_market_model_table.csv",
        help="Output CSV path.",
    )
    args = parser.parse_args()

    input_dir = pathlib.Path(args.input_dir)
    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")

    rows = []
    for path in sorted(input_dir.glob("*.xlsx")):
        kpi, model, market = _parse_filename(path)
        if not kpi or not model or not market:
            continue
        with zipfile.ZipFile(path, "r") as zf:
            shared_strings = _parse_shared_strings(zf)
            sheet_rows = _parse_sheet(zf, shared_strings)
        if not sheet_rows:
            continue
        header = sheet_rows[0]
        week_cols = [
            col
            for col, val in header.items()
            if isinstance(val, str) and WEEK_RE.match(val.strip())
        ]
        if not week_cols:
            continue
        for row in sheet_rows[1:]:
            channel = row.get("A")
            if channel is None:
                continue
            for col in week_cols:
                week = header.get(col)
                val = row.get(col)
                if week is None or val is None:
                    continue
                try:
                    value = float(val)
                except Exception:
                    continue
                rows.append({
                    "market": market,
                    "model": model,
                    "channel": channel,
                    "week": week,
                    "kpi": kpi,
                    "value": value,
                })

    if not rows:
        raise SystemExit("No rows found. Check file patterns and sheet structure.")

    pivot = {}
    for r in rows:
        key = (r["market"], r["model"], r["channel"], r["week"])
        if key not in pivot:
            pivot[key] = {
                "market": r["market"],
                "model": r["model"],
                "channel": r["channel"],
                "week": r["week"],
            }
        pivot[key][r["kpi"]] = r["value"]

    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "market",
        "model",
        "channel",
        "week",
        "icc_dcfs",
        "model_dcfs",
        "finder_dcfs",
        "dcfs",
        "spend",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in pivot.values():
            row_out = {
                "market": row.get("market"),
                "model": row.get("model"),
                "channel": row.get("channel"),
                "week": row.get("week"),
                "icc_dcfs": row.get("icc_dcfs", math.nan),
                "model_dcfs": row.get("model_dcfs", math.nan),
                "finder_dcfs": row.get("finder_dcfs", math.nan),
                "spend": row.get("spend", math.nan),
            }
            parts = [
                row_out["icc_dcfs"],
                row_out["model_dcfs"],
                row_out["finder_dcfs"],
            ]
            if any(not isinstance(val, (int, float)) or math.isnan(val) for val in parts):
                row_out["dcfs"] = math.nan
            else:
                row_out["dcfs"] = sum(float(val) for val in parts)
            writer.writerow(row_out)
    print(f"Wrote {len(pivot)} rows to {output_path}")


if __name__ == "__main__":
    main()
