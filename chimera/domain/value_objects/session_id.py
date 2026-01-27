from dataclasses import dataclass

@dataclass(frozen=True)
class SessionId:
    """
    Value Object representing a unique session identifier for Tmux.
    """
    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("Session ID cannot be empty")

    def __str__(self):
        return self.value
