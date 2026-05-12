from __future__ import annotations

import argparse
import csv
import mimetypes
import re
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable


@dataclass
class Contact:
    market: str
    section: str
    name: str
    email: str
    market_label: str = ""
    deadline: str = ""
    cc_emails: str = ""


DEFAULT_TO_SECTIONS = ["Market Key Contact", "PAG Client Contact", "PlanIt Champion"]
DEFAULT_CC_SECTIONS = ["PlanIt Champion"]
DEFAULT_MARKET_ALIASES = {
    "pap": "APAC",
    "pca": "Canada",
    "pcee": "PCEE",
    "pcgb": "UK",
    "pch": "Switzerland",
    "pcl": "LATAM",
    "pcna": "USA",
    "pd": "Germany",
    "pit": "Italy",
    "pko": "Korea",
    "pme": "Middle East",
    "pno": "Norway",
    "pof": "France",
    "ppl": "Poland",
    "psg": "Singapore",
    "ptw": "Taiwan",
}


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def parse_market_code_from_filename(file_name: str) -> str | None:
    match = re.match(r"(.+)_UTM_Response\.xlsx$", file_name, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1)


def read_contacts(addressbook_csv: Path) -> list[Contact]:
    contacts: list[Contact] = []
    with addressbook_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            market_code = (row.get("market") or row.get("market_code") or "").strip()
            if not market_code:
                continue
            market_label = (row.get("market_label") or market_code).strip()
            to_names = split_multi(row.get("to_names", ""))
            to_emails = split_multi(row.get("to_emails", ""))
            cc_emails = split_multi(row.get("cc_emails", ""))
            deadline = (row.get("deadline") or "").strip()
            for idx, email in enumerate(to_emails):
                email = email.strip()
                if not email:
                    continue
                contacts.append(
                    Contact(
                        market=market_code,
                        section="Market Key Contact",
                        name=to_names[idx].strip() if idx < len(to_names) else "",
                        email=email,
                        market_label=market_label,
                        deadline=deadline,
                        cc_emails=";".join(cc_emails),
                    )
                )
            for email in cc_emails:
                email = email.strip()
                if not email:
                    continue
                contacts.append(
                    Contact(
                        market=market_code,
                        section="PlanIt Champion",
                        name="",
                        email=email,
                        market_label=market_label,
                        deadline=deadline,
                        cc_emails=";".join(cc_emails),
                    )
                )
    return contacts


def read_aliases(alias_csv: Path | None) -> dict[str, str]:
    aliases: dict[str, str] = dict(DEFAULT_MARKET_ALIASES)
    if alias_csv is None:
        return aliases
    with alias_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = (row.get("market_code") or "").strip()
            market = (row.get("addressbook_market") or "").strip()
            if code and market:
                aliases[normalize_key(code)] = market
    return aliases


def group_contacts_by_market(contacts: Iterable[Contact]) -> dict[str, list[Contact]]:
    grouped: dict[str, list[Contact]] = {}
    for c in contacts:
        key = normalize_key(c.market)
        if not key:
            continue
        grouped.setdefault(key, []).append(c)
    return grouped


def dedupe_emails(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen = set()
    out = []
    for name, email in items:
        k = email.lower().strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append((name.strip(), email.strip()))
    return out


def pick_recipients(
    market_code: str,
    contacts_by_market: dict[str, list[Contact]],
    aliases: dict[str, str],
    to_sections: list[str],
    cc_sections: list[str],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], str, str, list[str]]:
    market_key = normalize_key(market_code)
    contacts = contacts_by_market.get(market_key, [])

    # Optional explicit alias mapping (market code -> addressbook market)
    if not contacts and market_key in aliases:
        alias_market = aliases[market_key]
        contacts = contacts_by_market.get(normalize_key(alias_market), [])

    # If still not found, try broad contains match.
    if not contacts:
        for k, v in contacts_by_market.items():
            if market_key and (market_key in k or k in market_key):
                contacts = v
                break

    selected_market_label = contacts[0].market_label if contacts and contacts[0].market_label else market_code
    selected_deadline = contacts[0].deadline if contacts else ""
    selected_cc_emails = split_multi(contacts[0].cc_emails) if contacts else []

    to_list: list[tuple[str, str]] = []
    for section in to_sections:
        section_contacts = [
            (c.name or c.email.split("@")[0], c.email)
            for c in contacts
            if normalize_key(c.section) == normalize_key(section)
        ]
        if section_contacts:
            to_list = dedupe_emails(section_contacts)
            break

    # Fallback: use first 1-2 contacts if no preferred section exists.
    if not to_list and contacts:
        to_list = dedupe_emails([(c.name or c.email.split("@")[0], c.email) for c in contacts[:2]])

    cc_list = dedupe_emails(
        [
            (c.name or c.email.split("@")[0], c.email)
            for c in contacts
            if normalize_key(c.section) in {normalize_key(s) for s in cc_sections}
        ]
    )
    # Avoid duplicates between To and CC.
    to_emails = {e.lower() for _, e in to_list}
    cc_list = [(n, e) for n, e in cc_list if e.lower() not in to_emails]

    return to_list, cc_list, selected_market_label, selected_deadline, selected_cc_emails


def format_addresses(items: list[tuple[str, str]]) -> str:
    formatted = []
    for name, email in items:
        name = (name or "").strip()
        email = (email or "").strip()
        if not email:
            continue
        if name:
            formatted.append(f"{name} <{email}>")
        else:
            formatted.append(email)
    return ", ".join(formatted)


def build_subject(market_label: str, deadline: str) -> str:
    return f"UTM Response Request – {market_label} – Action Needed by {deadline}"


def build_body(first_name: str, market_label: str, deadline: str) -> str:
    return (
        f"Hi {first_name},\n\n"
        f"I hope you are well.\n\n"
        f"Please find attached your market-specific UTM response form for {market_label}.\n"
        "This file already includes the issues identified in our central review. "
        "Please complete only the response columns in the 'Issue Responses' sheet.\n\n"
        "What we need from you:\n"
        "- confirm/update response traffic light per issue\n"
        "- provide concise response summary and action plan\n"
        "- add response owner name/email and target date\n"
        "- indicate where central support is needed\n\n"
        f"Please return the completed file by **{deadline}**.\n\n"
        "Important: We appreciate if you put all responses directly on the attached sheet, so we can prepare the report timely for the client. "
        "Please do not add any comments or text in the email body or thread, as this disrupts structural processing. "
        "Only reply to this email if there is something that absolutely requires clarification; otherwise, simply attach the completed sheet and send it back.\n\n"
        "Notes:\n"
        "- do not rename sheets or columns\n"
        "- use dropdown values where available\n"
        "- keep one clear response per prefilled issue row\n\n"
        "Thank you for the support.\n\n"
        "Best regards,\n\n"
        "Ali Malek\n"
        "Global Media Data Intelligence Lead - Porsche Account\n"
    )


def write_eml(
    eml_path: Path,
    to_addresses: str,
    cc_addresses: str,
    subject: str,
    body: str,
    attachment_file: Path,
):
    msg = EmailMessage()
    # Parse and validate email addresses
    msg["To"] = to_addresses.strip() if to_addresses else ""
    if cc_addresses and cc_addresses.strip():
        msg["Cc"] = cc_addresses.strip()
    msg["Subject"] = subject
    msg["From"] = "ali.malek@omc.com"
    msg.set_content(body)

    content = attachment_file.read_bytes()
    mime_type, _ = mimetypes.guess_type(str(attachment_file))
    if mime_type:
        maintype, subtype = mime_type.split("/", 1)
    else:
        maintype, subtype = "application", "octet-stream"
    msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=attachment_file.name)

    eml_path.write_bytes(bytes(msg))


def build_drafts(
    forms_folder: Path,
    addressbook_csv: Path,
    deadline: str,
    cc_extra: list[str],
    to_sections: list[str],
    cc_sections: list[str],
    alias_csv: Path | None,
) -> tuple[int, int]:
    contacts = read_contacts(addressbook_csv)
    contacts_by_market = group_contacts_by_market(contacts)
    aliases = read_aliases(alias_csv)

    generated = 0
    skipped = 0
    for file in sorted(forms_folder.glob("*_UTM_Response.xlsx")):
        if file.name.startswith("~$"):
            continue
        market_code = parse_market_code_from_filename(file.name)
        if not market_code:
            print(f"[skip] Could not parse market code from {file.name}")
            skipped += 1
            continue
        to_list, cc_list, market_label, market_deadline, market_cc_emails = pick_recipients(
            market_code=market_code,
            contacts_by_market=contacts_by_market,
            aliases=aliases,
            to_sections=to_sections,
            cc_sections=cc_sections,
        )
        if not to_list:
            print(f"[skip] No recipient found for market '{market_code}' from {file.name}")
            skipped += 1
            continue

        # Get all names from to_list and join with commas
        names = [name.strip() for name, _ in to_list if name]
        greeting_names = ", ".join(names) if names else market_label
        to_addresses = format_addresses(to_list)

        extra_cc_pairs = [("", email.strip()) for email in cc_extra if email.strip()]
        cc_list = dedupe_emails(cc_list + extra_cc_pairs + [("", email) for email in market_cc_emails])
        cc_addresses = format_addresses(cc_list)

        effective_deadline = market_deadline or deadline
        subject = build_subject(market_label, effective_deadline)
        body = build_body(greeting_names, market_label, effective_deadline)
        eml_file = forms_folder / f"{market_code}_UTM_Request.eml"
        write_eml(
            eml_path=eml_file,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            subject=subject,
            body=body,
            attachment_file=file,
        )
        generated += 1
        print(f"[ok] {eml_file.name} -> To: {to_addresses}")

    return generated, skipped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create .eml drafts per market from generated UTM response forms."
    )
    parser.add_argument(
        "--forms-folder",
        type=Path,
        required=True,
        help="Folder containing *_UTM_Response.xlsx files. .eml drafts are written here.",
    )
    parser.add_argument(
        "--addressbook-csv",
        type=Path,
        required=True,
        help="Addressbook CSV path with market/section/name/email columns.",
    )
    parser.add_argument(
        "--deadline",
        type=str,
        default="Friday, 09 May 2026",
        help="Default deadline text if not in addressbook.",
    )
    parser.add_argument(
        "--cc",
        type=str,
        default="",
        help="Extra cc emails, separated by ';' or ','.",
    )
    parser.add_argument(
        "--to-sections",
        type=str,
        default=";".join(DEFAULT_TO_SECTIONS),
        help="Priority list of addressbook sections used for To, separated by ';'.",
    )
    parser.add_argument(
        "--cc-sections",
        type=str,
        default=";".join(DEFAULT_CC_SECTIONS),
        help="Addressbook sections to include in Cc, separated by ';'.",
    )
    parser.add_argument(
        "--market-alias-csv",
        type=Path,
        default=None,
        help="Optional CSV with columns: market_code,addressbook_market.",
    )
    return parser.parse_args()


def split_multi(value: str) -> list[str]:
    return [v.strip() for v in re.split(r"[;,]", value or "") if v.strip()]


def main():
    args = parse_args()
    cc_extra = split_multi(args.cc)
    to_sections = split_multi(args.to_sections) or DEFAULT_TO_SECTIONS
    cc_sections = split_multi(args.cc_sections) or DEFAULT_CC_SECTIONS

    generated, skipped = build_drafts(
        forms_folder=args.forms_folder,
        addressbook_csv=args.addressbook_csv,
        deadline=args.deadline,
        cc_extra=cc_extra,
        to_sections=to_sections,
        cc_sections=cc_sections,
        alias_csv=args.market_alias_csv,
    )
    print(f"Done. Generated: {generated}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
