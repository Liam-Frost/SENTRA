from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

REQUIRED_KEYS = {"root_causes", "recommended_actions", "risks", "rollback_conditions"}


def explain_incidents(
    world_state: Dict[str, Any],
    incidents: List[Dict[str, Any]],
    decisions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    payload = _call_ai(world_state, incidents, decisions or [])
    if payload is None:
        return _default_payload(incidents)
    return payload


def _call_ai(
    world_state: Dict[str, Any],
    incidents: List[Dict[str, Any]],
    decisions: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    api_url = os.getenv("SENTRA_AI_API_URL")
    api_key = os.getenv("SENTRA_AI_API_KEY")
    model = os.getenv("SENTRA_AI_MODEL")
    if not api_url or not api_key or not model or requests is None:
        return None

    messages = [
        {
            "role": "system",
            "content": (
                "You are SENTRA AI. Output strict JSON with keys: "
                "root_causes, recommended_actions, risks, rollback_conditions. "
                "No extra keys. Arrays of short strings only."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "world_state": world_state,
                    "incidents": incidents,
                    "decisions": decisions,
                },
                ensure_ascii=True,
            ),
        },
    ]

    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }

    try:
        response = requests.post(
            api_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=20,
        )
    except Exception:
        return None

    if response.status_code >= 400:
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    content = _extract_content(data)
    if content is None:
        return None

    payload = _parse_json(content)
    if payload is None:
        return None
    if not _validate_payload(payload):
        return None
    return payload


def _extract_content(data: Dict[str, Any]) -> Optional[str]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    return content


def _parse_json(content: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(content[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _validate_payload(payload: Dict[str, Any]) -> bool:
    if set(payload.keys()) != REQUIRED_KEYS:
        return False
    for key in REQUIRED_KEYS:
        value = payload.get(key)
        if not isinstance(value, list):
            return False
        if any(not isinstance(item, str) for item in value):
            return False
    return True


def _default_payload(incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
    if incidents:
        root_causes = [incident.get("message", "incident detected") for incident in incidents]
    else:
        root_causes = ["no incidents detected"]

    recommended_actions = [
        "enableCooling on affected servers",
        "reroute load away from affected servers",
        "throttle incoming_traffic if incidents persist",
        "restart only if temp < 85 and error_rate > 5",
    ]
    risks = [
        "Cooling increases power consumption",
        "Reroute may increase load on other servers",
        "Throttle reduces throughput",
    ]
    rollback_conditions = [
        "If temp stays > 85 for 5 ticks, block restart",
        "If health continues to drop after 2 escalations, disable autonomy",
    ]

    return {
        "root_causes": root_causes,
        "recommended_actions": recommended_actions,
        "risks": risks,
        "rollback_conditions": rollback_conditions,
    }
