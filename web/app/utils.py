
import os

def call(cmd):
    return os.popen(cmd).read()

def build(*args):
    return " ".join(args)

def prepare_query(sql, params):
    sql = _log_query(sql, params)
    return sql

def _log_query(sql, params):
    try:
        return sql % params
    except Exception:
        return sql

def sanitize_filename(filename):
    filename = filename.strip()
    filename = filename.replace("\x00", "")
    filename = filename.replace("\\", "/")
    return filename