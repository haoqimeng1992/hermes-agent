# Reasoning — 推理层

"""
基于信息做决策

推理类型：
- 演绎推理（从一般到特殊）
- 归纳推理（从特殊到一般）
- 溯因推理（从结果到原因）
- 类比推理（从相似到相似）

设计原理：
- 推理需要清晰的结构
- 不同类型的问题需要不同的推理方式
- 推理需要可解释
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

HERMES_HOME = Path.home() / ".hermes"
REASONING_DIR = HERMES_HOME / "knowledge" / "reasoning"


class ReasoningType(Enum):
    DEDUCTIVE = "deductive"         # 演绎推理
    INDUCTIVE = "inductive"       # 归纳推理
    ABDUCTIVE = "abductive"      # 溯因推理
    ANALOGICAL = "analogical"     # 类比推理
    CAUSAL = "causal"           # 因果推理


@dataclass
class ReasoningChain:
    """推理链"""
    id: str
    type: ReasoningType
    premise: str                     # 前提
    inference: str                   # 推理过程
    conclusion: str                  # 结论
    confidence: float = 0.5         # 置信度
    evidence: list[str] = field(default_factory=list)
    counter_arguments: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "premise": self.premise,
            "inference": self.inference,
            "conclusion": self.conclusion,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "counter_arguments": self.counter_arguments,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "ReasoningChain":
        d["type"] = ReasoningType(d.get("type", "deductive"))
        return cls(**d)


@dataclass
class Decision:
    """决策"""
    id: str
    options: list[str]              # 选项
    reasoning_chains: list[str] = field(default_factory=list)  # 推理链ID列表
    chosen_option: Optional[str] = None
    confidence: float = 0.5
    reasoning: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    outcome: Optional[str] = None   # 决策结果
    success: Optional[bool] = None  # 决策是否正确
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "options": self.options,
            "reasoning_chains": self.reasoning_chains,
            "chosen_option": self.chosen_option,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
            "outcome": self.outcome,
            "success": self.success,
        }


class ReasoningLayer:
    """
    推理层 — 基于信息做决策
    
    核心职责：
    1. 构建推理链
    2. 评估置信度
    3. 做出决策
    4. 追踪决策结果
    
    感知 → 推理 → 决策 → 行动 → 评估
    """
    
    def __init__(self):
        REASONING_DIR.mkdir(parents=True, exist_ok=True)
        self._chains: dict[str, ReasoningChain] = {}
        self._decisions: dict[str, Decision] = {}
        self._load()
    
    def _load(self):
        """从磁盘加载"""
        chains_file = REASONING_DIR / "chains.jsonl"
        if chains_file.exists():
            with open(chains_file) as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        chain = ReasoningChain.from_dict(d)
                        self._chains[chain.id] = chain
        
        decisions_file = REASONING_DIR / "decisions.json"
        if decisions_file.exists():
            with open(decisions_file) as f:
                data = json.load(f)
                for d in data.values():
                    self._decisions[d["id"]] = Decision(**d)
    
    def _save_chain(self, chain: ReasoningChain):
        """保存推理链"""
        chains_file = REASONING_DIR / "chains.jsonl"
        with open(chains_file, "a") as f:
            f.write(json.dumps(chain.to_dict(), ensure_ascii=False) + "\n")
    
    def _save_decision(self, decision: Decision):
        """保存决策"""
        decisions_file = REASONING_DIR / "decisions.json"
        data = {did: d.to_dict() for did, d in self._decisions.items()}
        with open(decisions_file, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # === 推理构建 ===
    
    def reason(
        self,
        type: ReasoningType,
        premise: str,
        inference: str,
        conclusion: str,
        evidence: list[str] = None,
        counter_arguments: list[str] = None,
    ) -> ReasoningChain:
        """构建推理链"""
        chain = ReasoningChain(
            id=f"chain_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            type=type,
            premise=premise,
            inference=inference,
            conclusion=conclusion,
            evidence=evidence or [],
            counter_arguments=counter_arguments or [],
        )
        
        # 计算置信度
        chain.confidence = self._calculate_confidence(chain)
        
        self._chains[chain.id] = chain
        self._save_chain(chain)
        
        return chain
    
    def _calculate_confidence(self, chain: ReasoningChain) -> float:
        """计算推理链置信度"""
        base = 0.5
        
        # 证据越多，置信度越高
        if chain.evidence:
            base += min(len(chain.evidence) * 0.05, 0.2)
        
        # 考虑反驳论点
        if chain.counter_arguments:
            base -= min(len(chain.counter_arguments) * 0.05, 0.2)
        
        return max(0.0, min(1.0, base))
    
    def deduct(
        self,
        rule: str,
        case: str,
        evidence: list[str] = None,
    ) -> ReasoningChain:
        """演绎推理：从一般到特殊"""
        return self.reason(
            type=ReasoningType.DEDUCTIVE,
            premise=f"规则: {rule}\n案例: {case}",
            inference="应用规则到案例",
            conclusion=f"结论: {case} 符合规则",
            evidence=evidence,
        )
    
    def induce(
        self,
        cases: list[str],
        pattern: str,
        evidence: list[str] = None,
    ) -> ReasoningChain:
        """归纳推理：从特殊到一般"""
        return self.reason(
            type=ReasoningType.INDUCTIVE,
            premise="案例:\n" + "\n".join(f"- {c}" for c in cases),
            inference="识别共同模式",
            conclusion=f"模式: {pattern}",
            evidence=evidence,
        )
    
    def abduce(
        self,
        observation: str,
        hypothesis: str,
        evidence: list[str] = None,
    ) -> ReasoningChain:
        """溯因推理：从结果到原因"""
        return self.reason(
            type=ReasoningType.ABDUCTIVE,
            premise=f"观察: {observation}",
            inference="推断最可能的原因",
            conclusion=f"原因: {hypothesis}",
            evidence=evidence,
        )
    
    # === 决策 ===
    
    def decide(
        self,
        options: list[str],
        reasoning: str,
        chains: list[str] = None,
    ) -> Decision:
        """做出决策"""
        decision = Decision(
            id=f"dec_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            options=options,
            reasoning=reasoning,
            reasoning_chains=chains or [],
        )
        
        # 选择置信度最高的选项（这里简化处理）
        decision.chosen_option = options[0] if options else None
        decision.confidence = 0.5
        
        self._decisions[decision.id] = decision
        self._save_decision(decision)
        
        return decision
    
    def record_outcome(
        self,
        decision_id: str,
        outcome: str,
        success: bool,
    ) -> bool:
        """记录决策结果"""
        decision = self._decisions.get(decision_id)
        if not decision:
            return False
        
        decision.outcome = outcome
        decision.success = success
        self._save_decision(decision)
        
        return True
    
    # === 查询 ===
    
    def get_recent_chains(self, limit: int = 20) -> list[ReasoningChain]:
        """获取最近推理链"""
        chains = list(self._chains.values())
        chains.sort(key=lambda c: c.timestamp, reverse=True)
        return chains[:limit]
    
    def get_recent_decisions(self, limit: int = 20) -> list[Decision]:
        """获取最近决策"""
        decisions = list(self._decisions.values())
        decisions.sort(key=lambda d: d.timestamp, reverse=True)
        return decisions[:limit]
    
    def get_decision_accuracy(self) -> float:
        """计算决策准确率"""
        decided = [d for d in self._decisions.values() if d.success is not None]
        if not decided:
            return 0.0
        return sum(1 for d in decided if d.success) / len(decided)
    
    # === 摘要 ===
    
    def get_summary(self) -> dict:
        """获取推理层摘要"""
        type_counts = {}
        for rt in ReasoningType:
            type_counts[rt.value] = len([c for c in self._chains.values() if c.type == rt])
        
        return {
            "total_chains": len(self._chains),
            "type_distribution": type_counts,
            "total_decisions": len(self._decisions),
            "decision_accuracy": round(self.get_decision_accuracy(), 2),
        }


# 全局单例
_reasoning: Optional[ReasoningLayer] = None

def get_reasoning() -> ReasoningLayer:
    global _reasoning
    if _reasoning is None:
        _reasoning = ReasoningLayer()
    return _reasoning
