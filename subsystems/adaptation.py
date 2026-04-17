# Adaptation — 适应层

"""
根据环境变化调整自身行为

适应维度：
- 性能适应（根据负载调整）
- 行为适应（根据用户偏好调整）
- 策略适应（根据任务类型调整）

设计原理：
- 好的系统能感知环境变化并自适应
- 适应需要基于反馈
- 避免过度适应（震荡）
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

HERMES_HOME = Path.home() / ".hermes"
ADAPTATION_DIR = HERMES_HOME / "knowledge" / "adaptation"


class AdaptationType(Enum):
    PERFORMANCE = "performance"     # 性能适应
    BEHAVIORAL = "behavioral"   # 行为适应
    STRATEGIC = "strategic"     # 策略适应


@dataclass
class AdaptationRule:
    """适应规则"""
    id: str
    trigger: str                        # 触发条件
    condition: str                      # 条件表达式
    action: str                         # 执行的调整动作
    parameter: str                      # 参数名
    target_value: Any                   # 目标值
    enabled: bool = True
    applied_count: int = 0
    last_applied: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "trigger": self.trigger,
            "condition": self.condition,
            "action": self.action,
            "parameter": self.parameter,
            "target_value": str(self.target_value),
            "enabled": self.enabled,
            "applied_count": self.applied_count,
            "last_applied": self.last_applied,
        }


@dataclass
class AdaptationEvent:
    """适应事件"""
    rule_id: str
    trigger_value: Any
    previous_value: Any
    new_value: Any
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    reason: str = ""
    
    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "trigger_value": str(self.trigger_value),
            "previous_value": str(self.previous_value),
            "new_value": str(self.new_value),
            "timestamp": self.timestamp,
            "reason": self.reason,
        }


class AdaptationLayer:
    """
    适应层 — 根据环境变化调整自身行为
    
    核心职责：
    1. 监控环境和行为变化
    2. 触发适应规则
    3. 防止过度适应
    4. 学习新的适应模式
    
    监控 → 评估 → 决策 → 调整 → 学习
    """
    
    def __init__(self):
        ADAPTATION_DIR.mkdir(parents=True, exist_ok=True)
        self._rules: dict[str, AdaptationRule] = {}
        self._events: list[AdaptationEvent] = []
        self._load_rules()
        
        # 内置适应规则
        self._init_builtin_rules()
    
    def _load_rules(self):
        """加载规则"""
        rules_file = ADAPTATION_DIR / "rules.json"
        if rules_file.exists():
            with open(rules_file) as f:
                data = json.load(f)
                for d in data.values():
                    self._rules[d["id"]] = AdaptationRule(**d)
    
    def _save_rules(self):
        """保存规则"""
        rules_file = ADAPTATION_DIR / "rules.json"
        data = {k: v.to_dict() for k, v in self._rules.items()}
        with open(rules_file, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _init_builtin_rules(self):
        """初始化内置适应规则"""
        builtin_rules = [
            {
                "id": "high_load_compression",
                "trigger": "cpu_percent > 80",
                "condition": "metrics.cpu_percent > 80",
                "action": "increase_compression_threshold",
                "parameter": "compression_threshold",
                "target_value": "0.95",
            },
            {
                "id": "low_load_downgrade",
                "trigger": "cpu_percent < 20 for 5min",
                "condition": "metrics.cpu_percent < 20",
                "action": "decrease_compression_threshold",
                "parameter": "compression_threshold",
                "target_value": "0.85",
            },
            {
                "id": "high_error_rate",
                "trigger": "error_rate > 0.05",
                "condition": "metrics.error_rate > 0.05",
                "action": "reduce_parallel_tasks",
                "parameter": "max_concurrent",
                "target_value": "2",
            },
            {
                "id": "slow_response",
                "trigger": "avg_response_time > 10s",
                "condition": "metrics.avg_response_time > 10000",
                "action": "switch_to_faster_model",
                "parameter": "model",
                "target_value": "MiniMax-M2.5",
            },
        ]
        
        for rule_data in builtin_rules:
            if rule_data["id"] not in self._rules:
                self._rules[rule_data["id"]] = AdaptationRule(**rule_data)
        
        self._save_rules()
    
    # === 适应监控 ===
    
    def observe(self, metrics: dict) -> list[AdaptationEvent]:
        """观察环境，触发适应的规则"""
        events = []
        
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            
            if self._evaluate_condition(rule.condition, metrics):
                event = self._apply_rule(rule, metrics)
                if event:
                    events.append(event)
        
        return events
    
    def _evaluate_condition(self, condition: str, metrics: dict) -> bool:
        """评估条件是否满足"""
        try:
            # 简单的条件评估
            # 例如: "metrics.cpu_percent > 80"
            local_vars = {"metrics": metrics}
            return eval(condition, {"__builtins__": {}}, local_vars)
        except Exception:
            return False
    
    def _apply_rule(self, rule: AdaptationRule, metrics: dict) -> Optional[AdaptationEvent]:
        """应用规则"""
        # 获取当前值（这里需要从配置或运行时获取）
        current_value = self._get_parameter(rule.parameter)
        
        # 检查是否需要调整
        if str(current_value) == str(rule.target_value):
            return None
        
        # 创建适应事件
        event = AdaptationEvent(
            rule_id=rule.id,
            trigger_value=metrics.get(rule.trigger.split()[0], "unknown"),
            previous_value=current_value,
            new_value=rule.target_value,
            reason=f"Trigger: {rule.trigger}",
        )
        
        self._events.append(event)
        rule.applied_count += 1
        rule.last_applied = datetime.now().isoformat()
        
        # 实际调整参数
        self._set_parameter(rule.parameter, rule.target_value)
        
        self._save_rules()
        
        return event
    
    def _get_parameter(self, parameter: str) -> Any:
        """获取参数当前值"""
        # 这里需要接入实际配置系统
        # 暂时返回默认值
        defaults = {
            "compression_threshold": 0.85,
            "max_concurrent": 3,
            "model": "MiniMax-M2.7-highspeed",
        }
        return defaults.get(parameter, None)
    
    def _set_parameter(self, parameter: str, value: Any):
        """设置参数"""
        # 这里需要接入实际配置系统
        pass
    
    # === 规则管理 ===
    
    def add_rule(
        self,
        trigger: str,
        condition: str,
        action: str,
        parameter: str,
        target_value: Any,
    ) -> AdaptationRule:
        """添加新规则"""
        import hashlib
        rule_id = f"rule_{hashlib.md5(f'{trigger}{parameter}'.encode()).hexdigest()[:8]}"
        
        rule = AdaptationRule(
            id=rule_id,
            trigger=trigger,
            condition=condition,
            action=action,
            parameter=parameter,
            target_value=target_value,
        )
        
        self._rules[rule_id] = rule
        self._save_rules()
        
        return rule
    
    def enable_rule(self, rule_id: str) -> bool:
        """启用规则"""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True
            self._save_rules()
            return True
        return False
    
    def disable_rule(self, rule_id: str) -> bool:
        """禁用规则"""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False
            self._save_rules()
            return True
        return False
    
    def get_enabled_rules(self) -> list[AdaptationRule]:
        """获取启用的规则"""
        return [r for r in self._rules.values() if r.enabled]
    
    # === 历史 ===
    
    def get_recent_events(self, limit: int = 20) -> list[AdaptationEvent]:
        """获取最近的适应事件"""
        return self._events[-limit:]
    
    def get_event_history(self, rule_id: str = None) -> list[AdaptationEvent]:
        """获取规则的历史事件"""
        if rule_id:
            return [e for e in self._events if e.rule_id == rule_id]
        return self._events
    
    # === 摘要 ===
    
    def get_summary(self) -> dict:
        """获取适应层摘要"""
        return {
            "total_rules": len(self._rules),
            "enabled_rules": len(self.get_enabled_rules()),
            "total_events": len(self._events),
            "recent_events": len(self.get_recent_events()),
            "most_active_rule": (
                max(self._rules.values(), key=lambda r: r.applied_count).id
                if self._rules else None
            ),
        }


# 全局单例
_adaptation: Optional[AdaptationLayer] = None

def get_adaptation() -> AdaptationLayer:
    global _adaptation
    if _adaptation is None:
        _adaptation = AdaptationLayer()
    return _adaptation
