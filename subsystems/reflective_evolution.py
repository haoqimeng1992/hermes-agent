#!/usr/bin/env python3
"""
Reflective Evolution — 反思进化子系统。
维护 ~/.hermes/learnings.json

功能：
  - 从错误/失败中学习
  - 记录教训，避免重复犯错
  - 诊断失败根因，提出改进建议

触发方式：
  1. Cron定期诊断
  2. Feishu命令: /learnings status | /learnings add | /learnings diagnose
  3. 被动：读取learnings影响下次决策
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import HERMES_HOME, Subsystem

logger = logging.getLogger(__name__)


class ReflectiveEvolution(Subsystem):
    DATA_FILE = "learnings.json"

    def __init__(self):
        super().__init__("ReflectiveEvolution")
        self.path = self.data_file(self.DATA_FILE)
        self._ensure_file()

    def _ensure_file(self):
        if not self.path.exists():
            self.save(self.DATA_FILE, {
                "version": 1,
                "updated_at": self.timestamp(),
                "learnings": [],
                "stats": {"total": 0, "by_category": {}},
            })

    def load_data(self) -> Dict:
        return self.load(self.DATA_FILE)

    def save_data(self, data: Dict):
        self.save(self.DATA_FILE, data)

    def add_learning(
        self,
        category: str,
        lesson: str,
        tags: List[str] = None,
        confidence: float = 0.8,
    ) -> Dict:
        """添加一条学习教训。

        Args:
            category: 分类（如 "terminal", "api", "memory"）
            lesson: 教训内容
            tags: 标签列表
            confidence: 置信度 0.0~1.0
        """
        data = self.load_data()
        entry = {
            "id": len(data.get("learnings", [])) + 1,
            "category": category,
            "lesson": lesson,
            "tags": tags or [],
            "confidence": confidence,
            "timestamp": self.timestamp(),
            "times_applied": 0,
        }
        data.setdefault("learnings", []).append(entry)
        data["updated_at"] = self.timestamp()
        stats = data.get("stats", {})
        stats["total"] = len(data["learnings"])
        by_cat = stats.get("by_category", {})
        by_cat[category] = by_cat.get(category, 0) + 1
        stats["by_category"] = by_cat
        data["stats"] = stats
        self.save_data(data)
        return entry

    def get_relevant_learnings(self, query: str, limit: int = 5) -> List[Dict]:
        """获取与查询相关的学习教训。"""
        data = self.load_data()
        learnings = data.get("learnings", [])
        q_lower = query.lower()
        scored = []
        for l in learnings:
            text_fields = [l.get("category", ""), l.get("lesson", l.get("content", ""))] + l.get("tags", [])
            score = sum(1 for kw in text_fields if kw.lower() in q_lower or q_lower in kw.lower())
            if score > 0:
                scored.append((score, l))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [l for _, l in scored[:limit]]

    def diagnose_failure(self, context: str) -> Dict[str, Any]:
        """诊断失败，给出改进建议。"""
        learnings = self.get_relevant_learnings(context, limit=3)
        advice = []
        if learnings:
            advice = [f"参考教训#{l['id']}: {l.get('lesson', l.get('content', ''))}" for l in learnings]
        return {
            "diagnosis": f"基于{len(learnings)}条相关教训的分析",
            "advice": advice,
            "learnings_found": len(learnings),
        }

    # ── Run ─────────────────────────────────────────────────────────────

    def run(self, **kwargs) -> Dict[str, Any]:
        data = self.load_data()
        learnings = data.get("learnings", [])
        stats = data.get("stats", {})
        return {
            "ok": True,
            "message": f"共{stats.get('total', 0)}条学习教训，{len(learnings)}条最新",
            "details": {
                "total": stats.get("total", 0),
                "by_category": stats.get("by_category", {}),
                "recent_learnings": learnings[-5:] if learnings else [],
            },
        }

    # ── Status ──────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        data = self.load_data()
        learnings = data.get("learnings", [])
        stats = data.get("stats", {})
        return {
            "ok": True,
            "name": self.name,
            "total": stats.get("total", 0),
            "by_category": stats.get("by_category", {}),
            "latest_learning": learnings[-1] if learnings else None,
        }
