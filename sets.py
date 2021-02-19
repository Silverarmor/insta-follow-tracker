
old_followers = ["a", "b", "d", "e"]
followers = ["b", "c", "d", "e"]

nolonger_following_me = list(set(old_followers) - set(followers))
print(nolonger_following_me)
new_following_me = list(set(followers) - set(old_followers))
print(new_following_me)
