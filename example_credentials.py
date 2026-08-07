# Copy this file to credentials.py and fill it out.
# credentials.py is gitignored - never commit it.

# Account to track. Leave empty ("") to track the bot account itself.
# If the tracked account is private, the bot account must follow it.
scrape_username = ""

# Bot account credentials (use a burner account, NOT your main account)
username = "instagram"
password = "password"

# Discord webhook URL (Server Settings -> Integrations -> Webhooks)
discord_webhook_url = "https://discord.com/api/webhooks/..."

# Optional: Google Sheets backup (leave both "" to disable).
# One row is appended per run, including the full follower/following lists,
# so history survives if the machine running the tracker dies.
service_account_path = ""      # e.g. "service_account.json"
sheet_key = ""                 # the long ID in the sheet's URL
worksheet_name = ""            # tab name; defaults to the tracked username

# Optional tuning
session_file = "session.json"  # cached login session (gitignored)
delay_range = [3, 8]           # random seconds between Instagram API requests
