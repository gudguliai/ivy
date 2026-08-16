#!/usr/bin/env python3
"""Ivy 2028 deadline alerts → astrodastic@gmail.com.

Reads the latest pipeline CSV, finds urgent (<=7d) and upcoming (<=30d)
deadlines, emails a digest with the app URL. Uses the Gmail API with the
shared Google token (~/.hermes/google_token.json).

Usage:
  python3.13 send_alerts.py --dry-run   # print what would be sent
  python3.13 send_alerts.py             # actually send
"""
import argparse
import base64
import csv
import glob
import json
import os
import urllib.request
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

APP_URL = "https://gudguliai.github.io/ivy/"
TO_EMAIL = "astrodastic@gmail.com"
FROM_EMAIL = "gudguliai@gmail.com"
TOKEN_PATH = os.path.expanduser("~/.hermes/google_token.json")


def latest_csv() -> str:
    files = sorted(glob.glob(
        os.path.expanduser("~/projects/ivy-2028-v2/output/*results.csv")))
    return files[-1] if files else None


def parse_deadline(raw: str):
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%d %b %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def build_items(rows, max_days):
    today = date.today()
    out = []
    for r in rows:
        dl = parse_deadline(r.get("deadline"))
        if not dl:
            continue
        days = (dl - today).days
        if 0 <= days <= max_days:
            out.append((days, r))
    return sorted(out, key=lambda x: x[0])


def item_html(days, r) -> str:
    dl = r.get("deadline", "")
    cost = r.get("cost", "") or ""
    aid = r.get("aid", "") or ""
    extra = " · ".join(x for x in [cost, aid] if x and x != "N/A")
    notes = (r.get("notes") or "")[:120]
    note_html = f" · {notes}" if notes else ""
    return (f'<li><b>{r.get("name", "?")}</b> — {dl}'
            f' ({days}d){f" · {extra}" if extra else ""}'
            f' — <a href="{r.get("url", APP_URL)}">link</a>{note_html}</li>')


def _refresh_if_needed(cred):
    """Refresh the Google access token via refresh_token; update the file."""
    import urllib.parse
    try:
        data = urllib.parse.urlencode({
            "client_id": cred["client_id"],
            "client_secret": cred["client_secret"],
            "refresh_token": cred["refresh_token"],
            "grant_type": "refresh_token",
        }).encode()
        req = urllib.request.Request(cred["token_uri"], data=data)
        tok = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
        cred["token"] = tok["access_token"]
        json.dump(cred, open(TOKEN_PATH, "w"), indent=2)
        return cred["token"]
    except Exception:
        return None


def send_email(subject, html_body):
    cred = json.load(open(TOKEN_PATH))
    access = cred.get("token")

    def _do(access):
        msg = MIMEMultipart("alternative")
        msg["To"] = TO_EMAIL
        msg["From"] = FROM_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        req = urllib.request.Request(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            data=json.dumps({"raw": raw}).encode(),
            headers={"Authorization": f"Bearer {access}",
                     "Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())

    try:
        resp = _do(access)
        return resp.get("id")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            new_access = _refresh_if_needed(cred)
            if new_access:
                return _do(new_access).get("id")
            raise
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    csv_path = latest_csv()
    if not csv_path:
        print("NO_CSV")
        return
    rows = list(csv.DictReader(open(csv_path)))

    urgent = build_items(rows, 7)
    upcoming = build_items(rows, 30)
    upcoming = [x for x in upcoming if x[0] > 7]

    if not urgent and not upcoming:
        print(f"NO_ALERTS (csv={os.path.basename(csv_path)})")
        return

    u_html = "".join(item_html(d, r) for d, r in urgent) or "<li>None</li>"
    n_html = "".join(item_html(d, r) for d, r in upcoming) or "<li>None</li>"

    html = f"""<html><body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#0f172a">
<h2 style="margin-bottom:0">Ivy — Opportunity Alerts</h2>
<p style="color:#64748b">Data from {os.path.basename(csv_path)} · generated {date.today()}</p>
<h3>🔥 Urgent (≤ 7 days)</h3><ul>{u_html}</ul>
<h3>📅 Upcoming (≤ 30 days)</h3><ul>{n_html}</ul>
<hr><p style="color:#64748b">Full digest: <a href="{APP_URL}">{APP_URL}</a></p>
</body></html>"""

    subject = f"Ivy Alert: {len(urgent)} urgent · {len(upcoming)} upcoming (30d)"
    if args.dry_run:
        print(f"DRY RUN — would send: {subject} to {TO_EMAIL}")
        print(html[:2000])
        return
    msg_id = send_email(subject, html)
    print(f"SENT {msg_id} | {subject}")


if __name__ == "__main__":
    main()
