"""Shared test fixtures for Eddie."""

import pytest


@pytest.fixture
def sample_keywords():
    """Sample keyword dict as would come from the LLM."""
    return {
        "user_input": "What time is it in Tokyo?",
        "city": "tokyo",
    }
