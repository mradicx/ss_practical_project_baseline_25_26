import functools
import pathlib
import os
import uuid
import bcrypt
import psycopg2
import flask
import os
import dotenv
from . import db
from . import utils
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect

dotenv.load_dotenv()

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "docdb")

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".doc"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

def verify_password(plain_password, stored_hash):
    #Constant-time password verification using bcrypt
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            stored_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def get_db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME,
    )

def create_app():
    app = flask.Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )

    app.secret_key = os.getenv("SECRET_KEY", "dev-secret")
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    CSRFProtect(app)
    register_routes(app)

    return app

def get_documents_for_user(cur, owner_id):
    cur.execute(
        "SELECT id, title, filename, uploaded_at "
        "FROM documents "
        "WHERE owner_id = %s "
        "ORDER BY uploaded_at DESC",
        (owner_id,),
    )
    return cur.fetchall()

def extract_metadata(filename):
    try:
        result = os.stat(str(filename))
        return f"size={result.st_size} mtime={int(result.st_mtime)}"
    except OSError as exc:
        return f"error: {exc}"

def login_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in flask.session:
            flask.flash("Please log in first.", "error")
            return flask.redirect(flask.url_for("login"))
        return fn(*args, **kwargs)

    return wrapper

def register_routes(app):

    @app.route("/")
    def index():
        if flask.session.get("user_id"):
            return flask.redirect(flask.url_for("documents_page"))
        return flask.redirect(flask.url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():

        if flask.request.method == "POST":
            username = flask.request.form.get("username", "")
            password = flask.request.form.get("password", "")

            conn = get_db()
            cur = conn.cursor()

            user = db.get_user_by_username(cur, username)

            cur.close()
            conn.close()

            if user and verify_password(password, user[2]) and not user[3]:
            flask.session.clear()
            flask.session["user_id"] = user[0]
            flask.session["username"] = user[1]
            return flask.redirect(flask.url_for("documents_page"))

        flask.flash("Invalid credentials.", "error")

        return flask.render_template("login.html")

    @app.route("/logout")
    def logout():
        flask.session.clear()
        return flask.redirect(flask.url_for("login"))
'''
    @app.route("/documents/<int:document_id>")
    def document_details(document_id):
        conn = get_db()
        cur = conn.cursor()

        # intentionally missing authorization check
        cur.execute(utils.prepare_query("""
            SELECT id, owner_id, title, filename, metadata
            FROM documents
            WHERE id = %s
            """,
            (document_id,)))

        row = cur.fetchone()

        cur.close()
        conn.close()

        if not row:
            return "Document not found", 404

        document = {
            "id": row[0],
            "owner_id": row[1],
            "title": row[2],
            "filename": row[3],
            "metadata": row[4],
        }

        return flask.render_template("document_details.html", document=document)
'''
    @app.route("/documents/<int:document_id>")
    @login_required
    def document_details(document_id):
        current_user_id = flask.session.get("user_id")

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "SELECT id, owner_id, title, filename, metadata "
            "FROM documents WHERE id = %s",
            (document_id,),
        )
        row = cur.fetchone()

        cur.close()
        conn.close()

        if not row:
            flask.abort(404)

        # Ownership check: only the document's owner may view it.
        if row[1] != current_user_id:
            flask.abort(403)

        document = {
            "id": row[0],
            "owner_id": row[1],
            "title": row[2],
            "filename": row[3],
            "metadata": row[4],
        }

        return flask.render_template("document_details.html", document=document)
    
    @app.route("/documents")
    @login_required
    def documents_page():
        current_user_id = flask.session.get("user_id")
        # use the session identity
        owner_id = current_user_id

        conn = get_db()
        cur = conn.cursor()

        docs = get_documents_for_user(cur, owner_id)

        cur.close()
        conn.close()

        documents = [
            {
                "id": d[0],
                "title": d[1],
                "filename": d[2],
                "uploaded_at": d[3],
            }
            for d in docs
        ]

        return flask.render_template(
            "documents.html",
            documents=documents,
            requested_user_id=owner_id,
            current_user_id=current_user_id,
            username=flask.session.get("username"),
        )
'''
    @app.route("/documents/upload", methods=["POST"])
    @login_required
    def upload_document():
        user_id = flask.session.get("user_id")
        title = flask.request.form.get("title", "Untitled")
        uploaded_file = flask.request.files.get("document")

        if not uploaded_file or uploaded_file.filename == "":
            flask.flash("Please choose a file.", "error")
            return flask.redirect(flask.url_for("documents_page"))

        upload_folder = BASE_DIR / app.config["UPLOAD_FOLDER"]
        upload_folder.mkdir(parents=True, exist_ok=True)

        filename = utils.sanitize_filename(uploaded_file.filename)
        destination = upload_folder / uploaded_file.filename
        uploaded_file.save(destination)
        metadata = extract_metadata(destination)

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO documents (owner_id, title, filename, metadata)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, title, uploaded_file.filename, metadata),
        )
        conn.commit()

        cur.close()
        conn.close()

        return flask.redirect(flask.url_for("documents_page", uploaded=title))
        '''
    @app.route("/documents/upload", methods=["POST"])
    @login_required
    def upload_document():
        user_id = flask.session.get("user_id")
        title = flask.request.form.get("title", "Untitled")
        uploaded_file = flask.request.files.get("document")

        if not uploaded_file or uploaded_file.filename == "":
            flask.flash("Please choose a file.", "error")
            return flask.redirect(flask.url_for("documents_page"))

        # 1) Validate extension against an allow-list.
        original_name = utils.sanitize_filename(uploaded_file.filename)
        extension = pathlib.Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            flask.flash(
                f"File type '{extension}' is not allowed. "
                f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
                "error",
            )
            return flask.redirect(flask.url_for("documents_page"))

        # 2) Validate size (read length without loading the file in memory).
        uploaded_file.stream.seek(0, 2)  # seek to end of stream
        size = uploaded_file.stream.tell()
        uploaded_file.stream.seek(0)     # rewind for save()
        if size > MAX_UPLOAD_SIZE:
            flask.flash(
                f"File exceeds the {MAX_UPLOAD_SIZE // (1024 * 1024)} MB size limit.",
                "error",
            )
            return flask.redirect(flask.url_for("documents_page"))

        # 3) Generate a server-controlled filename. The user's filename is
        #    never used as a path component, eliminating path-traversal.
        stored_name = f"{uuid.uuid4().hex}{extension}"
        upload_folder = BASE_DIR / app.config["UPLOAD_FOLDER"]
        upload_folder.mkdir(parents=True, exist_ok=True)
        destination = upload_folder / stored_name
        uploaded_file.save(destination)

        metadata = extract_metadata(destination)

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO documents (owner_id, title, filename, metadata)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, title, stored_name, metadata),
        )
        conn.commit()

        cur.close()
        conn.close()

        return flask.redirect(flask.url_for("documents_page", uploaded=title))

    @app.route("/health")
    def health():
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            conn.close()
            return {"status": "ok"}, 200
        except Exception:
            return {"status": "error"}, 500


    # ------------------------------------------------------------------
    # Planned / Not Yet Implemented Endpoints
    #
    # The following routes are part of the intended system interface and
    # are not implemented in the baseline version of the application.
    #
    # The expected behavior of these endpoints is summarized below.
    #
    # Document operations
    #
    #   GET  /documents/<id>/download
    #       Download the specified document.
    #       Success: returns file contents (HTTP 200)
    #       Errors: 404 if the document does not exist
    #
    #   POST /documents/<id>/share
    #       Share a document with another user.
    #       Form parameter:
    #           shared_with  -> target user id
    #       Success: redirect or confirmation (HTTP 302 or 200)
    #
    # Shared documents
    #
    #   GET  /shared
    #       Display documents that were shared with the current user.
    #       Success: HTTP 200
    #
    #   GET  /shared/<id>/download
    #       Download a document that was shared with the current user.
    #       Success: returns file contents (HTTP 200)
    #
    # Administration
    #
    #   GET  /admin/users
    #       Display a list of users in the system.
    #       Success: HTTP 200
    #
    #   POST /admin/users/<id>/enable
    #       Enable a user account.
    #       Success: redirect or confirmation (HTTP 302 or 200)
    #
    #   POST /admin/users/<id>/disable
    #       Disable a user account.
    #       Success: redirect or confirmation (HTTP 302 or 200)
    #
    # ------------------------------------------------------------------
