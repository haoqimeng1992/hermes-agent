#!/usr/bin/env python3
"""
Identity Evolution — 身份进化子系统。
维护 ~/.hermes/identity_evolution.json

功能：
  - 追踪行为特质(verbosity, proactivity等)
  - 根据用户反馈自动微调
  - 检测行为信号(详细/简洁/纠正/正向)

触发方式：
  1. Cron任务自动运行（收集对话特征）
  2. Feishu命令: /identity status | /identity traits | /identity adapt
  3. 被动：下次对话时读取traits注入prompt segment
"""
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .base import HERMES_HOME, Subsystem

logger = logging.getLogger(__name__)

# 与现有数据文件schema兼容
TRAITS_SCHEMA = {
    "verbosity": 0.7,
    "proactivity": 0.5,
    "code_preference": 0.4,
    "emoji_usage": 0.6,
    "risk_tolerance": 0.3,
    "learning_display": 0.5,
}

ADJUSTMENTS = {
    "verbose_request": {"verbosity": 0.05, "explanation_depth": 0.05},
    "brief_request": {"verbosity": -0.03},
    "correction": {"proactivity": -0.02},
    "positive_feedback": {"proactivity": 0.01, "verbosity": 0.01},
    "error_recovery": {"proactivity": -0.01, "risk_tolerance": -0.01},
    "long_task": {"verbosity": 0.02, "proactivity": 0.01},
    "quick_task": {"verbosity": -0.02, "proactivity": -0.01},
}


class IdentityEvolution(Subsystem):
    DATA_FILE = "identity_evolution.json"

    def __init__(self):
        super().__init__("IdentityEvolution")
        self.path = self.data_file(self.DATA_FILE)
        self._ensure_file()

    def _ensure_file(self):
        if not self.path.exists():
            self.save(self.DATA_FILE, {
                "version": 1,
                "created_at": datetime.now(timezone.utc).timestamp(),
                "behavioral_params": dict(TRAITS_SCHEMA),
                "adaptation_log": [],
                "signal_counts": {},
                "last_updated": self.timestamp(),
            })

    def load_data(self) -> Dict:
        return self.load(self.DATA_FILE)

    def save_data(self, data: Dict):
        data["last_updated"] = self.timestamp()
        self.save(self.DATA_FILE, data)

    def get_traits(self) -> Dict[str, float]:
        data = self.load_data()
        return data.get("behavioral_params", dict(TRAITS_SCHEMA))

    def adapt(self, signal_type: str, strength: float = 1.0) -> Dict:
        """根据信号类型调整特质。"""
        data = self.load_data()
        traits = data.get("behavioral_params", dict(TRAITS_SCHEMA))
        adjustments = ADJUSTMENTS.get(signal_type, {})

        log_entry = {
            "signal": signal_type,
            "strength": strength,
            "timestamp": datetime.now(timezone.utc).timestamp(),
            "before": {},
            "after": {},
        }

        for trait, delta in adjustments.items():
            if trait in traits:
                old = traits[trait]
                new = max(0.0, min(1.0, old + delta * strength))
                traits[trait] = round(new, 4)
                log_entry["before"][trait] = old
                log_entry["after"][trait] = new

        data["behavioral_params"] = traits
        data.setdefault("adaptation_log", []).append(log_entry)
        data["signal_counts"] = data.get("signal_counts", {})
        data["signal_counts"][signal_type] = data["signal_counts"].get(signal_type, 0) + 1
        self.save_data(data)

        return log_entry

    def get_prompt_segment(self) -> str:
        """生成身份引导prompt segment，供注入到system prompt。"""
        traits = self.get_traits()
        parts = []

        # verbosity
        v = traits.get("verbosity", 0.7)
        if v > 0.8:
            parts.append("详细展开，解释过程")
        elif v < 0.4:
            parts.append("简洁直接，一针见血")

        # proactivity
        p = traits.get("proactivity", 0.5)
        if p > 0.7:
            parts.append("主动预判需求，提前行动")
        elif p < 0.3:
            parts.append("被动响应，只在明确要求时行动")

        # code_preference
        if traits.get("code_preference", 0.4) > 0.6:
            parts.append("优先给出代码示例")

        # emoji_usage
        if traits.get("emoji_usage", 0.6) > 0.7:
            parts.append("适当使用emoji增强可读性")

        if parts:
            return f"[身份指导] {'；'.join(parts)}。"
        return ""

    # ── Run ─────────────────────────────────────────────────────────────

    def run(self, **kwargs) -> Dict[str, Any]:
        """定期自检+记录。"""
        data = self.load_data()
        traits = data.get("behavioral_params", {})
        log = data.get("adaptation_log", [])
        signals = data.get("signal_counts", {})

        # 检查异常
        warnings = []
        for trait, val in traits.items():
            if val <= 0.05 or val >= 0.95:
                warnings.append(f"{trait}值异常: {val}")

        return {
            "ok": True,
            "message": f"当前{len(traits)}个特质，{len(log)}次适应记录",
            "details": {
                "traits": traits,
                "total_adaptations": len(log),
                "signal_counts": signals,
                "warnings": warnings,
                "last_updated": data.get("last_updated"),
            },
        }

    # ── Status ──────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        data = self.load_data()
        traits = data.get("behavioral_params", {})
        return {
            "ok": True,
            "name": self.name,
            "traits": traits,
            "total_adaptations": len(data.get("adaptation_log", [])),
            "signal_counts": data.get("signal_counts", {}),
            "prompt_segment": self.get_prompt_segment(),
        }
