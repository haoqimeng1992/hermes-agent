# Evolution — 进化层

"""
根据经验持续改进自身

进化机制：
- 代码级进化（修改自身代码）
- 策略级进化（改进决策策略）
- 知识级进化（更新知识库）
- 架构级进化（调整子系统）

设计原理：
- 进化是基于反馈的持续改进
- 进化需要有方向（适应度函数）
- 进化需要评估和选择
"""

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

HERMES_HOME = Path.home() / ".hermes"
EVOLUTION_DIR = HERMES_HOME / "knowledge" / "evolution"


class EvolutionType(Enum):
    CODE = "code"               # 代码级进化
    STRATEGY = "strategy"     # 策略级进化
    KNOWLEDGE = "knowledge"   # 知识级进化
    ARCHITECTURE = "architecture"  # 架构级进化


class EvolutionStatus(Enum):
    PROPOSED = "proposed"     # 提议阶段
    TESTING = "testing"       # 测试中
    ADOPTED = "adopted"       # 已采纳
    REJECTED = "rejected"     # 已拒绝
    REVERTED = "reverted"     # 已回滚


@dataclass
class Evolution:
    """进化记录"""
    id: str
    type: EvolutionType
    description: str                      # 进化描述
    change_summary: str                  # 变更摘要
    previous_state: str                   # 之前状态
    new_state: str                       # 新状态
    rationale: str                       # 理由
    expected_benefit: str                # 预期收益
    risk_level: str = "medium"         # low/medium/high
    status: EvolutionStatus = EvolutionStatus.PROPOSED
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tested_at: Optional[str] = None
    adopted_at: Optional[str] = None
    rejected_at: Optional[str] = None
    reverted_at: Optional[str] = None
    test_results: dict = field(default_factory=dict)
    source: str = "unknown"             # 来源（reflection/science_loop/...）
    evidence: list[str] = field(default_factory=list)
    related_evolution_ids: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "description": self.description,
            "change_summary": self.change_summary,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "rationale": self.rationale,
            "expected_benefit": self.expected_benefit,
            "risk_level": self.risk_level,
            "status": self.status.value,
            "created_at": self.created_at,
            "tested_at": self.tested_at,
            "adopted_at": self.adopted_at,
            "rejected_at": self.rejected_at,
            "reverted_at": self.reverted_at,
            "test_results": self.test_results,
            "source": self.source,
            "evidence": self.evidence,
            "related_evolution_ids": self.related_evolution_ids,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "Evolution":
        d["type"] = EvolutionType(d.get("type", "knowledge"))
        d["status"] = EvolutionStatus(d.get("status", "proposed"))
        return cls(**d)


@dataclass
class EvolutionResult:
    """进化结果评估"""
    evolution_id: str
    improvement: float                  # 改进幅度 0-1
    metrics_before: dict                # 进化前指标
    metrics_after: dict                 # 进化后指标
    side_effects: list[str] = field(default_factory=list)
    verdict: str = "pending"           # adopt/reject/modify
    notes: str = ""
    evaluated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return {
            "evolution_id": self.evolution_id,
            "improvement": self.improvement,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "side_effects": self.side_effects,
            "verdict": self.verdict,
            "notes": self.notes,
            "evaluated_at": self.evaluated_at,
        }


class EvolutionLayer:
    """
    进化层 — 根据经验持续改进自身
    
    核心职责：
    1. 提出进化建议
    2. 测试和评估进化
    3. 选择和采纳进化
    4. 跟踪进化历史
    
    建议 → 测试 → 评估 → 选择 → 采纳
    """
    
    def __init__(self):
        EVOLUTION_DIR.mkdir(parents=True, exist_ok=True)
        self._evolutions: dict[str, Evolution] = {}
        self._results: dict[str, EvolutionResult] = {}
        self._load()
    
    def _load(self):
        """从磁盘加载"""
        evolutions_file = EVOLUTION_DIR / "evolutions.jsonl"
        if evolutions_file.exists():
            with open(evolutions_file) as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        e = Evolution.from_dict(d)
                        self._evolutions[e.id] = e
        
        results_file = EVOLUTION_DIR / "results.json"
        if results_file.exists():
            with open(results_file) as f:
                data = json.load(f)
                for d in data.values():
                    self._results[d["evolution_id"]] = EvolutionResult(**d)
    
    def _save_evolution(self, e: Evolution):
        """保存进化"""
        evolutions_file = EVOLUTION_DIR / "evolutions.jsonl"
        with open(evolutions_file, "a") as f:
            f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
    
    def _save_result(self, r: EvolutionResult):
        """保存结果"""
        results_file = EVOLUTION_DIR / "results.json"
        data = {rid: r.to_dict() for rid, r in self._results.items()}
        with open(results_file, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # === 进化提议 ===
    
    def propose(
        self,
        type: EvolutionType,
        description: str,
        change_summary: str,
        rationale: str,
        expected_benefit: str,
        risk_level: str = "medium",
        source: str = "unknown",
        evidence: list[str] = None,
    ) -> Evolution:
        """提议进化"""
        evolution = Evolution(
            id=f"evo_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            type=type,
            description=description,
            change_summary=change_summary,
            previous_state="current",
            new_state="proposed",
            rationale=rationale,
            expected_benefit=expected_benefit,
            risk_level=risk_level,
            source=source,
            evidence=evidence or [],
        )
        
        self._evolutions[evolution.id] = evolution
        self._save_evolution(evolution)
        
        return evolution
    
    def propose_from_reflection(
        self,
        reflection_id: str,
        description: str,
        change_summary: str,
    ) -> Evolution:
        """从反思提议进化"""
        return self.propose(
            type=EvolutionType.STRATEGY,
            description=description,
            change_summary=change_summary,
            rationale=f"基于反思 {reflection_id}",
            expected_benefit="改进策略",
            source=f"reflection:{reflection_id}",
        )
    
    def propose_from_science(
        self,
        hypothesis_id: str,
        experiment_id: str,
        change_summary: str,
    ) -> Evolution:
        """从科学循环提议进化"""
        return self.propose(
            type=EvolutionType.CODE,
            description=f"基于实验 {experiment_id}",
            change_summary=change_summary,
            rationale=f"假说 {hypothesis_id} 实验验证",
            expected_benefit="代码改进",
            source=f"science:hypothesis:{hypothesis_id}",
        )
    
    # === 进化测试 ===
    
    def start_testing(self, evolution_id: str) -> bool:
        """开始测试进化"""
        e = self._evolutions.get(evolution_id)
        if not e or e.status != EvolutionStatus.PROPOSED:
            return False
        
        e.status = EvolutionStatus.TESTING
        self._save_evolution(e)
        
        return True
    
    def complete_test(
        self,
        evolution_id: str,
        test_results: dict,
        metrics_before: dict,
        metrics_after: dict,
    ) -> bool:
        """完成测试"""
        e = self._evolutions.get(evolution_id)
        if not e or e.status != EvolutionStatus.TESTING:
            return False
        
        e.status = EvolutionStatus.TESTING
        e.tested_at = datetime.now().isoformat()
        e.test_results = test_results
        
        # 评估结果
        improvement = 0.0
        if metrics_before and metrics_after:
            for key in metrics_after:
                if key in metrics_before and metrics_before[key] != 0:
                    improvement += (metrics_after[key] - metrics_before[key]) / abs(metrics_before[key])
            improvement /= len(metrics_after)
        
        result = EvolutionResult(
            evolution_id=evolution_id,
            improvement=improvement,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
        )
        
        # 判断是否采纳
        if improvement > 0.05:  # 5%以上改进
            result.verdict = "adopt"
            e.status = EvolutionStatus.ADOPTED
            e.adopted_at = datetime.now().isoformat()
        else:
            result.verdict = "reject"
            e.status = EvolutionStatus.REJECTED
            e.rejected_at = datetime.now().isoformat()
        
        self._results[evolution_id] = result
        self._save_evolution(e)
        self._save_result(result)
        
        return True
    
    # === 进化采纳 ===
    
    def adopt(self, evolution_id: str) -> bool:
        """采纳进化"""
        e = self._evolutions.get(evolution_id)
        if not e:
            return False
        
        e.status = EvolutionStatus.ADOPTED
        e.adopted_at = datetime.now().isoformat()
        self._save_evolution(e)
        
        return True
    
    def reject(self, evolution_id: str, reason: str = "") -> bool:
        """拒绝进化"""
        e = self._evolutions.get(evolution_id)
        if not e:
            return False
        
        e.status = EvolutionStatus.REJECTED
        e.rejected_at = datetime.now().isoformat()
        self._save_evolution(e)
        
        return True
    
    def revert(self, evolution_id: str) -> bool:
        """回滚进化"""
        e = self._evolutions.get(evolution_id)
        if not e or e.status != EvolutionStatus.ADOPTED:
            return False
        
        e.status = EvolutionStatus.REVERTED
        e.reverted_at = datetime.now().isoformat()
        self._save_evolution(e)
        
        return True
    
    # === 进化检索 ===
    
    def get_proposed(self) -> list[Evolution]:
        """获取提议中的进化"""
        return [e for e in self._evolutions.values() if e.status == EvolutionStatus.PROPOSED]
    
    def get_adopted(self) -> list[Evolution]:
        """获取已采纳的进化"""
        return [e for e in self._evolutions.values() if e.status == EvolutionStatus.ADOPTED]
    
    def get_recent(self, limit: int = 20) -> list[Evolution]:
        """获取最近的进化"""
        evolutions = list(self._evolutions.values())
        evolutions.sort(key=lambda e: e.created_at, reverse=True)
        return evolutions[:limit]
    
    def get_by_type(self, type: EvolutionType) -> list[Evolution]:
        """按类型获取"""
        return [e for e in self._evolutions.values() if e.type == type]
    
    def get_result(self, evolution_id: str) -> Optional[EvolutionResult]:
        """获取进化结果"""
        return self._results.get(evolution_id)
    
    # === 摘要 ===
    
    def get_summary(self) -> dict:
        """获取进化层摘要"""
        status_counts = {}
        for status in EvolutionStatus:
            status_counts[status.value] = len([e for e in self._evolutions.values() if e.status == status])
        
        type_counts = {}
        for et in EvolutionType:
            type_counts[et.value] = len([e for e in self._evolutions.values() if e.type == et])
        
        adopted = [e for e in self._evolutions.values() if e.status == EvolutionStatus.ADOPTED]
        avg_improvement = (
            sum(self._results.get(e.id, EvolutionResult(evolution_id=e.id, improvement=0)).improvement
                for e in adopted) / len(adopted) if adopted else 0
        )
        
        return {
            "total_evolutions": len(self._evolutions),
            "status_distribution": status_counts,
            "type_distribution": type_counts,
            "adoption_rate": len(adopted) / len(self._evolutions) if self._evolutions else 0,
            "avg_improvement": round(avg_improvement, 3),
        }


# 全局单例
_evolution: Optional[EvolutionLayer] = None

def get_evolution() -> EvolutionLayer:
    global _evolution
    if _evolution is None:
        _evolution = EvolutionLayer()
    return _evolution
