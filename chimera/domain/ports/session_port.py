"""
Session Port

Architectural Intent:
- Port interface for managing persistent sessions (e.g., Tmux)
- Abstracts session lifecycle and command execution within sessions
- Implemented by TmuxAdapter or other session managers
"""

from typing import Protocol, runtime_checkable
from chimera.domain.value_objects.session_id import SessionId


@runtime_checkable
class SessionPort(Protocol):
    """Port interface for managing persistent sessions (e.g., Tmux)."""

    async def create_session(self, session_id: SessionId) -> bool: ...

    async def list_sessions(self) -> list[SessionId]: ...

    async def kill_session(self, session_id: SessionId) -> bool: ...

    async def run_command(self, session_id: SessionId, command: str) -> bool: ...

    async def attach_command(self, session_id: SessionId) -> str: ...
