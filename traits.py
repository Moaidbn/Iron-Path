"""
traits.py

Traits are earned, not granted. Gemini may flag behavior_changes and
may suggest trait_candidates in its state-evaluation JSON, but the
actual unlock decision is made here, in Python, against fixed
thresholds -- so a lucky prompt can't hand out a trait Gemini merely
mentioned.

Each trait definition:
    key, display_name, description, requires: {behavior_name: min_value, ...}

A trait unlocks the first time ALL of its requirements are met.
"""

TRAIT_DEFINITIONS = {
    "ruthless_tactician": {
        "display_name": "Ruthless Tactician",
        "description": "Feared more than trusted. Fearful NPCs comply faster; "
                        "honorable factions trust you less by default.",
        "requires": {"cruelty": 60, "intimidation": 60},
    },
    "iron_negotiator": {
        "display_name": "Iron Negotiator",
        "description": "A reputation for making deals stick. Diplomatic outcomes "
                        "land more easily; successful negotiations build trust faster.",
        "requires": {"diplomacy": 60, "honesty": 40},
    },
    "lord_of_his_men": {
        "display_name": "Lord of His Men",
        "description": "Retainers and soldiers know you won't spend them cheaply. "
                        "Loyalty gains from protecting your people are amplified.",
        "requires": {"loyalty": 55, "generosity": 45},
    },
    "shadow_broker": {
        "display_name": "Shadow Broker",
        "description": "Comfortable in the space between truth and lies. "
                        "Deception and information-gathering actions are more effective.",
        "requires": {"deception": 60, "manipulation": 55},
    },
    "the_pragmatist": {
        "display_name": "The Pragmatist",
        "description": "Chooses what works over what's satisfying. "
                        "Reduced narrative penalty for morally ambiguous choices.",
        "requires": {"pragmatism": 65, "risk_taking": 40},
    },
}


def evaluate_trait_unlocks(behavior_scores, already_unlocked_keys):
    """
    Returns a list of trait dicts newly qualified for unlock this turn.
    Does not mutate the database -- state_manager.py calls
    database.unlock_trait() for anything this returns.
    """

    newly_unlocked = []

    for key, definition in TRAIT_DEFINITIONS.items():

        if key in already_unlocked_keys:
            continue

        requirements = definition["requires"]

        meets_all = all(
            behavior_scores.get(stat, 0) >= threshold
            for stat, threshold in requirements.items()
        )

        if meets_all:
            newly_unlocked.append({
                "key": key,
                "display_name": definition["display_name"],
                "description": definition["description"],
            })

    return newly_unlocked
