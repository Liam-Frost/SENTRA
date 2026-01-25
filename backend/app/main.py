from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask

from app.web.routes import bp as api_bp


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"

    app = create_app()
    app.run(host="0.0.0.0", port=port, debug=debug)
