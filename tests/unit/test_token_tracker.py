"""Tests for ai_code2doc token tracker."""

from __future__ import annotations

from ai_code2doc.llm.token_tracker import TokenTracker, TokenUsage


class TestTokenTracker:
    def test_initial_state(self) -> None:
        tracker = TokenTracker()
        u = tracker.usage
        assert u.request_count == 0
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.total_tokens == 0

    def test_add_once(self) -> None:
        tracker = TokenTracker()
        tracker.add(100, 50)
        u = tracker.usage
        assert u.prompt_tokens == 100
        assert u.completion_tokens == 50
        assert u.total_tokens == 150
        assert u.request_count == 1

    def test_add_multiple(self) -> None:
        tracker = TokenTracker()
        tracker.add(100, 50)
        tracker.add(200, 100)
        u = tracker.usage
        assert u.prompt_tokens == 300
        assert u.completion_tokens == 150
        assert u.total_tokens == 450
        assert u.request_count == 2

    def test_report(self) -> None:
        tracker = TokenTracker()
        tracker.add(100, 50)
        report = tracker.report()
        assert "150" in report
        assert "100" in report
        assert "50" in report
        assert "1" in report

    def test_report_empty(self) -> None:
        tracker = TokenTracker()
        report = tracker.report()
        assert "0" in report
