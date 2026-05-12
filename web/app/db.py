#from . import utils

def get_user_by_username(cur, username):
    cur.execute(
        "SELECT id, username, password, is_disabled "
        "FROM users WHERE username = %s",
        (username,),
    )
    return cur.fetchone()


def get_all_users(cur):
    cur.execute(
        "SELECT id, username, is_disabled FROM users ORDER BY id"
    )
    return cur.fetchall()


def enable_user_by_id(cur, user_id):
    cur.execute(
        "UPDATE users SET is_disabled = false WHERE id = %s",
        (user_id,),
    )


def disable_user_by_id(cur, user_id):
    cur.execute(
        "UPDATE users SET is_disabled = true WHERE id = %s",
        (user_id,),
    )
