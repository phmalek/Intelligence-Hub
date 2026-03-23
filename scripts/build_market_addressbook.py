from __future__ import annotations

import csv
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}


@dataclass
class Record:
    market: str
    section: str
    name: str
    title: str
    email: str
    notes: str
    source_sheet: str


class WorkbookReader:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.shared_strings: List[str] = []
        self.sheet_targets: Dict[str, str] = {}
        self._load_workbook()

    def _load_workbook(self) -> None:
        with zipfile.ZipFile(self.path) as zf:
            if "xl/sharedStrings.xml" in zf.namelist():
                root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                for si in root.findall("a:si", NS):
                    text = "".join(t.text or "" for t in si.findall(".//a:t", NS))
                    self.shared_strings.append(text)

            workbook = ET.fromstring(zf.read("xl/workbook.xml"))
            relationships = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            rid_to_target = {
                rel.attrib["Id"]: rel.attrib["Target"]
                for rel in relationships.findall("pr:Relationship", NS)
            }
            for sheet in workbook.find("a:sheets", NS):
                name = sheet.attrib["name"]
                rid = sheet.attrib[
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                ]
                self.sheet_targets[name] = "xl/" + rid_to_target[rid]

    def rows(self, sheet_name: str) -> List[List[str]]:
        with zipfile.ZipFile(self.path) as zf:
            ws = ET.fromstring(zf.read(self.sheet_targets[sheet_name]))

        parsed: List[List[str]] = []
        for row in ws.findall(".//a:sheetData/a:row", NS):
            mapping: Dict[int, str] = {}
            max_col = 0
            for cell in row.findall("a:c", NS):
                ref = cell.attrib.get("r", "A1")
                col_match = re.match(r"([A-Z]+)", ref)
                if not col_match:
                    continue
                col_num = 0
                for ch in col_match.group(1):
                    col_num = (col_num * 26) + ord(ch) - 64
                max_col = max(max_col, col_num)

                cell_type = cell.attrib.get("t")
                value_node = cell.find("a:v", NS)
                inline_node = cell.find("a:is", NS)
                value = ""
                if cell_type == "s" and value_node is not None:
                    value = self.shared_strings[int(value_node.text)]
                elif cell_type == "inlineStr" and inline_node is not None:
                    value = "".join(t.text or "" for t in inline_node.findall(".//a:t", NS))
                elif value_node is not None:
                    value = value_node.text or ""
                mapping[col_num] = value.replace("\xa0", " ").strip()

            if max_col:
                row_values = [mapping.get(i, "") for i in range(1, max_col + 1)]
                if any(v.strip() for v in row_values):
                    parsed.append(row_values)
        return parsed


def split_emails(raw: str) -> List[str]:
    parts = re.split(r"[\n,;]+", raw)
    cleaned = []
    for part in parts:
        email = part.strip()
        if email:
            cleaned.append(email)
    return cleaned


def normalize_market(value: str) -> str:
    return value.strip()


def add_record(records: List[Record], **kwargs: str) -> None:
    email = kwargs["email"].strip()
    if not email:
        return
    records.append(Record(**{k: v.strip() for k, v in kwargs.items()}))


def build_records(reader: WorkbookReader) -> List[Record]:
    records: List[Record] = []

    for row in reader.rows("Market Key Contacts"):
        if len(row) < 7 or row[2] in {"", "Market", "Market Key Contacts"}:
            continue
        market = normalize_market(row[2])
        name = row[3]
        title = row[4]
        comments = row[6]
        cluster = row[1]
        notes = "; ".join(v for v in [f"Cluster: {cluster}" if cluster else "", comments] if v)
        for email in split_emails(row[5]):
            add_record(
                records,
                market=market,
                section="Market Key Contact",
                name=name,
                title=title,
                email=email,
                notes=notes,
                source_sheet="Market Key Contacts",
            )

    for sheet_name, section in [
        ("Digital Contacts", "Digital Contact"),
        ("Search Contacts", "Search Contact"),
    ]:
        for row in reader.rows(sheet_name):
            if len(row) < 5 or row[1] in {"", "Market", "Market Contacts", sheet_name}:
                continue
            market = normalize_market(row[1])
            for email in split_emails(row[4]):
                add_record(
                    records,
                    market=market,
                    section=section,
                    name=row[2],
                    title=row[3],
                    email=email,
                    notes="",
                    source_sheet=sheet_name,
                )

    for row in reader.rows("Omni Champions"):
        if len(row) < 4 or row[1] in {"", "Market", "Omni Champions"}:
            continue
        market = normalize_market(row[1])
        for email in split_emails(row[3]):
            add_record(
                records,
                market=market,
                section="Omni Champion",
                name=row[2],
                title="",
                email=email,
                notes="",
                source_sheet="Omni Champions",
            )

    current_market = ""
    for row in reader.rows("PlanIt Champions"):
        if len(row) < 3 or row[1] == "Market":
            continue
        if row[1]:
            current_market = normalize_market(row[1])
        if not current_market:
            continue
        for email in split_emails(row[2]):
            add_record(
                records,
                market=current_market,
                section="PlanIt Champion",
                name="",
                title="",
                email=email,
                notes="",
                source_sheet="PlanIt Champions",
            )

    for row in reader.rows("PAG Client Contacts"):
        if len(row) < 6 or row[1] in {"", "First name", "Porsche Contacts"}:
            continue
        first = row[1].strip()
        last = row[2].strip()
        name = (first + " " + last).strip()
        market = normalize_market(row[4])
        notes = row[5] if len(row) > 5 else ""
        if len(row) > 6 and row[6]:
            notes = "; ".join(v for v in [notes, row[6]] if v)
        add_record(
            records,
            market=market,
            section="PAG Client Contact",
            name=name,
            title="",
            email=row[3],
            notes=notes,
            source_sheet="PAG Client Contacts",
        )

    return records


def enrich_records(records: List[Record]) -> List[Record]:
    by_email: Dict[str, Record] = {}
    priority = {
        "Market Key Contact": 5,
        "Digital Contact": 4,
        "Search Contact": 4,
        "Omni Champion": 3,
        "PlanIt Champion": 2,
        "PAG Client Contact": 1,
    }
    for record in records:
        email_key = record.email.lower()
        existing = by_email.get(email_key)
        if existing is None or priority[record.section] > priority[existing.section]:
            by_email[email_key] = record

    enriched: List[Record] = []
    seen = set()
    for record in records:
        template = by_email.get(record.email.lower())
        name = record.name or (template.name if template else "")
        title = record.title or (template.title if template else "")
        market = record.market or (template.market if template else "")
        key = (market.lower(), record.section.lower(), name.lower(), title.lower(), record.email.lower())
        if key in seen:
            continue
        seen.add(key)
        enriched.append(
            Record(
                market=market,
                section=record.section,
                name=name,
                title=title,
                email=record.email,
                notes=record.notes,
                source_sheet=record.source_sheet,
            )
        )
    return enriched


def write_csv(records: Iterable[Record], output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["market", "section", "name", "title", "email", "notes", "source_sheet"])
        for record in sorted(records, key=lambda r: (r.market.lower(), r.section.lower(), r.name.lower(), r.email.lower())):
            writer.writerow([record.market, record.section, record.name, record.title, record.email, record.notes, record.source_sheet])


def main() -> int:
    source = Path("UTM_data/PHD Local Market Key Contacts MASTER.xlsx")
    output = Path("UTM_data/PHD_Local_Market_Addressbook.csv")
    reader = WorkbookReader(source)
    records = build_records(reader)
    enriched = enrich_records(records)
    write_csv(enriched, output)
    print(f"Wrote {len(enriched)} records to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
