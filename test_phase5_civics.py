"""Non-destructive regression checks for player shops, civic data, and campaign time.

The test reads the active campaign only.  It does not open a shop, settle a city,
or advance campaign time, so no test data persists in ``data/story.db``.
"""
from database import (
    get_civic_profiles,
    get_player_shops,
    get_shop_options,
    get_world_clock,
    initialize_database,
)


def main():
    initialize_database()
    profiles = get_civic_profiles("ar")
    assert len(profiles) >= 9, f"expected at least 9 civic profiles, received {len(profiles)}"
    required = {
        "households", "workforce", "food_days", "treasury_copper",
        "maintenance_copper", "debt_copper", "last_settled_turn",
    }
    assert required.issubset(profiles[0]), "operational civic metrics are missing"
    assert all(profile["households"] > 0 and profile["workforce"] > 0 for profile in profiles)

    options = get_shop_options("Ashvale Hold", "en")
    assert options and options["options"], "Ashvale Hold should offer a shop licence"
    assert all(item["opening_cost_copper"] > 0 for item in options["options"])
    assert all(item["estimated_turn_profit_copper"] > 0 for item in options["options"])

    clock = get_world_clock()
    assert "absolute_minutes" in clock and "display" in clock, "continuous campaign clock is missing"
    assert clock["absolute_minutes"] >= 0, "campaign time cannot be negative"

    shops = get_player_shops("ar")
    print(
        f"phase5 civic checks passed: {len(profiles)} profiles, "
        f"{len(options['options'])} Ashvale licences, {len(shops)} existing player shops, "
        f"campaign time {clock['display']} (read-only)."
    )


if __name__ == "__main__":
    main()
