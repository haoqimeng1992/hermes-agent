#!/usr/bin/env python3
"""
Self Model — 总仪表盘子系统。
维护 ~/.hermes/self_model.json，汇总所有子系统的健康状态。

触发方式：
  1. Cron定时任务（每小时/每天）
  2. Feishu命令: /selfmodel status
  3. 其他子系统run()完成后调用 update_from_subsystem()
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .base import HERMES_HOME, Subsystem

logger = logging.getLogger(__name__)


class SelfModel(Subsystem):
    """总仪表盘 — 追踪所有子系统的metrics和状态。"""

    DATA_FILE = "self_model.json"

    def __init__(self):
        super().__init__("SelfModel")
        self.path = self.data_file(self.DATA_FILE)

    # ── Load / Save ─────────────────────────────────────────────────────

    def load_data(self) -> Dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return self._default_data()

    def save_data(self, data: Dict):
        data["last_updated"] = self.timestamp()
        self.save(self.DATA_FILE, data)

    def _default_data(self) -> Dict:
        return {
            "version": 1,
            "created_at": datetime.now(timezone.utc).timestamp(),
            "last_reflection": None,
            "identity": {},
            "capabilities": {},
            "preferences": {},
            "behavioral_patterns": {},
            "evolution_log": [],
            "metrics": {
                "total_interactions": 0,
                "successful_interactions": 0,
                "last_interaction": None,
                "subsystem_runs": {},
                "identity_adaptations": 0,
            },
            "reflection_count": 0,
            "strategies": [],
            "behavioral_metrics": {},
            "recent_reflections": [],
            "active_goals": [],
            "subsystem_health": {},
        }

    # ── Metrics helpers ─────────────────────────────────────────────────

    def increment_interaction(self, success: bool = True):
        data = self.load_data()
        m = data.get("metrics", {})
        m["total_interactions"] = m.get("total_interactions", 0) + 1
        if success:
            m["successful_interactions"] = m.get("successful_interactions", 0) + 1
        m["last_interaction"] = self.timestamp()
        data["metrics"] = m
        self.save_data(data)

    def update_subsystem_run(self, subsystem_name: str, ok: bool, details: str = ""):
        data = self.load_data()
        m = data.get("metrics", {})
        runs = m.get("subsystem_runs", {})
        runs[subsystem_name] = {
            "last_run": self.timestamp(),
            "ok": ok,
            "details": details,
        }
        m["subsystem_runs"] = runs
        data["metrics"] = m
        data["subsystem_health"] = {
            k: v.get("ok", False) for k, v in runs.items()
        }
        self.save_data(data)

    # ── Subsystem integration ────────────────────────────────────────────

    def update_from_subsystem(self, subsystem_name: str, metrics: Dict):
        """其他子系统run()完成后调用，汇总metrics。"""
        data = self.load_data()
        m = data.get("metrics", {})
        sm = {**m.get("subsystem_metrics", {}), subsystem_name: metrics}
        m["subsystem_metrics"] = sm
        data["metrics"] = m
        self.save_data(data)

    # ── Run ─────────────────────────────────────────────────────────────

    def run(self, **kwargs) -> Dict[str, Any]:
        """全面自检：汇总所有数据文件的状态。"""
        data = self.load_data()
        health = {}

        # 检查各数据文件
        files_to_check = [
            "identity_evolution.json",
            "governance_audit.json",
            "learnings.json",
            "fitness_functions.json",
            "goals.json",
            "orchestration_history.json",
        ]
        for fn in files_to_check:
            path = HERMES_HOME / fn
            if path.exists():
                try:
                    d = json.loads(path.read_text(encoding="utf-8"))
                    health[fn] = {"ok": True, "keys": list(d.keys())[:5]}
                except Exception as e:
                    health[fn] = {"ok": False, "error": str(e)}
            else:
                health[fn] = {"ok": False, "error": "file not found"}

        # 更新subsystem_health
        data["subsystem_health"] = health
        self.save_data(data)

        metrics = data.get("metrics", {})
        total = metrics.get("total_interactions", 0)
        success = metrics.get("successful_interactions", 0)
        rate = (success / total * 100) if total > 0 else 0

        return {
            "ok": True,
            "message": f"总交互{total}次，成功率{rate:.1f}%",
            "details": {
                "metrics": metrics,
                "health": health,
                "last_updated": data.get("last_updated"),
            },
        }

    # ── Status ──────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        data = self.load_data()
        m = data.get("metrics", {})
        return {
            "ok": True,
            "name": self.name,
            "total_interactions": m.get("total_interactions", 0),
            "identity_adaptations": m.get("identity_adaptations", 0),
            "subsystem_runs": list(m.get("subsystem_runs", {}).keys()),
            "last_interaction": m.get("last_interaction"),
            "health": data.get("subsystem_health", {}),
        }
