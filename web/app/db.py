#from . import utils

def get_user_by_username(cur, username):
    cur.execute(
        "SELECT id, username, password, is_disabled "
        "FROM users WHERE username = %s",
        (username,),
    )
    return cur.fetchone()
