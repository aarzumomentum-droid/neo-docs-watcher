# docs.neo.work watcher for the Neo Blog Desk

Every hour from 9 am to 7 pm IST, Monday to Friday, this repository checks the public docs at https://docs.neo.work.
It fingerprints every feature page and, when a page is added, changed or removed,
it tells the Neo Blog Desk, which:

- starts a feature blog for a **new** page (Neo task "Blog: …", message sheet ready at check 1);
- compares a **changed** page with its saved copy, finds the blog posts the change makes wrong, and opens a "Blog update: …" task with the exact edits to approve;
- flags posts that link to a **removed** page.

Nothing is published. Approved edits become Sanity drafts. No access to the docs source repository is needed.

## Setup (once, about 5 minutes)

1. **Create a repository** on your own GitHub account, for example `neo-docs-watcher`. Public is best: scheduled Actions on public repositories are free. (Private works too; see "Cost" below.)
2. **Upload these files** keeping the folders: `watch_docs.py`, `state/pages.json`, `.github/workflows/watch-docs.yml`, `README.md`. On github.com: Add file → Upload files, then drag in the folder contents.
3. **Add two secrets:** Settings → Secrets and variables → Actions → New repository secret.
   - `BLOG_DESK_FIRE_URL`: on claude.ai/code → Scheduled → "Neo Blog Desk docs hook" → Triggers → API, copy the URL.
   - `BLOG_DESK_TOKEN`: the token you copied when the task was created. If you didn't keep it, open the task → Edit → API → Regenerate.
4. **Allow the workflow to save its state:** Settings → Actions → General → Workflow permissions → "Read and write permissions" → Save.
5. **Run it once:** Actions → "Watch docs.neo.work" → Run workflow. The first run only saves fingerprints (no notification). After that it runs every hour on weekdays, 9 am to 7 pm IST.

To see what it would send without sending anything, run it with "Only print what would be sent" ticked.

## How it behaves

- Reads the page list from https://docs.neo.work/llms.txt and fetches each page's `.md` version. Troubleshooting, changelog, API reference and legal pages are skipped.
- A page that fails to load once is kept as it was, so a network blip never looks like a removal.
- One notification per check, listing up to 60 pages. If the desk doesn't accept it, the fingerprints aren't saved, so the next check retries.
- GitHub may start scheduled runs a few minutes late, so a docs change usually reaches the desk within 15 to 30 minutes. The 11 am IST weekday desk run is a safety net.

## Cost

Each check takes well under a minute. On a public repository Actions minutes are free. On a private repository 96 checks a day use roughly 2,900 of the 2,000 free minutes a month, so change the cron in `.github/workflows/watch-docs.yml` to `"*/30 * * * *"` (about 1,450 minutes).

Claude usage happens only when a page actually changed.

## Turning it off

Actions → "Watch docs.neo.work" → ⋯ → Disable workflow. Or delete the token in the scheduled task.
