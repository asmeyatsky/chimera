from dataclasses import dataclass
import re

@dataclass(frozen=True)
class NixHash:
    """
    Value Object representing a cryptographic hash used in Nix.
    Ensures that the hash format is valid.
    """
    value: str

    def __post_init__(self):
        if not self._is_valid(self.value):
            raise ValueError(f"Invalid Nix hash format: {self.value}")

    @staticmethod
    def _is_valid(value: str) -> bool:
        # Basic validation for Nix store path hash (usually 32 chars base32)
        # Assuming standard store path hash part length
        return bool(re.match(r'^[0-9a-z]{32}$', value))

    def __str__(self):
        return self.value
