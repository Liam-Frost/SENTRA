from __future__ import annotations

from pathlib import Path
import sys

import pytest
from flask import Flask

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from app.services import autonomy_service, tick_service
from app.web.routes import bp as api_bp


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setenv("SENTRA_DB_PATH", str(db_path))
    monkeypatch.setenv("SENTRA_SIM_ENABLED", "true")
    yield db_path


@pytest.fixture(autouse=True)
def reset_state(isolated_db):
    autonomy_service.set_autonomy_enabled(False, tick=0)
    tick_service.reset(reset_events=True)
    yield


@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()
