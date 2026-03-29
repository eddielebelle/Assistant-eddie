"""Dice and coin tools for Eddie."""

import random


def roll_dice(count: int = 1, sides: int = 6) -> str:
    """Roll one or more dice and return the results."""
    count = max(1, min(count, 100))  # Clamp to reasonable range
    sides = max(2, min(sides, 100))

    results = [random.randint(1, sides) for _ in range(count)]
    numbers = ", ".join(str(n) for n in results)
    total = sum(results)

    if count == 1:
        return f"Rolled a {results[0]} on a {sides}-sided die."
    else:
        return f"Rolled {count}d{sides}: {numbers} (total: {total})."


def flip_coin() -> str:
    """Flip a coin and return the result."""
    result = random.choice(["heads", "tails"])
    return f"The coin landed on {result}."
