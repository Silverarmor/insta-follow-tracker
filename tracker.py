#!/usr/bin/env python3
"""Instagram follower/following tracker.

Takes a daily snapshot of an account's followers and following lists,
diffs it against the previous snapshot, and reports the changes to a
Discord webhook:

  - Users who stopped following you :angry:
  - Users who started following you
  - Users you stopped following
  - Users you started following

Two data sources are supported:

  scrape (default) - logs in with a bot account via instagrapi (private
      mobile API). Convenient but against Instagram ToS; use a burner
      account, a residential IP and run at most once per day.

  export - parses Instagram's official "Download your information"
      export (Accounts Center -> Your information and permissions).
      Fully allowed, zero ban risk, but you have to request the export
      manually each time:  python tracker.py --source export <zip-or-dir>

Snapshots are stored under data/ as dated JSON files; the newest one is
the baseline for the next run's diff.
"""

import argparse
import json
import random
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

import requests

VERSION = "v2.0.0"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Discord embed colours (same scheme as v1)
COLOR_DATA = 0x7289DA
COLOR_NOLONGER_FOLLOWERS = 0xFF0000
COLOR_NEW_FOLLOWERS = 0x00FF00
COLOR_NOLONGER_FOLLOWING = 0x0000FF
COLOR_NEW_FOLLOWING = 0xFF8C00
COLOR_NO_CHANGE = 0xFFFFFF
COLOR_ERROR = 0xFF0000

WEBHOOK_USERNAME = "Instagram Statistics Tracker"
WEBHOOK_AVATAR = "https://i.imgur.com/IpIG5TP.png"

# Discord embed descriptions cap at 4096 chars; stay well under it.
CHUNK_SIZE = 1000


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

def load_config():
    try:
        import credentials
    except ImportError:
        sys.exit(
            "credentials.py not found. Copy example_credentials.py to "
            "credentials.py and fill it out."
        )
    cfg = {
        "scrape_username": getattr(credentials, "scrape_username", "") or "",
        "username": getattr(credentials, "username", "") or "",
        "password": getattr(credentials, "password", "") or "",
        "discord_webhook_url": getattr(credentials, "discord_webhook_url", "") or "",
        "session_file": getattr(credentials, "session_file", "session.json"),
        "delay_range": getattr(credentials, "delay_range", [3, 8]),
    }
    return cfg


# --------------------------------------------------------------------------
# Discord webhook
# --------------------------------------------------------------------------

class DiscordReporter:
    def __init__(self, webhook_url, enabled=True):
        self.webhook_url = webhook_url
        self.enabled = enabled and bool(webhook_url)

    def send_embed(self, title, description="", color=COLOR_DATA, fields=None,
                   footer=None, timestamp=True):
        embed = {"title": title, "color": color}
        if description:
            embed["description"] = description
        if fields:
            embed["fields"] = [
                {"name": n, "value": v, "inline": False} for n, v in fields
            ]
        if footer:
            embed["footer"] = {"text": footer}
        if timestamp:
            embed["timestamp"] = datetime.utcnow().isoformat()

        if not self.enabled:
            print(f"[dry-run webhook] {title}: {description[:120]}")
            return

        payload = {
            "username": WEBHOOK_USERNAME,
            "avatar_url": WEBHOOK_AVATAR,
            "embeds": [embed],
        }
        resp = requests.post(self.webhook_url, json=payload, timeout=30)
        if resp.status_code == 429:
            retry_after = resp.json().get("retry_after", 2)
            time.sleep(float(retry_after) + 0.5)
            resp = requests.post(self.webhook_url, json=payload, timeout=30)
        resp.raise_for_status()
        time.sleep(0.5)  # stay clear of Discord rate limits

    def send_change_category(self, title, usernames, color):
        if not usernames:
            self.send_embed(title, "None today!", color=COLOR_NO_CHANGE)
            return
        # Escape underscores so Discord doesn't italicise usernames
        joined = ", ".join(u.replace("_", "\\_") for u in sorted(usernames))
        for i in range(0, len(joined), CHUNK_SIZE):
            self.send_embed(title, joined[i:i + CHUNK_SIZE], color=color)


# --------------------------------------------------------------------------
# Source: instagrapi scrape
# --------------------------------------------------------------------------

def fetch_via_scrape(cfg, verification_code=""):
    try:
        from instagrapi import Client
        from instagrapi.exceptions import (
            ChallengeRequired,
            LoginRequired,
            TwoFactorRequired,
        )
    except ImportError:
        sys.exit("instagrapi is not installed. Run: pip install -r requirements.txt")

    if not cfg["username"] or not cfg["password"]:
        sys.exit("username/password missing from credentials.py")

    cl = Client()
    # Randomised delay between every API request - the single most
    # effective anti-detection knob instagrapi exposes.
    cl.delay_range = cfg["delay_range"]

    session_path = BASE_DIR / cfg["session_file"]

    def login():
        if session_path.exists():
            # Reusing the device/session is far less suspicious than a
            # fresh username+password login every day.
            cl.load_settings(session_path)
        try:
            cl.login(cfg["username"], cfg["password"],
                     verification_code=verification_code)
        except TwoFactorRequired:
            code = verification_code or input("Enter the 2FA code: ").strip()
            cl.login(cfg["username"], cfg["password"], verification_code=code)
        cl.dump_settings(session_path)

    login()
    print("Logged in")

    target = cfg["scrape_username"] or cfg["username"]
    try:
        user_id = cl.user_id_from_username(target)
        time.sleep(random.uniform(*cfg["delay_range"]))

        info = cl.user_info(user_id)
        time.sleep(random.uniform(*cfg["delay_range"]))

        print(f"Fetching followers of {target} ({info.follower_count})...")
        followers = [u.username for u in cl.user_followers(user_id).values()]
        time.sleep(random.uniform(*cfg["delay_range"]))

        print(f"Fetching following of {target} ({info.following_count})...")
        following = [u.username for u in cl.user_following(user_id).values()]
    except (ChallengeRequired, LoginRequired) as exc:
        raise RuntimeError(
            f"Instagram challenged the login ({type(exc).__name__}). "
            "Log into the bot account in a real browser/app, resolve the "
            "checkpoint, delete session.json and try again tomorrow."
        ) from exc

    profile = {
        "username": info.username,
        "full_name": info.full_name,
        "biography": info.biography,
        "follower_count": info.follower_count,
        "following_count": info.following_count,
        "post_count": info.media_count,
        "is_private": info.is_private,
    }
    return followers, following, profile


# --------------------------------------------------------------------------
# Source: official Instagram data export
# --------------------------------------------------------------------------

def _usernames_from_export_json(obj):
    """Both followers_1.json and following.json boil down to a list of
    {"string_list_data": [{"value": "<username>", ...}]} records."""
    if isinstance(obj, dict):
        # following.json wraps the list in {"relationships_following": [...]}
        for value in obj.values():
            if isinstance(value, list):
                obj = value
                break
        else:
            return []
    names = []
    for entry in obj:
        for item in entry.get("string_list_data", []):
            if item.get("value"):
                names.append(item["value"])
    return names


def fetch_via_export(export_path):
    path = Path(export_path)
    if not path.exists():
        sys.exit(f"Export path not found: {path}")

    def read_json(root, relative_hint):
        """Find a file whose name matches the hint inside a dir or zip."""
        if root.is_dir():
            matches = sorted(root.rglob(relative_hint))
            if not matches:
                return None
            merged = []
            for m in matches:
                merged.append(json.loads(m.read_text(encoding="utf-8")))
            return merged
        with zipfile.ZipFile(root) as zf:
            merged = []
            for name in sorted(zf.namelist()):
                if Path(name).name.startswith(relative_hint.replace("*", "").replace(".json", "")) and name.endswith(".json"):
                    merged.append(json.loads(zf.read(name)))
            return merged or None

    followers_docs = read_json(path, "followers_1.json") or read_json(path, "followers*.json")
    following_docs = read_json(path, "following.json")

    if not followers_docs or not following_docs:
        sys.exit(
            "Could not find followers_1.json / following.json in the export.\n"
            "Make sure you requested the export in JSON format (not HTML) and "
            "included 'Followers and following'."
        )

    followers = []
    for doc in followers_docs:
        followers.extend(_usernames_from_export_json(doc))
    following = []
    for doc in following_docs:
        following.extend(_usernames_from_export_json(doc))

    profile = {
        "username": "(from export)",
        "follower_count": len(followers),
        "following_count": len(following),
    }
    return followers, following, profile


# --------------------------------------------------------------------------
# Snapshots & diffing
# --------------------------------------------------------------------------

def latest_snapshot():
    if not DATA_DIR.exists():
        return None
    snapshots = sorted(DATA_DIR.glob("snapshot-*.json"))
    if not snapshots:
        return None
    return json.loads(snapshots[-1].read_text(encoding="utf-8"))


def save_snapshot(followers, following, profile):
    DATA_DIR.mkdir(exist_ok=True)
    now = datetime.now()
    snapshot = {
        "taken_at": now.isoformat(timespec="seconds"),
        "profile": profile,
        "followers": sorted(followers),
        "following": sorted(following),
    }
    out = DATA_DIR / f"snapshot-{now.strftime('%Y-%m-%d')}.json"
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    return out


def diff_lists(old, new):
    old_set, new_set = set(old), set(new)
    return sorted(new_set - old_set), sorted(old_set - new_set)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", choices=["scrape", "export"],
                        default="scrape",
                        help="scrape = instagrapi login (default); "
                             "export = parse an official Instagram data export")
    parser.add_argument("export_path", nargs="?",
                        help="path to the export zip/folder (source=export)")
    parser.add_argument("--2fa", dest="two_fa", default="",
                        help="current 2FA code, for non-interactive runs")
    parser.add_argument("--dry-run", action="store_true",
                        help="don't send webhooks, just print the diff")
    args = parser.parse_args()

    cfg = load_config()
    reporter = DiscordReporter(cfg["discord_webhook_url"],
                               enabled=not args.dry_run)

    if args.source == "export" and not args.export_path:
        parser.error("--source export requires the export zip/folder path")

    # ---- Fetch current lists -------------------------------------------
    try:
        if args.source == "export":
            followers, following, profile = fetch_via_export(args.export_path)
        else:
            followers, following, profile = fetch_via_scrape(cfg, args.two_fa)
    except Exception as exc:
        reporter.send_embed("Error", f"Tracker failed: `{exc}`",
                            color=COLOR_ERROR, footer=VERSION)
        raise

    if not followers and not following:
        reporter.send_embed(
            "Error",
            "Scrape returned empty follower AND following lists - not "
            "saving a snapshot (a bad scrape would poison tomorrow's diff).",
            color=COLOR_ERROR, footer=VERSION)
        sys.exit("Empty scrape; aborting without saving.")

    # ---- Diff against previous snapshot --------------------------------
    previous = latest_snapshot()
    first_run = previous is None
    if first_run:
        new_followers = lost_followers = new_following = lost_following = []
    else:
        new_followers, lost_followers = diff_lists(previous["followers"], followers)
        new_following, lost_following = diff_lists(previous["following"], following)

    snapshot_path = save_snapshot(followers, following, profile)
    print(f"Snapshot saved to {snapshot_path}")

    # ---- Report --------------------------------------------------------
    summary = (
        f"**Users who started following you** - {len(new_followers)}\n"
        f"**Users who stopped following you** - {len(lost_followers)}\n"
        f"**Users you started following** - {len(new_following)}\n"
        f"**Users you stopped following** - {len(lost_following)}"
    )
    basic = (
        f"**Followers Count** - {profile.get('follower_count', len(followers))}\n"
        f"**Following Count** - {profile.get('following_count', len(following))}"
    )
    fields = [("Basic Data", basic), ("Summary", summary)]
    if profile.get("biography"):
        fields.insert(1, ("Bio", f"```{profile['biography']}```"))

    description = "**Ran Successfully**\nTracking " + (
        cfg["scrape_username"] or profile.get("username", "?"))
    if first_run:
        description += "\n\nFirst run - baseline snapshot saved, no diff yet."

    reporter.send_embed(profile.get("username", "Instagram") + "'s Instagram Tracker",
                        description, color=COLOR_DATA, fields=fields,
                        footer=VERSION)

    if not first_run:
        reporter.send_change_category(
            "Users who stopped following you :angry:", lost_followers,
            COLOR_NOLONGER_FOLLOWERS)
        reporter.send_change_category(
            "Users who started following you", new_followers,
            COLOR_NEW_FOLLOWERS)
        reporter.send_change_category(
            "Users you stopped following", lost_following,
            COLOR_NOLONGER_FOLLOWING)
        reporter.send_change_category(
            "Users you started following", new_following,
            COLOR_NEW_FOLLOWING)

    if args.dry_run and not first_run:
        print("\n--- Diff ---")
        print("Stopped following you:", ", ".join(lost_followers) or "none")
        print("Started following you:", ", ".join(new_followers) or "none")
        print("You stopped following:", ", ".join(lost_following) or "none")
        print("You started following:", ", ".join(new_following) or "none")

    print("Done.")


if __name__ == "__main__":
    main()
