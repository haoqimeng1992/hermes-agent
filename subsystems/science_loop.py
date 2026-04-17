#!/usr/bin/env python3
"""
Science Loop — 科学循环子系统。
维护 ~/.hermes/goals.json（作为假说数据库）

功能：
  - 假说→实验→评估→保留/丢弃
  - 追踪目标完成情况
  - 评估当前策略有效性

触发方式：
  1. Cron定期运行（每周/每天）
  2. Feishu命令: /goals status | /goals add
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import HERMES_HOME, Subsystem

logger = logging.getLogger(__name__)


class ScienceLoop(Subsystem):
    DATA_FILE = "goals.json"

    def __init__(self):
        super().__init__("ScienceLoop")
        self.path = self.data_file(self.DATA_FILE)
        self._ensure_file()

    def _ensure_file(self):
        if not self.path.exists():
            self.save(self.DATA_FILE, {
                "version": 1,
                "hypotheses": [],
                "experiments": [],
                "evaluations": [],
            })

    def load_data(self) -> Dict:
        return self.load(self.DATA_FILE)

    def save_data(self, data: Dict):
        self.save(self.DATA_FILE, data)

    def add_hypothesis(self, description: str, category: str = "default") -> Dict:
        """添加一个假说。"""
        data = self.load_data()
        entry = {
            "id": f"hyp_{datetime.now(timezone.utc).timestamp()}",
            "description": description,
            "category": category,
            "status": "active",
            "created_at": self.timestamp(),
            "evaluations": 0,
            "verdict": None,
        }
        data.setdefault("hypotheses", []).append(entry)
        self.save_data(data)
        return entry

    def record_experiment(
        self,
        hypothesis_id: str,
        result: str,
        outcome: str = "inconclusive",
    ) -> Dict:
        """记录一个实验结果。

        Args:
            hypothesis_id: 假说ID
            result: 实验结果描述
            outcome: success/failure/inconclusive
        """
        data = self.load_data()
        entry = {
            "hypothesis_id": hypothesis_id,
            "result": result,
            "outcome": outcome,
            "timestamp": self.timestamp(),
        }
        data.setdefault("experiments", []).append(entry)
        # 更新假说状态
        for h in data.get("hypotheses", []):
            if h["id"] == hypothesis_id:
                h["evaluations"] += 1
                break
        self.save_data(data)
        return entry

    def evaluate_hypothesis(
        self,
        hypothesis_id: str,
        verdict: str,
        evaluation_data: Dict = None,
    ) -> Dict:
        """评估假说。

        Args:
            hypothesis_id: 假说ID
            verdict: 裁决结果 retain/discard/modify
            evaluation_data: 详细评估数据 {metrics, results, reasoning}
        """
        data = self.load_data()
        for h in data.get("hypotheses", []):
            if h["id"] == hypothesis_id:
                h["verdict"] = verdict
                h["verdict_at"] = self.timestamp()
                if evaluation_data:
                    h["evaluation_data"] = evaluation_data
                break
        # 记录评估历史
        eval_entry = {
            "hypothesis_id": hypothesis_id,
            "verdict": verdict,
            "evaluation_data": evaluation_data or {},
            "timestamp": self.timestamp(),
        }
        data.setdefault("evaluations", []).append(eval_entry)
        self.save_data(data)
        return {"hypothesis_id": hypothesis_id, "verdict": verdict}

    # ── Run ─────────────────────────────────────────────────────────────

    def run(self, **kwargs) -> Dict[str, Any]:
        data = self.load_data()
        hyps = data.get("hypotheses", [])
        exps = data.get("experiments", [])
        active = [h for h in hyps if h.get("status") == "active"]
        discarded = [h for h in hyps if h.get("verdict") == "discard"]
        return {
            "ok": True,
            "message": f"假说{len(hyps)}个，活跃{len(active)}个，实验{len(exps)}次",
            "details": {
                "total_hypotheses": len(hyps),
                "active": len(active),
                "discarded": len(discarded),
                "total_experiments": len(exps),
                "active_hypotheses": active[-5:],
            },
        }

    # ── Status ──────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        data = self.load_data()
        hyps = data.get("hypotheses", [])
        return {
            "ok": True,
            "name": self.name,
            "total_hypotheses": len(hyps),
            "active": len([h for h in hyps if h.get("status") == "active"]),
            "discarded": len([h for h in hyps if h.get("verdict") == "discard"]),
        }
