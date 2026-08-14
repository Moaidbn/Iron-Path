"""Isolated scalability check for a twelve-month explicit time jump."""
from __future__ import annotations

import json
import resource
import time

from database import (
    DAYS_PER_MONTH,
    MINUTES_PER_DAY,
    advance_campaign_time,
    get_connection,
    get_wallet,
    initialize_database,
    open_player_shop,
    record_wallet_transaction,
    settle_civic_time,
)


def main():
    initialize_database()
    record_wallet_transaction(10_000, "long-benchmark-funding", memo="isolated annual benchmark", idempotency_key="long-benchmark-funds")
    open_player_shop("Ashvale Hold", "market_stall", turn_number=0)
    wallet_before = get_wallet()["balance_copper"]
    conn = get_connection()
    locations = conn.execute("SELECT COUNT(*) FROM civic_profiles").fetchone()[0]
    conn.close()

    memory_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started = time.perf_counter()
    jump = advance_campaign_time("انتظر 12 شهر")
    civic = settle_civic_time(jump["after_minutes"])
    elapsed = time.perf_counter() - started
    memory_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    expected_days = 12 * DAYS_PER_MONTH
    assert jump["elapsed_minutes"] == expected_days * MINUTES_PER_DAY, jump
    assert civic["settled_days"] == expected_days, civic
    assert civic["settled_locations"] == expected_days * locations, civic
    assert civic["total_shop_profit_copper"] > 0, civic
    assert get_wallet()["balance_copper"] - wallet_before == civic["total_shop_profit_copper"]
    print(json.dumps({
        "months": 12,
        "settled_days": civic["settled_days"],
        "settled_locations": civic["settled_locations"],
        "shop_profit_copper": civic["total_shop_profit_copper"],
        "elapsed_ms": round(elapsed * 1000, 3),
        "peak_memory_increase_kb": max(0, memory_after - memory_before),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
