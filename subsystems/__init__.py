"""Hermes Subsystems — 13 living-system modules (8 capabilities)."""
from .self_model import SelfModel
from .identity_evolution import IdentityEvolution
from .governance import Governance
from .reflective_evolution import ReflectiveEvolution
from .science_loop import ScienceLoop
from .orchestrator import Orchestrator
from .fitness_builder import FitnessBuilder
from .metacognitive import Metacognitive
from .memory_tiering import MemoryTiering, get_tiering, add_entry, record_access, recall
from .living_core import LivingCore, SemanticRecall, WechatUrlDetect, PostLLMUpdate, OrchestratorHint, ScienceLoopHint
from .perception import PerceptionLayer
from .reasoning import ReasoningLayer
from .knowledge import KnowledgeLayer
from .adaptation import AdaptationLayer
from .reflection import ReflectionLayer
from .evolution import EvolutionLayer
from .integration import IntegrationLayer

__all__ = [
    # Core 9
    "SelfModel",
    "IdentityEvolution",
    "Governance",
    "ReflectiveEvolution",
    "ScienceLoop",
    "Orchestrator",
    "FitnessBuilder",
    "Metacognitive",
    "MemoryTiering",
    # Living core
    "LivingCore",
    "SemanticRecall",
    "WechatUrlDetect",
    "PostLLMUpdate",
    "OrchestratorHint",
    "ScienceLoopHint",
    # 8 capabilities (13 total subsystems)
    "PerceptionLayer",
    "ReasoningLayer",
    "KnowledgeLayer",
    "AdaptationLayer",
    "ReflectionLayer",
    "EvolutionLayer",
    "IntegrationLayer",
]
