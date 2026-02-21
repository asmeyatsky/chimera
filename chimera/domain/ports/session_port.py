"""
Session Port

Architectural Intent:
- Port interface for managing persistent sessions (e.g., Tmux)
- Abstracts session lifecycle and command execution within sessions
- Implemented by TmuxAdapter or other session managers
"""

from abc import ABC, abstractmethod
from typing import List
from chimera.domain.value_objects.session_id import SessionId


class SessionPort(ABC):
    """
    Port interface for managing persistent sessions (e.g., Tmux).
    """

    @abstractmethod
    async def create_session(self, session_id: SessionId) -> bool:
        """
        Creates a new session. Returns True if created, False if already exists.
        """
        pass

    @abstractmethod
    async def list_sessions(self) -> List[SessionId]:
        """
        Lists all active sessions.
        """
        pass

    @abstractmethod
    async def kill_session(self, session_id: SessionId) -> bool:
        """
        Kills an active session.
        """
        pass

    @abstractmethod
    async def run_command(self, session_id: SessionId, command: str) -> bool:
        """
        Runs a command within a specific session.
        """
        pass

    @abstractmethod
    async def attach_command(self, session_id: SessionId) -> str:
        """
        Returns the shell command to attach to a session.
        """
        pass
