"""可恢复、可审计的 DeepResearch 离线引擎。"""

from .audit import audit_citations
from .engine import ResearchEngine
from .evidence import build_claims, extract_evidence
from .experiment import run_demo
from .retriever import FixtureRetriever, RetrievalError, dedupe_sources
from .schemas import Claim, Citation, Evidence, ResearchQuery, ResearchState, Source
from .storage import ArtifactStore, CheckpointStore

__all__ = [
    "ArtifactStore",
    "CheckpointStore",
    "Claim",
    "Citation",
    "Evidence",
    "FixtureRetriever",
    "ResearchEngine",
    "ResearchQuery",
    "ResearchState",
    "RetrievalError",
    "Source",
    "audit_citations",
    "build_claims",
    "dedupe_sources",
    "extract_evidence",
    "run_demo",
]
