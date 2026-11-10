"""Principals (API consumers) and API-key authentication.

Principal definitions live in config/principals.json (committed, no secrets). Each principal names the
environment variable that holds its API key; keys live only in .env / the environment (CLAUDE.md rule).
No real identity provider: this is a declared limitation of the prototype.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from p14_search.models import AccessLevel

ALL_OFFICES = "*"


@dataclass(frozen=True)
class Principal:
    name: str
    role: str  # consumer | employee | officer | admin
    level: AccessLevel  # highest access level this principal may ever see
    offices: tuple[str, ...] = field(default_factory=tuple)  # offices whose restricted docs are visible

    @property
    def all_offices(self) -> bool:
        return ALL_OFFICES in self.offices

    @property
    def pseudonym(self) -> str:
        """Stored in logs instead of the principal name (data minimisation)."""
        return hashlib.sha256(f"p14|{self.name}".encode()).hexdigest()[:16]

    def can_manage(self, office: str) -> bool:
        """Ingest/approve documents of `office`: admins, and officers for their own offices."""
        if self.role == "admin":
            return True
        return self.role == "officer" and (self.all_offices or office in self.offices)


class PrincipalRegistry:
    def __init__(self, keyed: dict[str, Principal]):
        # Store SHA-256 of keys only; compare in constant time.
        self._by_hash = {hashlib.sha256(k.encode()).hexdigest(): p for k, p in keyed.items() if k}

    def authenticate(self, api_key: str | None) -> Principal | None:
        if not api_key:
            return None
        digest = hashlib.sha256(api_key.encode()).hexdigest()
        for known, principal in self._by_hash.items():
            if hmac.compare_digest(known, digest):
                return principal
        return None

    @property
    def principals(self) -> list[Principal]:
        return list(self._by_hash.values())

    @classmethod
    def from_config(cls, path: Path, env_file: Path | str = ".env") -> PrincipalRegistry:
        env = {**dotenv_values(env_file), **os.environ}
        keyed = {}
        for item in json.loads(Path(path).read_text(encoding="utf-8"))["principals"]:
            key = env.get(item["api_key_env"])
            if key:
                keyed[key] = Principal(item["name"], item["role"], AccessLevel(item["level"]), tuple(item["offices"]))
        return cls(keyed)
