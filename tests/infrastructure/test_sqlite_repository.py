"""Tests for SQLite repository."""

import pytest
from chimera.infrastructure.repositories.sqlite_repository import SQLiteRepository


@pytest.fixture
def repo(tmp_path):
    """Create a fresh SQLite repository for each test."""
    db_path = str(tmp_path / "test.db")
    r = SQLiteRepository(db_path)
    r.connect()
    yield r
    r.close()


class TestDriftEvents:
    def test_record_drift(self, repo):
        event_id = repo.record_drift("node-1", "HIGH", "aaa", "bbb", "test drift")
        assert event_id >= 1

    def test_get_drift_history(self, repo):
        repo.record_drift("node-1", "HIGH")
        repo.record_drift("node-2", "LOW")
        history = repo.get_drift_history()
        assert len(history) == 2

    def test_get_drift_history_by_node(self, repo):
        repo.record_drift("node-1", "HIGH")
        repo.record_drift("node-2", "LOW")
        history = repo.get_drift_history(node_id="node-1")
        assert len(history) == 1
        assert history[0]["node_id"] == "node-1"

    def test_resolve_drift(self, repo):
        event_id = repo.record_drift("node-1", "HIGH")
        repo.resolve_drift(event_id, 120.5)
        history = repo.get_drift_history()
        assert history[0]["resolved_at"] is not None
        assert history[0]["resolution_time_seconds"] == 120.5

    def test_get_unresolved_drifts(self, repo):
        repo.record_drift("node-1", "HIGH")
        event_id = repo.record_drift("node-2", "LOW")
        repo.resolve_drift(event_id, 60.0)
        unresolved = repo.get_unresolved_drifts()
        assert len(unresolved) == 1
        assert unresolved[0]["node_id"] == "node-1"

    def test_drift_count(self, repo):
        repo.record_drift("node-1", "HIGH")
        repo.record_drift("node-1", "LOW")
        repo.record_drift("node-2", "MEDIUM")
        assert repo.get_drift_count() == 3
        assert repo.get_drift_count("node-1") == 2

    def test_mean_resolution_time(self, repo):
        e1 = repo.record_drift("node-1", "HIGH")
        repo.resolve_drift(e1, 60.0)
        e2 = repo.record_drift("node-1", "HIGH")
        repo.resolve_drift(e2, 120.0)
        assert repo.get_mean_resolution_time() == 90.0

    def test_mean_resolution_time_none(self, repo):
        repo.record_drift("node-1", "HIGH")  # unresolved
        assert repo.get_mean_resolution_time() is None


class TestPlaybookRuns:
    def test_record_playbook_run(self, repo):
        run_id = repo.record_playbook_run("pb-1", "rollback", "node-1", "running")
        assert run_id >= 1

    def test_complete_playbook_run(self, repo):
        run_id = repo.record_playbook_run("pb-1", "rollback", "node-1", "running")
        repo.complete_playbook_run(run_id, "success")
        runs = repo.get_playbook_runs()
        assert runs[0]["status"] == "success"
        assert runs[0]["completed_at"] is not None

    def test_get_playbook_runs_by_node(self, repo):
        repo.record_playbook_run("pb-1", "rollback", "node-1", "success")
        repo.record_playbook_run("pb-2", "rebuild", "node-2", "success")
        runs = repo.get_playbook_runs(node_id="node-1")
        assert len(runs) == 1


class TestSLOViolations:
    def test_record_violation(self, repo):
        vid = repo.record_slo_violation("uptime", 99.9, 98.5, 24, "outage")
        assert vid >= 1

    def test_get_violations(self, repo):
        repo.record_slo_violation("uptime", 99.9, 98.5, 24)
        repo.record_slo_violation("latency", 99.0, 97.0, 1)
        violations = repo.get_slo_violations()
        assert len(violations) == 2


class TestHealingActions:
    def test_record_healing(self, repo):
        aid = repo.record_healing_action(
            "node-1", "rollback", "nix-env --rollback", True, 5.0, "ok"
        )
        assert aid >= 1

    def test_get_healing_history(self, repo):
        repo.record_healing_action("node-1", "rollback", "cmd", True)
        repo.record_healing_action("node-2", "rebuild", "cmd", False)
        history = repo.get_healing_history()
        assert len(history) == 2

    def test_get_healing_by_node(self, repo):
        repo.record_healing_action("node-1", "rollback", "cmd", True)
        repo.record_healing_action("node-2", "rebuild", "cmd", False)
        history = repo.get_healing_history(node_id="node-1")
        assert len(history) == 1
        assert history[0]["success"] == 1


class TestLifecycle:
    def test_connect_close(self, tmp_path):
        repo = SQLiteRepository(str(tmp_path / "test.db"))
        repo.connect()
        repo.record_drift("node-1", "HIGH")
        repo.close()

        # Reopen and verify data persisted
        repo2 = SQLiteRepository(str(tmp_path / "test.db"))
        repo2.connect()
        assert repo2.get_drift_count() == 1
        repo2.close()
