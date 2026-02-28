"""
Chimera Web Dashboard

Architectural Intent:
- Lightweight web server built entirely on Python stdlib (http.server + asyncio).
- No external dependencies (no Flask, FastAPI, aiohttp, etc.).
- Serves a REST API for programmatic fleet inspection and rollback triggers.
- Serves a minimal HTML dashboard at the root for browser-based monitoring.
- Designed as a foundation layer: the API surface is intentionally small and
  can be extended with additional endpoints as the project evolves.

API Surface:
    GET  /              -> HTML dashboard with fleet overview
    GET  /api/fleet     -> JSON fleet status summary
    GET  /api/nodes/{id} -> JSON health detail for a specific node
    POST /api/rollback  -> Trigger rollback (JSON body: {"targets": [...], "generation": "..."})

Threading Model:
    The stdlib HTTPServer is synchronous.  We run it in a background thread so
    the main asyncio event loop remains free for agent coordination.  Handlers
    that need to call async code (e.g. RollbackDeployment.execute) schedule
    coroutines on the event loop from the handler thread.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
from datetime import datetime, UTC
from functools import partial
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Optional

from chimera.infrastructure.agent.agent_registry import AgentRegistry, AgentRecord
from chimera.infrastructure.agent.chimera_agent import NodeHealth, AgentStatus
from chimera.application.use_cases.rollback_deployment import RollbackDeployment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML template for the dashboard
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Chimera Fleet Dashboard</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; background: #0f1117; color: #e0e0e0; }
    header { background: #1a1d28; padding: 1rem 2rem; border-bottom: 1px solid #2a2d3a; }
    header h1 { font-size: 1.4rem; color: #7eb8f7; }
    .container { max-width: 1000px; margin: 2rem auto; padding: 0 1rem; }
    .summary { display: flex; gap: 1rem; margin-bottom: 2rem; }
    .card { flex: 1; background: #1a1d28; border-radius: 8px; padding: 1.2rem;
            border: 1px solid #2a2d3a; }
    .card h2 { font-size: 0.85rem; text-transform: uppercase; color: #888; margin-bottom: 0.5rem; }
    .card .value { font-size: 2rem; font-weight: 700; }
    .healthy { color: #4caf50; }
    .drifted { color: #ff9800; }
    .stale   { color: #f44336; }
    table { width: 100%; border-collapse: collapse; background: #1a1d28;
            border-radius: 8px; overflow: hidden; }
    th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #2a2d3a; }
    th { background: #22252f; color: #999; font-size: 0.8rem; text-transform: uppercase; }
    .status-badge { padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.8rem; }
    .status-HEALTHY { background: #1b3a1b; color: #4caf50; }
    .status-DRIFT_DETECTED { background: #3a2e1b; color: #ff9800; }
    .status-DEGRADED { background: #3a1b1b; color: #f44336; }
    .status-UNREACHABLE { background: #3a1b1b; color: #f44336; }
    .status-UNKNOWN { background: #2a2d3a; color: #888; }
    .status-HEALING { background: #1b2a3a; color: #2196f3; }
    #error { color: #f44336; padding: 1rem; display: none; }
  </style>
</head>
<body>
  <header><h1>Chimera Fleet Dashboard</h1></header>
  <div class="container">
    <div id="error"></div>
    <div class="summary">
      <div class="card"><h2>Total Nodes</h2><div class="value" id="total">-</div></div>
      <div class="card"><h2>Healthy</h2><div class="value healthy" id="healthy">-</div></div>
      <div class="card"><h2>Drifted</h2><div class="value drifted" id="drifted">-</div></div>
      <div class="card"><h2>Stale</h2><div class="value stale" id="stale">-</div></div>
    </div>
    <table>
      <thead><tr><th>Node ID</th><th>Status</th><th>Last Seen</th></tr></thead>
      <tbody id="nodes"></tbody>
    </table>
  </div>
  <script>
    async function refresh() {
      try {
        const r = await fetch('/api/fleet');
        const data = await r.json();
        document.getElementById('total').textContent = data.total;
        document.getElementById('healthy').textContent = data.healthy;
        document.getElementById('drifted').textContent = data.drifted;
        document.getElementById('stale').textContent = data.stale;
        const tbody = document.getElementById('nodes');
        tbody.innerHTML = data.nodes.map(n =>
          `<tr>
            <td>${n.node_id}</td>
            <td><span class="status-badge status-${n.status}">${n.status}</span></td>
            <td>${n.last_seen}</td>
          </tr>`
        ).join('');
        document.getElementById('error').style.display = 'none';
      } catch (e) {
        const el = document.getElementById('error');
        el.textContent = 'Failed to fetch fleet data: ' + e.message;
        el.style.display = 'block';
      }
    }
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NODE_PATH_RE = re.compile(r"^/api/nodes/([^/]+)$")


def _agent_record_to_dict(record: AgentRecord) -> dict[str, Any]:
    """Serialize an AgentRecord to a JSON-safe dict."""
    health = record.health
    return {
        "node_id": record.node_id,
        "status": health.status.name if health else "UNKNOWN",
        "last_seen": record.last_seen.isoformat(),
        "is_stale": record.is_stale,
        "cpu_percent": health.cpu_percent if health else None,
        "memory_percent": health.memory_percent if health else None,
        "disk_percent": health.disk_percent if health else None,
        "current_hash": health.current_hash if health else None,
        "expected_hash": health.expected_hash if health else None,
    }


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class ChimeraRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Chimera web dashboard.

    Attributes on the *server* instance (set by ChimeraWebApp):
        registry:  AgentRegistry  -- fleet state
        rollback:  RollbackDeployment -- rollback use case
        loop:      asyncio event loop (for scheduling async calls)
    """

    # Silence per-request log lines from BaseHTTPRequestHandler
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        logger.debug("web: %s", format % args)

    # ---- routing -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        """Route GET requests."""
        if self.path == "/":
            self._serve_dashboard()
        elif self.path == "/api/fleet":
            self._serve_fleet_status()
        else:
            match = _NODE_PATH_RE.match(self.path)
            if match:
                self._serve_node_health(match.group(1))
            else:
                self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        """Route POST requests."""
        if self.path == "/api/rollback":
            self._handle_rollback()
        else:
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    # ---- endpoint implementations ------------------------------------------

    def _serve_dashboard(self) -> None:
        """Return the HTML dashboard page."""
        body = _DASHBOARD_HTML.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_fleet_status(self) -> None:
        """Return JSON summary of the entire fleet."""
        registry: AgentRegistry = self.server.registry  # type: ignore[attr-defined]
        agents = registry.get_all()
        payload = {
            "total": registry.total_count,
            "healthy": registry.healthy_count,
            "drifted": registry.drifted_count,
            "stale": len(registry.get_stale()),
            "nodes": [_agent_record_to_dict(a) for a in agents],
        }
        self._send_json(payload)

    def _serve_node_health(self, node_id: str) -> None:
        """Return JSON health detail for a single node."""
        registry: AgentRegistry = self.server.registry  # type: ignore[attr-defined]
        record = registry.get(node_id)
        if record is None:
            self._send_json({"error": f"node '{node_id}' not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json(_agent_record_to_dict(record))

    def _handle_rollback(self) -> None:
        """Trigger a rollback via the RollbackDeployment use case.

        Expected JSON body:
            {"targets": ["10.0.0.1", ...], "generation": "optional-gen-id"}
        """
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(content_length)
            body = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, ValueError):
            self._send_json({"error": "invalid JSON body"}, HTTPStatus.BAD_REQUEST)
            return

        targets = body.get("targets", [])
        if not targets or not isinstance(targets, list):
            self._send_json(
                {"error": "targets must be a non-empty list"},
                HTTPStatus.BAD_REQUEST,
            )
            return

        generation = body.get("generation")
        rollback_uc: RollbackDeployment = self.server.rollback  # type: ignore[attr-defined]

        # Run the async use case in a fresh event loop on this handler thread.
        # This avoids deadlocks when the main event loop is busy.
        try:
            success = asyncio.run(
                rollback_uc.execute(targets=targets, generation=generation),
            )
        except Exception as exc:
            logger.error("Rollback failed: %s", exc)
            self._send_json(
                {"error": str(exc)},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        status = HTTPStatus.OK if success else HTTPStatus.INTERNAL_SERVER_ERROR
        self._send_json({"success": success, "targets": targets}, status)

    # ---- helpers -----------------------------------------------------------

    def _send_json(self, data: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        """Serialize *data* as JSON and send it as the HTTP response."""
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Web application wrapper
# ---------------------------------------------------------------------------

class ChimeraWebApp:
    """Async-friendly web server for the Chimera fleet dashboard.

    Architectural Intent:
    - Wraps Python's stdlib HTTPServer with project-specific routing and state.
    - Accepts an AgentRegistry (read-only fleet view) and a RollbackDeployment
      use case (write path) so the web layer stays a thin presentation adapter
      with no domain logic of its own.
    - Runs the blocking HTTPServer in a daemon thread so it can coexist with
      the asyncio event loop used by the rest of Chimera.

    Usage::

        app = ChimeraWebApp(registry=my_registry, rollback=my_rollback_uc)
        await app.start("0.0.0.0", 8080)
        # ... later ...
        app.stop()
    """

    def __init__(
        self,
        registry: AgentRegistry,
        rollback: RollbackDeployment,
    ) -> None:
        self.registry = registry
        self.rollback = rollback
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    async def start(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        """Start the web server in a background thread.

        The server is non-blocking from the caller's perspective.  The current
        asyncio event loop is captured so that POST /api/rollback can schedule
        async work back onto it.
        """
        self._server = HTTPServer(
            (host, port),
            ChimeraRequestHandler,
        )
        # Attach application state to the server so handlers can access it.
        self._server.registry = self.registry  # type: ignore[attr-defined]
        self._server.rollback = self.rollback  # type: ignore[attr-defined]

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="chimera-web",
        )
        self._thread.start()
        logger.info("Chimera web dashboard started on http://%s:%d", host, port)

    def stop(self) -> None:
        """Shut down the web server gracefully."""
        if self._server is not None:
            self._server.shutdown()
            logger.info("Chimera web dashboard stopped")
        if self._thread is not None:
            self._thread.join(timeout=5)
