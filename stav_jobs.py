#!/usr/bin/env python3
"""Check https://stav-dresden.de/en/jobs and email new job listings.

Seen job IDs are stored in seen_jobs.json next to this script. On the very
first run, all current jobs are recorded without sending an email, so you
only get notified about jobs added afterwards.

Configuration (environment variables):
    SMTP_USER       Gmail address used to send (e.g. avadhoot.khedekar.de@gmail.com)
    SMTP_PASSWORD   Gmail App Password (https://myaccount.google.com/apppasswords)
    EMAIL_TO        Recipient (defaults to SMTP_USER)
    SMTP_HOST       Defaults to smtp.gmail.com
    SMTP_PORT       Defaults to 465 (SSL)

Usage:
    python3 stav_jobs.py            # check and email new jobs
    python3 stav_jobs.py --dry-run  # print new jobs, don't email or save
"""

import html
import json
import os
import re
import smtplib
import sys
import urllib.request
from email.message import EmailMessage
from pathlib import Path

BASE_URL = "https://stav-dresden.de"
JOBS_URL = f"{BASE_URL}/en/jobs"
STATE_FILE = Path(__file__).resolve().parent / "seen_jobs.json"

JOB_CARD_RE = re.compile(
    r'<a[^>]*href="/en/jobs/(\d+)"[^>]*>.*?<h3[^>]*>(.*?)</h3>', re.DOTALL
)


def fetch_jobs():
    """Return {job_id: title} for every job currently listed."""
    req = urllib.request.Request(JOBS_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        page = resp.read().decode("utf-8", errors="replace")

    jobs = {}
    for job_id, title in JOB_CARD_RE.findall(page):
        title = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        jobs[job_id] = title
    if not jobs:
        raise RuntimeError("No jobs found - the page layout may have changed.")
    return jobs


def load_seen():
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return None


def save_seen(ids):
    STATE_FILE.write_text(json.dumps(sorted(ids, key=int), indent=2))


def send_email(new_jobs):
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    to = os.environ.get("EMAIL_TO") or user
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))

    lines = [f"{title}\n{BASE_URL}/en/jobs/{job_id}\n" for job_id, title in new_jobs]
    msg = EmailMessage()
    msg["Subject"] = f"STAV Dresden: {len(new_jobs)} new job(s)"
    msg["From"] = user
    msg["To"] = to
    msg.set_content("New jobs on STAV Dresden:\n\n" + "\n".join(lines))

    with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)


def main():
    dry_run = "--dry-run" in sys.argv
    jobs = fetch_jobs()
    seen = load_seen()

    if seen is None:
        print(f"First run: recording {len(jobs)} existing jobs, no email sent.")
        if not dry_run:
            save_seen(jobs.keys())
        return

    new_jobs = sorted(
        ((jid, title) for jid, title in jobs.items() if jid not in seen),
        key=lambda j: int(j[0]),
    )
    if not new_jobs:
        print("No new jobs.")
        return

    for job_id, title in new_jobs:
        print(f"NEW: {title} - {BASE_URL}/en/jobs/{job_id}")

    if dry_run:
        return
    send_email(new_jobs)
    # Only mark as seen once the email went out, so failures are retried.
    save_seen(seen | set(jobs.keys()))
    print(f"Emailed {len(new_jobs)} new job(s).")


if __name__ == "__main__":
    main()
