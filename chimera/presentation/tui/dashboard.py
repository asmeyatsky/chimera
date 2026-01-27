from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Log
from textual.containers import Container, Horizontal, Vertical
from typing import List
import asyncio
from datetime import datetime

from chimera.domain.value_objects.node import Node
from chimera.domain.value_objects.nix_hash import NixHash
from chimera.infrastructure.adapters.fabric_adapter import FabricAdapter

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
    ]

    def __init__(self, targets: List[str]):
        super().__init__()
        self.targets = [Node.parse(t) for t in targets]
        self.adapter = FabricAdapter()
        # Mock expected hash for demo if not provided, or resolve it.
        # For visualization, we'll just show current hash.
        
    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            DataTable(id="fleet_table"),
            Log(id="activity_log")
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Node", "Status", "Current Hash", "Last Check")
        
        # Initial population
        for node in self.targets:
            table.add_row(str(node), "Pending", "...", "Never")

        self.log_message("Chimera Dashboard Initialized.")
        self.set_interval(5, self.update_fleet_status)

    def log_message(self, message: str) -> None:
        log = self.query_one(Log)
        timestamp = datetime.now().strftime("%H:%M:%S")
        log.write_line(f"[{timestamp}] {message}")

    async def update_fleet_status(self) -> None:
        table = self.query_one(DataTable)
        self.log_message("Scanning fleet...")
        
        # In a real TUI, this should be async/threaded to not block UI.
        # Fabric is blocking. We should wrap in thread.
        # For V1, we accept minor blocking or use run_in_executor.
        
        rows = []
        for i, node in enumerate(self.targets):
            # We need to run get_current_hash in thread
            loop = asyncio.get_running_loop()
            
            # Using verify_phase3 logic: check /tmp/chimera_current_hash
            # But let's check current hash properly via adapter
            h = await loop.run_in_executor(None, self.adapter.get_current_hash, node)
            
            status = "Online" if h else "Unreachable"
            hash_val = str(h) if h else "N/A"
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Update row in place (Textual allows updating cell by key if we used keys, 
            # or we can clear and re-add, but that flickers.
            # Better: update_cell using coordinate)
            
            # Simple approach: Clear and re-add for prototype
            # table.clear() 
            # Re-adding all rows logic...
            
            # Better: update cell by coordinate
            table.update_cell_at((i, 1), status)
            table.update_cell_at((i, 2), hash_val)
            table.update_cell_at((i, 3), timestamp)
            
            if status == "Unreachable":
                 self.log_message(f"[!] Node {node} is UNREACHABLE")
        
        self.log_message("Scan complete.")

if __name__ == "__main__":
    app = Dashboard(["localhost"])
    app.run()
