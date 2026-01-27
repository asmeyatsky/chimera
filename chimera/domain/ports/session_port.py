from abc import ABC, abstractmethod
from typing import List, Optional
from chimera.domain.value_objects.session_id import SessionId

class SessionPort(ABC):
    """
    Port interface for managing persistent sessions (e.g., Tmux).
    """

    @abstractmethod
    def create_session(self, session_id: SessionId) -> bool:
        """
        Creates a new session. Returns True if created, False if already exists.
        """
        pass

    @abstractmethod
    def list_sessions(self) -> List[SessionId]:
        """
        Lists all active sessions.
        """
        pass

    @abstractmethod
    def kill_session(self, session_id: SessionId) -> bool:
        """
        Kills an active session.
        """
        pass

    @abstractmethod
    def run_command(self, session_id: SessionId, command: str) -> bool:
        """
        Runs a command within a specific session.
        """
        pass

    @abstractmethod
    def attach_command(self, session_id: SessionId) -> str:
        """
        Returns the shell command to attach to a session.
        """
        pass
