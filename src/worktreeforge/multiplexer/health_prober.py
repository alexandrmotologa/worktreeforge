"""HTTP health prober and browser launcher for multiplexed ports."""

import http.client
import time
from typing import Any, Dict, Optional
import webbrowser


def probe_http_health(port: int, path: str = "/", timeout: float = 1.0) -> Dict[str, Any]:
    """Test if a local server is actively responding with HTTP headers."""
    start_time = time.perf_counter()
    normalized_path = path if path.startswith("/") else f"/{path}"

    try:
        conn = http.client.HTTPConnection("127.0.0.1", port=port, timeout=timeout)
        conn.request("GET", normalized_path)
        response = conn.getresponse()
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        status_code = response.status
        conn.close()

        # Any HTTP status (even 404, 302, 500) indicates an active HTTP server
        is_ok = 100 <= status_code < 600

        return {
            "port": port,
            "is_http_ok": is_ok,
            "status_code": status_code,
            "latency_ms": round(elapsed_ms, 1),
        }
    except Exception:
        return {
            "port": port,
            "is_http_ok": False,
            "status_code": None,
            "latency_ms": 0.0,
        }


def launch_in_browser(port: int, path: str = "/") -> bool:
    """Open localhost URL in user's default web browser."""
    normalized_path = path if path.startswith("/") else f"/{path}"
    url = f"http://localhost:{port}{normalized_path}"
    try:
        return webbrowser.open(url)
    except Exception:
        return False
