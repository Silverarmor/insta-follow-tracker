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

# Optional tuning
session_file = "session.json"  # cached login session (gitignored)
delay_range = [3, 8]           # random seconds between Instagram API requests
