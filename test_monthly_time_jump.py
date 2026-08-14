"""Isolated performance and integrity benchmark for a one-month time jump.

Run only in a disposable project copy.  The scenario exercises the same public
functions used by the game: legal funding, shop licensing, character movement,
an explicit natural-language wait command, arrival processing, and daily civic
settlement.
"""
from __future__ import annotations

import json
import resource
import time

from database import (
    DAYS_PER_MONTH,
    MINUTES_PER_DAY,
    advance_campaign_time,
    get_campaign_minutes,
    get_connection,
    get_wallet,
    initialize_database,
    open_player_shop,
    record_wallet_transaction,
    refresh_due_character_movements,
    settle_civic_time,
    validate_and_record_character_presence,
)


def economy_snapshot():
    conn = get_connection()
    try:
        profiles = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(treasury_copper), 0), COALESCE(SUM(population), 0), "
            "COALESCE(SUM(food_days), 0), COALESCE(SUM(prosperity), 0) FROM civic_profiles"
        ).fetchone()
        market = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(stock), 0), COALESCE(SUM(price_multiplier), 0) FROM local_market_goods"
        ).fetchone()
        entries = conn.execute("SELECT COUNT(*) FROM civic_ledger").fetchone()[0]
        return {
            "locations": profiles[0], "treasury_copper": profiles[1], "population": profiles[2],
            "food_days": profiles[3], "prosperity_points": profiles[4],
            "market_rows": market[0], "market_stock": market[1], "price_multiplier_total": round(market[2], 4),
            "civic_ledger_entries": entries,
        }
    finally:
        conn.close()


def schedule_benchmark_trip(current_minutes: int):
    conn = get_connection()
    try:
        traveler = conn.execute(
            "SELECT canonical_name, current_location FROM character_presence "
            "WHERE availability = 'active' ORDER BY canonical_name LIMIT 1"
        ).fetchone()
        target = conn.execute(
            "SELECT name FROM map_locations WHERE name <> ? ORDER BY name LIMIT 1", (traveler[1],)
        ).fetchone()[0]
    finally:
        conn.close()
    result = validate_and_record_character_presence(
        scene_id=None,
        turn_number=0,
        present_names=[],
        mentioned_names=[],
        presence_updates=[{
            "type": "MOVE", "name": traveler[0], "to_location": target,
            "travel_minutes": 4 * 60, "reason": "monthly-jump benchmark journey",
        }],
        current_minutes=current_minutes,
    )
    return traveler[0], target, result


def main():
    initialize_database()
    clock_before = get_campaign_minutes()
    before = economy_snapshot()

    # Fund only the disposable benchmark campaign, then obtain a licence through
    # the ordinary player-facing function so profit uses the atomic ledger.
    record_wallet_transaction(10_000, "benchmark_funding", memo="isolated monthly benchmark", idempotency_key="monthly-benchmark-funds")
    options_conn = get_connection()
    try:
        shop_type = options_conn.execute(
            "SELECT shop_type FROM player_shops LIMIT 1"
        ).fetchone()
    finally:
        options_conn.close()
    if shop_type:
        raise AssertionError("benchmark campaign must begin without a player shop")
    opening = open_player_shop("Ashvale Hold", "market_stall", turn_number=0)
    wallet_after_opening = get_wallet()["balance_copper"]

    traveler, destination, movement = schedule_benchmark_trip(clock_before)
    assert not movement["rejected"], movement

    memory_before_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started = time.perf_counter()
    jump = advance_campaign_time("انتظر شهر كامل")
    advance_seconds = time.perf_counter() - started

    settlement_started = time.perf_counter()
    arrivals = refresh_due_character_movements(jump["after_minutes"])
    civic = settle_civic_time(jump["after_minutes"])
    settlement_seconds = time.perf_counter() - settlement_started
    memory_after_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    after = economy_snapshot()
    wallet_after = get_wallet()["balance_copper"]

    expected_minutes = DAYS_PER_MONTH * MINUTES_PER_DAY
    assert jump["mode"] == "explicit_wait", jump
    assert jump["elapsed_minutes"] == expected_minutes, jump
    assert civic["settled_days"] == DAYS_PER_MONTH, civic
    arrival = next((item for item in arrivals if item["name"] == traveler and item["location"] == destination), None)
    assert arrival, arrivals
    assert arrival["arrived_at"].endswith("12:00"), arrival
    assert civic["total_shop_profit_copper"] > 0, civic
    assert wallet_after - wallet_after_opening == civic["total_shop_profit_copper"], {
        "wallet_after_opening": wallet_after_opening,
        "wallet_after": wallet_after,
        "reported_profit": civic["total_shop_profit_copper"],
    }
    assert after["civic_ledger_entries"] >= before["civic_ledger_entries"] + before["locations"] * DAYS_PER_MONTH, after

    report = {
        "scenario": "explicit full-month wait with one licensed shop and one scheduled journey",
        "time_before_minutes": clock_before,
        "time_after_minutes": jump["after_minutes"],
        "elapsed_minutes": jump["elapsed_minutes"],
        "settled_days": civic["settled_days"],
        "settled_locations": civic["settled_locations"],
        "shop_opening_cost_copper": opening["opening_cost_copper"],
        "shop_profit_copper": civic["total_shop_profit_copper"],
        "arrivals": arrivals,
        "timing_ms": {
            "clock_advance": round(advance_seconds * 1000, 3),
            "arrivals_and_civic_settlement": round(settlement_seconds * 1000, 3),
            "total": round((advance_seconds + settlement_seconds) * 1000, 3),
        },
        "peak_memory_kb": {"before": memory_before_kb, "after": memory_after_kb, "increase": max(0, memory_after_kb - memory_before_kb)},
        "economy_before": before,
        "economy_after": after,
        "wallet_delta_after_shop_opening": wallet_after - wallet_after_opening,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
