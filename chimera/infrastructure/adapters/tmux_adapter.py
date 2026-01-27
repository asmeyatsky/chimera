import libtmux
from typing import List, Optional
from chimera.domain.ports.session_port import SessionPort
from chimera.domain.value_objects.session_id import SessionId

class TmuxAdapter(SessionPort):
    def __init__(self):
        self.server = libtmux.Server()

    def create_session(self, session_id: SessionId) -> bool:
        try:
            if self.server.has_session(str(session_id)):
                return False
            self.server.new_session(session_name=str(session_id), kill_session=False, attach=False)
            return True
        except Exception:
            # Fallback or specific error handling
            return False

    def list_sessions(self) -> List[SessionId]:
        sessions = self.server.sessions
        return [SessionId(s.session_name) for s in sessions]

    def kill_session(self, session_id: SessionId) -> bool:
        try:
            session = self.server.sessions.get(session_name=str(session_id))
            if session:
                session.kill_session()
                return True
            return False
        except Exception:
            return False

    def run_command(self, session_id: SessionId, command: str) -> bool:
        session = self.server.sessions.get(session_name=str(session_id))
        if not session:
            return False
        
        # Get the active window/pane
        try:
            window = session.active_window
            pane = window.active_pane
            pane.send_keys(command)
            return True
        except Exception:
            return False
            
    def attach_command(self, session_id: SessionId) -> str:
        return f"tmux attach-session -t {session_id}"
