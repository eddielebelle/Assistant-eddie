"""Tests for the timer tool."""

from eddie.tools.timer import TimerManager


def test_parse_duration_minutes():
    assert TimerManager.parse_duration("5 minutes") == 300


def test_parse_duration_seconds():
    assert TimerManager.parse_duration("30 seconds") == 30


def test_parse_duration_hours():
    assert TimerManager.parse_duration("2 hours") == 7200


def test_parse_duration_word_numbers():
    assert TimerManager.parse_duration("ten minutes") == 600


def test_parse_duration_bare_number():
    result = TimerManager.parse_duration("60")
    assert result == 60


def test_parse_duration_invalid():
    result = TimerManager.parse_duration("some nonsense")
    assert result is None


def test_set_and_check_timer():
    mgr = TimerManager()
    result = mgr.set_timer("5 minutes", label="test")
    assert "set for" in result

    check = mgr.check_timer("test")
    assert "remaining" in check

    # Clean up
    mgr.cancel_timer("test")


def test_cancel_timer():
    mgr = TimerManager()
    mgr.set_timer("10 minutes", label="cancel-me")
    result = mgr.cancel_timer("cancel-me")
    assert "cancelled" in result


def test_cancel_nonexistent():
    mgr = TimerManager()
    result = mgr.cancel_timer("nope")
    assert "not found" in result.lower() or "No" in result


def test_check_no_timers():
    mgr = TimerManager()
    result = mgr.check_timer()
    assert "No active" in result
