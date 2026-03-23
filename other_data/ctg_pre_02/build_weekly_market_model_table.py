#!/usr/bin/env python3
"""
Build a combined weekly table from the CTG pre-02 Excel workbook.

Source:
  other_data/ctg_pre_02/20260302_CTG_RAWdata_Cost_Leads.xlsx

Sheets:
  PD Conv / PD Costs
  POF Conv / POF Costs
  PCGB Conv / PCGB Costs
  PIT Conv / PIT Costs
  PCL Conv / PCL Costs

Each sheet contains weekly blocks:
  - A numeric Excel date serial in column A marks a week boundary.
  - Date rows are not campaign rows and are only used to set the current week.
  - Every non-date row is ingested and attached to the current week.

Output schema:
  market,model,channel,week,icc_dcfs,model_dcfs,finder_dcfs,dcfs,spend

Rules:
  - Conversion is DCFS → stored in icc_dcfs, and dcfs mirrors icc_dcfs.
  - model_dcfs and finder_dcfs are NaN (not available in this dataset).
  - channel is always "paid search".
  - model is inferred from campaign strings; non‑matching rows are labeled "none".
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import pathlib
import re
import zipfile
import xml.etree.ElementTree as ET


NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _parse_shared_strings(zf: zipfile.ZipFile):
    try:
        xml = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(xml)
    strings = []
    for si in root.findall("x:si", NS):
        text_parts = [t.text or "" for t in si.findall(".//x:t", NS)]
        strings.append("".join(text_parts))
    return strings


def _col_letter(cell_ref: str) -> str:
    return re.sub(r"\d", "", cell_ref)


def _excel_serial_to_week(serial: float) -> str:
    base = dt.datetime(1899, 12, 30)
    date = base + dt.timedelta(days=float(serial))
    iso = date.isocalendar()
    return f"{iso.year}-{iso.week:02d}"


def _infer_model(text: str):
    if not text:
        return None
    t = str(text).lower()
    if "macan" in t:
        return "macan"
    if "cayenne" in t:
        return "cayenne"
    if "taycan" in t:
        return "taycan"
    if "panamera" in t:
        return "panamera"
    if "911" in t:
        return "911"
    if "718" in t:
        return "718"
    return None


def _load_workbook_sheets(zf: zipfile.ZipFile):
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    sheets = {}
    for sheet in wb.findall("x:sheets/x:sheet", NS):
        name = sheet.attrib["name"]
        rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        sheets[rel_id] = name

    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {}
    for rel in rels.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
        rel_map[rel.attrib["Id"]] = rel.attrib["Target"]

    sheet_files = {}
    for rel_id, name in sheets.items():
        target = rel_map.get(rel_id)
        if target:
            sheet_files[name] = f"xl/{target}"
    return sheet_files


def _parse_sheet_rows(zf: zipfile.ZipFile, sheet_path: str, shared_strings):
    xml = zf.read(sheet_path)
    root = ET.fromstring(xml)
    rows = []
    for row in root.findall("x:sheetData/x:row", NS):
        cells = {}
        for c in row.findall("x:c", NS):
            ref = c.attrib.get("r")
            if not ref:
                continue
            col = _col_letter(ref)
            v = c.find("x:v", NS)
            if v is None:
                continue
            val = v.text
            if c.attrib.get("t") == "s":
                try:
                    val = shared_strings[int(val)]
                except Exception:
                    pass
            cells[col] = val
        if cells:
            rows.append(cells)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="other_data/ctg_pre_02/20260302_CTG_RAWdata_Cost_Leads.xlsx",
        help="Input Excel workbook path.",
    )
    parser.add_argument(
        "--output",
        default="other_data/ctg_pre_02/weekly_market_model_table.csv",
        help="Output CSV path.",
    )
    args = parser.parse_args()

    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    records = []
    with zipfile.ZipFile(input_path, "r") as zf:
        shared_strings = _parse_shared_strings(zf)
        sheet_files = _load_workbook_sheets(zf)

        market_name_map = {
            "PD": "GERMANY",
            "PIT": "ITALY",
            "POF": "FRANCE",
            "PCGB": "UK",
            "PCL": "CANADA",
        }
        for sheet_name, sheet_path in sheet_files.items():
            if not sheet_name.endswith(("Conv", "Cost", "Costs")):
                continue
            market_code = sheet_name.split()[0].upper()
            market = market_name_map.get(market_code, market_code)
            metric = "icc_dcfs" if sheet_name.endswith("Conv") else "spend"
            rows = _parse_sheet_rows(zf, sheet_path, shared_strings)
            current_week = None
            for row in rows:
                a = row.get("A")
                b = row.get("B")
                if a is None or b is None:
                    continue
                # Detect week boundary (Excel date serial in column A)
                try:
                    a_num = float(a)
                except Exception:
                    a_num = None
                if a_num is not None and a_num >= 40000:
                    current_week = _excel_serial_to_week(a_num)
                    continue
                if current_week is None:
                    continue
                try:
                    b_num = float(b)
                except Exception:
                    continue
                model = _infer_model(a)
                if model is None:
                    model = "none"
                records.append({
                    "market": market,
                    "model": model,
                    "channel": "Paid Search",
                    "week": current_week,
                    metric: b_num,
                })

    if not records:
        raise SystemExit("No records found. Check sheet parsing.")

    pivot = {}
    for r in records:
        key = (r["market"], r["model"], r["channel"], r["week"])
        if key not in pivot:
            pivot[key] = {
                "market": r["market"],
                "model": r["model"],
                "channel": r["channel"],
                "week": r["week"],
            }
        if "icc_dcfs" in r:
            pivot[key]["icc_dcfs"] = r["icc_dcfs"]
        if "spend" in r:
            pivot[key]["spend"] = r["spend"]

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
            icc_dcfs = row.get("icc_dcfs", math.nan)
            spend = row.get("spend", math.nan)
            row_out = {
                "market": row.get("market"),
                "model": row.get("model"),
                "channel": row.get("channel"),
                "week": row.get("week"),
                "icc_dcfs": icc_dcfs,
                "model_dcfs": math.nan,
                "finder_dcfs": math.nan,
                "dcfs": icc_dcfs,
                "spend": spend,
            }
            writer.writerow(row_out)
    print(f"Wrote {len(pivot)} rows to {output_path}")


if __name__ == "__main__":
    main()
