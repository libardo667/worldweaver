"""Tests for game API cache cleanup functionality."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from src.api.game import cleanup_old_sessions
from src.services.session_service import (
    _state_managers,
    _spatial_navigators,
    get_spatial_navigator,
    get_state_manager,
)


class TestCacheCleanupLogic:

    def setup_method(self):
        _state_managers.clear()
        _spatial_navigators.clear()

    def test_cleanup_old_sessions_precise_cache_removal(self):
        mock_db = Mock()
        mock_db.execute.side_effect = [
            Mock(fetchall=Mock(return_value=[("s1",), ("s2",), ("s3",)])),
            Mock(rowcount=3),
        ]
        _state_managers.update({"s1": Mock(), "s2": Mock(), "s3": Mock(), "s4": Mock(), "s5": Mock()})
        result = cleanup_old_sessions(db=mock_db)
        assert result["sessions_removed"] == 3 and result["cache_entries_removed"] == 3
        assert "s4" in _state_managers and "s1" not in _state_managers

    def test_cleanup_with_no_sessions_to_delete(self):
        mock_db = Mock()
        mock_db.execute.side_effect = [Mock(fetchall=Mock(return_value=[])), Mock(rowcount=0)]
        _state_managers["active"] = Mock()
        result = cleanup_old_sessions(db=mock_db)
        assert result["sessions_removed"] == 0 and len(_state_managers) == 1

    def test_cleanup_cache_entries_not_in_database(self):
        mock_db = Mock()
        mock_db.execute.side_effect = [Mock(fetchall=Mock(return_value=[("s1",)])), Mock(rowcount=1)]
        _state_managers.update({"s1": Mock(), "orphan": Mock()})
        cleanup_old_sessions(db=mock_db)
        assert "s1" not in _state_managers and "orphan" in _state_managers

    def test_cleanup_handles_database_error(self):
        from fastapi import HTTPException

        mock_db = Mock()
        mock_db.execute.side_effect = Exception("DB fail")
        with pytest.raises(HTTPException) as exc_info:
            cleanup_old_sessions(db=mock_db)
        assert exc_info.value.status_code == 500
        mock_db.rollback.assert_called_once()

    @patch("src.api.game.state.logging")
    def test_cleanup_logging_behavior(self, mock_logging):
        mock_db = Mock()
        mock_db.execute.side_effect = [Mock(fetchall=Mock(return_value=[("s1",), ("s2",)])), Mock(rowcount=2)]
        _state_managers.update({"s1": Mock(), "s2": Mock()})
        cleanup_old_sessions(db=mock_db)
        mock_logging.info.assert_called_once()

    @patch("src.api.game.state.logging")
    def test_cleanup_error_logging(self, mock_logging):
        from fastapi import HTTPException

        mock_db = Mock()
        mock_db.execute.side_effect = Exception("err")
        with pytest.raises(HTTPException):
            cleanup_old_sessions(db=mock_db)
        mock_logging.error.assert_called_once()

    def test_cleanup_cutoff_time_calculation(self):
        mock_db = Mock()
        captured = []

        def capture(*args, **kw):
            if len(args) > 1:
                captured.append(args[1])
            return Mock(fetchall=Mock(return_value=[]))

        mock_db.execute.side_effect = capture
        before = datetime.now(timezone.utc)
        cleanup_old_sessions(db=mock_db)
        after = datetime.now(timezone.utc)
        cutoff = captured[0]["cutoff"]
        lower = before - timedelta(hours=24)
        upper = after - timedelta(hours=24)
        if getattr(cutoff, "tzinfo", None) is None:
            lower = lower.replace(tzinfo=None)
            upper = upper.replace(tzinfo=None)
        assert lower <= cutoff <= upper

    def test_cleanup_endpoint_integration(self, seeded_client):
        data = seeded_client.post("/api/cleanup-sessions").json()
        assert "success" in data and "sessions_removed" in data

    def test_state_manager_cache_respects_max_size(self, db_session):
        original_max = _state_managers.max_size
        try:
            _state_managers.max_size = 5
            for i in range(20):
                get_state_manager(f"sess-{i}", db_session)
            assert len(_state_managers) <= 5
        finally:
            _state_managers.max_size = original_max
            _state_managers.clear()

    @patch("src.services.session_service.SpatialNavigator")
    def test_spatial_navigator_is_created_per_request_session(self, mock_navigator_cls):
        db_a = Mock()
        db_b = Mock()
        first = Mock()
        second = Mock()
        mock_navigator_cls.side_effect = [first, second]

        n1 = get_spatial_navigator(db_a)
        n2 = get_spatial_navigator(db_b)

        assert n1 is first
        assert n2 is second
        assert n1 is not n2
        assert mock_navigator_cls.call_count == 2
