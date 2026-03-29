"""Tests for the dice and coin tools."""

from eddie.tools.dice import flip_coin, roll_dice


def test_roll_single_die():
    result = roll_dice()
    assert "Rolled a" in result
    assert "6-sided" in result


def test_roll_multiple_dice():
    result = roll_dice(count=3, sides=6)
    assert "3d6" in result
    assert "total:" in result


def test_roll_custom_sides():
    result = roll_dice(count=1, sides=20)
    assert "20-sided" in result


def test_roll_clamped_count():
    # Should clamp to 100 max
    result = roll_dice(count=200, sides=6)
    assert "100d6" in result


def test_flip_coin():
    result = flip_coin()
    assert "heads" in result or "tails" in result


def test_flip_coin_randomness():
    # Run many flips, should get both results
    results = {flip_coin() for _ in range(100)}
    assert len(results) == 2
