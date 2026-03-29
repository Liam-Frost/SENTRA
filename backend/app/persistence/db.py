from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Union

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - exercised in PostgreSQL environments
    psycopg = None
    dict_row = None

DEFAULT_DB_FILENAME = "dev.sqlite3"
POSTGRES_SCHEMES = ("postgres://", "postgresql://", "postgresql+psycopg://")


class CursorCompat:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> Any:
        return self._cursor.fetchall()

    @property
    def lastrowid(self) -> Optional[int]:
        return getattr(self._cursor, "lastrowid", None)

    @property
    def rowcount(self) -> int:
        return int(getattr(self._cursor, "rowcount", -1))

    def __iter__(self):
        return iter(self._cursor)


class ConnectionCompat:
    def __init__(self, raw: Any, dialect: str) -> None:
        self._raw = raw
        self.dialect = dialect

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None) -> CursorCompat:
        if self.dialect == "postgres":
            statement = _convert_qmark_to_pyformat(sql)
            cursor = self._raw.cursor()
            if params is None:
                cursor.execute(statement)
            else:
                cursor.execute(statement, _normalize_params(params))
            return CursorCompat(cursor)

        if params is None:
            return CursorCompat(self._raw.execute(sql))
        return CursorCompat(self._raw.execute(sql, _normalize_params(params)))

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()


def get_db_path() -> Path:
    env_path = os.getenv("SENTRA_DB_PATH")
    if env_path:
        return Path(env_path)
    root = Path(__file__).resolve().parents[3]
    return root / "data" / DEFAULT_DB_FILENAME


def get_database_target(db_path: Optional[Union[str, Path]] = None) -> str:
    if db_path is not None:
        return str(db_path)

    database_url = os.getenv("SENTRA_DATABASE_URL") or os.getenv("SENTRA_DB_URL")
    if database_url:
        return database_url

    return str(get_db_path())


def get_database_backend(db_path: Optional[Union[str, Path]] = None) -> str:
    target = get_database_target(db_path).lower()
    if target.startswith(POSTGRES_SCHEMES):
        return "postgres"
    return "sqlite"


def connect(db_path: Optional[Union[str, Path]] = None) -> ConnectionCompat:
    target = get_database_target(db_path)
    backend = get_database_backend(db_path)

    if backend == "postgres":
        if psycopg is None:
            raise RuntimeError("psycopg is required for PostgreSQL connections")
        conn_str = _normalize_postgres_url(target)
        raw = psycopg.connect(conn_str, row_factory=dict_row)
        return ConnectionCompat(raw=raw, dialect="postgres")

    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(str(path), check_same_thread=False)
    raw.row_factory = sqlite3.Row
    return ConnectionCompat(raw=raw, dialect="sqlite")


def init_db(conn: ConnectionCompat) -> None:
    if is_postgres(conn):
        statements = _postgres_schema_statements()
    else:
        statements = _sqlite_schema_statements()
    for statement in statements:
        conn.execute(statement)
    conn.commit()


def clear_events(conn: ConnectionCompat) -> None:
    conn.execute("DELETE FROM events")
    conn.commit()


def clear_policy_runtime(conn: ConnectionCompat) -> None:
    conn.execute("DELETE FROM policy_condition_state")
    conn.execute("DELETE FROM policy_runtime")
    conn.commit()


def is_postgres(conn: Any) -> bool:
    return str(getattr(conn, "dialect", "")).lower() == "postgres"


def _normalize_postgres_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url[len("postgresql+psycopg://") :]
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _normalize_params(params: Iterable[Any]) -> Sequence[Any]:
    if isinstance(params, tuple):
        return params
    if isinstance(params, list):
        return tuple(params)
    return tuple(params)


def _convert_qmark_to_pyformat(sql: str) -> str:
    in_single = False
    in_double = False
    converted: list[str] = []
    index = 0
    while index < len(sql):
        char = sql[index]
        if char == "'" and not in_double:
            if in_single and index + 1 < len(sql) and sql[index + 1] == "'":
                converted.append("''")
                index += 2
                continue
            in_single = not in_single
            converted.append(char)
            index += 1
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            converted.append(char)
            index += 1
            continue
        if char == "?" and not in_single and not in_double:
            converted.append("%s")
        else:
            converted.append(char)
        index += 1
    return "".join(converted)


def _sqlite_schema_statements() -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tick INTEGER NOT NULL,
            ts TEXT NOT NULL,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            payload TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS actions (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            category TEXT,
            capability TEXT NOT NULL,
            availability TEXT NOT NULL,
            risk_level INTEGER NOT NULL,
            requires_target INTEGER NOT NULL,
            description TEXT,
            parameters_schema TEXT,
            default_parameters TEXT,
            is_system INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS policies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version INTEGER NOT NULL,
            status TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            mode TEXT NOT NULL,
            priority INTEGER NOT NULL,
            risk_level INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            data TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS policy_versions (
            policy_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            data TEXT NOT NULL,
            PRIMARY KEY (policy_id, version)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS policy_runtime (
            policy_id TEXT NOT NULL,
            target TEXT NOT NULL,
            last_fire_tick INTEGER,
            window_start_tick INTEGER,
            window_count INTEGER NOT NULL DEFAULT 0,
            last_blocked_tick INTEGER,
            PRIMARY KEY (policy_id, target)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS policy_condition_state (
            policy_id TEXT NOT NULL,
            target TEXT NOT NULL,
            condition_index INTEGER NOT NULL,
            true_since_tick INTEGER NOT NULL,
            PRIMARY KEY (policy_id, target, condition_index)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS operations (
            id TEXT PRIMARY KEY,
            action_type TEXT NOT NULL,
            status TEXT NOT NULL,
            approval_state TEXT NOT NULL,
            mode TEXT NOT NULL,
            targets TEXT NOT NULL,
            parameters TEXT,
            initiator TEXT NOT NULL,
            policy_id TEXT,
            policy_version INTEGER,
            policy_name TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS operation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id TEXT NOT NULL,
            node_id TEXT,
            status TEXT NOT NULL,
            started_at INTEGER,
            finished_at INTEGER,
            output TEXT,
            exit_code INTEGER
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS operation_run_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            operation_id TEXT NOT NULL,
            node_id TEXT,
            stream TEXT NOT NULL,
            message TEXT NOT NULL,
            ts INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY,
            hostname TEXT NOT NULL,
            ip TEXT,
            os TEXT,
            arch TEXT,
            status TEXT NOT NULL,
            metadata TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            node_id TEXT NOT NULL,
            hostname TEXT,
            version TEXT,
            token TEXT,
            capabilities TEXT,
            last_seen_at INTEGER,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS node_heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            agent_id TEXT,
            status TEXT,
            payload TEXT,
            ts INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS node_metrics_latest (
            node_id TEXT PRIMARY KEY,
            cpu_load REAL NOT NULL,
            mem_used REAL NOT NULL,
            disk_used REAL NOT NULL,
            net_in REAL NOT NULL,
            net_out REAL NOT NULL,
            temp REAL NOT NULL,
            error_rate REAL NOT NULL,
            health REAL NOT NULL,
            power REAL NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS node_metric_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            cpu_load REAL NOT NULL,
            mem_used REAL NOT NULL,
            disk_used REAL NOT NULL,
            net_in REAL NOT NULL,
            net_out REAL NOT NULL,
            temp REAL NOT NULL,
            error_rate REAL NOT NULL,
            health REAL NOT NULL,
            power REAL NOT NULL,
            ts INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS load_balancers (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            listen_port INTEGER,
            config TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS operation_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS operation_template_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            name TEXT NOT NULL,
            command TEXT NOT NULL,
            timeout_sec INTEGER NOT NULL,
            continue_on_error INTEGER NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS lb_policies (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL,
            dr_mode TEXT NOT NULL,
            health_check_path TEXT,
            health_check_interval_sec INTEGER NOT NULL,
            failure_threshold INTEGER NOT NULL,
            recovery_threshold INTEGER NOT NULL,
            auto_failback INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS lb_policy_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            weight INTEGER NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 100
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_operation_runs_operation_id
        ON operation_runs (operation_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_operation_runs_node_status
        ON operation_runs (node_id, status)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_operation_run_logs_run_id
        ON operation_run_logs (run_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_node_metric_samples_node_ts
        ON node_metric_samples (node_id, ts)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_node_heartbeats_node_ts
        ON node_heartbeats (node_id, ts)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_operation_template_steps_template
        ON operation_template_steps (template_id, position)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_lb_policies_project
        ON lb_policies (project_id, updated_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_lb_policy_allocations_policy
        ON lb_policy_allocations (policy_id, priority)
        """,
    ]


def _postgres_schema_statements() -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS events (
            id BIGSERIAL PRIMARY KEY,
            tick BIGINT NOT NULL,
            ts TEXT NOT NULL,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            payload TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS actions (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            category TEXT,
            capability TEXT NOT NULL,
            availability TEXT NOT NULL,
            risk_level INTEGER NOT NULL,
            requires_target SMALLINT NOT NULL,
            description TEXT,
            parameters_schema TEXT,
            default_parameters TEXT,
            is_system SMALLINT NOT NULL DEFAULT 0,
            created_at BIGINT NOT NULL,
            updated_at BIGINT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS policies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version INTEGER NOT NULL,
            status TEXT NOT NULL,
            enabled SMALLINT NOT NULL,
            mode TEXT NOT NULL,
            priority INTEGER NOT NULL,
            risk_level INTEGER NOT NULL,
            created_at BIGINT NOT NULL,
            updated_at BIGINT NOT NULL,
            data TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS policy_versions (
            policy_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            created_at BIGINT NOT NULL,
            data TEXT NOT NULL,
            PRIMARY KEY (policy_id, version)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS policy_runtime (
            policy_id TEXT NOT NULL,
            target TEXT NOT NULL,
            last_fire_tick BIGINT,
            window_start_tick BIGINT,
            window_count INTEGER NOT NULL DEFAULT 0,
            last_blocked_tick BIGINT,
            PRIMARY KEY (policy_id, target)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS policy_condition_state (
            policy_id TEXT NOT NULL,
            target TEXT NOT NULL,
            condition_index INTEGER NOT NULL,
            true_since_tick BIGINT NOT NULL,
            PRIMARY KEY (policy_id, target, condition_index)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS operations (
            id TEXT PRIMARY KEY,
            action_type TEXT NOT NULL,
            status TEXT NOT NULL,
            approval_state TEXT NOT NULL,
            mode TEXT NOT NULL,
            targets TEXT NOT NULL,
            parameters TEXT,
            initiator TEXT NOT NULL,
            policy_id TEXT,
            policy_version INTEGER,
            policy_name TEXT,
            created_at BIGINT NOT NULL,
            updated_at BIGINT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS operation_runs (
            id BIGSERIAL PRIMARY KEY,
            operation_id TEXT NOT NULL,
            node_id TEXT,
            status TEXT NOT NULL,
            started_at BIGINT,
            finished_at BIGINT,
            output TEXT,
            exit_code INTEGER
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS operation_run_logs (
            id BIGSERIAL PRIMARY KEY,
            run_id BIGINT NOT NULL,
            operation_id TEXT NOT NULL,
            node_id TEXT,
            stream TEXT NOT NULL,
            message TEXT NOT NULL,
            ts BIGINT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY,
            hostname TEXT NOT NULL,
            ip TEXT,
            os TEXT,
            arch TEXT,
            status TEXT NOT NULL,
            metadata TEXT,
            created_at BIGINT NOT NULL,
            updated_at BIGINT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            node_id TEXT NOT NULL,
            hostname TEXT,
            version TEXT,
            token TEXT,
            capabilities TEXT,
            last_seen_at BIGINT,
            created_at BIGINT NOT NULL,
            updated_at BIGINT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS node_heartbeats (
            id BIGSERIAL PRIMARY KEY,
            node_id TEXT NOT NULL,
            agent_id TEXT,
            status TEXT,
            payload TEXT,
            ts BIGINT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS node_metrics_latest (
            node_id TEXT PRIMARY KEY,
            cpu_load DOUBLE PRECISION NOT NULL,
            mem_used DOUBLE PRECISION NOT NULL,
            disk_used DOUBLE PRECISION NOT NULL,
            net_in DOUBLE PRECISION NOT NULL,
            net_out DOUBLE PRECISION NOT NULL,
            temp DOUBLE PRECISION NOT NULL,
            error_rate DOUBLE PRECISION NOT NULL,
            health DOUBLE PRECISION NOT NULL,
            power DOUBLE PRECISION NOT NULL,
            updated_at BIGINT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS node_metric_samples (
            id BIGSERIAL PRIMARY KEY,
            node_id TEXT NOT NULL,
            cpu_load DOUBLE PRECISION NOT NULL,
            mem_used DOUBLE PRECISION NOT NULL,
            disk_used DOUBLE PRECISION NOT NULL,
            net_in DOUBLE PRECISION NOT NULL,
            net_out DOUBLE PRECISION NOT NULL,
            temp DOUBLE PRECISION NOT NULL,
            error_rate DOUBLE PRECISION NOT NULL,
            health DOUBLE PRECISION NOT NULL,
            power DOUBLE PRECISION NOT NULL,
            ts BIGINT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at BIGINT NOT NULL,
            updated_at BIGINT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS load_balancers (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            listen_port INTEGER,
            config TEXT,
            created_at BIGINT NOT NULL,
            updated_at BIGINT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS operation_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at BIGINT NOT NULL,
            updated_at BIGINT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS operation_template_steps (
            id BIGSERIAL PRIMARY KEY,
            template_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            name TEXT NOT NULL,
            command TEXT NOT NULL,
            timeout_sec INTEGER NOT NULL,
            continue_on_error SMALLINT NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS lb_policies (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL,
            dr_mode TEXT NOT NULL,
            health_check_path TEXT,
            health_check_interval_sec INTEGER NOT NULL,
            failure_threshold INTEGER NOT NULL,
            recovery_threshold INTEGER NOT NULL,
            auto_failback SMALLINT NOT NULL DEFAULT 0,
            created_at BIGINT NOT NULL,
            updated_at BIGINT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS lb_policy_allocations (
            id BIGSERIAL PRIMARY KEY,
            policy_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            weight INTEGER NOT NULL,
            enabled SMALLINT NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 100
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_operation_runs_operation_id
        ON operation_runs (operation_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_operation_runs_node_status
        ON operation_runs (node_id, status)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_operation_run_logs_run_id
        ON operation_run_logs (run_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_node_metric_samples_node_ts
        ON node_metric_samples (node_id, ts)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_node_heartbeats_node_ts
        ON node_heartbeats (node_id, ts)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_operation_template_steps_template
        ON operation_template_steps (template_id, position)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_lb_policies_project
        ON lb_policies (project_id, updated_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_lb_policy_allocations_policy
        ON lb_policy_allocations (policy_id, priority)
        """,
    ]
