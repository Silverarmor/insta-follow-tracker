from instaclient import InstaClient
from instaclient.errors import *
from credentials import *
import os
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed
import time

# Initialise Time
now = datetime.now()
init_time = now.strftime("%H:%M:%S")

# # Uncomment if you want to prompt user for account to scrape. Else will use credentials.py's version
# scrape_username = input("Enter an Instagram account's username to scrape it's data: ")

# ! SCRAPING

# Create a instaclient object. Place as driver_path argument the path that leads to where you saved the chromedriver.exe file
client = InstaClient(driver_path=driver_path, localhost_headless=True)

# Backup where headless is not desired.
# client = InstaClient(driver_path=driver_path)

try:
    # Login
    client.login(username=username, password=password)
except VerificationCodeNecessary:
    # This error is raised if the user has 2FA turned on.
    code = input('Enter the 2FA security code generated by your Authenticator App or sent to you by SMS')
    client.input_verification_code(code)
except SuspisciousLoginAttemptError as error:
    # This error is raised by Instagram's anti-bot measures
    if error.mode == SuspisciousLoginAttemptError.EMAIL:
        code = input('Enter the security code that was sent to you via email: ')
    else:
        code = input('Enter the security code that was sent to you via SMS: ')
    client.input_security_code(code)

# Scrape Instagram followers
try:
    # Try to get the users following the scrape user, as aTuple
    followers = client.get_followers(user=scrape_username, count=None, use_api=False, callback_frequency=100)
    # Changing from Tuple to List (Taking only the first item in Tuple)
    followers = followers[0]
except InvalidUserError:
    # Exception raised if the username is not valid
    print('The username is not valid')
except PrivateAccountError:
    # Exception raised if the account you are trying to scrape is private
    print('{} is a private account'.format(username))
except:
    client.disconnect()

# Scrape Instagram following
try:
    # Try to get the users following the scrape user, as a Tuple
    following = client.get_following(user=scrape_username, count=None, use_api=False, callback_frequency=100)
    # Changing from Tuple to List (Taking only the first item in Tuple)
    following = following[0]
except InvalidUserError:
    # Exception raised if the username is not valid
    print('The username is not valid')
except PrivateAccountError:
    # Exception raised if the account you are trying to scrape is private
    print('{} is a private account'.format(username))
except:
    client.disconnect()

# Scrape Instagram profile information
try:
    # Scrape profile into 'profile' object
    profile = client.get_profile(scrape_username)
except:
    client.disconnect()

# Processing Data
following_me_only = list((set(followers) - set(following)))
following_them_only = list((set(following) - set(followers)))

# Closing the client to prevent memory leaks
client.disconnect()

# Reading File & comparing with new strings
# defining empty lists
old_following_me_only =  []
old_following_them_only = []

# Reading files
if os.path.exists('following_me_only.txt'):
    with open('following_me_only.txt', 'r') as filehandle:
        old_following_me_only = [current_place.rstrip() for current_place in filehandle.readlines()]
else:
    print("following_me_only file does not exist, skipping reading...")
    
if os.path.exists('following_them_only.txt'):
    with open('following_them_only.txt', 'r') as filehandle:
        old_following_them_only = [current_place.rstrip() for current_place in filehandle.readlines()]
else:
    print("following_them_only file does not exist, skipping reading...")

# Comparing old and current lists
if os.path.exists('following_me_only.txt') and os.path.exists('following_them_only.txt'):
    new_following_me_only = list(set(following_me_only) - set(old_following_me_only))
    nolonger_following_me_only = list(set(old_following_me_only) - set(following_me_only))

    new_following_them_only = set(following_them_only) - set(old_following_them_only)
    nolonger_following_them_only = set(old_following_them_only) - set(following_them_only)
else:
    print("Skipping comparing old and current lists. Loading the lists as full")
    new_following_me_only = following_me_only
    new_following_them_only = following_them_only
    # Set nolonger vars as empty to prevent errors.
    nolonger_following_me_only = ""
    nolonger_following_them_only = ""

# Overwriting files with new data.
with open('following_me_only.txt', 'w') as filehandle:
    filehandle.writelines("%s\n" % user for user in following_me_only)

with open('following_them_only.txt', 'w') as filehandle:
    filehandle.writelines("%s\n" % user for user in following_them_only)

# Converting into comma separated string for Discord
"""NOTE THIS ALSO CHANGES VARS FROM LIST to STR"""
new_following_me_only = (', '.join(new_following_me_only))
nolonger_following_me_only = (', '.join(nolonger_following_me_only))
new_following_them_only = (', '.join(new_following_them_only))
nolonger_following_them_only = (', '.join(nolonger_following_them_only))

# Escaping any underscores
new_following_me_only = new_following_me_only.replace("_", "\\_")
nolonger_following_me_only = nolonger_following_me_only.replace("_", "\\_")
new_following_them_only = new_following_them_only.replace("_", "\\_")
nolonger_following_me_only = nolonger_following_me_only.replace("_", "\\_")

# Splitting string into 1000 characters per list, since webhooks' embed description are limited to 1024 characters
# Maxmimum message length? Will split message(s) into this number if required.
# Split Function
def string_divide(string, div):
       list = []
       for i in range(0, len(string), div):
           list.append(string[i:i+div])
       return list

# How many chars in each string in the list?
split_length = 1000

# Splitting
new_following_me_only = string_divide(new_following_me_only, split_length)
nolonger_following_me_only = string_divide(nolonger_following_me_only, split_length)
new_following_them_only = string_divide(new_following_them_only, split_length)
nolonger_following_me_only = string_divide(nolonger_following_me_only, split_length)


# WEBHOOK SENDING
# Webhook Config
webhook = DiscordWebhook(url=discord_webhook_url, avatar_url="https://i.imgur.com/IpIG5TP.png", username="Instagram Statistics Tracker")
footer_text = "Silverarmor's Instagram tracking of " + scrape_username

# # Webhook Data Message
# VARS
data_description = "**Ran Successfully**\nTracking " + scrape_username
data_details = "**Name** - " + str(profile.name) + "\n**Private** - " + str(profile.is_private) + "\n**Business Account** - " + str(profile.is_business_account) +  "\n**Posts Count** - " + str(profile.post_count)

# Colours
color_data = 0x7289da
color_nolonger_following_me = 0xFF0000
color_new_following_me = 0x00FF00
color_nolonger_following_them = 0xFFFF00
color_new_following_them = 0xFFA500
color_no_change = 0xbfff00


# General Data Webhook
embed = DiscordEmbed(title="Silverarmor's Instagram Tracker", description=data_description, color=color_data)
embed.set_timestamp()
embed.set_footer(text="Initialised at " + str(init_time))

embed.set_thumbnail(url='https://i.imgur.com/IpIG5TP.png')

embed.add_embed_field(name="Basic Data", value="**Followers Count** - " + str(profile.follower_count) + "\n**Following Count** - " + str(profile.followed_count), inline=False)
embed.add_embed_field(name="Bio", value=profile.biography, inline=False)
embed.add_embed_field(name="Details", value=data_details, inline=False)
# embed.add_embed_field(name="Data 4", value="Data 4", inline=False)


# Add embed object to webhook
webhook.add_embed(embed)

# nolonger_following_me_only
if len(nolonger_following_me_only) > 0:
    for msg in nolonger_following_me_only:
        # Create embed object for webhook
        embed = DiscordEmbed(title="Users who stopped following you :angry:", description=msg, color=color_nolonger_following_me)
        # Add embed object to webhook
        webhook.add_embed(embed)
        time.sleep(0.5)
elif len(nolonger_following_me_only) == 0:
    # Create embed object for webhook
    embed = DiscordEmbed(title="Users who stopped following you :angry:", description="None today!", color=color_no_change)
    # Add embed object to webhook
    webhook.add_embed(embed)
    time.sleep(0.5)

# new_following_me_only
if len(new_following_me_only) > 0:
    for msg in new_following_me_only:
        # Create embed object for webhook
        embed = DiscordEmbed(title="Users who started following you", description=msg, color=color_new_following_me)
        # Add embed object to webhook
        webhook.add_embed(embed)
        time.sleep(0.5)
elif len(new_following_me_only) == 0:
    # Create embed object for webhook
    embed = DiscordEmbed(title="Users who started following you", description="None today!", color=color_no_change)
    # Add embed object to webhook
    webhook.add_embed(embed)
    time.sleep(0.5)

# nolonger_following_them_only
if len(nolonger_following_them_only) > 0:
    for msg in nolonger_following_them_only:
        # Create embed object for webhook
        embed = DiscordEmbed(title="Users you stopped following", description=msg, color=color_nolonger_following_them)
        # Add embed object to webhook
        webhook.add_embed(embed)
        time.sleep(0.5)
elif len(nolonger_following_them_only) == 0:
    # Create embed object for webhook
    embed = DiscordEmbed(title="Users you stopped following", description="None today!", color=color_no_change)
    # Add embed object to webhook
    webhook.add_embed(embed)
    time.sleep(0.5)

# new_following_them_only
if len(new_following_them_only) > 0:
    for msg in new_following_them_only:
        # Create embed object for webhook
        embed = DiscordEmbed(title="Users you started following", description=msg, color=color_new_following_them)
        # Add embed object to webhook
        webhook.add_embed(embed)
        time.sleep(0.5)
elif len(new_following_them_only) == 0:
    # Create embed object for webhook
    embed = DiscordEmbed(title="Users you started following", description="None today!", color=color_no_change)
    # Add embed object to webhook
    webhook.add_embed(embed)
    time.sleep(0.5)

# Send webhook with all created embeds
response = webhook.execute()

print("Completed")

"""
logging

# Is the logfile NOT empty?
if os.path.getsize("LOGFILE") != 0:



"""