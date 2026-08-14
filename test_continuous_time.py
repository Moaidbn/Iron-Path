"""Regression checks for continuous in-world campaign time.

Run this module only in a disposable project copy.  It advances the campaign clock
and deliberately crosses a world-day boundary to verify time-based settlement.
"""
from database import (
    MINUTES_PER_DAY,
    advance_campaign_time,
    get_campaign_minutes,
    get_world_clock,
    initialize_database,
    settle_civic_time,
)


def main():
    initialize_database()
    initial = get_campaign_minutes()

    natural = advance_campaign_time("أتفقد خريطة المعسكر")
    assert natural["mode"] == "natural_action", natural
    assert 1 <= natural["elapsed_minutes"] <= 12 * 60, natural
    assert natural["after_minutes"] == initial + natural["elapsed_minutes"], natural

    explicit_wait = advance_campaign_time("انتظر 3 ساعات")
    assert explicit_wait["mode"] == "explicit_wait", explicit_wait
    assert explicit_wait["elapsed_minutes"] == 180, explicit_wait

    before_dawn = get_campaign_minutes()
    dawn_jump = advance_campaign_time("انتظر حتى الفجر")
    assert dawn_jump["mode"] == "explicit_jump", dawn_jump
    assert dawn_jump["elapsed_minutes"] > 0, dawn_jump
    assert dawn_jump["after_minutes"] > before_dawn, dawn_jump

    # Only an explicit request crosses a full day here.  City settlement is
    # keyed to completed world days, never to the number of scenes saved.
    before_day = get_campaign_minutes()
    day_wait = advance_campaign_time("انتظر 1 يوم")
    assert day_wait["mode"] == "explicit_wait" and day_wait["elapsed_minutes"] == MINUTES_PER_DAY, day_wait
    civic = settle_civic_time(day_wait["after_minutes"])
    assert civic["settled_days"] >= 1, civic
    assert get_campaign_minutes() == before_day + MINUTES_PER_DAY

    clock = get_world_clock()
    assert clock["absolute_minutes"] == get_campaign_minutes(), clock
    assert clock["display"] and ":" in clock["display"], clock
    print("Continuous-time regression checks passed:", clock["display"])


if __name__ == "__main__":
    main()
