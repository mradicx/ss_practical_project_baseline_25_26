from . import utils

def get_user_by_username(cur, username):
    query = utils.prepare_query("SELECT id, username, password, is_disabled FROM users WHERE username='%s'", username)
    cur.execute(query)
    return cur.fetchone()
