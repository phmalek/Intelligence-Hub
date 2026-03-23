#!/usr/bin/env python3
"""
Enrich matched campaign-week stats with model, market name, conversion and spend.

Input matched CSV schema:
  market,campaign_name,week

Output (same file, overwritten):
  market,market_name,campaign_name,week,model,conv,spend

Matching key:
  (market_code, campaign_name, week)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import pathlib
import re
import zipfile
import xml.etree.ElementTree as ET


NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

MARKET_NAME = {
    "PD": "Germany",
    "PCL": "Canada",
    "PCGB": "UK",
    "POF": "France",
    "PIT": "Italy",
}


def _excel_serial_to_week(serial: float) -> str:
    base = dt.datetime(1899, 12, 30)
    date = base + dt.timedelta(days=float(serial))
    iso = date.isocalendar()
    return f"{iso.year}-{iso.week:02d}"


def _infer_model(text: str) -> str:
    s = (text or "").lower()
    if "macan" in s:
        return "macan"
    if "cayenne" in s:
        return "cayenne"
    if "taycan" in s:
        return "taycan"
    if "panamera" in s:
        return "panamera"
    if "911" in s:
        return "911"
    if "718" in s:
        return "718"
    return "none"


def _col_letter(cell_ref: str) -> str:
    return re.sub(r"\d", "", cell_ref)


def _parse_shared_strings(zf: zipfile.ZipFile):
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    out = []
    for si in root.findall("x:si", NS):
        out.append("".join((t.text or "") for t in si.findall(".//x:t", NS)))
    return out


def _sheet_map(zf: zipfile.ZipFile):
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
    }
    return {
        s.attrib["name"]: f"xl/{rid_to_target[s.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]}"
        for s in wb.findall("x:sheets/x:sheet", NS)
    }


def _extract_metric_map(zf: zipfile.ZipFile, sheet_path: str, shared_strings):
    """
    Return dict[(campaign_name, week)] = metric_value for a single sheet.
    """
    root = ET.fromstring(zf.read(sheet_path))
    out = {}
    current_week = None
    for row in root.findall("x:sheetData/x:row", NS):
        cells = {}
        for c in row.findall("x:c", NS):
            ref = c.attrib.get("r", "")
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
        if not cells:
            continue
        a = cells.get("A")
        b = cells.get("B")
        if a is None or b is None:
            continue
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
            metric = float(b)
        except Exception:
            continue
        campaign = str(a).strip()
        if not campaign:
            continue
        out[(campaign, current_week)] = metric
    return out


def build_lookup(workbook_path: pathlib.Path):
    """
    Build lookup:
      lookup[(market_code, campaign, week)] = {"conv": x, "spend": y}
    """
    lookup = {}
    with zipfile.ZipFile(workbook_path, "r") as zf:
        shared = _parse_shared_strings(zf)
        sheets = _sheet_map(zf)
        for market_code in ["PD", "POF", "PCGB", "PCL", "PIT"]:
            conv_sheet = f"{market_code} Conv"
            cost_sheet = f"{market_code} Cost" if f"{market_code} Cost" in sheets else f"{market_code} Costs"
            if conv_sheet not in sheets or cost_sheet not in sheets:
                continue
            conv_map = _extract_metric_map(zf, sheets[conv_sheet], shared)
            cost_map = _extract_metric_map(zf, sheets[cost_sheet], shared)
            all_keys = set(conv_map.keys()) | set(cost_map.keys())
            for campaign, week in all_keys:
                lookup[(market_code, campaign, week)] = {
                    "conv": conv_map.get((campaign, week)),
                    "spend": cost_map.get((campaign, week)),
                }
    return lookup


def enrich(matched_csv: pathlib.Path, lookup):
    with matched_csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    for r in rows:
        market = (r.get("market") or "").strip()
        campaign = (r.get("campaign_name") or "").strip()
        week = (r.get("week") or "").strip()
        m = lookup.get((market, campaign, week), {})
        out_rows.append(
            {
                "market": market,
                "market_name": MARKET_NAME.get(market, market),
                "campaign_name": campaign,
                "week": week,
                "model": _infer_model(campaign),
                "conv": m.get("conv"),
                "spend": m.get("spend"),
            }
        )

    with matched_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["market", "market_name", "campaign_name", "week", "model", "conv", "spend"],
        )
        w.writeheader()
        w.writerows(out_rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workbook", required=True, help="Workbook path (.xlsx)")
    p.add_argument("--matched-csv", required=True, help="Matched CSV to enrich (overwritten)")
    args = p.parse_args()

    workbook = pathlib.Path(args.workbook)
    matched = pathlib.Path(args.matched_csv)
    if not workbook.exists():
        raise SystemExit(f"Workbook not found: {workbook}")
    if not matched.exists():
        raise SystemExit(f"Matched CSV not found: {matched}")

    lookup = build_lookup(workbook)
    enrich(matched, lookup)
    print(f"Enriched: {matched}")


if __name__ == "__main__":
    main()
