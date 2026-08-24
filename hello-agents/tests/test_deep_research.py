import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "14-deep-research"
sys.path.insert(0, str(PROJECT))

from deep_research.audit import audit_citations
from deep_research.evidence import build_claims, extract_evidence
from deep_research.engine import ResearchEngine
from deep_research.retriever import FixtureRetriever, dedupe_sources
from deep_research.schemas import Citation, ResearchQuery
from deep_research.storage import CheckpointStore


def query(**overrides):
    payload = {
        "query_id": "research-001",
        "question": "Agent 如何保存状态并支持离线回归？",
        "max_rounds": 2,
        "max_sources": 5,
        "max_tokens": 2000,
        "budget_usd": 0.10,
    }
    payload.update(overrides)
    return ResearchQuery(**payload)


class DeepResearchTests(unittest.TestCase):
    def test_sources_are_provenanced_and_duplicates_are_removed(self):
        retriever = FixtureRetriever()
        sources = retriever.search(query(), round_index=1)
        self.assertTrue(sources)
        self.assertTrue(sources[0].url)
        self.assertTrue(sources[0].published_at)
        self.assertEqual(len(dedupe_sources([*sources, *sources])), len(sources))

    def test_evidence_keeps_source_provenance_and_claim_links(self):
        sources = FixtureRetriever().search(query(), round_index=1)
        evidence = extract_evidence(sources)
        claims = build_claims(evidence)
        self.assertTrue(evidence)
        self.assertTrue(all(item.source_id for item in evidence))
        self.assertTrue(all(item.evidence_ids for item in claims))

    def test_engine_completes_two_round_research_with_citations(self):
        state = ResearchEngine(FixtureRetriever()).run(query())
        self.assertEqual("COMPLETED", state.status)
        self.assertEqual(2, state.round)
        self.assertTrue(state.sources)
        self.assertTrue(state.evidence)
        self.assertTrue(state.claims)
        self.assertTrue(state.citations)
        self.assertTrue(audit_citations(state)["passed"])

    def test_conflicting_sources_mark_claim_uncertainty(self):
        state = ResearchEngine(FixtureRetriever(conflict=True)).run(query())
        self.assertTrue(any(claim.uncertain for claim in state.claims))
        self.assertIn("conflicting_evidence", state.warnings)

    def test_retrieval_failure_degrades_without_losing_previous_round(self):
        state = ResearchEngine(FixtureRetriever(fail_on_round=2)).run(query())
        self.assertEqual("COMPLETED", state.status)
        self.assertEqual(1, state.round)
        self.assertIn("retrieval_failed_round_2", state.warnings)
        self.assertTrue(state.sources)

    def test_source_budget_stops_research(self):
        state = ResearchEngine(FixtureRetriever()).run(query(max_sources=1))
        self.assertLessEqual(len(state.sources), 1)
        self.assertIn("source_budget_exhausted", state.warnings)

    def test_checkpoint_interrupt_and_resume_does_not_repeat_round_one(self):
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "checkpoint.json"
            interrupted = ResearchEngine(FixtureRetriever()).run(
                query(), interrupt_after_round=1, checkpoint_path=checkpoint
            )
            self.assertEqual("INTERRUPTED", interrupted.status)
            resumed = ResearchEngine(FixtureRetriever()).resume(checkpoint)
        self.assertEqual("COMPLETED", resumed.status)
        self.assertEqual(2, resumed.round)
        self.assertEqual(len(resumed.sources), len({item.source_id for item in resumed.sources}))

    def test_audit_rejects_dangling_or_mismatched_citation(self):
        state = ResearchEngine(FixtureRetriever()).run(query())
        bad = replace(
            state,
            citations=(Citation("BAD", "missing-claim", "missing-evidence", "wrong-source"),),
        )
        audit = audit_citations(bad)
        self.assertFalse(audit["passed"])
        self.assertTrue(audit["issues"])

    def test_checkpoint_store_round_trips_state(self):
        state = ResearchEngine(FixtureRetriever()).run(query())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            CheckpointStore(path).save(state)
            loaded = CheckpointStore(path).load()
        self.assertEqual(state.query, loaded.query)
        self.assertEqual(state.sources, loaded.sources)
        self.assertEqual(state.status, loaded.status)

    def test_cli_supports_conflict_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            conflict = subprocess.run(
                [sys.executable, str(PROJECT / "main.py"), "--demo", "--json", "--conflict"],
                capture_output=True,
                text=True,
                check=True,
            )
            conflict_report = json.loads(conflict.stdout)
            self.assertIn("conflicting_evidence", conflict_report["state"]["warnings"])

            subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "main.py"),
                    "--demo",
                    "--interrupt-after-round",
                    "1",
                    "--output-dir",
                    directory,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            checkpoint = Path(directory) / "checkpoint.json"
            resumed = subprocess.run(
                [sys.executable, str(PROJECT / "main.py"), "--resume", str(checkpoint), "--json"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual("COMPLETED", json.loads(resumed.stdout)["state"]["status"])


if __name__ == "__main__":
    unittest.main()
