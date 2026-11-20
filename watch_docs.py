"""Watch docs.neo.work and tell the Neo Blog Desk when pages are added, changed or removed.

Reads the public page list (llms.txt), fetches every page as markdown, and compares a
fingerprint of each page with state/pages.json. When something changed it sends one
notification to the desk's scheduled task, then saves the new fingerprints.
The first run only saves fingerprints and sends nothing.

Environment:
  DOCS_BASE_URL   default https://docs.neo.work
  FIRE_URL        the scheduled task's Fire URL   (secret BLOG_DESK_FIRE_URL)
  FIRE_TOKEN      the scheduled task's API token  (secret BLOG_DESK_TOKEN)
  DRY_RUN         "1" to print what would be sent without sending or saving
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("DOCS_BASE_URL", "https://docs.neo.work").rstrip("/")
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "pages.json")
UA = "neo-blog-desk-docs-watcher/1.0"
SKIP = re.compile(r"/(troubleshooting|changelog|api-reference|legal)(/|\.md$)", re.I)


def get(url, tries=3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/markdown, text/plain, */*"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, ""
            if attempt == tries - 1:
                raise
        except Exception:
            if attempt == tries - 1:
                raise
        time.sleep(3 * (attempt + 1))


def page_urls(index_text):
    urls = re.findall(r"\((https?://[^)\s]+\.md)\)", index_text)
    seen, out = set(), []
    for u in urls:
        if not u.startswith(BASE + "/") or SKIP.search(u) or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def fingerprint(text):
    norm = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def fire(text):
    url, token = os.environ.get("FIRE_URL", ""), os.environ.get("FIRE_TOKEN", "")
    if not url or not token:
        sys.exit("Missing BLOG_DESK_FIRE_URL or BLOG_DESK_TOKEN secret.")
    body = json.dumps({"text": text}).encode("utf-8")
    for attempt in range(2):
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "Authorization": "Bearer " + token,
            "anthropic-beta": "experimental-cc-routine-2026-04-01",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "User-Agent": UA,
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8") or "{}")
                print("Blog Desk run started:", data.get("claude_code_session_url", "(no link returned)"))
                return True
        except urllib.error.HTTPError as e:
            print("Notification failed: HTTP", e.code, e.read().decode("utf-8", "replace")[:500])
            if 400 <= e.code < 500 and e.code != 429:
                return False
        except Exception as e:  # network trouble: retry once
            print("Notification failed:", e)
        time.sleep(30)
    return False


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    status, index = get(BASE + "/llms.txt")
    if status != 200 or not index:
        sys.exit("Couldn't read %s/llms.txt (HTTP %s)" % (BASE, status))
    urls = page_urls(index)
    if not urls:
        sys.exit("llms.txt listed no pages; leaving the saved state alone.")

    try:
        with open(STATE) as f:
            old = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        old = {}
    first_run = not old.get("pages")
    old_pages = old.get("pages", {})

    new_pages, lines = {}, []
    for u in urls:
        st, text = get(u)
        if st != 200 or not text.strip():
            print("Skipped (HTTP %s): %s" % (st, u))
            if u in old_pages:
                new_pages[u] = old_pages[u]  # keep it; a blip isn't a removal
            continue
        fp = fingerprint(text)
        new_pages[u] = fp
        path = u[len(BASE) + 1:]
        if u not in old_pages:
            lines.append("A %s %s" % (path, u))
        elif old_pages[u] != fp:
            lines.append("M %s %s" % (path, u))
    for u in old_pages:
        if u not in new_pages and u not in urls:
            lines.append("D %s %s" % (u[len(BASE) + 1:], u))

    print("Pages checked: %d, changes: %d" % (len(urls), len(lines)))
    for l in lines:
        print("  " + l)

    if first_run:
        print("First run: saving fingerprints only.")
    elif lines:
        shown = lines[:60]
        extra = len(lines) - len(shown)
        text = "commit docs-watcher %s %s\n%s%s" % (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            os.environ.get("RUN_URL", ""),
            "\n".join(shown),
            ("\n(and %d more pages: run the full docs watch)" % extra) if extra else "",
        )
        if dry:
            print("DRY RUN, would send:\n" + text)
            return
        if not fire(text):
            sys.exit("The Blog Desk didn't accept the notification. Fingerprints not saved, so the next check retries.")

    if dry:
        return
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump({"base": BASE, "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pages": new_pages}, f, indent=1, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main()
