"""اقتصاد معزول: لا يلمس بيانات حملة اللاعب."""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="iron_path_economy_") as tmpdir:
        os.chdir(tmpdir)
        sys.path.insert(0, str(ROOT))
        database = importlib.import_module("database")
        database.initialize_database()

        starting_balance = database.get_wallet()["balance_copper"]
        opening = database.record_wallet_transaction(
            1000, "test_opening", memo="رصيد اختبار معزول", idempotency_key="economy-test-opening"
        )
        expected_after_opening = starting_balance + 1000
        assert opening["wallet"]["balance_copper"] == expected_after_opening
        assert database.get_wallet()["denominations"] == {"crown": 12, "silver": 5, "copper": 0}

        purchase = database.trade_good("salt", 2, "buy", turn_number=1)
        assert purchase["amount_copper"] == -24
        assert database.get_wallet()["balance_copper"] == expected_after_opening - 24
        assert next(g for g in database.get_market_goods() if g["good_id"] == "salt")["player_quantity"] == 2

        sale = database.trade_good("salt", 1, "sell", turn_number=1)
        assert sale["amount_copper"] == 7
        assert database.get_wallet()["balance_copper"] == expected_after_opening - 17
        assert next(g for g in database.get_market_goods() if g["good_id"] == "salt")["player_quantity"] == 1

        try:
            database.trade_good("spice", 99, "buy", turn_number=1)
        except ValueError as exc:
            assert "الرصيد" in str(exc) or "مخزون" in str(exc)
        else:
            raise AssertionError("يجب رفض صفقة تتجاوز الرصيد أو المخزون")

        ledger = database.get_ledger_entries(20)
        assert sum(item["delta_copper"] for item in ledger) == database.get_wallet()["balance_copper"]
        assert all(item["balance_after"] >= 0 for item in ledger)
        print("ECONOMY TEST PASSED", database.get_wallet())


if __name__ == "__main__":
    main()
