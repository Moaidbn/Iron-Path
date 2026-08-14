"""
mastery.py

Handles the specialization trees under each of the three core
masteries (Weapons / Trade / Conversation). Specializations unlock
once the parent mastery reaches a threshold level -- deterministically,
in Python, not by Gemini's say-so.

Phase 1 note: specializations are currently binary (locked/unlocked)
rather than independently leveled. Give them their own XP/level track
in a later phase if you want deeper sub-progression.
"""

SPECIALIZATION_UNLOCK_LEVEL = 5


def evaluate_specialization_unlocks(character_stats, current_specializations, turn_number):
    """
    character_stats: list from database.get_character_stats()
    current_specializations: list from database.get_mastery_specializations()

    Returns a list of (mastery_name, specialization) tuples that just
    became eligible to unlock (parent mastery hit the threshold level
    and the specialization wasn't already unlocked).
    """

    level_by_mastery = {s["name"]: s["level"] for s in character_stats}

    newly_eligible = []

    for spec in current_specializations:
        if spec["unlocked"]:
            continue

        mastery_level = level_by_mastery.get(spec["mastery_name"], 0)

        if mastery_level >= SPECIALIZATION_UNLOCK_LEVEL:
            newly_eligible.append((spec["mastery_name"], spec["specialization"]))

    return newly_eligible
