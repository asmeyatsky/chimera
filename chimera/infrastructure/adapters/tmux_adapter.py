"""
Tmux Adapter

Architectural Intent:
- Infrastructure adapter implementing SessionPort via Tmux
- Provides session lifecycle management using libtmux
"""

import asyncio
import libtmux
from typing import List
from chimera.domain.ports.session_port import SessionPort
from chimera.domain.value_objects.session_id import SessionId


class TmuxAdapter(SessionPort):
    def __init__(self):
        self.server = libtmux.Server()

    async def create_session(self, session_id: SessionId) -> bool:
        def _create():
            try:
                if self.server.has_session(str(session_id)):
                    return False
                self.server.new_session(
                    session_name=str(session_id), kill_session=False, attach=False
                )
                return True
            except Exception:
                return False

        return await asyncio.get_event_loop().run_in_executor(None, _create)

    async def list_sessions(self) -> List[SessionId]:
        def _list():
            try:
                sessions = self.server.sessions
                return [SessionId(s.session_name) for s in sessions if s.session_name]
            except Exception:
                return []

        return await asyncio.get_event_loop().run_in_executor(None, _list)

    async def kill_session(self, session_id: SessionId) -> bool:
        def _kill():
            try:
                session = self.server.sessions.get(session_name=str(session_id))
                if session:
                    session.kill_session()
                    return True
                return False
            except Exception:
                return False

        return await asyncio.get_event_loop().run_in_executor(None, _kill)

    async def run_command(self, session_id: SessionId, command: str) -> bool:
        def _run():
            try:
                session = self.server.sessions.get(session_name=str(session_id))
                if not session:
                    return False
                window = session.active_window
                pane = window.active_pane
                pane.send_keys(command)
                return True
            except Exception:
                return False

        return await asyncio.get_event_loop().run_in_executor(None, _run)

    async def attach_command(self, session_id: SessionId) -> str:
        return f"tmux attach-session -t {session_id}"
