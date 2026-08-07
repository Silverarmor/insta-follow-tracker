# insta-follow-tracker v2

Daily tracker for an Instagram account's followers/following. Each run takes a
snapshot, diffs it against the previous snapshot, and posts the changes to a
Discord webhook:

- **Users who stopped following you** :angry: (red)
- **Users who started following you** (green)
- **Users you stopped following** (blue)
- **Users you started following** (orange)

Snapshots are kept as dated JSON files in `data/`, so you also build up a
history over time.

> v1 (`insta.py` on `master`) used the abandoned `instaclient`/Selenium stack
> and no longer works. v2 is a rewrite.

## How it gets the data — pick your source

There is no official API that returns your follower *list*. Your options, from
safest to riskiest:

| Option | Allowed by IG ToS? | Works in 2026? | Bot-detection risk | Notes |
|---|---|---|---|---|
| **Official data export** (Accounts Center → Download your information) | ✅ Yes | ✅ Always | None | Manual: you must request + download the export each time. Supported here via `--source export`. |
| **Official Graph API** (business/creator account) | ✅ Yes | Partially | None | Only exposes `followers_count` — **not the list of followers**, so it can't power this tracker. (The old Basic Display API was shut down Dec 2024.) |
| **Private mobile API via `instagrapi`** (default here) | ❌ No | ✅ Yes, actively maintained | Low–medium with precautions | No browser needed. Reuses a device session, supports 2FA. Accounts doing this can be challenged ("checkpoint") or temporarily action-blocked. |
| **`instaloader`** | ❌ No | ⚠️ Mostly | Medium | Popular, but `get_followers()` is notoriously prone to 429s/`challenge_required` at the moment. |
| **Browser automation** (Selenium/Playwright — the v1 approach) | ❌ No | ⚠️ Fragile | Medium–high | Headless browsers are fingerprinted; breaks whenever the UI changes. Not worth it when instagrapi exists. |
| **Paid scraping APIs** (HikerAPI, Apify, ScrapFly, …) | ❌ No (they carry the risk) | ✅ Yes | None to *your* account | Costs money; overkill for tracking one personal account. |

**Recommendation:** default to `instagrapi` with a **burner bot account**, run
**once per day from a residential IP** (e.g. a Raspberry Pi at home — *not*
GitHub Actions/VPS datacenter IPs, which Instagram flags aggressively). If the
bot account gets banned, your main account is untouched. If you want zero
risk, use `--source export` weekly instead of daily.

### Staying under the radar (scrape mode)

- The script reuses a cached device session (`session.json`) — a fresh
  username+password login every day is the biggest red flag. Don't delete it.
- Random 3–8 s delays between every API request (`delay_range` in
  `credentials.py`).
- Run once per day, at a randomised-ish time if you can. Never in a loop.
- Warm up a brand-new bot account for a few days (log in via the app, browse,
  follow the target) before pointing the tracker at it.
- If you hit a challenge/checkpoint: resolve it in the real app or browser,
  delete `session.json`, and give the account a day off.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp example_credentials.py credentials.py   # then fill it out
```

`credentials.py` needs:

- `username` / `password` — bot account (must follow the target if it's private)
- `scrape_username` — account to track (empty = the bot account itself)
- `discord_webhook_url` — Server Settings → Integrations → Webhooks → New Webhook

## Usage

```bash
python tracker.py                 # scrape, diff, post to Discord
python tracker.py --dry-run       # no webhooks, print the diff
python tracker.py --2fa 123456    # pass a 2FA code non-interactively
python tracker.py --source export ~/Downloads/instagram-export.zip
```

The first run just saves a baseline snapshot; diffs start from the second run.

For the export mode: Accounts Center → Your information and permissions →
Download your information → select **"Followers and following"**, format
**JSON**. Point the script at the downloaded zip (or unzipped folder).

## Running daily

Cron (runs at 09:17 with up to 40 min of extra jitter, so the time isn't
robotically identical each day):

```cron
17 9 * * * sleep $((RANDOM \% 2400)) && cd /home/you/insta-follow-tracker && ./venv/bin/python tracker.py >> tracker.log 2>&1
```

Avoid scheduling from cloud CI (GitHub Actions etc.) in scrape mode —
datacenter IPs plus a login is a fast way to get the account checkpointed.
