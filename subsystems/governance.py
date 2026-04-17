#!/usr/bin/env python3
"""
Governance — 治理层子系统。
维护 ~/.hermes/governance_audit.json

功能：
  - 记录所有操作审计日志
  - 追踪危险/敏感操作标记
  - L1预检拦截，L2结果审计

触发方式：
  1. Cron定期汇总报告
  2. Feishu命令: /governance status | /governance audit
"""
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Union

from .base import HERMES_HOME, Subsystem

logger = logging.getLogger(__name__)

# 危险操作模式 — 匹配 action dict 的 type + command/goal/content
DANGEROUS_PATTERNS: List[Dict[str, Any]] = [
    # 递归删除
    {"type": "terminal", "pattern": r"rm\s+-rf\s+/", "severity": "critical", "reason": "递归删除根目录"},
    {"type": "execute_code", "pattern": r"rm\s+-rf\s+/", "severity": "critical", "reason": "代码执行递归删除根目录"},
    # 格式化
    {"type": "terminal", "pattern": r"mkfs|format\s+/dev", "severity": "critical", "reason": "格式化磁盘"},
    # 危险信号
    {"type": "terminal", "pattern": r"kill\s+-9\s+1", "severity": "high", "reason": "杀init进程"},
    {"type": "delegate", "pattern": r"delete\s+all\s+files?", "severity": "critical", "reason": "删除全部文件委托"},
    {"type": "execute_code", "pattern": r"os\.system\s*\(\s*['\"]rm\s+-rf", "severity": "critical", "reason": "代码执行删除命令"},
    {"type": "terminal", "pattern": r"curl.*\|\s*bash", "severity": "high", "reason": "远程代码注入管道"},
    {"type": "terminal", "pattern": r"wget.*\|\s*bash", "severity": "high", "reason": "远程代码注入管道"},
    # 危险权限操作
    {"type": "terminal", "pattern": r"chmod\s+777\s+/", "severity": "medium", "reason": "开放根目录权限"},
    {"type": "terminal", "pattern": r">\s*/etc/passwd", "severity": "critical", "reason": "覆写系统密码文件"},
]


class Governance(Subsystem):
    DATA_FILE = "governance_audit.json"

    def __init__(self):
        super().__init__("Governance")
        self.path = self.data_file(self.DATA_FILE)
        self._ensure_file()

    def _ensure_file(self):
        if not self.path.exists():
            self.save(self.DATA_FILE, {"audit_trail": [], "blocks": [], "summary": {}})

    def load_data(self) -> Dict:
        return self.load(self.DATA_FILE)

    def save_data(self, data: Dict):
        self.save(self.DATA_FILE, data)

    # ── 核心方法 ─────────────────────────────────────────────────────────

    def _is_action_dangerous(self, action: Dict) -> tuple[bool, str, str]:
        """检查操作是否危险。返回 (是否危险, 危险等级, 原因)。"""
        action_type = action.get("type", "")
        # 提取可能的字符串内容进行匹配
        search_text = json.dumps(action, ensure_ascii=False).lower()

        for rule in DANGEROUS_PATTERNS:
            if rule["type"] != action_type:
                continue
            if re.search(rule["pattern"], search_text, re.IGNORECASE):
                return True, rule["severity"], rule["reason"]

        # 检查 execute_code 中的危险模式
        if action_type == "execute_code":
            code = action.get("code", "")
            if re.search(r"os\.system\s*\(.*rm\s+-rf", code, re.IGNORECASE):
                return True, "critical", "代码执行危险删除命令"
            if re.search(r"subprocess.*shell\s*=\s*True", code):
                return True, "high", "subprocess shell=True 远程命令注入风险"

        return False, "safe", ""

    def _extract_action_summary(self, action: Union[str, Dict]) -> str:
        """提取操作摘要字符串。兼容旧数据（str）和新数据（dict）。"""
        if isinstance(action, str):
            return action
        if isinstance(action, dict):
            t = action.get("type", "?")
            if t == "terminal":
                return f"terminal: {action.get('command', '')[:60]}"
            if t == "execute_code":
                return f"execute_code: {action.get('code', '')[:60]}"
            if t == "delegate":
                return f"delegate: {action.get('goal', '')[:60]}"
            if t == "read_file":
                return f"read_file: {action.get('path', '')}"
            if t == "web_search":
                return f"web_search: {action.get('query', '')}"
            return f"{t}: {str(action)[:60]}"
        return str(action)

    def record_action(
        self,
        action: Union[Dict, str],
        result: str,
        risk_level: str = "low",
        quality_score: float = 1.0,
        details: str = "",
    ):
        """记录一个操作到审计日志。

        Args:
            action: 操作描述，支持 dict（{type, command/goal/code, ...}）或 str（兼容旧数据）
            result: 操作结果字符串
            risk_level: 风险等级 low/medium/high/critical
            quality_score: 质量评分 0.0~1.0
            details: 额外详情
        """
        data = self.load_data()
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat()[:19],
            "action": action,
            "action_summary": self._extract_action_summary(action),
            "result": result,
            "risk_level": risk_level,
            "quality_score": quality_score,
            "details": details,
        }
        data.setdefault("audit_trail", []).append(entry)
        # 保留最近1000条
        data["audit_trail"] = data["audit_trail"][-1000:]
        self.save_data(data)

    def block_action(self, action: Dict, agent_goal: str) -> bool:
        """预检操作，判断是否拦截。返回 True=拦截，False=放行。

        Args:
            action: 操作字典 {type, command/goal/code, ...}
            agent_goal: agent 当前目标描述
        Returns:
            True 表示拦截，False 表示放行
        """
        is_dangerous, severity, reason = self._is_action_dangerous(action)

        data = self.load_data()
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat()[:19],
            "action": action,
            "action_summary": self._extract_action_summary(action),
            "agent_goal": agent_goal,
            "blocked": is_dangerous,
            "severity": severity,
            "reason": reason,
        }
        data.setdefault("blocks", []).append(entry)
        data["blocks"] = data["blocks"][-200:]
        self.save_data(data)

        return is_dangerous

    def get_summary(self) -> Dict[str, int]:
        data = self.load_data()
        audit = data.get("audit_trail", [])
        blocks = data.get("blocks", [])
        return {
            "total_actions": len(audit),
            "total_blocks": len(blocks),
        }

    # ── Run ─────────────────────────────────────────────────────────────

    def run(self, **kwargs) -> Dict[str, Any]:
        data = self.load_data()
        audit = data.get("audit_trail", [])
        blocks = data.get("blocks", [])
        summary = self.get_summary()
        return {
            "ok": True,
            "message": f"审计记录{summary['total_actions']}次，拦截{summary['total_blocks']}次",
            "details": {
                "total_actions": summary["total_actions"],
                "total_blocks": summary["total_blocks"],
                "recent_actions": audit[-10:] if audit else [],
                "recent_blocks": blocks[-10:] if blocks else [],
            },
        }

    # ── Status ──────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        summary = self.get_summary()
        return {
            "ok": True,
            "name": self.name,
            "total_actions": summary["total_actions"],
            "total_blocks": summary["total_blocks"],
        }
