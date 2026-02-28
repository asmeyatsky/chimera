"""
Dashboard TUI

Architectural Intent:
- Textual-based fleet dashboard for monitoring node status
- Supports severity-colored log messages
- Configurable refresh interval (+/- keys) and log pagination (n/p keys)
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Log
from textual.containers import Vertical
from typing import List
import asyncio
import logging
from datetime import datetime

from chimera.domain.value_objects.node import Node
from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter

logger = logging.getLogger(__name__)

SEVERITY_STYLES = {
    "info": "green",
    "warning": "yellow",
    "error": "red",
    "critical": "bold red",
}


class Dashboard(App):
    """A Textual app to manage the Chimera Fleet."""

    CSS = """
    Screen {
        layout: vertical;
    }
    DataTable {
        height: 1fr;
        border: solid green;
    }
    Log {
        height: 1fr;
        border: solid yellow;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh Status"),
        ("+", "increase_interval", "Slower"),
        ("-", "decrease_interval", "Faster"),
        ("n", "next_page", "Next Page"),
        ("p", "prev_page", "Prev Page"),
    ]

    def __init__(self, targets: List[str]):
        super().__init__()
        self.targets = [Node.parse(t) for t in targets]
        self.adapter = FabricAdapter()
        self._refresh_interval: float = 5.0
        self._page: int = 0
        self._page_size: int = 20
        self._log_max_lines: int = 500
        self._log_lines: list[str] = []
        self._timer = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(DataTable(id="fleet_table"), Log(id="activity_log"))
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Node", "Status", "Current Hash", "Last Check")

        for i, node in enumerate(self.targets):
            table.add_row(str(node), "Pending", "...", "Never", key=str(i))

        self.log_message("Chimera Dashboard Initialized.", severity="info")
        self.log_message(
            f"Refresh interval: {self._refresh_interval}s (use +/- to adjust)",
            severity="info",
        )
        self._timer = self.set_interval(self._refresh_interval, self._update_fleet_status)

    def log_message(self, message: str, severity: str = "info") -> None:
        log_widget = self.query_one(Log)
        timestamp = datetime.now().strftime("%H:%M:%S")
        style = SEVERITY_STYLES.get(severity, "")
        prefix = severity.upper()

        line = f"[{timestamp}] [{prefix}] {message}"
        self._log_lines.append(line)

        # Cap log growth
        if len(self._log_lines) > self._log_max_lines:
            self._log_lines = self._log_lines[-self._log_max_lines:]

        if style:
            log_widget.write_line(f"[{style}]{line}[/{style}]")
        else:
            log_widget.write_line(line)

    def action_increase_interval(self) -> None:
        self._refresh_interval = min(60.0, self._refresh_interval + 1.0)
        self._restart_timer()
        self.log_message(
            f"Refresh interval: {self._refresh_interval}s", severity="info"
        )

    def action_decrease_interval(self) -> None:
        self._refresh_interval = max(1.0, self._refresh_interval - 1.0)
        self._restart_timer()
        self.log_message(
            f"Refresh interval: {self._refresh_interval}s", severity="info"
        )

    def action_next_page(self) -> None:
        max_page = max(0, len(self.targets) - 1) // self._page_size
        if self._page < max_page:
            self._page += 1
            self.log_message(f"Page {self._page + 1}", severity="info")

    def action_prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self.log_message(f"Page {self._page + 1}", severity="info")

    def _restart_timer(self) -> None:
        if self._timer:
            self._timer.stop()
        self._timer = self.set_interval(self._refresh_interval, self._update_fleet_status)

    async def _update_fleet_status(self) -> None:
        try:
            await self.update_fleet_status()
        except Exception as e:
            self.log_message(f"Error during scan: {e}", severity="error")

    async def update_fleet_status(self) -> None:
        table = self.query_one(DataTable)
        self.log_message("Scanning fleet...", severity="info")

        start = self._page * self._page_size
        end = min(start + self._page_size, len(self.targets))

        for i in range(start, end):
            node = self.targets[i]
            try:
                loop = asyncio.get_running_loop()
                h = await loop.run_in_executor(
                    None, self.adapter.get_current_hash, node
                )

                status = "Online" if h else "Unreachable"
                hash_val = str(h) if h else "N/A"
                timestamp = datetime.now().strftime("%H:%M:%S")

                table.update_cell_at((i, 1), status)
                table.update_cell_at((i, 2), hash_val)
                table.update_cell_at((i, 3), timestamp)

                if status == "Unreachable":
                    self.log_message(
                        f"Node {node} is UNREACHABLE", severity="warning"
                    )

            except Exception as e:
                self.log_message(f"Error checking {node}: {e}", severity="error")

        self.log_message("Scan complete.", severity="info")


if __name__ == "__main__":
    app = Dashboard(["localhost"])
    app.run()
