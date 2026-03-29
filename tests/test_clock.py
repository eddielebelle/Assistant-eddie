"""Tests for the clock tool."""

from eddie.tools.clock import get_current_time


def test_get_current_time_london():
    result = get_current_time("london")
    assert "London" in result
    assert "time" in result.lower() or "o'clock" in result.lower() or "past" in result.lower() or "to" in result.lower()


def test_get_current_time_default():
    result = get_current_time()
    assert "London" in result


def test_get_current_time_tokyo():
    result = get_current_time("tokyo")
    assert "Tokyo" in result


def test_get_current_time_new_york():
    result = get_current_time("new york")
    assert "New York" in result


def test_get_current_time_unknown_city():
    result = get_current_time("atlantis")
    assert "don't have" in result.lower()


def test_get_current_time_case_insensitive():
    result = get_current_time("LONDON")
    assert "London" in result
