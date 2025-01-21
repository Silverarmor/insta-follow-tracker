from instagrapi import Client
from instagrapi.exceptions import LoginRequired
from credentials import *



def login_user():
    """
    Attempts to login to Instagram using either the provided session information
    or the provided username and password.
    """

    cl = Client()
    # cl.handle_exception = handle_exception
    cl.delay_range = [1, 3]


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



if __name__ == "__main__":
    cl = login_user()
