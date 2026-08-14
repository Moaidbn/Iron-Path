"""
military.py

Deterministic combat resolution. Per the architecture principle in
the review: Gemini is never trusted to pick troop losses or a winner
directly -- it can only signal that a battle happened (attacker,
defender, terrain/weather context) via state_evaluator's
battle_trigger. This module does the actual arithmetic, so the same
inputs always produce a consistent, explainable result, and the
database stays the authoritative record even 100+ turns later.

This is intentionally a simple model, not a full wargame simulator:
effective power scales with troop count, morale, and organization;
terrain/weather apply a flat multiplier; the loser takes
disproportionately heavier casualties. Good enough to make numbers
consistent and give the story real stakes, without pretending to be
a tactical combat engine.
"""

import random

TERRAIN_MODIFIERS = {
    "forest": {"attacker": 0.9, "defender": 1.1},
    "hills": {"attacker": 0.9, "defender": 1.15},
    "river_crossing": {"attacker": 0.75, "defender": 1.2},
    "open_field": {"attacker": 1.0, "defender": 1.0},
    "fortified": {"attacker": 0.7, "defender": 1.3},
    "urban": {"attacker": 0.85, "defender": 1.1},
}

WEATHER_MODIFIERS = {
    "clear": 1.0,
    "rain": 0.95,
    "storm": 0.85,
    "snow": 0.85,
    "fog": 0.9,
}


def _effective_power(troops, morale, organization):
    quality = ((morale or 50) + (organization or 50)) / 200  # 0.0 - 1.0
    return troops * (0.5 + quality)


def resolve_battle(attacker, defender, terrain="open_field", weather="clear", rng=None):
    """
    attacker / defender: dicts with at least total_troops, morale,
    organization (as stored in the armies table).

    Returns a result dict with exact before/after troop counts,
    casualties for both sides, and a victor -- nothing here is left
    for the AI to invent.
    """
    rng = rng or random

    terrain_mod = TERRAIN_MODIFIERS.get(terrain, TERRAIN_MODIFIERS["open_field"])
    weather_mod = WEATHER_MODIFIERS.get(weather, 1.0)

    attacker_troops = max(0, int(attacker.get("total_troops", 0)))
    defender_troops = max(0, int(defender.get("total_troops", 0)))

    attacker_power = _effective_power(
        attacker_troops, attacker.get("morale"), attacker.get("organization")
    ) * terrain_mod["attacker"] * weather_mod

    defender_power = _effective_power(
        defender_troops, defender.get("morale"), defender.get("organization")
    ) * terrain_mod["defender"] * weather_mod

    total_power = attacker_power + defender_power
    if total_power <= 0:
        # No forces to fight with -- nothing happens, mechanically.
        return {
            "attacker_start": attacker_troops, "defender_start": defender_troops,
            "attacker_end": attacker_troops, "defender_end": defender_troops,
            "attacker_casualties": 0, "defender_casualties": 0,
            "victor": "none", "attacker_power": 0, "defender_power": 0,
        }

    attacker_win_chance = attacker_power / total_power
    roll = rng.random()
    victor = "attacker" if roll < attacker_win_chance else "defender"

    # Winner's casualty rate is lower, loser's is higher. Some
    # randomness keeps outcomes from feeling like a lookup table.
    if victor == "attacker":
        attacker_rate = rng.uniform(0.04, 0.14)
        defender_rate = rng.uniform(0.20, 0.45)
    else:
        attacker_rate = rng.uniform(0.20, 0.45)
        defender_rate = rng.uniform(0.04, 0.14)

    # A heavily outmatched side takes proportionally worse losses.
    if total_power > 0:
        power_ratio = attacker_power / total_power
        if power_ratio > 0.7:
            defender_rate = min(0.6, defender_rate * 1.4)
        elif power_ratio < 0.3:
            attacker_rate = min(0.6, attacker_rate * 1.4)

    attacker_casualties = min(attacker_troops, round(attacker_troops * attacker_rate))
    defender_casualties = min(defender_troops, round(defender_troops * defender_rate))

    return {
        "attacker_start": attacker_troops,
        "defender_start": defender_troops,
        "attacker_end": attacker_troops - attacker_casualties,
        "defender_end": defender_troops - defender_casualties,
        "attacker_casualties": attacker_casualties,
        "defender_casualties": defender_casualties,
        "victor": victor,
        "attacker_power": round(attacker_power, 1),
        "defender_power": round(defender_power, 1),
    }


def generate_loot(defender_casualties, defender_troops_start, rng=None):
    """
    Simple, deterministic loot generation scaled to how many of the
    defeated side's troops were lost -- more casualties (more bodies
    and abandoned gear) means more loot, within sane bounds.
    """
    rng = rng or random

    if defender_troops_start <= 0:
        return {"gold": 0, "items": []}

    loss_ratio = defender_casualties / defender_troops_start
    gold = round(defender_casualties * rng.uniform(2, 6))

    items = []
    if defender_casualties >= 5:
        items.append({
            "name": "Salvaged weapons", "category": "weapon",
            "quantity": max(1, defender_casualties // 3),
            "description": "Blades and spears recovered from the field.",
        })
    if defender_casualties >= 10:
        items.append({
            "name": "Salvaged armor", "category": "armor",
            "quantity": max(1, defender_casualties // 5),
            "description": "Damaged but serviceable armor pieces.",
        })
    if loss_ratio > 0.3 and rng.random() < 0.4:
        items.append({
            "name": "Supply wagon", "category": "misc",
            "quantity": 1,
            "description": "An abandoned supply wagon, contents intact.",
        })

    return {"gold": gold, "items": items}
