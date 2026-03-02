#!/usr/bin/env python3
"""
Build a clean media spend table from media_spend_flat.csv.

Outputs columns:
  country, campaign, campaign_string, budget
"""
from __future__ import annotations

import csv
import pathlib


def _to_float(val: str):
    try:
        return float(val)
    except Exception:
        return None


def main():
    base = pathlib.Path("other_data/ctg_pre_01")
    flat_path = base / "media_spend_flat.csv"
    if not flat_path.exists():
        raise SystemExit(f"Missing file: {flat_path}")

    rows = []
    with flat_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        all_rows = list(reader)

    header_idx = None
    for i, row in enumerate(all_rows):
        if len(row) >= 3 and row[0] == "Country" and row[1] == "Campaign Name":
            header_idx = i
            break
    if header_idx is None:
        raise SystemExit("Header row not found (Country / Campaign Name).")

    header = all_rows[header_idx]
    data_rows = all_rows[header_idx + 1 :]
    if len(header) < 4:
        raise SystemExit("Header row missing month columns.")

    country_idx = header.index("Country")
    campaign_idx = header.index("Campaign Name")
    campaign_str_idx = header.index("Campaign String")
    value_start = campaign_str_idx + 1

    current_country = None
    for row in data_rows:
        if not row or all(not cell for cell in row):
            continue
        country = row[country_idx] if len(row) > country_idx else ""
        if country:
            current_country = country
        if not current_country:
            continue
        campaign = row[campaign_idx] if len(row) > campaign_idx else ""
        campaign_string = row[campaign_str_idx] if len(row) > campaign_str_idx else ""
        if not campaign and not campaign_string:
            continue
        total = 0.0
        has_value = False
        for val in row[value_start:]:
            num = _to_float(val)
            if num is None:
                continue
            total += num
            has_value = True
        rows.append({
            "country": current_country,
            "campaign": campaign,
            "campaign_string": campaign_string,
            "budget": total if has_value else None,
        })

    output_path = base / "media_spend_clean.csv"
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["country", "campaign", "campaign_string", "budget"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
