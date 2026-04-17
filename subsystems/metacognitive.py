#!/usr/bin/env python3
"""
Metacognitive — 元认知子系统。
维护 ~/.hermes/metacognitive.json（新建）

功能：
  - 监控自身认知状态
  - 检测思维盲点
  - 自我反思日志

触发方式：
  1. Cron定期自我反思
  2. Feishu命令: /metacognitive status | /reflect
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .base import HERMES_HOME, Subsystem

logger = logging.getLogger(__name__)


class Metacognitive(Subsystem):
    DATA_FILE = "metacognitive.json"

    def __init__(self):
        super().__init__("Metacognitive")
        self.path = self.data_file(self.DATA_FILE)
        self._ensure_file()

    def _ensure_file(self):
        if not self.path.exists():
            self.save(self.DATA_FILE, {
                "version": 1,
                "reflections": [],
                "cognitive_biases": [],
                "blind_spots": [],
                "insights": [],
                "stats": {"total_reflections": 0},
            })

    def load_data(self) -> Dict:
        return self.load(self.DATA_FILE)

    def save_data(self, data: Dict):
        self.save(self.DATA_FILE, data)

    def reflect(self, topic: str, observation: str, conclusion: str = "") -> Dict:
        """记录一次反思。"""
        data = self.load_data()
        entry = {
            "id": len(data.get("reflections", [])) + 1,
            "topic": topic,
            "observation": observation,
            "conclusion": conclusion,
            "timestamp": self.timestamp(),
        }
        data.setdefault("reflections", []).append(entry)
        data["stats"]["total_reflections"] = len(data["reflections"])
        self.save_data(data)
        return entry

    def add_insight(self, text: str, category: str = "general") -> Dict:
        """记录一个洞见。"""
        data = self.load_data()
        entry = {
            "id": len(data.get("insights", [])) + 1,
            "text": text,
            "category": category,
            "timestamp": self.timestamp(),
        }
        data.setdefault("insights", []).append(entry)
        self.save_data(data)
        return entry

    # ── Run ─────────────────────────────────────────────────────────────

    def run(self, **kwargs) -> Dict[str, Any]:
        data = self.load_data()
        reflections = data.get("reflections", [])
        insights = data.get("insights", [])
        return {
            "ok": True,
            "message": f"反思{len(reflections)}条，洞见{len(insights)}条",
            "details": {
                "total_reflections": len(reflections),
                "total_insights": len(insights),
                "recent_reflections": reflections[-5:] if reflections else [],
                "recent_insights": insights[-5:] if insights else [],
            },
        }

    # ── Status ──────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        data = self.load_data()
        return {
            "ok": True,
            "name": self.name,
            "total_reflections": data["stats"].get("total_reflections", 0),
            "total_insights": len(data.get("insights", [])),
            "latest_insight": data.get("insights", [])[-1] if data.get("insights") else None,
        }
