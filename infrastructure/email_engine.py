"""
email_engine.py — Ultron Autonomous Email & Inbox Intelligence Engine.

Provides complete autonomous email capabilities for Ultron:
  1. Multi-Profile Mapping (Work, Personal, Secondary, Custom)
  2. Inbox and Thread Search via IMAP SSL (sender, subject, keyword, unread)
  3. Full Message and MIME Thread Reading (HTML + Plaintext decoding)
  4. Local Email Draft Generation and .eml Archiving
  5. Direct Outbound SMTP Sending with Attachments and Telemetry
"""

from __future__ import annotations

import email
import email.message
from email.header import decode_header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, parseaddr
import imaplib
import json
import os
from pathlib import Path
import re
import smtplib
import ssl
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from config import EmailConfig


def _decode_mime_str(header_val: str | None) -> str:
    """Decodes RFC 2047 encoded email headers to clean Unicode."""
    if not header_val:
        return ""
    try:
        decoded_fragments = decode_header(header_val)
        parts = []
        for fragment, encoding in decoded_fragments:
            if isinstance(fragment, bytes):
                enc = encoding or "utf-8"
                try:
                    parts.append(fragment.decode(enc, errors="replace"))
                except Exception:
                    parts.append(fragment.decode("utf-8", errors="replace"))
            else:
                parts.append(str(fragment))
        return "".join(parts).strip()
    except Exception:
        return str(header_val).strip()


class EmailEngine:
    """
    Enterprise-grade autonomous email client for Ultron.
    Supports reading, searching, drafting, and sending emails across multiple profiles.
    """

    def __init__(self, config: EmailConfig | None = None) -> None:
        self.cfg = config or EmailConfig()
        self.drafts_dir = Path(self.cfg.drafts_dir)
        self.drafts_dir.mkdir(parents=True, exist_ok=True)

    def resolve_profile(self, profile_name: str | None = None) -> Dict[str, Any]:
        """
        Resolves account credentials and connection endpoints for a given profile.
        Supports: 'work', 'personal', 'secondary', 'default'.
        """
        p = (profile_name or self.cfg.default_profile).lower().strip()

        # Map profiles
        if "work" in p or "primary" in p or "corp" in p or "business" in p:
            email_user = self.cfg.work_user
            email_pass = self.cfg.work_password
            display_name = os.getenv("WORK_EMAIL_DISPLAY_NAME", "Ultron Work Agent")
        elif "personal" in p or "direct" in p:
            email_user = self.cfg.personal_user
            email_pass = self.cfg.personal_password
            display_name = os.getenv("PERSONAL_EMAIL_DISPLAY_NAME", "Ultron Personal Agent")
        elif "secondary" in p or "alt" in p:
            email_user = self.cfg.secondary_user
            email_pass = self.cfg.secondary_password
            display_name = os.getenv("SECONDARY_EMAIL_DISPLAY_NAME", "Ultron Secondary Agent")
        else:
            email_user = self.cfg.work_user
            email_pass = self.cfg.work_password
            display_name = os.getenv("DEFAULT_EMAIL_DISPLAY_NAME", f"Ultron Agent ({p.title()})")

        return {
            "profile_name": p,
            "display_name": display_name,
            "user": email_user,
            "password": email_pass,
            "imap_host": self.cfg.imap_host,
            "imap_port": self.cfg.imap_port,
            "smtp_host": self.cfg.smtp_host,
            "smtp_port": self.cfg.smtp_port,
            "use_ssl": self.cfg.use_ssl,
        }

    # ── 1. Search Inbox ───────────────────────────────────────────────────────

    def search_inbox(
        self,
        query: str = "",
        sender: str = "",
        subject: str = "",
        unread_only: bool = False,
        folder: str = "INBOX",
        profile: str = "default",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Searches the inbox using IMAP SSL.
        Returns a list of matching email headers and preview snippets.
        """
        prof = self.resolve_profile(profile)
        user = prof["user"]
        password = prof["password"]

        if not password:
            return {
                "success": False,
                "error": (
                    f"Email password for profile '{prof['profile_name']}' ({user}) is not configured in .env. "
                    f"Please add {prof['profile_name'].upper()}_EMAIL_PASSWORD to your .env file."
                ),
                "credentials_needed": True,
                "profile": prof["profile_name"],
                "account": user,
                "matches": [],
            }

        mail = None
        try:
            if prof["use_ssl"]:
                context = ssl.create_default_context()
                mail = imaplib.IMAP4_SSL(prof["imap_host"], prof["imap_port"], ssl_context=context)
            else:
                mail = imaplib.IMAP4(prof["imap_host"], prof["imap_port"])

            mail.login(user, password)
            status, _ = mail.select(folder, readonly=True)
            if status != "OK":
                return {"success": False, "error": f"Failed to select mailbox folder '{folder}'", "matches": []}

            # Build IMAP search criteria
            criteria = []
            if unread_only:
                criteria.append("UNSEEN")
            if sender:
                criteria.append(f'FROM "{sender}"')
            if subject:
                criteria.append(f'SUBJECT "{subject}"')
            if query and query.strip().upper() != "ALL":
                criteria.append(f'TEXT "{query}"')

            search_str = " ".join(criteria) if criteria else "ALL"
            status, data = mail.search(None, search_str)
            if status != "OK" or not data or not data[0]:
                return {
                    "success": True,
                    "account": user,
                    "folder": folder,
                    "search_criteria": search_str,
                    "total_found": 0,
                    "matches": [],
                    "message": f"No emails found matching criteria in {folder}.",
                }

            msg_ids = data[0].split()
            # Most recent first
            msg_ids.reverse()
            msg_ids = msg_ids[:limit]

            results = []
            for mid in msg_ids:
                try:
                    _, msg_data = mail.fetch(mid, "(RFC822.HEADER)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            msg_subject = _decode_mime_str(msg.get("Subject", "(No Subject)"))
                            msg_from = _decode_mime_str(msg.get("From", ""))
                            msg_to = _decode_mime_str(msg.get("To", ""))
                            msg_date = _decode_mime_str(msg.get("Date", ""))
                            msg_id_header = msg.get("Message-ID", "")

                            results.append({
                                "id": mid.decode("utf-8", errors="ignore"),
                                "message_id": msg_id_header,
                                "from": msg_from,
                                "to": msg_to,
                                "subject": msg_subject,
                                "date": msg_date,
                            })
                except Exception as fetch_err:
                    print(f"  [IMAP FETCH WARNING] Message {mid}: {fetch_err}")
                    continue

            return {
                "success": True,
                "account": user,
                "folder": folder,
                "search_criteria": search_str,
                "total_found": len(results),
                "matches": results,
                "emails": results,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"IMAP connection or search failed: {str(e)}",
                "profile": prof["profile_name"],
                "account": user,
                "matches": [],
            }
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except Exception:
                    pass

    search_emails = search_inbox

    # ── 2. Read Full Email Thread ─────────────────────────────────────────────

    def read_email_thread(
        self,
        message_id: str,
        folder: str = "INBOX",
        profile: str = "default",
    ) -> Dict[str, Any]:
        """
        Fetches and parses the full content of an email (plain text, HTML, and attachment names).
        """
        prof = self.resolve_profile(profile)
        user = prof["user"]
        password = prof["password"]

        if not password:
            return {
                "success": False,
                "error": f"Email password for profile '{prof['profile_name']}' is not configured in .env.",
                "credentials_needed": True,
            }

        mail = None
        try:
            if prof["use_ssl"]:
                context = ssl.create_default_context()
                mail = imaplib.IMAP4_SSL(prof["imap_host"], prof["imap_port"], ssl_context=context)
            else:
                mail = imaplib.IMAP4(prof["imap_host"], prof["imap_port"])

            mail.login(user, password)
            mail.select(folder, readonly=True)

            status, data = mail.fetch(message_id.encode("utf-8"), "(RFC822)")
            if status != "OK" or not data or not data[0]:
                return {"success": False, "error": f"Could not fetch message ID '{message_id}'."}

            raw_bytes = data[0][1]
            msg = email.message_from_bytes(raw_bytes)

            subject = _decode_mime_str(msg.get("Subject", "(No Subject)"))
            sender = _decode_mime_str(msg.get("From", ""))
            recipient = _decode_mime_str(msg.get("To", ""))
            cc = _decode_mime_str(msg.get("Cc", ""))
            date = _decode_mime_str(msg.get("Date", ""))

            body_plain = ""
            body_html = ""
            attachments = []

            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))

                    if "attachment" in content_disposition:
                        filename = _decode_mime_str(part.get_filename() or "attachment")
                        attachments.append(filename)
                        continue

                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        text = payload.decode(charset, errors="replace")
                        if content_type == "text/plain":
                            body_plain += text + "\n"
                        elif content_type == "text/html":
                            body_html += text + "\n"
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    text = payload.decode(charset, errors="replace")
                    if msg.get_content_type() == "text/html":
                        body_html = text
                    else:
                        body_plain = text

            snippet = body_plain.strip()
            if not snippet and body_html:
                snippet = re.sub(r"<[^>]+>", " ", body_html)
                snippet = re.sub(r"\s+", " ", snippet).strip()

            return {
                "success": True,
                "id": message_id,
                "subject": subject,
                "from": sender,
                "to": recipient,
                "cc": cc,
                "date": date,
                "body_plain": body_plain.strip(),
                "body_text": body_plain.strip() or snippet,
                "snippet": snippet[:500],
                "has_html": bool(body_html),
                "attachments": attachments,
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to read message {message_id}: {str(e)}"}
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except Exception:
                    pass

    # ── 3. Draft Email ────────────────────────────────────────────────────────

    def draft_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
        profile: str = "default",
    ) -> Dict[str, Any]:
        """
        Generates and archives an email draft locally as .eml and JSON.
        """
        prof = self.resolve_profile(profile)
        draft_id = f"draft_{int(time.time())}_{uuid.uuid4().hex[:6]}"

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{prof['display_name']} <{prof['user']}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc

        msg.attach(MIMEText(body, "plain", "utf-8"))

        eml_path = self.drafts_dir / f"{draft_id}.eml"
        json_path = self.drafts_dir / f"{draft_id}.json"

        with open(eml_path, "wb") as f:
            f.write(msg.as_bytes())

        draft_meta = {
            "draft_id": draft_id,
            "profile": prof["profile_name"],
            "from": msg["From"],
            "to": to,
            "cc": cc,
            "bcc": bcc,
            "subject": subject,
            "body": body,
            "eml_file": str(eml_path.resolve()),
            "created_at": time.time(),
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(draft_meta, f, indent=2)

        return {
            "success": True,
            "draft_id": draft_id,
            "from": msg["From"],
            "to": to,
            "subject": subject,
            "preview": body[:300],
            "eml_path": str(eml_path.resolve()),
            "message": f"Draft '{draft_id}' generated and saved locally for review.",
        }

    # ── 4. Send Email ─────────────────────────────────────────────────────────

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
        profile: str = "default",
        attachments: list[str] | None = None,
        is_html: bool = False,
    ) -> Dict[str, Any]:
        """
        Sends an outbound email via SMTP SSL or STARTTLS with full MIME packaging.
        """
        prof = self.resolve_profile(profile)
        user = prof["user"]
        password = prof["password"]

        if not password:
            draft_res = self.draft_email(to=to, subject=subject, body=body, cc=cc, bcc=bcc, profile=profile)
            return {
                "success": False,
                "error": (
                    f"Outbound SMTP password for '{prof['profile_name']}' ({user}) is not configured in .env. "
                    f"Your message was safely saved as draft: '{draft_res['draft_id']}' at {draft_res['eml_path']}."
                ),
                "credentials_needed": True,
                "draft_saved": draft_res,
            }

        msg = MIMEMultipart("mixed")
        msg["From"] = f"{prof['display_name']} <{user}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()
        if cc:
            msg["Cc"] = cc

        if is_html:
            msg.attach(MIMEText(body, "html", "utf-8"))
        else:
            msg.attach(MIMEText(body, "plain", "utf-8"))

        if attachments:
            for filepath in attachments:
                p = Path(filepath)
                if p.exists() and p.is_file():
                    with open(p, "rb") as af:
                        part = MIMEApplication(af.read(), Name=p.name)
                        part["Content-Disposition"] = f'attachment; filename="{p.name}"'
                        msg.attach(part)

        recipients = [parseaddr(r)[1] for r in to.split(",") if parseaddr(r)[1]]
        if cc:
            recipients.extend([parseaddr(r)[1] for r in cc.split(",") if parseaddr(r)[1]])
        if bcc:
            recipients.extend([parseaddr(r)[1] for r in bcc.split(",") if parseaddr(r)[1]])

        if not recipients:
            return {"success": False, "error": f"Invalid recipient address: '{to}'"}

        try:
            if prof["smtp_port"] == 465 or prof["use_ssl"]:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(prof["smtp_host"], prof["smtp_port"], context=context, timeout=20) as server:
                    server.login(user, password)
                    server.sendmail(user, recipients, msg.as_string())
            else:
                with smtplib.SMTP(prof["smtp_host"], prof["smtp_port"], timeout=20) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(user, password)
                    server.sendmail(user, recipients, msg.as_string())

            return {
                "success": True,
                "from": msg["From"],
                "to": to,
                "cc": cc,
                "subject": subject,
                "message_id": msg["Message-ID"],
                "attachments_count": len(attachments) if attachments else 0,
                "timestamp": time.time(),
                "status": "DELIVERED_TO_SMTP_RELAY",
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"SMTP dispatch failed: {str(e)}",
                "profile": prof["profile_name"],
                "account": user,
            }
