# Subsystem Framework — Gateway集成层

"""
Gateway层子系统统一入口。

真实实现在 ~/.hermes/subsystems/ (13个真实子系统)。
此模块作为Gateway的集成层，提供：
  - Capability → Subsystem 映射
  - 统一的初始化接口
  - 健康检查和摘要

8大能力映射：
  PERCEPTION → perception, knowledge
  MEMORY     → memory_tiering
  REASONING  → reasoning
  ACTION     → toolsets
  EVALUATION → fitness_builder
  MUTATION   → reflective_evolution, reflection
  COORDINATION → orchestration, science_loop, metacognitive
  GOVERNANCE → governance
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import Any, Optional

HERMES_HOME = Path.home() / ".hermes"
sys.path.insert(0, str(HERMES_HOME))

from subsystems import (
    SelfModel, IdentityEvolution, Governance,
    ReflectiveEvolution, ScienceLoop, Orchestrator,
    FitnessBuilder, Metacognitive, MemoryTiering,
    LivingCore,
    PerceptionLayer, ReasoningLayer, KnowledgeLayer, AdaptationLayer,
)


class Capability(Enum):
    PERCEPTION = "perception"
    MEMORY = "memory"
    REASONING = "reasoning"
    ACTION = "action"
    EVALUATION = "evaluation"
    MUTATION = "mutation"
    COORDINATION = "coordination"
    GOVERNANCE = "governance"


# Capability → Subsystem class mapping
CAPABILITY_SUBSYSTEMS: dict[Capability, list[type]] = {
    Capability.PERCEPTION: [PerceptionLayer, KnowledgeLayer],
    Capability.MEMORY: [MemoryTiering],
    Capability.REASONING: [ReasoningLayer],
    Capability.ACTION: [],  # toolsets handled elsewhere
    Capability.EVALUATION: [FitnessBuilder],
    Capability.MUTATION: [ReflectiveEvolution, AdaptationLayer],
    Capability.COORDINATION: [Orchestrator, ScienceLoop, Metacognitive],
    Capability.GOVERNANCE: [Governance],
}


def get_capabilities_summary() -> dict[str, list[str]]:
    """按能力返回子系统名称列表"""
    result = {}
    for cap, classes in CAPABILITY_SUBSYSTEMS.items():
        result[cap.value] = [cls.__name__ for cls in classes]
    return result


def initialize_all() -> dict[str, bool]:
    """初始化所有子系统"""
    results = {}
    for cap, classes in CAPABILITY_SUBSYSTEMS.items():
        for cls in classes:
            name = cls.__name__
            try:
                inst = cls()
                if hasattr(inst, "run"):
                    inst.run()
                results[name] = True
            except Exception as e:
                results[name] = False
    return results


def get_health() -> list[dict]:
    """获取所有子系统健康状态"""
    health = []
    for cap, classes in CAPABILITY_SUBSYSTEMS.items():
        for cls in classes:
            name = cls.__name__
            try:
                inst = cls()
                if hasattr(inst, "status"):
                    st = inst.status()
                    health.append({
                        "name": name,
                        "capability": cap.value,
                        "ok": st.get("ok", True),
                        "status": "ready",
                    })
                else:
                    health.append({
                        "name": name,
                        "capability": cap.value,
                        "ok": True,
                        "status": "no status method",
                    })
            except Exception as e:
                health.append({
                    "name": name,
                    "capability": cap.value,
                    "ok": False,
                    "status": f"error: {e}",
                })
    return health


def get_global_summary() -> dict:
    """全局摘要"""
    health = get_health()
    ready = sum(1 for h in health if h["ok"])
    return {
        "total": len(health),
        "ready": ready,
        "not_ready": len(health) - ready,
        "capabilities": {c.value: c.value for c in Capability},
        "capability_mapping": get_capabilities_summary(),
        "health": health,
    }
