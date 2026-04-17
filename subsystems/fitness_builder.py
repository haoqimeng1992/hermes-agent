#!/usr/bin/env python3
"""
Fitness Builder — 适应度构建子系统。
维护 ~/.hermes/fitness_functions.json

功能：
  - GOAL.md模式的适应度函数
  - 多维度加权评估
  - 追踪适应度变化趋势

触发方式：
  1. Cron定期评估
  2. Feishu命令: /fitness status | /fitness evaluate <name>
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import HERMES_HOME, Subsystem

logger = logging.getLogger(__name__)


class FitnessBuilder(Subsystem):
    DATA_FILE = "fitness_functions.json"

    def __init__(self):
        super().__init__("FitnessBuilder")
        self.path = self.data_file(self.DATA_FILE)
        self._ensure_file()

    def _ensure_file(self):
        if not self.path.exists():
            self.save(self.DATA_FILE, {
                "functions": {},
                "evaluation_history": [],
            })

    def load_data(self) -> Dict:
        data = self.load(self.DATA_FILE)
        # 兼容旧版 list 格式 → 转为 dict
        if isinstance(data.get("functions"), list):
            data["functions"] = {item["id"]: item for item in data["functions"]}
        return data

    def save_data(self, data: Dict):
        self.save(self.DATA_FILE, data)

    def create_function(self, name: str, target: str, dimensions: List[Dict]) -> Dict:
        """创建新的适应度函数。"""
        data = self.load_data()
        fid = f"fit_{uuid.uuid4().hex[:8]}"
        ff = {
            "id": fid,
            "name": name,
            "target": target,
            "dimensions": dimensions,
            "created_at": self.timestamp(),
            "updated_at": self.timestamp(),
            "current_score": 0.0,
            "history": [],
        }
        data["functions"][fid] = ff
        self.save_data(data)
        return ff

    def evaluate(self, fitness_id: str, scores: Dict[str, float]) -> Dict:
        """评估一个适应度函数。scores: {dimension_name: 0.0-1.0}"""
        data = self.load_data()
        ff = data["functions"].get(fitness_id)
        if not ff:
            return {"ok": False, "error": f"fitness {fitness_id} not found"}

        # 计算加权得分
        total_weight = sum(d.get("weight", 1.0) for d in ff["dimensions"])
        weighted_score = 0.0
        for dim in ff["dimensions"]:
            name = dim["name"]
            if name in scores:
                weighted_score += (dim.get("weight", 1.0) / total_weight) * scores[name]

        # 记录历史
        entry = {
            "timestamp": self.timestamp(),
            "dimensions": scores,
            "weighted_score": round(weighted_score, 4),
        }
        ff.setdefault("history", []).append(entry)
        ff["current_score"] = round(weighted_score, 4)
        ff["updated_at"] = self.timestamp()
        data["functions"][fitness_id] = ff

        # 记录全局历史
        data.setdefault("evaluation_history", []).append({
            "fitness_id": fitness_id,
            **entry,
        })
        data["evaluation_history"] = data["evaluation_history"][-500:]

        self.save_data(data)
        return {"ok": True, "fitness_id": fitness_id, "weighted_score": weighted_score}

    # ── Run ─────────────────────────────────────────────────────────────

    def run(self, **kwargs) -> Dict[str, Any]:
        data = self.load_data()
        funcs = data.get("functions", {})
        history = data.get("evaluation_history", [])
        return {
            "ok": True,
            "message": f"适应度函数{len(funcs)}个，评估历史{len(history)}条",
            "details": {
                "functions": {k: {"name": v["name"], "current_score": v.get("current_score", 0), "dimensions": len(v.get("dimensions", []))}
                              for k, v in funcs.items()},
                "recent_evaluations": history[-10:] if history else [],
            },
        }

    # ── Status ──────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        data = self.load_data()
        funcs = data.get("functions", {})
        return {
            "ok": True,
            "name": self.name,
            "total_functions": len(funcs),
            "functions": {k: {"name": v["name"], "score": v.get("current_score", 0)}
                          for k, v in funcs.items()},
        }
