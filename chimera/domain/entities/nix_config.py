from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class NixConfig:
    """
    Represents the Nix configuration source (e.g., path to flake.nix or default.nix).
    """
    path: Path

    def __post_init__(self):
        if not self.path.exists():
            raise FileNotFoundError(f"Nix config not found at path: {self.path}")

    @property
    def is_flake(self) -> bool:
        return self.path.name == 'flake.nix'
