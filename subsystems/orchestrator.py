#!/usr/bin/env python3
"""
Orchestrator — 编排系统子系统。
维护 ~/.hermes/orchestration_history.json

功能：
  - 记录任务类型→最优模式的经验
  - 推荐适合的编排模式（含推理过程和置信度）
  - 追踪各模式的使用效果

触发方式：
  1. Cron汇总使用情况
  2. Feishu命令: /orchestrator status | /orchestrator recommend <task>
"""
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import HERMES_HOME, Subsystem

logger = logging.getLogger(__name__)

PATTERNS = [
    ("triangular_review", "三角评审 — 3个reviewer并行审视"),
    ("review_fix", "评审修复 — reviewer发现问题→implementer修复→verifier验证"),
    ("scout_act_verify", "侦察行动 — scout收集→orchestrator规划→implementer执行→verifier确认"),
    ("shard_process", "分片处理 — 任务拆分为N片，并行worker处理，合并结果"),
    ("research_synthesize", "研究综合 — N个researcher并行调研，synthesizer综合"),
    ("option_burst", "选项冲刺 — N个worker同时尝试，选择最优结果"),
]

# 关键词→模式映射（用于推荐推理）
PATTERN_KEYWORDS = {
    "triangular_review": ["review", "review", "评审", "审视", "code review", "检查", "审视", "lint"],
    "review_fix": ["fix", "bug", "修复", "改错", "error", "问题", "缺陷"],
    "scout_act_verify": ["research", "研究", "探索", "investigate", "find", "调查", "侦察"],
    "shard_process": ["batch", "parallel", "大量", "分片", "并发", "split", "批量", "并行"],
    "research_synthesize": ["synthesize", "综合", "调研", "survey", "compare", "对比", "分析"],
    "option_burst": ["best", "optimal", "最优", "choose", "select", "try", "尝试", "选择"],
}


class Orchestrator(Subsystem):
    DATA_FILE = "orchestration_history.json"

    def __init__(self):
        super().__init__("Orchestrator")
        self.path = self.data_file(self.DATA_FILE)
        self._ensure_file()

    def _ensure_file(self):
        if not self.path.exists():
            self.save(self.DATA_FILE, {
                "version": 1,
                "pattern_stats": {},
                "recommendations": [],
            })

    def load_data(self) -> Dict:
        return self.load(self.DATA_FILE)

    def save_data(self, data: Dict):
        self.save(self.DATA_FILE, data)

    def recommend(self, task_description: str) -> Dict[str, Any]:
        """根据任务描述推荐编排模式。

        返回完整推荐对象（含推理过程、置信度、备选方案）。

        Returns:
            {
                "pattern": str,           # 主要推荐模式
                "pattern_desc": str,      # 模式描述
                "reasoning": str,         # 推理过程
                "confidence": float,      # 置信度 0.0~1.0
                "alternatives": List[Dict]  # 备选方案
            }
        """
        td = task_description.lower()
        scores = {}

        for pattern, keywords in PATTERN_KEYWORDS.items():
            scores[pattern] = sum(1 for kw in keywords if kw in td)

        if not scores or max(scores.values()) == 0:
            # 默认分片处理
            default_pattern = "shard_process"
            desc = dict(PATTERNS).get(default_pattern, default_pattern)
            return {
                "pattern": default_pattern,
                "pattern_desc": desc,
                "reasoning": f"任务描述「{task_description[:30]}」未匹配特定模式，默认使用分片处理。",
                "confidence": 0.3,
                "alternatives": self._get_alternatives(default_pattern, scores),
            }

        # 按分数排序
        sorted_patterns = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_patterns[0][0]
        primary_score = sorted_patterns[0][1]
        total_score = sum(s for _, s in sorted_patterns)

        # 生成推理过程
        matched_keywords = []
        for kw in PATTERN_KEYWORDS.get(primary, []):
            if kw in td:
                matched_keywords.append(kw)

        desc = dict(PATTERNS).get(primary, primary)
        confidence = min(0.95, primary_score * 0.3 + 0.4)  # 0.4~0.95

        return {
            "pattern": primary,
            "pattern_desc": desc,
            "reasoning": f"任务关键词 {matched_keywords} 匹配「{primary}」模式（匹配度{primary_score}），{desc}。",
            "confidence": round(confidence, 2),
            "alternatives": self._get_alternatives(primary, scores),
        }

    def _get_alternatives(self, primary: str, scores: Dict[str, int]) -> List[Dict]:
        """获取备选方案。"""
        alts = []
        for pattern, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            if pattern == primary or score == 0:
                continue
            if len(alts) >= 2:
                break
            desc = dict(PATTERNS).get(pattern, pattern)
            alts.append({
                "pattern": pattern,
                "pattern_desc": desc,
                "score": score,
            })
        return alts

    def record_recommendation(self, task_preview: str, pattern: str, result: str = ""):
        """记录一次推荐。

        Args:
            task_preview: 任务摘要
            pattern: 使用的模式
            result: 执行结果
        """
        data = self.load_data()
        rec = {
            "task_preview": task_preview[:100],
            "pattern": pattern,
            "result": result,
            "timestamp": self.timestamp(),
        }
        data.setdefault("recommendations", []).append(rec)
        # 保留最近200条
        data["recommendations"] = data["recommendations"][-200:]
        # 统计
        stats = data.get("pattern_stats", {})
        stats[pattern] = stats.get(pattern, 0) + 1
        data["pattern_stats"] = stats
        self.save_data(data)

    def get_pattern_description(self, pattern: str) -> str:
        for p, desc in PATTERNS:
            if p == pattern:
                return desc
        return pattern

    # ── Run ─────────────────────────────────────────────────────────────

    def run(self, **kwargs) -> Dict[str, Any]:
        data = self.load_data()
        stats = data.get("pattern_stats", {})
        recs = data.get("recommendations", [])
        return {
            "ok": True,
            "message": f"编排统计{len(recs)}次，模式使用: {stats}",
            "details": {
                "pattern_stats": stats,
                "recent_recommendations": recs[-10:] if recs else [],
                "all_patterns": [f"{p}: {d}" for p, d in PATTERNS],
            },
        }

    # ── Status ──────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        data = self.load_data()
        return {
            "ok": True,
            "name": self.name,
            "pattern_stats": data.get("pattern_stats", {}),
            "total_recommendations": len(data.get("recommendations", [])),
        }
