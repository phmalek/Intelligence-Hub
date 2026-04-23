from __future__ import annotations

import json
import re
import sqlite3
import sys
from datetime import datetime

try:
    import pythoncom
    import win32com.client
except Exception as exc:
    print(json.dumps({'ok': False, 'error': f'pywin32 import failed: {exc}'}))
    raise SystemExit(1)


def _json_out(payload: dict, exit_code: int = 0) -> None:
    print(json.dumps(payload, ensure_ascii=True))
    raise SystemExit(exit_code)


def _normalize_subject(value: str) -> str:
    cleaned = value or ''
    while True:
        updated = re.sub(r'^\s*(re|fw|fwd)\s*:\s*', '', cleaned, flags=re.IGNORECASE)
        if updated == cleaned:
            break
        cleaned = updated
    return ' '.join(cleaned.strip().lower().split())


def _outlook_datetime_literal(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return parsed.strftime('%m/%d/%Y %I:%M %p')


def _parse_iso_datetime(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def check() -> None:
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch('Outlook.Application')
        namespace = outlook.GetNamespace('MAPI')
        _ = namespace.Folders.Count
        _json_out({'ok': True, 'message': 'Outlook COM connection is available.'})
    except Exception as exc:
        _json_out({'ok': False, 'error': f'Outlook COM connection failed: {exc}'}, exit_code=1)
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def send_or_draft(payload_json: str) -> None:
    payload = json.loads(payload_json)
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch('Outlook.Application')
        mail_item = outlook.CreateItem(0)
        mail_item.To = '; '.join(payload.get('to_emails', []))
        mail_item.CC = '; '.join(payload.get('cc_emails', []))
        mail_item.Subject = payload.get('subject', '')
        mail_item.Body = payload.get('body', '')

        send_mode = payload.get('send_mode', 'draft')
        if send_mode == 'send':
            mail_item.Send()
            _json_out(
                {
                    'ok': True,
                    'entry_id': '',
                    'conversation_id': '',
                    'sent_at': datetime.now().isoformat(timespec='seconds'),
                    'sync_state': 'sent',
                }
            )

        mail_item.Save()
        entry_id = str(getattr(mail_item, 'EntryID', '') or '')
        conversation_id = str(getattr(mail_item, 'ConversationID', '') or '')
        mail_item.Display(False)
        _json_out(
            {
                'ok': True,
                'entry_id': entry_id,
                'conversation_id': conversation_id,
                'sent_at': datetime.now().isoformat(timespec='seconds'),
                'sync_state': 'draft',
            }
        )
    except Exception as exc:
        _json_out({'ok': False, 'error': f'Outlook {payload.get("send_mode", "draft")} failed: {exc}'}, exit_code=1)
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def sync_replies(db_path: str, workflow: str) -> None:
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch('Outlook.Application')
        namespace = outlook.GetNamespace('MAPI')
        inbox = namespace.GetDefaultFolder(6)
        sent_items = namespace.GetDefaultFolder(5)
        folder_items = []
        for folder in [inbox, sent_items]:
            items = folder.Items
            items.Sort('[ReceivedTime]', True)
            folder_items.append(items)

        conn = sqlite3.connect(db_path)
        messages = conn.execute(
            '''
            SELECT om.id, om.outlook_conversation_id, om.subject_rendered, om.sent_at
            FROM outreach_messages om
            INNER JOIN outreach_runs orun ON orun.id = om.run_id
            WHERE orun.workflow = ?
            ''',
            (workflow,),
        ).fetchall()

        updated = 0
        for message_id, conversation_id, subject_rendered, sent_at in messages:
            latest_reply_at = None
            latest_reply_from = ''
            latest_reply_subject = ''
            latest_reply_snippet = ''
            normalized_subject = _normalize_subject(subject_rendered or '')
            sent_at_dt = _parse_iso_datetime(sent_at or '')
            matched_items = []
            seen_entry_ids = set()

            for base_items in folder_items:
                candidate_items = base_items
                if sent_at_dt is not None:
                    try:
                        restricted = base_items.Restrict(f"[ReceivedTime] >= '{_outlook_datetime_literal(sent_at)}'")
                        restricted.Sort('[ReceivedTime]', True)
                        candidate_items = restricted
                    except Exception:
                        candidate_items = base_items

                try:
                    item_count = min(getattr(candidate_items, 'Count', 0), 250)
                except Exception:
                    item_count = 0

                for idx in range(1, item_count + 1):
                    try:
                        item = candidate_items.Item(idx)
                        sender = str(getattr(item, 'SenderEmailAddress', '') or '')
                        sender_name = str(getattr(item, 'SenderName', '') or '')
                        subject = str(getattr(item, 'Subject', '') or '')
                        body = str(getattr(item, 'Body', '') or '')
                        received_time = getattr(item, 'ReceivedTime', None)
                        item_conversation_id = str(getattr(item, 'ConversationID', '') or '')
                        item_entry_id = str(getattr(item, 'EntryID', '') or '')
                    except Exception:
                        continue

                    if not received_time:
                        continue
                    try:
                        received_at_dt = datetime(
                            received_time.year,
                            received_time.month,
                            received_time.day,
                            received_time.hour,
                            received_time.minute,
                            received_time.second,
                        )
                    except Exception:
                        received_at_dt = None

                    if sent_at_dt is not None and received_at_dt is not None and received_at_dt <= sent_at_dt:
                        continue

                    conversation_match = bool(conversation_id) and item_conversation_id == conversation_id
                    normalized_item_subject = _normalize_subject(subject)
                    subject_match = bool(normalized_subject) and (
                        normalized_item_subject == normalized_subject
                        or normalized_subject in normalized_item_subject
                        or normalized_item_subject in normalized_subject
                    )
                    if not conversation_match and not subject_match:
                        continue

                    dedupe_key = item_entry_id or f'{received_at_dt}|{sender}|{subject}'
                    if dedupe_key in seen_entry_ids:
                        continue
                    seen_entry_ids.add(dedupe_key)

                    received_at_str = received_at_dt.isoformat(sep=' ') if received_at_dt is not None else str(received_time)
                    matched_items.append(
                        {
                            'received_at': received_at_str,
                            'sender_email': sender,
                            'sender_name': sender_name,
                            'subject': subject,
                            'snippet': body[:280].strip(),
                            'body_text': body.strip(),
                            'outlook_entry_id': item_entry_id,
                        }
                    )

            matched_items.sort(key=lambda item: item['received_at'])

            conn.execute('DELETE FROM outreach_replies WHERE outreach_message_id = ?', (message_id,))
            for matched_item in matched_items:
                conn.execute(
                    '''
                    INSERT INTO outreach_replies (
                        outreach_message_id,
                        received_at,
                        sender_email,
                        sender_name,
                        subject,
                        snippet,
                        body_text,
                        outlook_entry_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        message_id,
                        matched_item['received_at'],
                        matched_item['sender_email'],
                        matched_item['sender_name'],
                        matched_item['subject'],
                        matched_item['snippet'],
                        matched_item['body_text'],
                        matched_item['outlook_entry_id'],
                    ),
                )

            if matched_items:
                latest_item = matched_items[-1]
                latest_reply_at = latest_item['received_at']
                latest_reply_from = latest_item['sender_email'] or latest_item['sender_name']
                latest_reply_subject = latest_item['subject']
                latest_reply_snippet = latest_item['snippet']

            if latest_reply_at:
                conn.execute(
                    '''
                    UPDATE outreach_messages
                    SET replied = 1,
                        last_reply_at = ?,
                        last_reply_from = ?,
                        last_reply_snippet = ?,
                        sync_state = 'synced'
                    WHERE id = ?
                    ''',
                    (latest_reply_at, latest_reply_from, latest_reply_snippet or latest_reply_subject, message_id),
                )
                updated += 1

        conn.commit()
        conn.close()
        _json_out({'ok': True, 'updated': updated})
    except Exception as exc:
        _json_out({'ok': False, 'error': f'Reply sync failed: {exc}'}, exit_code=1)
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def fetch_utm_threads(subject_keyword: str) -> None:
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch('Outlook.Application')
        namespace = outlook.GetNamespace('MAPI')
        inbox = namespace.GetDefaultFolder(6)
        sent_items = namespace.GetDefaultFolder(5)

        # Try to find a "UTM Follow-ups" folder as a sibling of Inbox
        utm_followups_folder = None
        try:
            for folder in inbox.Parent.Folders:
                if folder.Name.strip().lower() == 'utm follow-ups':
                    utm_followups_folder = folder
                    break
        except Exception:
            pass

        # Step 1: Scan Sent Items for seed emails matching the keyword
        seed_conversations: dict[str, dict] = {}
        try:
            sent = sent_items.Items
            sent.Sort('[SentOn]', True)
            count = min(getattr(sent, 'Count', 0), 1000)
            for i in range(1, count + 1):
                try:
                    item = sent.Item(i)
                    subj = str(getattr(item, 'Subject', '') or '')
                    if subject_keyword.lower() not in subj.lower():
                        continue
                    conv_id = str(getattr(item, 'ConversationID', '') or '')
                    if not conv_id or conv_id in seed_conversations:
                        continue
                    sent_on = getattr(item, 'SentOn', None)
                    ts = ''
                    if sent_on:
                        try:
                            ts = datetime(
                                sent_on.year, sent_on.month, sent_on.day,
                                sent_on.hour, sent_on.minute, sent_on.second,
                            ).isoformat(sep=' ')
                        except Exception:
                            pass
                    seed_conversations[conv_id] = {'subject': subj, 'first_sent_at': ts}
                except Exception:
                    continue
        except Exception:
            pass

        if not seed_conversations:
            _json_out({'ok': True, 'threads': []})

        # Step 2: Single pass per folder to collect all thread messages
        folders_to_search = [
            (sent_items, 'sent'),
            (inbox, 'received'),
        ]
        if utm_followups_folder is not None:
            folders_to_search.append((utm_followups_folder, 'received'))

        conv_messages: dict[str, list] = {cid: [] for cid in seed_conversations}
        seen_entry_ids: set[str] = set()

        for folder, default_direction in folders_to_search:
            try:
                folder_items = folder.Items
                count = min(getattr(folder_items, 'Count', 0), 2000)
                for i in range(1, count + 1):
                    try:
                        item = folder_items.Item(i)
                        item_conv_id = str(getattr(item, 'ConversationID', '') or '')
                        if item_conv_id not in conv_messages:
                            continue
                        entry_id = str(getattr(item, 'EntryID', '') or '')
                        if entry_id and entry_id in seen_entry_ids:
                            continue
                        if entry_id:
                            seen_entry_ids.add(entry_id)

                        sender_email = str(getattr(item, 'SenderEmailAddress', '') or '')
                        sender_name = str(getattr(item, 'SenderName', '') or '')
                        subj = str(getattr(item, 'Subject', '') or '')
                        body = str(getattr(item, 'Body', '') or '').strip()
                        to_str = str(getattr(item, 'To', '') or '')
                        cc_str = str(getattr(item, 'CC', '') or '')

                        ts_source = getattr(item, 'SentOn', None) or getattr(item, 'ReceivedTime', None)
                        ts_str = ''
                        if ts_source:
                            try:
                                ts_str = datetime(
                                    ts_source.year, ts_source.month, ts_source.day,
                                    ts_source.hour, ts_source.minute, ts_source.second,
                                ).isoformat(sep=' ')
                            except Exception:
                                pass

                        conv_messages[item_conv_id].append({
                            'outlook_entry_id': entry_id,
                            'direction': default_direction,
                            'sender_email': sender_email,
                            'sender_name': sender_name,
                            'to_emails': to_str,
                            'cc_emails': cc_str,
                            'timestamp': ts_str,
                            'subject': subj,
                            'body_text': body,
                        })
                    except Exception:
                        continue
            except Exception:
                continue

        # Step 3: Build thread objects
        threads = []
        for conv_id, seed_data in seed_conversations.items():
            messages = sorted(conv_messages[conv_id], key=lambda m: m['timestamp'] or '')
            participants = sorted({m['sender_email'] for m in messages if m['sender_email']})
            threads.append({
                'conversation_id': conv_id,
                'subject': seed_data['subject'],
                'first_sent_at': seed_data['first_sent_at'],
                'last_activity_at': messages[-1]['timestamp'] if messages else '',
                'message_count': len(messages),
                'participant_emails': ', '.join(participants),
                'messages': messages,
            })

        _json_out({'ok': True, 'threads': threads})
    except Exception as exc:
        _json_out({'ok': False, 'error': f'Fetch UTM threads failed: {exc}'}, exit_code=1)
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def main() -> int:
    if len(sys.argv) < 2:
        _json_out({'ok': False, 'error': 'Missing action.'}, exit_code=1)

    action = sys.argv[1]
    if action == 'check':
        check()
    if action == 'send_or_draft':
        if len(sys.argv) < 3:
            _json_out({'ok': False, 'error': 'Missing payload.'}, exit_code=1)
        send_or_draft(sys.argv[2])
    if action == 'sync_replies':
        if len(sys.argv) < 4:
            _json_out({'ok': False, 'error': 'Missing db_path/workflow.'}, exit_code=1)
        sync_replies(sys.argv[2], sys.argv[3])
    if action == 'fetch_utm_threads':
        if len(sys.argv) < 3:
            _json_out({'ok': False, 'error': 'Missing subject_keyword.'}, exit_code=1)
        fetch_utm_threads(sys.argv[2])

    _json_out({'ok': False, 'error': f'Unknown action: {action}'}, exit_code=1)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
