import os
from app import app

if __name__ == "__main__":
    app = app.create_app()
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=8000, debug=debug) # nosec B104
