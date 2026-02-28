"""
Web presentation layer for Chimera fleet management.

Architectural Intent:
- Provides a browser-based dashboard for fleet visibility
- Exposes REST API endpoints for fleet status, node health, and rollback
- Uses Python stdlib only (http.server + asyncio) -- no external dependencies
- Complements the CLI and TUI interfaces with a web-accessible option
"""
