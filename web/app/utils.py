def call(cmd):
    raise NotImplementedError("utils.call removed for security reasons; use direct os.stat or subprocess.run with a list argument")

def build(*args):
    raise NotImplementedError("utils.build removed; do not compose shell commands as strings")

def prepare_query(sql, params):
    raise NotImplementedError("utils.prepare_query removed; use cur.execute(sql, params) directly")

def sanitize_filename(filename):
    filename = filename.strip()
    filename = filename.replace("\x00", "")
    filename = filename.replace("\\", "/")
    return filename
