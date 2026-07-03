"""
Tests for _ThrottleGate chronic-failure detection.

All tests run offline -- no network, no SQLite. They exercise the state
machine logic of chronic detection, backoff ceiling escalation, and reset.
"""
import time
from unittest.mock import patch

import pytest

# _ThrottleGate is module-private; import via the module.
from extraction.met.image_enricher import _ThrottleGate


class TestChronicDetection:
    """
    Chronic-failure detection triggers after sustained failures.
    """

    def test_not_chronic_until_window_full(self):
        """
        Chronic flag should not activate before the deque fills (50 entries).
        """
        gate = _ThrottleGate()
        # 49 failures should NOT trigger chronic (window not full).
        for _ in range(49):
            gate.signal_throttle(None)
        assert gate.chronic is False

    def test_chronic_triggers_at_threshold(self):
        """
        50 consecutive failures (100% > 80%) should trigger chronic.
        """
        gate = _ThrottleGate()
        for _ in range(50):
            gate.signal_throttle(None)
        assert gate.chronic is True

    def test_chronic_not_triggered_below_80_percent(self):
        """
        If fewer than 80% of the window are failures, chronic stays False.
        """
        gate = _ThrottleGate()
        # Alternate: 10 successes then 40 failures = 40/50 = 80% exactly.
        # 80% is NOT > 0.8, so should NOT trigger.
        for _ in range(10):
            gate.note_success()
        for _ in range(40):
            gate.signal_throttle(None)
        assert gate.chronic is False

    def test_chronic_triggers_at_81_percent(self):
        """
        Just above threshold: 41/50 failures should trigger chronic.
        """
        gate = _ThrottleGate()
        # 9 successes + 41 failures = 41/50 = 0.82 > 0.8
        for _ in range(9):
            gate.note_success()
        for _ in range(41):
            gate.signal_throttle(None)
        assert gate.chronic is True


class TestBackoffCeilingEscalation:
    """
    Backoff ceiling doubles progressively up to the hard cap (300s).
    """

    def test_first_escalation_doubles_ceiling(self):
        """
        First chronic trigger should double max_backoff from 60 to 120.
        """
        gate = _ThrottleGate(max_backoff=60.0)
        for _ in range(50):
            gate.signal_throttle(None)
        assert gate._max == 120.0

    def test_progressive_escalation(self):
        """
        Continued failures should keep doubling: 60 -> 120 -> 240 -> 300 (cap).
        """
        gate = _ThrottleGate(max_backoff=60.0)
        # First trigger: 60 -> 120
        for _ in range(50):
            gate.signal_throttle(None)
        assert gate._max == 120.0
        assert gate.chronic is True

        # One more failure (window still full and >80% failures) -> 120 -> 240
        gate.signal_throttle(None)
        assert gate._max == 240.0

        # Another -> 240 -> 300 (capped at 300)
        gate.signal_throttle(None)
        assert gate._max == 300.0

        # Should not exceed cap.
        gate.signal_throttle(None)
        assert gate._max == 300.0

    def test_ceiling_hard_cap(self):
        """
        Ceiling never exceeds _max_ceiling (300s).
        """
        gate = _ThrottleGate(max_backoff=60.0)
        # Push through many failures to saturate escalation.
        for _ in range(100):
            gate.signal_throttle(None)
        assert gate._max <= 300.0


class TestChronicReset:
    """
    A single success after chronic episode resets the state.
    """

    def test_success_clears_chronic_flag(self):
        """
        note_success() after chronic should reset the flag.
        """
        gate = _ThrottleGate(max_backoff=60.0)
        # Trigger chronic.
        for _ in range(50):
            gate.signal_throttle(None)
        assert gate.chronic is True

        # One success should clear it.
        gate.note_success()
        assert gate.chronic is False

    def test_success_resets_ceiling(self):
        """
        Backoff ceiling should return to its initial value after reset.
        """
        gate = _ThrottleGate(max_backoff=60.0)
        # Trigger chronic + escalate.
        for _ in range(52):
            gate.signal_throttle(None)
        assert gate._max > 60.0

        gate.note_success()
        assert gate._max == 60.0

    def test_success_clears_history(self):
        """
        History deque should be empty after chronic reset.
        """
        gate = _ThrottleGate(max_backoff=60.0)
        for _ in range(50):
            gate.signal_throttle(None)
        assert gate.chronic is True

        gate.note_success()
        assert len(gate._history) == 0

    def test_chronic_can_retrigger_after_reset(self):
        """
        After a reset, a new streak of failures should re-trigger chronic.
        """
        gate = _ThrottleGate(max_backoff=60.0)
        # First episode.
        for _ in range(50):
            gate.signal_throttle(None)
        assert gate.chronic is True
        gate.note_success()
        assert gate.chronic is False
        assert gate._max == 60.0

        # Second episode.
        for _ in range(50):
            gate.signal_throttle(None)
        assert gate.chronic is True
        assert gate._max == 120.0


class TestWaitIfPaused:
    """
    wait_if_paused() blocks for the computed backoff duration.
    """

    @patch("extraction.met.image_enricher.time.sleep")
    def test_no_sleep_when_not_paused(self, mock_sleep):
        """
        Should not sleep if backoff_until is in the past.
        """
        gate = _ThrottleGate()
        gate.wait_if_paused()
        mock_sleep.assert_not_called()

    @patch("extraction.met.image_enricher.time.sleep")
    @patch("extraction.met.image_enricher.time.monotonic")
    def test_sleeps_for_remaining_backoff(self, mock_monotonic, mock_sleep):
        """
        Should sleep for exactly the remaining backoff duration.
        """
        gate = _ThrottleGate()
        # Simulate: backoff_until = 100.0, current time = 98.0 -> sleep 2s.
        gate._backoff_until = 100.0
        mock_monotonic.return_value = 98.0
        gate.wait_if_paused()
        mock_sleep.assert_called_once_with(2.0)
