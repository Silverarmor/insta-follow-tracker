from instagrapi import Client
from instagrapi.exceptions import LoginRequired, UserNotFound
from credentials import *
import json
from datetime import datetime, timedelta 
import os
import gspread

def get_username(user_id):
    """returns username from user_id, with error handling"""
    try:
        name = cl.user_info(user_id).username
    except UserNotFound as e:
        name = str(user_id) + " err"
    return name


def login_user():
    """
    Attempts to login to Instagram using either the provided session information
    or the provided username and password.
    """

    cl = Client()
    # cl.handle_exception = handle_exception
    cl.delay_range = [0.5, 1.5]


    session = cl.load_settings("session.json")

    login_via_session = False
    login_via_pw = False

    if session:
        try:
            cl.set_settings(session)
            cl.login(USERNAME, PASSWORD)

            # check if session is valid
            try:
                cl.get_timeline_feed()
            except LoginRequired:
                print("Session is invalid, need to login via username and password")

                old_session = cl.get_settings()

                # use the same device uuids across logins
                cl.set_settings({})
                cl.set_uuids(old_session["uuids"])

                cl.login(USERNAME, PASSWORD)
            login_via_session = True
        except Exception as e:
            print(f"Couldn't login user using session information: {e}")

    if not login_via_session:
        try:
            if cl.login(USERNAME, PASSWORD):
                login_via_pw = True
        except Exception as e:
            print(f"Couldn't login user using username and password: {e}")

    if not login_via_pw and not login_via_session:
        raise Exception("Couldn't login user with either password or session")
    
    return cl


def download_list(cl):
    # Get followers and following, as list of user ids
    followers = list(cl.user_followers(SCRAPE_ID).keys())
    following = list(cl.user_following(SCRAPE_ID).keys())

    # check the lists are not null, if they are retry
    if not followers or not following:
        print("FAIL - Retrying 1/1 to get followers and following")
        followers = list(cl.user_followers(SCRAPE_ID).keys())
        following = list(cl.user_following(SCRAPE_ID).keys())
    
    if not followers or not following:
        raise Exception("Couldn't get followers and following")

    # Change list of IDs to int type
    followers = list(map(int, followers))
    following = list(map(int, following))

    print("Writing data to json")

    with open(f"data/{today_date}.json", "w") as f:
        json.dump({"followers": followers, "following": following}, f)
    
    print("Data written to json")
    return followers, following


def read_data(read_date):
    """
    Returns followers and following from the json file with the given date
    """
    if os.path.exists(f"data/{read_date}.json"):
        with open(f"data/{read_date}.json", "r") as f:
            data = json.load(f)
        
        followers = data["followers"]
        following = data["following"]
    else:
        followers = []
        following = []

    return followers, following


def get_dates():
    global timeday, today_date, yesterday_date

    now = datetime.now()
    # init_time = now.strftime("%H:%M:%S") # Date in format HH:MM:SS
    timeday = now.strftime("%Y-%m-%d %H:%M:%S") # Date in format YYYY-MM-DD HH:MM:SS
    today_date = now.strftime("%Y-%m-%d") # Date in format YYYY-MM-DD
    yesterday_date = (now - timedelta(days=1)).strftime("%Y-%m-%d") # Date in format YYYY-MM-DD


def compare_data(cl, followers, following):
    "Read yesterdays data and compare to todays passed data"
    old_followers, old_following = read_data(yesterday_date)

    # Compare followers
    new_followers = list(set(followers) - set(old_followers))
    nolonger_followers = list(set(old_followers) - set(followers))
    new_following = list(set(following) - set(old_following))
    nolonger_following = list(set(old_following) - set(following))

    # For change list, get the usernames
    new_followers = [get_username(user_id) for user_id in new_followers]
    nolonger_followers = [get_username(user_id) for user_id in nolonger_followers]
    new_following = [get_username(user_id) for user_id in new_following]
    nolonger_following = [get_username(user_id) for user_id in nolonger_following]


    # Print the changes
    print(f"New Followers: {new_followers}")
    print(f"No Longer Followers: {nolonger_followers}")
    print(f"New Following: {new_following}")
    print(f"No Longer Following: {nolonger_following}")

    return (new_followers, nolonger_followers, new_following, nolonger_following)


def get_profile_info(cl):
    return cl.user_info_by_username(SCRAPE_USERNAME).model_dump()

def write_to_spreadsheet(follow_change, profile):
    new_followers, nolonger_followers, new_following, nolonger_following = follow_change

    # Authenticate, open and select worksheet
    gc = gspread.service_account(filename=service_account_path)
    spreadsheet = gc.open_by_key(sheet_key)
    worksheet = spreadsheet.worksheet(SCRAPE_USERNAME)

    # Construct row to write
    row = [
        timeday, profile["username"], profile["full_name"], profile["biography"],
        profile["media_count"], profile["is_private"], profile["follower_count"],
        profile["following_count"], len(new_followers), ", ".join(new_followers),
        len(nolonger_followers), ", ".join(nolonger_followers), len(new_following),
        ", ".join(new_following), len(nolonger_following), ", ".join(nolonger_following)]
    
    worksheet.append_row(row, value_input_option="USER_ENTERED", insert_data_option="INSERT_ROWS")

    print("Data written to Google Sheets")


def main():
    # Login and download follower/following data
    cl = login_user()
    get_dates()
    followers, following = download_list(cl)

    # Compare data
    follow_change = compare_data(cl, followers, following)
    profile = get_profile_info(cl)

    write_to_spreadsheet(follow_change, profile)


if __name__ == "__main__":
    main()
    # cl = login_user()
    # get_dates()

    # followers, following = read_data(today_date)

    # follow_change = compare_data(cl, followers, following)
    # profile = get_profile_info(cl)

    # write_to_spreadsheet(follow_change, profile)

    # cl = login_user()
    # download_list(cl)




