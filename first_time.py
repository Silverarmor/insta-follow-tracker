from instagrapi import Client
from credentials import *


cl = Client()
cl.login(USERNAME, PASSWORD)
cl.dump_settings("session.json")
