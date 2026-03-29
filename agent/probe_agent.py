from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests

try:
    import psutil
except ImportError:
    psutil = None


@dataclass
class AgentConfig:
    panel_url: str
    agent_id: str
    node_id: str
    hostname: str
    token: str
    interval_sec: float
    timeout_sec: int
    verify_tls: bool
    dry_run: bool


def main() -> int:
    cfg = load_config()
    print(f"[agent] starting agent_id={cfg.agent_id} node_id={cfg.node_id}")

    try:
        register(cfg)
    except Exception as exc:
        print(f"[agent] register failed: {exc}")

    while True:
        loop_started = time.time()
        try:
            send_heartbeat(cfg)
            send_metrics(cfg)
            run_next_command(cfg)
        except Exception as exc:
            print(f"[agent] loop error: {exc}")

        elapsed = time.time() - loop_started
        wait_for = max(0.5, cfg.interval_sec - elapsed)
        time.sleep(wait_for)


def load_config() -> AgentConfig:
    panel_url = str(os.getenv("SENTRA_PANEL_URL") or "http://127.0.0.1:5000").rstrip("/")
    hostname = str(os.getenv("SENTRA_NODE_HOSTNAME") or socket.gethostname())
    node_id = str(os.getenv("SENTRA_NODE_ID") or hostname)
    agent_id = str(os.getenv("SENTRA_AGENT_ID") or f"agent-{node_id}")
    token = str(os.getenv("SENTRA_AGENT_TOKEN") or "")
    interval = float(os.getenv("SENTRA_AGENT_INTERVAL", "3"))
    timeout = int(os.getenv("SENTRA_AGENT_TIMEOUT", "60"))
    verify_tls = _read_bool("SENTRA_AGENT_VERIFY_TLS", True)
    dry_run = _read_bool("SENTRA_AGENT_DRY_RUN", True)
    return AgentConfig(
        panel_url=panel_url,
        agent_id=agent_id,
        node_id=node_id,
        hostname=hostname,
        token=token,
        interval_sec=max(1.0, interval),
        timeout_sec=max(5, timeout),
        verify_tls=verify_tls,
        dry_run=dry_run,
    )


def register(cfg: AgentConfig) -> None:
    body = {
        "agent_id": cfg.agent_id,
        "node_id": cfg.node_id,
        "hostname": cfg.hostname,
        "ip": _detect_ip(),
        "os": platform.system().lower(),
        "arch": platform.machine().lower(),
        "version": "v1",
        "capabilities": {
            "run_command": True,
            "run_script": True,
            "restart_host": True,
            "shutdown_host": True,
            "deploy_lb_node": True,
            "remove_lb_node": True,
        },
        "token": cfg.token,
    }
    panel_post(cfg, "/api/agents/register", body)


def send_heartbeat(cfg: AgentConfig) -> None:
    panel_post(
        cfg,
        "/api/agents/heartbeat",
        {
            "agent_id": cfg.agent_id,
            "status": "online",
            "payload": {"dry_run": cfg.dry_run},
        },
    )


def send_metrics(cfg: AgentConfig) -> None:
    metrics = collect_metrics()
    panel_post(
        cfg,
        "/api/agents/metrics",
        {
            "agent_id": cfg.agent_id,
            "metrics": metrics,
            "ts": int(time.time() * 1000),
        },
    )


def run_next_command(cfg: AgentConfig) -> None:
    data = panel_get(
        cfg,
        "/api/agents/commands/next",
        params={"agent_id": cfg.agent_id},
    )
    command = data.get("command") if isinstance(data, dict) else None
    if not isinstance(command, dict):
        return

    run_id = int(command.get("runId"))
    action = str(command.get("action") or "")
    params = command.get("parameters") if isinstance(command.get("parameters"), dict) else {}

    post_log(cfg, run_id, "system", f"execute action={action}")
    ok, output, exit_code = execute_action(cfg, action, params)
    if action == "template_execution" and output:
        for line in str(output).splitlines():
            text = line.strip()
            if text:
                post_log(cfg, run_id, "stdout" if ok else "stderr", text[:2000])
    post_result(
        cfg,
        run_id,
        status="succeeded" if ok else "failed",
        output=output,
        exit_code=exit_code,
    )


def execute_action(cfg: AgentConfig, action: str, params: Dict[str, Any]) -> Tuple[bool, str, int]:
    if action == "template_execution":
        steps = params.get("steps") if isinstance(params.get("steps"), list) else []
        if not steps:
            return False, "missing parameters.steps", 2
        outputs: list[str] = []
        had_failure = False
        for index, raw_step in enumerate(steps, start=1):
            if not isinstance(raw_step, dict):
                return False, f"invalid step payload at {index}", 2
            step_name = str(raw_step.get("name") or f"Step {index}")
            command = str(raw_step.get("command") or "").strip()
            if not command:
                return False, f"missing command for step {index}", 2
            timeout = int(raw_step.get("timeoutSec") or raw_step.get("timeout") or cfg.timeout_sec)
            ok, output, exit_code = execute_shell(cfg, command, timeout)
            step_output = f"[{index}] {step_name}: {output}".strip()
            outputs.append(step_output)
            if not ok:
                had_failure = True
                if not bool(raw_step.get("continueOnError") or raw_step.get("continue_on_error")):
                    return False, "\n".join(outputs), int(exit_code)
        return (not had_failure), "\n".join(outputs), 0 if not had_failure else 1

    if action == "run_command":
        command = str(params.get("command") or "").strip()
        if not command:
            return False, "missing parameters.command", 2
        return execute_shell(cfg, command, int(params.get("timeout") or cfg.timeout_sec))

    if action == "run_script":
        script = str(params.get("script_path") or "").strip()
        if not script:
            return False, "missing parameters.script_path", 2
        timeout = int(params.get("timeout") or cfg.timeout_sec)
        return execute_shell(cfg, script, timeout)

    if action in {"restart_host", "shutdown_host", "deploy_lb_node", "remove_lb_node", "restart_service"}:
        message = f"dry-run action={action} params={json.dumps(params, ensure_ascii=True)}"
        if cfg.dry_run:
            return True, message, 0
        return True, f"not implemented: {message}", 0

    if action in {"health_check", "diagnostics", "maintenance_toggle", "maintenance_on", "maintenance_off"}:
        return True, f"ack action={action}", 0

    return False, f"unsupported action: {action}", 127


def execute_shell(cfg: AgentConfig, command: str, timeout: int) -> Tuple[bool, str, int]:
    if cfg.dry_run:
        return True, f"dry-run command: {command}", 0

    completed = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=max(1, timeout),
    )
    output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
    output = output.strip()
    return completed.returncode == 0, output, int(completed.returncode)


def post_log(cfg: AgentConfig, run_id: int, stream: str, message: str) -> None:
    panel_post(
        cfg,
        f"/api/agents/commands/{run_id}/logs",
        {"stream": stream, "message": message, "ts": int(time.time() * 1000)},
    )


def post_result(cfg: AgentConfig, run_id: int, status: str, output: str, exit_code: int) -> None:
    panel_post(
        cfg,
        f"/api/agents/commands/{run_id}/result",
        {
            "status": status,
            "output": output[:8000],
            "exit_code": int(exit_code),
        },
    )


def collect_metrics() -> Dict[str, float]:
    if psutil is None:
        return {
            "cpu": 0.0,
            "memory": 0.0,
            "disk": 0.0,
            "netIn": 0.0,
            "netOut": 0.0,
            "temp": 0.0,
            "errorRate": 0.0,
            "health": 100.0,
            "power": 0.0,
        }

    cpu = float(psutil.cpu_percent(interval=0.05))
    memory = float(psutil.virtual_memory().percent)
    disk = float(psutil.disk_usage("/").percent)
    net = psutil.net_io_counters()
    temp = _read_temp()
    health = max(0.0, 100.0 - max(cpu - 80.0, 0.0) - max(memory - 85.0, 0.0))
    power = max(0.0, min(500.0, cpu * 2.5))
    return {
        "cpu": round(cpu, 2),
        "memory": round(memory, 2),
        "disk": round(disk, 2),
        "netIn": float(net.bytes_recv),
        "netOut": float(net.bytes_sent),
        "temp": round(temp, 2),
        "errorRate": 0.0,
        "health": round(health, 2),
        "power": round(power, 2),
    }


def _read_temp() -> float:
    if psutil is None:
        return 0.0
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return 0.0
    if not temps:
        return 0.0
    for values in temps.values():
        if not values:
            continue
        entry = values[0]
        current = getattr(entry, "current", None)
        if isinstance(current, (int, float)):
            return float(current)
    return 0.0


def panel_get(cfg: AgentConfig, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    headers = _headers(cfg)
    response = requests.get(
        f"{cfg.panel_url}{path}",
        params=params,
        headers=headers,
        timeout=15,
        verify=cfg.verify_tls,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


def panel_post(cfg: AgentConfig, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    headers = _headers(cfg)
    response = requests.post(
        f"{cfg.panel_url}{path}",
        json=body,
        headers=headers,
        timeout=20,
        verify=cfg.verify_tls,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


def _headers(cfg: AgentConfig) -> Dict[str, str]:
    headers: Dict[str, str] = {"content-type": "application/json"}
    if cfg.token:
        headers["authorization"] = f"Bearer {cfg.token}"
    return headers


def _detect_ip() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on", "enabled"}


if __name__ == "__main__":
    raise SystemExit(main())
