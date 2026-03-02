#!/usr/bin/env python3
"""
Build a combined CSV joining market performance files with media spend.

Join logic options (enable via flags):
  --substring : manual campaign name is a substring of campaign_string
  --token     : token overlap score above threshold
  --fuzzy     : fuzzy match (difflib) above threshold
  --id        : numeric campaign ID match (len >= 6)

Output columns:
  market, manual_campaign_name, sessions_total, spend_budget,
  matched_campaign_strings, match_strategy, match_score
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import difflib


def _norm(text: str) -> str:
    return "".join(ch.lower() for ch in text.strip() if ch.isalnum())


def _extract_ids(text: str, min_len: int = 5):
    ids = []
    current = []
    for ch in text:
        if ch.isalnum():
            current.append(ch)
        else:
            if len(current) >= min_len:
                ids.append("".join(current))
            current = []
    if len(current) >= min_len:
        ids.append("".join(current))
    return ids


def _tokenize(text: str):
    return [t for t in _norm(text).split() if t]


def _token_overlap(a: str, b: str):
    a_tokens = set(_tokenize(a))
    b_tokens = set(_tokenize(b))
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / max(1, len(a_tokens))


def _load_spend(path: pathlib.Path, min_len: int):
    spend_rows = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            spend_rows.append({
                "country": (row.get("country") or "").strip(),
                "campaign": (row.get("campaign") or "").strip(),
                "campaign_string": (row.get("campaign_string") or "").strip(),
                "budget": row.get("budget"),
                "budget_num": float(row["budget"]) if row.get("budget") not in (None, "", "nan") else None,
                "campaign_string_norm": _norm(row.get("campaign_string") or ""),
                "campaign_ids": _extract_ids(row.get("campaign_string") or "", min_len=min_len),
            })
    return spend_rows


def _load_performance(path: pathlib.Path):
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        data_rows = []
        header_idx = None
        for idx, row in enumerate(reader):
            if not row:
                continue
            if row[0].startswith("#"):
                continue
            data_rows.append(row)
            if row and row[0].strip().lower() == "country":
                header_idx = len(data_rows) - 1
                break
        if header_idx is None:
            return rows
        header = data_rows[header_idx]
        country_idx = header.index("country")
        manual_idx = header.index("Manual campaign name")

        for row in reader:
            if not row or (row[0].startswith("#")):
                continue
            if len(row) <= manual_idx:
                continue
            country = (row[country_idx] or "").strip()
            manual = (row[manual_idx] or "").strip()
            if not country and not manual:
                continue
            if "grand total" in " ".join(row).lower():
                continue
            # take last numeric as sessions total
            total = None
            for cell in reversed(row):
                try:
                    total = float(cell)
                    break
                except Exception:
                    continue
            rows.append({
                "market": country,
                "manual_campaign_name": manual,
                "sessions_total": total,
            })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--substring", action="store_true", help="Enable substring matching")
    parser.add_argument("--token", action="store_true", help="Enable token overlap matching")
    parser.add_argument("--fuzzy", action="store_true", help="Enable fuzzy matching")
    parser.add_argument("--id", action="store_true", help="Enable numeric ID matching")
    parser.add_argument("--id-min-length", type=int, default=5, help="Minimum length for numeric IDs")
    parser.add_argument("--token-threshold", type=float, default=0.4)
    parser.add_argument("--fuzzy-threshold", type=float, default=0.75)
    args = parser.parse_args()

    # default: enable all strategies
    if not (args.substring or args.token or args.fuzzy or args.id):
        args.substring = args.token = args.fuzzy = args.id = True

    base = pathlib.Path("other_data/ctg_pre_01")
    spend_path = base / "media_spend_clean.csv"
    if not spend_path.exists():
        raise SystemExit(f"Missing spend CSV: {spend_path}")
    spend_rows = _load_spend(spend_path, min_len=args.id_min_length)

    perf_rows = []
    for path in sorted(base.glob("* Dealer Submits.csv")):
        perf_rows.extend(_load_performance(path))

    # Build index by campaign id
    id_index = {}
    for s in spend_rows:
        for cid in s["campaign_ids"]:
            id_index.setdefault(cid, []).append(s)

    out_rows = []
    match_counts = {"id": 0, "substring": 0, "token": 0, "fuzzy": 0, "none": 0}
    id_match_counts = {}
    for row in perf_rows:
        manual = row["manual_campaign_name"]
        manual_norm = _norm(manual)
        manual_ids = _extract_ids(manual, min_len=args.id_min_length)
        matches = []
        spend_total = 0.0
        best_strategy = None
        best_score = None

        if args.id and manual_ids:
            for cid in manual_ids:
                for s in id_index.get(cid, []):
                    if s["budget_num"] is not None:
                        spend_total += s["budget_num"]
                    matches.append(s["campaign_string"])
            if matches:
                best_strategy = "id"
                best_score = 1.0
                for cid in manual_ids:
                    if cid in id_index:
                        id_match_counts[cid] = id_match_counts.get(cid, 0) + 1

        if args.substring and manual_norm and not matches:
            for s in spend_rows:
                if manual_norm and manual_norm in s["campaign_string_norm"]:
                    if s["budget_num"] is not None:
                        spend_total += s["budget_num"]
                    matches.append(s["campaign_string"])
            if matches:
                best_strategy = "substring"
                best_score = 1.0

        if args.token and manual_norm and not matches:
            for s in spend_rows:
                score = _token_overlap(manual, s["campaign_string"])
                if score >= args.token_threshold:
                    if s["budget_num"] is not None:
                        spend_total += s["budget_num"]
                    matches.append(s["campaign_string"])
            if matches:
                best_strategy = "token"
                best_score = args.token_threshold

        if args.fuzzy and manual_norm and not matches:
            for s in spend_rows:
                score = difflib.SequenceMatcher(None, manual_norm, s["campaign_string_norm"]).ratio()
                if score >= args.fuzzy_threshold:
                    if s["budget_num"] is not None:
                        spend_total += s["budget_num"]
                    matches.append(s["campaign_string"])
            if matches:
                best_strategy = "fuzzy"
                best_score = args.fuzzy_threshold

        out_rows.append({
            "market": row["market"],
            "manual_campaign_name": manual,
            "sessions_total": row["sessions_total"],
            "spend_budget": spend_total if matches else None,
            "matched_campaign_strings": " | ".join(matches[:5]) if matches else "",
            "match_strategy": best_strategy or "",
            "match_score": best_score,
        })
        match_counts[best_strategy or "none"] += 1

    output_path = base / "campaign_performance_with_spend.csv"
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "market",
                "manual_campaign_name",
                "sessions_total",
                "spend_budget",
                "matched_campaign_strings",
                "match_strategy",
                "match_score",
            ],
        )
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"Wrote {output_path}")
    total = sum(match_counts.values())
    print("Match stats:")
    for key in ["id", "substring", "token", "fuzzy", "none"]:
        count = match_counts.get(key, 0)
        pct = (count / total * 100.0) if total else 0.0
        print(f"  {key:9s}: {count:5d} ({pct:5.1f}%)")
    if id_match_counts:
        top_ids = sorted(id_match_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        print("Top matched IDs:")
        for cid, count in top_ids:
            print(f"  {cid}: {count}")


if __name__ == "__main__":
    main()
