#!/usr/bin/env python3
"""
Base class for all Hermes subsystems.
Each subsystem:
  - Lives in ~/.hermes/subsystems/
  - Reads/writes only JSON data files in ~/.hermes/
  - Has .run() method for cron/CLI invocation
  - Has .status() method for health check
  - Is completely independent — no import from gateway code
"""
import json
import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

HERMES_HOME = Path.home() / ".hermes"


class Subsystem(ABC):
    """Base class for all subsystems."""

    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.home = HERMES_HOME
        self._lock = threading.Lock()
        self._data: Optional[Dict] = None

    # ── Data persistence ─────────────────────────────────────────────────

    def data_file(self, filename: str) -> Path:
        return self.home / filename

    def load(self, filename: str) -> Dict:
        path = self.data_file(filename)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("%s: failed to load %s — %s", self.name, filename, e)
                return {}
        return {}

    def save(self, filename: str, data: Dict):
        path = self.data_file(filename)
        with self._lock:
            try:
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except OSError as e:
                logger.error("%s: failed to save %s — %s", self.name, filename, e)

    # ── Lifecycle ────────────────────────────────────────────────────────

    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """Main entry point. Returns dict with 'ok', 'message', 'details'."""
        raise NotImplementedError

    def status(self) -> Dict[str, Any]:
        """Health check. Override in subclass."""
        return {"ok": True, "name": self.name, "note": "no status check implemented"}

    def timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()[:19]
