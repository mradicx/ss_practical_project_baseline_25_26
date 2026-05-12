import functools
import pathlib
import os
import uuid
import logging
import bcrypt
import psycopg2
import flask
import dotenv
from flask_wtf.csrf import CSRFProtect
from . import db
from . import utils

dotenv.load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
audit_logger = logging.getLogger("audit")

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
    """Constant-time password verification using bcrypt."""
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


def admin_required(fn):
    """Restricts a route to the admin account.

    Must be applied AFTER @login_required so that an unauthenticated
    request is redirected to /login (handled by login_required) rather
    than aborted as 403. Identifies the admin by session username,
    which is set during /login from the authenticated users row.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if flask.session.get("username") != "admin":
            audit_logger.warning(
                f"admin_access_denied user_id={flask.session.get('user_id')} "
                f"username={flask.session.get('username')!r} "
                f"path={flask.request.path}"
            )
            flask.abort(403)
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
                audit_logger.info(
                    f"login_success user_id={user[0]} username={user[1]!r} "
                    f"ip={flask.request.remote_addr}"
                )
                return flask.redirect(flask.url_for("documents_page"))

            audit_logger.warning(
                f"login_failure username={username!r} "
                f"ip={flask.request.remote_addr}"
            )
            flask.flash("Invalid credentials.", "error")

        return flask.render_template("login.html")

    @app.route("/logout")
    def logout():
        flask.session.clear()
        return flask.redirect(flask.url_for("login"))

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

        if row[1] != current_user_id:
            audit_logger.warning(
                f"document_access_denied user_id={current_user_id} "
                f"document_id={document_id} owner_id={row[1]}"
            )
            flask.abort(403)

        audit_logger.info(
            f"document_view user_id={current_user_id} document_id={document_id}"
        )

        document = {
            "id": row[0],
            "owner_id": row[1],
            "title": row[2],
            "filename": row[3],
            "metadata": row[4],
        }

        return flask.render_template("document_details.html", document=document)

    @app.route("/documents/<int:document_id>/download")
    @login_required
    def download_document(document_id):
        current_user_id = flask.session.get("user_id")

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "SELECT id, owner_id, filename "
            "FROM documents WHERE id = %s",
            (document_id,),
        )
        row = cur.fetchone()

        cur.close()
        conn.close()

        if not row:
            flask.abort(404)

        if row[1] != current_user_id:
            audit_logger.warning(
                f"download_access_denied user_id={current_user_id} "
                f"document_id={document_id} owner_id={row[1]}"
            )
            flask.abort(403)

        stored_name = row[2]
        upload_folder = BASE_DIR / app.config["UPLOAD_FOLDER"]

        audit_logger.info(
            f"download_success user_id={current_user_id} "
            f"document_id={document_id} stored_name={stored_name}"
        )

        # send_from_directory ensures stored_name is resolved relative to
        # upload_folder and refuses path-traversal attempts.
        return flask.send_from_directory(
            str(upload_folder), stored_name, as_attachment=True
        )

    @app.route("/documents")
    @login_required
    def documents_page():
        current_user_id = flask.session.get("user_id")
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

    @app.route("/documents/upload", methods=["POST"])
    @login_required
    def upload_document():
        user_id = flask.session.get("user_id")
        title = flask.request.form.get("title", "Untitled")
        uploaded_file = flask.request.files.get("document")

        if not uploaded_file or uploaded_file.filename == "":
            flask.flash("Please choose a file.", "error")
            return flask.redirect(flask.url_for("documents_page"))

        original_name = utils.sanitize_filename(uploaded_file.filename)
        extension = pathlib.Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            audit_logger.warning(
                f"upload_rejected_extension user_id={user_id} "
                f"extension={extension!r}"
            )
            flask.flash(
                f"File type '{extension}' is not allowed. "
                f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
                "error",
            )
            return flask.redirect(flask.url_for("documents_page"))

        uploaded_file.stream.seek(0, 2)
        size = uploaded_file.stream.tell()
        uploaded_file.stream.seek(0)
        if size > MAX_UPLOAD_SIZE:
            audit_logger.warning(
                f"upload_rejected_size user_id={user_id} size={size}"
            )
            flask.flash(
                f"File exceeds the {MAX_UPLOAD_SIZE // (1024 * 1024)} MB size limit.",
                "error",
            )
            return flask.redirect(flask.url_for("documents_page"))

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

        audit_logger.info(
            f"upload_success user_id={user_id} stored_name={stored_name}"
        )
        return flask.redirect(flask.url_for("documents_page", uploaded=title))

    @app.route("/admin/users")
    @login_required
    @admin_required
    def admin_users():
        current_user_id = flask.session.get("user_id")

        conn = get_db()
        cur = conn.cursor()

        rows = db.get_all_users(cur)

        cur.close()
        conn.close()

        users = [
            {"id": row[0], "username": row[1], "is_disabled": row[2]}
            for row in rows
        ]

        audit_logger.info(
            f"admin_users_listed user_id={current_user_id} count={len(users)}"
        )

        return flask.render_template(
            "users.html",
            users=users,
            current_user_id=current_user_id,
            username=flask.session.get("username"),
        )

    @app.route("/admin/users/<int:user_id>/enable", methods=["POST"])
    @login_required
    @admin_required
    def enable_user(user_id):
        current_user_id = flask.session.get("user_id")

        conn = get_db()
        cur = conn.cursor()

        db.enable_user_by_id(cur, user_id)
        conn.commit()

        cur.close()
        conn.close()

        audit_logger.info(
            f"user_enabled by_user_id={current_user_id} target_user_id={user_id}"
        )
        flask.flash("User enabled.", "success")
        return flask.redirect(flask.url_for("admin_users"))

    @app.route("/admin/users/<int:user_id>/disable", methods=["POST"])
    @login_required
    @admin_required
    def disable_user(user_id):
        current_user_id = flask.session.get("user_id")

        # Defence-in-depth: prevent admin from disabling themselves
        # even if the UI is bypassed.
        if user_id == current_user_id:
            audit_logger.warning(
                f"admin_self_disable_attempt user_id={current_user_id}"
            )
            flask.flash("Cannot disable your own account.", "error")
            return flask.redirect(flask.url_for("admin_users"))

        conn = get_db()
        cur = conn.cursor()

        db.disable_user_by_id(cur, user_id)
        conn.commit()

        cur.close()
        conn.close()

        audit_logger.info(
            f"user_disabled by_user_id={current_user_id} target_user_id={user_id}"
        )
        flask.flash("User disabled.", "success")
        return flask.redirect(flask.url_for("admin_users"))

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
    # Document sharing operations remain out of scope for this delivery:
    #
    #   POST /documents/<id>/share         (share with another user)
    #   GET  /shared                       (list documents shared with you)
    #   GET  /shared/<id>/download         (download a shared document)
    #
    # Implementation would require an additional document_shares
    # association table in the database schema and corresponding
    # templates
    # ------------------------------------------------------------------
