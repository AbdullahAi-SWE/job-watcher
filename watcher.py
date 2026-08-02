import requests
import json
import os
import time
import base64
import threading
from bs4 import BeautifulSoup
from datetime import datetime
import re

# ============================================================
#  CONFIG — all values come from Railway environment variables
# ============================================================
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GITHUB_TOKEN     = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO      = os.environ.get("GITHUB_REPO", "")   # e.g. "yourname/job-watcher"

LOCATION             = "Egypt"
INTERVAL_MINUTES     = 5
SEEN_JOBS_FILE       = "seen_jobs.json"
TIME_FILTER_SECONDS  = 3600   # only jobs posted in the last 1 hour
# ============================================================

# Keywords that MUST appear somewhere in the job title or description
KEYWORDS_REQUIRED = [
    ".net", ".net core", "c#", "dotnet",
    "asp.net", "asp .net", "entity framework", "ef core"
]

# Job titles we care about — anything else is skipped immediately
# Internship/trainee titles are intentionally excluded
TITLE_KEYWORDS = ["developer", "engineer"]

# Words in the title that flag a posting as an internship — skip these
INTERNSHIP_KEYWORDS = ["intern", "internship", "training", "trainee", "graduate"]

# Search terms sent to LinkedIn
SEARCH_TERMS = [
    "software developer",
    "software engineer",
    "backend developer",
    "backend engineer",
    ".net developer",
    ".net engineer",
]

# ── Blocked companies (exact match, lowercase) ───────────────
# Add any spammy company name exactly as shown on LinkedIn, lowercased
BLOCKED_COMPANIES = {
    "bairesdev",
    "micro1",
    "jobs ai",
}

# ── Blocked description phrases ──────────────────────────────
# If ANY phrase appears in the description the job is silently skipped
BLOCKED_DESCRIPTION_PHRASES = [
    "joveo",
    "recruitment advertising platform",
    "real-time bidding",
    "jobsai",
    "jobs-ai",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

stats = {
    "jobs_checked"  : 0,
    "jobs_notified" : 0,
    "started_at"    : datetime.now(),
    "last_check"    : None,
}

# ── GitHub persistence ────────────────────────────────────────

def github_get_file():
    """Returns (content_str, sha) or (None, None) if file doesn't exist yet."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{SEEN_JOBS_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        data    = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]
    except Exception as e:
        print(f"[GitHub read error] {e}")
        return None, None


def load_seen_jobs():
    content, _ = github_get_file()
    if content:
        try:
            return set(json.loads(content))
        except Exception:
            pass
    return set()


def save_seen_jobs(seen):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{SEEN_JOBS_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    content_bytes = json.dumps(list(seen), indent=2).encode("utf-8")
    encoded       = base64.b64encode(content_bytes).decode("utf-8")

    _, sha = github_get_file()

    payload = {
        "message": "chore: update seen jobs [skip railway]",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    try:
        r = requests.put(url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        print("  [GitHub] seen_jobs.json saved ✅")
    except Exception as e:
        print(f"[GitHub write error] {e}")


# ── Telegram ─────────────────────────────────────────────────

def send_telegram(message, chat_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id"                 : chat_id or TELEGRAM_CHAT_ID,
        "text"                    : message,
        "parse_mode"              : "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"[Telegram error] {e}")


def poll_telegram_commands():
    """Runs in background — responds to /status messages."""
    offset = None
    while True:
        try:
            url    = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": offset}
            r      = requests.get(url, params=params, timeout=40)
            data   = r.json()

            for update in data.get("result", []):
                offset  = update["update_id"] + 1
                msg     = update.get("message", {})
                text    = msg.get("text", "").strip().lower()
                chat_id = str(msg.get("chat", {}).get("id", ""))

                if text in ("/status", "status", "s"):
                    uptime           = datetime.now() - stats["started_at"]
                    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
                    minutes          = remainder // 60
                    last             = stats["last_check"].strftime("%H:%M:%S") if stats["last_check"] else "not yet"

                    reply = (
                        f"✅ <b>Watcher is alive!</b>\n\n"
                        f"📊 Jobs scanned: <b>{stats['jobs_checked']}</b>\n"
                        f"🚨 Matches sent: <b>{stats['jobs_notified']}</b>\n"
                        f"🕐 Last check: <b>{last}</b>\n"
                        f"⏱ Uptime: <b>{hours}h {minutes}m</b>\n"
                        f"📍 Watching: Egypt | .NET & C# jobs only"
                    )
                    send_telegram(reply, chat_id=chat_id)

        except Exception as e:
            print(f"[Poll error] {e}")
            time.sleep(5)


# ── LinkedIn scraping ─────────────────────────────────────────

def search_jobs(keyword, location):
    url    = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    params = {
        "keywords": keyword,
        "location": location,
        "f_TPR"   : f"r{TIME_FILTER_SECONDS}",
        "start"   : 0,
        "count"   : 25,
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code == 429:
            print("[LinkedIn] Rate-limited, waiting 60s...")
            time.sleep(60)
            return []
        r.raise_for_status()
        soup  = BeautifulSoup(r.text, "html.parser")
        cards = soup.find_all("li")
        jobs  = []
        for card in cards:
            job_id_tag = card.find("div", {"data-entity-urn": True})
            if not job_id_tag:
                continue
            job_id = job_id_tag["data-entity-urn"].split(":")[-1]

            title_tag   = card.find("h3")
            company_tag = card.find("h4")
            loc_tag     = card.find("span", class_=re.compile("job-search-card__location"))

            jobs.append({
                "id"      : job_id,
                "title"   : title_tag.get_text(strip=True)   if title_tag   else "Unknown Title",
                "company" : company_tag.get_text(strip=True) if company_tag else "Unknown Company",
                "location": loc_tag.get_text(strip=True)     if loc_tag     else "",
                "url"     : f"https://www.linkedin.com/jobs/view/{job_id}",
            })
        return jobs
    except Exception as e:
        print(f"[Search error] {e}")
        return []


def get_job_description(job_id):
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    try:
        r    = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        tag  = soup.find("div", class_=re.compile("description|show-more-less-html"))
        return tag.get_text(" ", strip=True).lower() if tag else r.text.lower()
    except Exception as e:
        print(f"[Description error for {job_id}] {e}")
        return ""


def clean_description(text):
    """Strip URLs so domain extensions like .net inside links don't trigger keyword matches."""
    return " ".join(w for w in text.split() if "://" not in w and not w.startswith("www."))


def is_spam_description(description):
    return any(phrase in description for phrase in BLOCKED_DESCRIPTION_PHRASES)


def job_matches(job, description):
    title    = job["title"].lower()
    combined = (title + " " + clean_description(description)).lower()

    # Skip internships / training programs entirely
    if any(kw in title for kw in INTERNSHIP_KEYWORDS):
        return False

    # Must be a developer or engineer role
    if not any(kw in title for kw in TITLE_KEYWORDS):
        return False

    # Must mention .NET or C# somewhere in title or description
    return any(kw in combined for kw in KEYWORDS_REQUIRED)


# ── Main loop ─────────────────────────────────────────────────

def check_jobs(silent=False):
    timestamp = datetime.now().strftime("%H:%M:%S")
    if silent:
        print(f"[{timestamp}] First run — seeding seen jobs (no notifications)...")
    else:
        print(f"[{timestamp}] Checking for new jobs...")

    seen = load_seen_jobs()

    all_jobs = {}
    for term in SEARCH_TERMS:
        jobs = search_jobs(term, LOCATION)
        for job in jobs:
            all_jobs[job["id"]] = job
        time.sleep(2)

    print(f"  {len(all_jobs)} recent listing(s) found.")

    new_jobs_found = False

    for job_id, job in all_jobs.items():
        if job_id in seen:
            continue

        seen.add(job_id)
        new_jobs_found = True

        if silent:
            print(f"  (seed) {job['title']} @ {job['company']}")
            continue

        # Block known spammy companies before any HTTP call
        if job["company"].strip().lower() in BLOCKED_COMPANIES:
            print(f"  ✗ Blocked company: {job['company']} — {job['title']}")
            continue

        title_lower = job["title"].lower()

        # Skip internships immediately, no HTTP call needed
        if any(kw in title_lower for kw in INTERNSHIP_KEYWORDS):
            print(f"  ✗ Internship skip: {job['title']}")
            continue

        # Skip irrelevant titles without making any HTTP call
        if not any(kw in title_lower for kw in TITLE_KEYWORDS):
            print(f"  ✗ Title skip: {job['title']}")
            continue

        stats["jobs_checked"] += 1
        description = get_job_description(job_id)
        time.sleep(1.5)

        # Block spam aggregators by description fingerprint
        if is_spam_description(description):
            print(f"  ✗ Blocked spam: {job['title']} @ {job['company']}")
            continue

        if job_matches(job, description):
            stats["jobs_notified"] += 1
            msg = (
                f"🚨 <b>New .NET / C# Job in Egypt!</b>\n\n"
                f"📌 <b>{job['title']}</b>\n"
                f"🏢 {job['company']}\n"
                f"📍 {job['location']}\n"
                f"🕐 Posted within the last hour\n\n"
                f"🔗 <a href='{job['url']}'>View on LinkedIn</a>"
            )
            print(f"  ✅ MATCH → {job['title']} @ {job['company']}")
            send_telegram(msg)
        else:
            print(f"  ✗ No match: {job['title']}")

    if new_jobs_found:
        save_seen_jobs(seen)
    else:
        print("  No new jobs this cycle, skipping GitHub save.")

    stats["last_check"] = datetime.now()


if __name__ == "__main__":
    print("LinkedIn Job Watcher — Egypt | .NET & C# jobs only")
    print(f"Watching every {INTERVAL_MINUTES} minutes...\n")

    # Start Telegram /status listener in background
    t = threading.Thread(target=poll_telegram_commands, daemon=True)
    t.start()

    # On very first run, just record existing jobs without notifying
    first_run = (load_seen_jobs() == set())
    if first_run:
        check_jobs(silent=True)

    while True:
        check_jobs(silent=False)
        print(f"  Sleeping {INTERVAL_MINUTES} minutes...\n")
        time.sleep(INTERVAL_MINUTES * 60)
