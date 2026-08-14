import json
import re
import sqlite3
from pathlib import Path

from world_content import FACTIONS as WORLD_FACTIONS, HISTORY, LORE_ENTRIES, LORDS, LOCATIONS, REGIONS, WORLD
from world_expansion import (
    ATLAS_LORDS_EN, ATLAS_LOCATION_TEXT_EN,
    CHARACTER_TYPES_AR, CHARACTER_TYPES_EN,
    CIVIC_PROFILES, GOODS as LOCAL_GOODS, HISTORICAL_WARS, LOCATION_NAMES_AR,
    LOCATION_NAMES_EN, MARKET_CATALOG, PRESENCE_REASONS_AR, PRESENCE_REASONS_EN,
    REGION_NAMES_AR, REGION_NAMES_EN, RETAINER_ASSIGNMENTS_AR,
    RETAINER_ASSIGNMENTS_EN, UI, localize_atlas_payload, translated,
)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "story.db"

DEFAULT_STATS = [
    ("weapons_mastery", "Weapons Mastery", "Skill with blades, bows, and battlefield combat."),
    ("dueling_mastery", "Dueling Mastery", "Skill in one-on-one combat, footwork, timing, and counters."),
    ("trade_mastery", "Trade Mastery", "Skill negotiating deals, tariffs, and commerce."),
    ("conversation_mastery", "Conversation Mastery", "Skill persuading, reading, and manipulating people in dialogue."),
    ("strategy_mastery", "Strategy Mastery", "Skill in planning campaigns, tactics, contingencies, and positioning."),
    ("leadership_mastery", "Leadership Mastery", "Skill directing people, building cohesion, and carrying authority."),
    ("exploration_mastery", "Exploration Mastery", "Skill reading routes, searching locations, and surviving travel."),
    ("intrigue_mastery", "Intrigue Mastery", "Skill in deception, spying, leverage, and covert operations."),
]


def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():

    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            turn_number INTEGER NOT NULL,
            player_action TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(scene_id) REFERENCES scenes(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS character_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,
            xp INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # Phase 1 state tables (factions, retainers, quests, holdings,
    # world clock, behavior scores, traits, event log). Additive
    # only -- never touches scenes/memories/character_stats.
    init_phase1_tables(conn)
    init_phase2_tables(conn)
    init_phase3_tables(conn)
    init_phase3b_tables(conn)
    init_phase4_atlas_tables(conn)
    init_phase5_economy_tables(conn)
    init_phase6_expansion_tables(conn)
    init_phase7_presence_tables(conn)
    init_phase8_continuous_time_tables(conn)

    for name, display_name, description in DEFAULT_STATS:

        conn.execute(
            """
            INSERT OR IGNORE INTO character_stats
            (name, display_name, level, xp, description)
            VALUES (?, ?, 1, 0, ?)
            """,
            (name, display_name, description)
        )

    conn.commit()
    conn.close()


def save_scene(turn_number, player_action, ai_response):

    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO scenes
        (turn_number, player_action, ai_response)
        VALUES (?, ?, ?)
        """,
        (turn_number, player_action, ai_response)
    )

    scene_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return scene_id


def get_recent_scenes(limit=8):

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT turn_number, player_action, ai_response
        FROM scenes
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()

    conn.close()

    return list(reversed(rows))


def get_turn_count():

    conn = get_connection()

    result = conn.execute(
        "SELECT COUNT(*) FROM scenes"
    ).fetchone()[0]

    conn.close()

    return result


# -----------------------------------------------------------------
# PHASE 1: persistent game-state tables
#
# Gemini never writes to these directly. state_evaluator.py asks
# Gemini for a structured proposal; state_manager.py validates and
# applies it through the functions below.
# -----------------------------------------------------------------

BEHAVIOR_COUNTERS = [
    "mercy", "cruelty", "diplomacy", "intimidation", "deception",
    "honesty", "aggression", "pragmatism", "generosity", "ambition",
    "loyalty", "manipulation", "risk_taking"
]


def init_phase1_tables(conn):

    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            level INTEGER NOT NULL DEFAULT 1,
            total_xp INTEGER NOT NULL DEFAULT 0,
            reputation INTEGER NOT NULL DEFAULT 50,
            wealth INTEGER NOT NULL DEFAULT 0,
            political_influence INTEGER NOT NULL DEFAULT 0,
            military_influence INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute(
        "INSERT OR IGNORE INTO player_state (id) VALUES (1)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS behavior_scores (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0
        )
    """)
    for name in BEHAVIOR_COUNTERS:
        conn.execute(
            "INSERT OR IGNORE INTO behavior_scores (name, value) VALUES (?, 0)",
            (name,)
        )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS traits (
            key TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            description TEXT,
            unlock_turn INTEGER,
            unlock_reason TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS factions (
            name TEXT PRIMARY KEY,
            trust INTEGER NOT NULL DEFAULT 50,
            fear INTEGER NOT NULL DEFAULT 0,
            loyalty INTEGER NOT NULL DEFAULT 0,
            leverage INTEGER NOT NULL DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS retainers (
            name TEXT PRIMARY KEY,
            loyalty INTEGER NOT NULL DEFAULT 50,
            morale INTEGER NOT NULL DEFAULT 50,
            trust INTEGER NOT NULL DEFAULT 50,
            respect INTEGER NOT NULL DEFAULT 50,
            status TEXT DEFAULT 'active',
            assignment TEXT,
            location TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS quests (
            quest_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            objectives TEXT,
            involved_characters TEXT,
            involved_factions TEXT,
            location TEXT,
            deadline TEXT,
            discovered_info TEXT,
            updated_turn INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS holdings (
            name TEXT PRIMARY KEY,
            prosperity INTEGER NOT NULL DEFAULT 50,
            security INTEGER NOT NULL DEFAULT 50,
            population INTEGER NOT NULL DEFAULT 0,
            wealth INTEGER NOT NULL DEFAULT 0,
            food_supply INTEGER NOT NULL DEFAULT 50,
            military_strength INTEGER NOT NULL DEFAULT 0,
            loyalty INTEGER NOT NULL DEFAULT 50,
            governor TEXT,
            active_problems TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS world_clock (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            day INTEGER NOT NULL DEFAULT 1,
            month INTEGER NOT NULL DEFAULT 1,
            year INTEGER NOT NULL DEFAULT 1,
            season TEXT NOT NULL DEFAULT 'Autumn'
        )
    """)
    conn.execute(
        "INSERT OR IGNORE INTO world_clock (id) VALUES (1)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            turn_number INTEGER,
            event_type TEXT,
            title TEXT,
            summary TEXT,
            consequences TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()


def get_player_state():
    conn = get_connection()
    row = conn.execute(
        "SELECT level, total_xp, reputation, wealth, political_influence, military_influence "
        "FROM player_state WHERE id = 1"
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "level": row[0], "total_xp": row[1], "reputation": row[2],
        "wealth": row[3], "political_influence": row[4], "military_influence": row[5]
    }


# -----------------------------------------------------------------
# PHASE 5: Economy — single wallet, immutable ledger, and local market
#
# All money is stored in copper-units.  Crowns, silvers, and copper are
# presentation denominations only (1 crown = 100 copper; 1 silver = 10).
# The ledger is the audit trail; the wallet balance is a cached projection.
# -----------------------------------------------------------------

CURRENCY_DENOMINATIONS = (
    ("crown", "تاج", 100),
    ("silver", "فضة", 10),
    ("copper", "نحاس", 1),
)

# A location permits one player business.  The cost is a real licence payment,
# while the return is settled deterministically once for each narrative turn.
# Keeping the operating rules here makes both the UI and the turn engine obey
# exactly the same eligibility and financial model.
SHOP_TYPES = {
    "market_stall": {
        "label_ar": "كشك سوق", "label_en": "Market stall",
        "description_ar": "بيع سريع للسلع اليومية برخصة سوق محلية.",
        "description_en": "Fast turnover in everyday goods under a local market licence.",
        "base_cost": 70, "base_profit": 26, "min_tier": 1, "location_types": None,
    },
    "caravan_warehouse": {
        "label_ar": "مخزن قوافل", "label_en": "Caravan warehouse",
        "description_ar": "مخزن جملة للقوافل في عقد الطرق والمرافئ.",
        "description_en": "A wholesale storehouse for routes, crossings and ports.",
        "base_cost": 245, "base_profit": 54, "min_tier": 2,
        "location_types": {"fortress-city", "river-town", "port-city", "estate-town", "capital-city"},
    },
    "fort_provisioner": {
        "label_ar": "مورد حصن", "label_en": "Fort provisioner",
        "description_ar": "عقد تموين للحامية؛ الطلب مستقر لكن التعاقد منضبط.",
        "description_en": "A garrison supply contract with dependable but regulated demand.",
        "base_cost": 165, "base_profit": 42, "min_tier": 1,
        "location_types": {"fortress-city", "fortress-mine", "fortress-market", "northern-fortress"},
    },
    "guild_agency": {
        "label_ar": "وكالة نقابة", "label_en": "Guild agency",
        "description_ar": "وكالة تجارية تستفيد من النفوذ النقابي مقابل عمولات صارمة.",
        "description_en": "A trading office that buys guild influence at the price of strict commissions.",
        "base_cost": 315, "base_profit": 67, "min_tier": 3,
        "location_types": {"river-town", "port-city", "capital-city"},
    },
    "charter_house": {
        "label_ar": "دار عطاءات", "label_en": "Charter house",
        "description_ar": "دار عقود طويلة الأجل تحتاج إلى رأس مال وضمانات كبيرة.",
        "description_en": "A long-contract house that requires substantial capital and guarantees.",
        "base_cost": 480, "base_profit": 96, "min_tier": 4,
        "location_types": {"port-city", "capital-city"},
    },
}


def init_phase5_economy_tables(conn):
    """Additive, idempotent economy migration and initial market catalogue."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wallet (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            balance_copper INTEGER NOT NULL DEFAULT 0 CHECK (balance_copper >= 0),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT OR IGNORE INTO wallet (id, balance_copper) VALUES (1, 0)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS currency_denominations (
            code TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            copper_value INTEGER NOT NULL CHECK (copper_value > 0)
        )
    """)
    for code, display_name, copper_value in CURRENCY_DENOMINATIONS:
        conn.execute(
            "INSERT OR IGNORE INTO currency_denominations (code, display_name, copper_value) VALUES (?, ?, ?)",
            (code, display_name, copper_value),
        )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS economic_ledger (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key TEXT UNIQUE,
            turn_number INTEGER,
            entry_type TEXT NOT NULL,
            delta_copper INTEGER NOT NULL,
            balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
            counterparty TEXT,
            location TEXT,
            reference_type TEXT,
            reference_id TEXT,
            memo TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_economic_ledger_turn ON economic_ledger(turn_number DESC, entry_id DESC)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_goods (
            good_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            base_price_copper INTEGER NOT NULL CHECK (base_price_copper > 0),
            sell_factor REAL NOT NULL DEFAULT 0.65 CHECK (sell_factor > 0 AND sell_factor <= 1),
            origin TEXT,
            category TEXT NOT NULL DEFAULT 'general'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS merchant_stock (
            good_id TEXT PRIMARY KEY,
            quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(good_id) REFERENCES trade_goods(good_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_trade_goods (
            good_id TEXT PRIMARY KEY,
            quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
            FOREIGN KEY(good_id) REFERENCES trade_goods(good_id)
        )
    """)

    catalogue = [
        ("salt", "ملح بحر الشمال", "ملح أبيض محفوظ من مرافئ الملح؛ أساس الطعام والتبادل.", 12, 0.65, "المرافئ", "provisions", 30),
        ("timber", "خشب ويندمير", "خشب صلب للسفن والتحصينات، مطلوب في القلاع والورش.", 28, 0.62, "ويندمير", "material", 18),
        ("iron", "حديد الجبال", "سبائك غير مصقولة من ممرات النحاس، نافعة للسلاح والإصلاح.", 45, 0.68, "مرتفعات الغرب", "material", 12),
        ("wool", "صوف المروج", "صوف مصبوغ من قطعان المروج، ثابت الطلب في المدن.", 20, 0.66, "سهول هالغروف", "textile", 22),
        ("spice", "توابل المضيق", "بضاعة نادرة من السفن البعيدة؛ ربحها أعلى ومخزونها محدود.", 75, 0.58, "المضيق البعيد", "luxury", 6),
    ]
    for good_id, name, description, price, factor, origin, category, stock in catalogue:
        conn.execute(
            "INSERT OR IGNORE INTO trade_goods (good_id, name, description, base_price_copper, sell_factor, origin, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (good_id, name, description, price, factor, origin, category),
        )
        conn.execute("INSERT OR IGNORE INTO merchant_stock (good_id, quantity) VALUES (?, ?)", (good_id, stock))
        conn.execute("INSERT OR IGNORE INTO player_trade_goods (good_id, quantity) VALUES (?, 0)", (good_id,))

    # One-time migration of the legacy wealth field and old currency items.
    # The unique key makes the migration safe across every subsequent startup.
    migrated = conn.execute("SELECT 1 FROM economic_ledger WHERE idempotency_key = 'legacy-opening-balance-v1'").fetchone()
    if not migrated:
        legacy_wealth_row = conn.execute("SELECT wealth FROM player_state WHERE id = 1").fetchone()
        legacy_wealth = int(legacy_wealth_row[0] or 0) if legacy_wealth_row else 0
        legacy_items_row = conn.execute("SELECT COALESCE(SUM(quantity), 0) FROM inventory WHERE category = 'currency'").fetchone()
        legacy_items = int(legacy_items_row[0] or 0)
        opening_balance = max(0, legacy_wealth + legacy_items)
        if opening_balance:
            current_balance = conn.execute("SELECT balance_copper FROM wallet WHERE id = 1").fetchone()[0]
            new_balance = current_balance + opening_balance
            conn.execute("UPDATE wallet SET balance_copper = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (new_balance,))
            conn.execute(
                "INSERT INTO economic_ledger (idempotency_key, entry_type, delta_copper, balance_after, memo) VALUES (?, ?, ?, ?, ?)",
                ("legacy-opening-balance-v1", "opening_balance", opening_balance, new_balance, "ترحيل الرصيد السابق إلى دفتر القيود"),
            )
        else:
            conn.execute(
                "INSERT INTO economic_ledger (idempotency_key, entry_type, delta_copper, balance_after, memo) VALUES (?, ?, 0, 0, ?)",
                ("legacy-opening-balance-v1", "opening_balance", "تهيئة دفتر القيود بلا رصيد سابق"),
            )
        conn.execute("DELETE FROM inventory WHERE category = 'currency'")
        conn.execute("UPDATE player_state SET wealth = 0 WHERE id = 1")

    # Give a modest, ledger-backed first-market charter only once.  This keeps a
    # new campaign tradable without creating an untracked purse or duplicating it
    # on later launches.
    starter_key = "campaign-market-charter-v1"
    starter_exists = conn.execute(
        "SELECT 1 FROM economic_ledger WHERE idempotency_key = ?", (starter_key,)
    ).fetchone()
    if not starter_exists:
        current_balance = conn.execute("SELECT balance_copper FROM wallet WHERE id = 1").fetchone()[0]
        starter_amount = 250
        new_balance = current_balance + starter_amount
        conn.execute("UPDATE wallet SET balance_copper = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (new_balance,))
        conn.execute(
            """INSERT INTO economic_ledger
               (idempotency_key, entry_type, delta_copper, balance_after, counterparty, reference_type, reference_id, memo)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (starter_key, "market_charter", starter_amount, new_balance, "خزانة بيت مودسبين", "campaign", "market-charter", "رأس مال افتتاحي للتجارة"),
        )
    conn.commit()


# -----------------------------------------------------------------
# EXPANSION: bilingual history, civic simulation inputs, and local markets
# -----------------------------------------------------------------


def init_phase6_expansion_tables(conn):
    """Create and idempotently seed the bilingual world-expansion tables."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historical_wars (
            slug TEXT PRIMARY KEY,
            year TEXT NOT NULL,
            name_ar TEXT NOT NULL,
            name_en TEXT NOT NULL,
            summary_ar TEXT NOT NULL,
            summary_en TEXT NOT NULL,
            legacy_ar TEXT NOT NULL,
            legacy_en TEXT NOT NULL,
            regions TEXT NOT NULL,
            regions_en TEXT NOT NULL DEFAULT ''
        )
    """)
    war_columns = {row[1] for row in conn.execute("PRAGMA table_info(historical_wars)").fetchall()}
    if "regions_en" not in war_columns:
        conn.execute("ALTER TABLE historical_wars ADD COLUMN regions_en TEXT NOT NULL DEFAULT ''")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS civic_profiles (
            location TEXT PRIMARY KEY,
            location_ar TEXT NOT NULL,
            location_en TEXT NOT NULL,
            civic_type TEXT NOT NULL,
            population INTEGER NOT NULL CHECK (population >= 0),
            government_ar TEXT NOT NULL,
            government_en TEXT NOT NULL,
            governor_ar TEXT NOT NULL,
            governor_en TEXT NOT NULL,
            tax_rate INTEGER NOT NULL CHECK (tax_rate BETWEEN 0 AND 25),
            security INTEGER NOT NULL CHECK (security BETWEEN 0 AND 100),
            prosperity INTEGER NOT NULL CHECK (prosperity BETWEEN 0 AND 100),
            loyalty INTEGER NOT NULL CHECK (loyalty BETWEEN 0 AND 100),
            supply_ar TEXT NOT NULL,
            supply_en TEXT NOT NULL,
            demand_ar TEXT NOT NULL,
            demand_en TEXT NOT NULL,
            market_tier INTEGER NOT NULL CHECK (market_tier BETWEEN 1 AND 5),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS local_market_goods (
            location TEXT NOT NULL,
            good_id TEXT NOT NULL,
            name_ar TEXT NOT NULL,
            name_en TEXT NOT NULL,
            description_ar TEXT NOT NULL,
            description_en TEXT NOT NULL,
            base_price_copper INTEGER NOT NULL CHECK (base_price_copper > 0),
            sell_factor REAL NOT NULL CHECK (sell_factor > 0 AND sell_factor <= 1),
            origin TEXT NOT NULL,
            category TEXT NOT NULL,
            price_multiplier REAL NOT NULL CHECK (price_multiplier > 0),
            stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (location, good_id),
            FOREIGN KEY(location) REFERENCES civic_profiles(location)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_shops (
            shop_id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL UNIQUE,
            shop_type TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 5),
            daily_profit INTEGER NOT NULL DEFAULT 0 CHECK (daily_profit >= 0),
            opened_turn INTEGER NOT NULL DEFAULT 0,
            last_settled_turn INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(location) REFERENCES civic_profiles(location)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS civic_ledger (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key TEXT NOT NULL UNIQUE,
            turn_number INTEGER NOT NULL,
            location TEXT NOT NULL,
            entry_type TEXT NOT NULL,
            delta_copper INTEGER NOT NULL,
            treasury_after INTEGER NOT NULL CHECK (treasury_after >= 0),
            memo TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(location) REFERENCES civic_profiles(location)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_civic_ledger_location_turn ON civic_ledger(location, turn_number DESC, entry_id DESC)")

    # Civic metrics were added after the first read-only profile migration.
    # The columns are deliberately additive so established campaigns retain all
    # known values; only previously absent operational metrics receive defaults.
    civic_columns = {row[1] for row in conn.execute("PRAGMA table_info(civic_profiles)").fetchall()}
    civic_metric_columns = {
        "households": "INTEGER NOT NULL DEFAULT 0",
        "workforce": "INTEGER NOT NULL DEFAULT 0",
        "food_days": "INTEGER NOT NULL DEFAULT 30",
        "treasury_copper": "INTEGER NOT NULL DEFAULT 0",
        "maintenance_copper": "INTEGER NOT NULL DEFAULT 0",
        "debt_copper": "INTEGER NOT NULL DEFAULT 0",
        "last_settled_turn": "INTEGER NOT NULL DEFAULT 0",
    }
    for column, declaration in civic_metric_columns.items():
        if column not in civic_columns:
            conn.execute(f"ALTER TABLE civic_profiles ADD COLUMN {column} {declaration}")

    for war in HISTORICAL_WARS:
        conn.execute(
            """INSERT INTO historical_wars
               (slug, year, name_ar, name_en, summary_ar, summary_en, legacy_ar, legacy_en, regions, regions_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(slug) DO UPDATE SET
               year=excluded.year, name_ar=excluded.name_ar, name_en=excluded.name_en,
               summary_ar=excluded.summary_ar, summary_en=excluded.summary_en,
               legacy_ar=excluded.legacy_ar, legacy_en=excluded.legacy_en, regions=excluded.regions,
               regions_en=excluded.regions_en""",
            (war["slug"], war["year"], war["name_ar"], war["name_en"], war["summary_ar"], war["summary_en"], war["legacy_ar"], war["legacy_en"], war["regions"], war.get("regions_en", war["regions"])),
        )

    for profile in CIVIC_PROFILES:
        conn.execute(
            """INSERT INTO civic_profiles
               (location, location_ar, location_en, civic_type, population, government_ar, government_en,
                governor_ar, governor_en, tax_rate, security, prosperity, loyalty, supply_ar, supply_en,
                demand_ar, demand_en, market_tier)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(location) DO UPDATE SET
               location_ar=excluded.location_ar, location_en=excluded.location_en, civic_type=excluded.civic_type,
               government_ar=excluded.government_ar, government_en=excluded.government_en,
               governor_ar=excluded.governor_ar, governor_en=excluded.governor_en,
               supply_ar=excluded.supply_ar, supply_en=excluded.supply_en, demand_ar=excluded.demand_ar,
               demand_en=excluded.demand_en, updated_at=CURRENT_TIMESTAMP""",
            (profile["location"], profile["location_ar"], profile["location_en"], profile["type"], profile["population"],
             profile["government_ar"], profile["government_en"], profile["governor_ar"], profile["governor_en"],
             profile["tax_rate"], profile["security"], profile["prosperity"], profile["loyalty"],
             profile["supply_ar"], profile["supply_en"], profile["demand_ar"], profile["demand_en"], profile["tier"]),
        )

    # Static profiles are detailed hand-authored records.  All other populated
    # atlas locations receive a restrained civic baseline so the player can
    # licence a shop at every city, town, port, fortress and seat—without
    # pretending that wilderness, ruins and monasteries have a retail market.
    civic_kind_defaults = {
        "crown": ("capital-city", 5, 54000), "city": ("city", 3, 15200),
        "port": ("port-city", 3, 17600), "town": ("market-town", 2, 7600),
        "village": ("village-market", 1, 3300), "settlement": ("settlement-market", 1, 4400),
        "castle": ("fortress-market", 2, 9200), "fortress": ("fortress-market", 2, 7800),
        "seat": ("estate-seat", 2, 6800),
    }
    regional_goods = {
        "ashvale": {"barley": 0.82, "timber": 0.92, "tools": 1.08, "salt": 1.22},
        "crownlands": {"wine": 0.94, "tools": 0.96, "barley": 1.02, "iron": 1.10},
        "wolf_march": {"fur": 0.93, "iron": 1.08, "barley": 1.16, "salt": 1.22},
        "western_coast": {"salt": 0.78, "glass": 0.88, "timber": 0.98, "barley": 1.15},
        "eastern_gentry": {"wine": 0.83, "tools": 1.02, "iron": 1.10, "salt": 1.08},
        "greywood": {"timber": 0.76, "fur": 0.98, "tools": 1.12, "salt": 1.24},
        "southern_reach": {"barley": 0.90, "wine": 0.92, "salt": 1.02, "tools": 1.08},
        "frostward": {"fur": 0.77, "timber": 0.80, "iron": 0.94, "salt": 1.30},
        "far_crossing": {"salt": 0.91, "glass": 1.06, "wine": 1.08, "timber": 1.02},
    }
    static_profile_locations = {profile["location"] for profile in CIVIC_PROFILES}
    for index, (location, region, _x, _y, _description, kind, _discovered) in enumerate(LOCATIONS):
        if kind not in civic_kind_defaults:
            continue
        civic_type, tier, baseline_population = civic_kind_defaults[kind]
        population = baseline_population + (index % 5) * max(220, baseline_population // 14)
        generated_name_en = LOCATION_NAMES_EN.get(location, location)
        conn.execute(
            """INSERT OR IGNORE INTO civic_profiles
               (location, location_ar, location_en, civic_type, population, government_ar, government_en,
                governor_ar, governor_en, tax_rate, security, prosperity, loyalty, supply_ar, supply_en,
                demand_ar, demand_en, market_tier)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (location, location, generated_name_en, civic_type, population,
             "مجلس محلي ووكيل طريق", "Local council and road reeve",
             "الوكيل المحلي", "The local reeve", min(10, 3 + tier),
             min(90, 54 + tier * 7 + index % 5), min(88, 47 + tier * 8 + index % 7),
             min(84, 55 + tier * 5 + index % 9), "سلع الإقليم ومخازنه", "Regional goods and storehouses",
             "احتياجات القوافل والحامية", "Caravan and garrison needs", tier),
        )
        if location not in static_profile_locations:
            conn.execute(
                "UPDATE civic_profiles SET location_ar = ?, location_en = ?, updated_at = CURRENT_TIMESTAMP WHERE location = ?",
                (location, generated_name_en, location),
            )

    goods_by_id = {good[0]: good for good in LOCAL_GOODS}
    tiers_by_location = {row[0]: row[1] for row in conn.execute("SELECT location, market_tier FROM civic_profiles").fetchall()}
    for location, goods in MARKET_CATALOG.items():
        for good_id, multiplier in goods.items():
            good = goods_by_id[good_id]
            stock = max(4, int(tiers_by_location.get(location, 1) * 9 / multiplier))
            conn.execute(
                """INSERT INTO local_market_goods
                   (location, good_id, name_ar, name_en, description_ar, description_en, base_price_copper,
                    sell_factor, origin, category, price_multiplier, stock)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(location, good_id) DO UPDATE SET
                   name_ar=excluded.name_ar, name_en=excluded.name_en, description_ar=excluded.description_ar,
                   description_en=excluded.description_en, base_price_copper=excluded.base_price_copper,
                   sell_factor=excluded.sell_factor, origin=excluded.origin, category=excluded.category,
                   stock=MAX(local_market_goods.stock, excluded.stock), updated_at=CURRENT_TIMESTAMP""",
                (location, good[0], good[1], good[2], good[3], good[4], good[5], good[6], good[7], good[8], multiplier, stock),
            )
    region_by_location = {location: region for location, region, *_rest in LOCATIONS}
    for location, tier in tiers_by_location.items():
        if location in MARKET_CATALOG:
            continue
        for good_id, multiplier in regional_goods.get(region_by_location.get(location), {"barley": 1.0, "salt": 1.12, "tools": 1.08}).items():
            good = goods_by_id[good_id]
            stock = max(4, int(tier * 9 / multiplier))
            conn.execute(
                """INSERT OR IGNORE INTO local_market_goods
                   (location, good_id, name_ar, name_en, description_ar, description_en, base_price_copper,
                    sell_factor, origin, category, price_multiplier, stock)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (location, good[0], good[1], good[2], good[3], good[4], good[5], good[6], good[7], good[8], multiplier, stock),
            )
    # Establish operational baselines exactly once.  They are campaign values,
    # not test fixtures, and subsequent turn settlement evolves them instead of
    # reseeding them from static content.
    current_turn = conn.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
    conn.execute("UPDATE civic_profiles SET households = MAX(1, CAST(population / 5 AS INTEGER)) WHERE households = 0")
    conn.execute("UPDATE civic_profiles SET workforce = MAX(1, CAST(population * 55 / 100 AS INTEGER)) WHERE workforce = 0")
    conn.execute("UPDATE civic_profiles SET food_days = MAX(20, 26 + market_tier * 5) WHERE food_days <= 0")
    conn.execute("UPDATE civic_profiles SET treasury_copper = population * (market_tier + 5) WHERE treasury_copper = 0")
    conn.execute("UPDATE civic_profiles SET maintenance_copper = MAX(180, CAST(population / 18 AS INTEGER) + market_tier * 70) WHERE maintenance_copper = 0")
    conn.execute("UPDATE civic_profiles SET last_settled_turn = ? WHERE last_settled_turn = 0", (current_turn,))
    conn.commit()


def _language(language):
    return "en" if language == "en" else "ar"


def get_ui_strings(language="ar"):
    return {"language": _language(language), "strings": UI[_language(language)]}


def get_historical_wars(language="ar"):
    lang = _language(language)
    conn = get_connection()
    rows = conn.execute(
        "SELECT slug, year, name_ar, name_en, summary_ar, summary_en, legacy_ar, legacy_en, regions, regions_en FROM historical_wars ORDER BY rowid"
    ).fetchall()
    conn.close()
    return [
        {"slug": row[0], "year": row[1], "name": row[3] if lang == "en" else row[2],
         "summary": row[5] if lang == "en" else row[4], "legacy": row[7] if lang == "en" else row[6],
         "regions": row[9] if lang == "en" else row[8]}
        for row in rows
    ]


def _civic_row_to_dict(row, language):
    lang = _language(language)
    return {
        "location": row[0], "name": row[2] if lang == "en" else row[1], "type": row[3], "population": row[4],
        "government": row[6] if lang == "en" else row[5], "governor": row[8] if lang == "en" else row[7],
        "tax_rate": row[9], "security": row[10], "prosperity": row[11], "loyalty": row[12],
        "supply": row[14] if lang == "en" else row[13], "demand": row[16] if lang == "en" else row[15],
        "tier": row[17], "households": row[18], "workforce": row[19], "food_days": row[20],
        "treasury_copper": row[21], "maintenance_copper": row[22], "debt_copper": row[23],
        "last_settled_turn": row[24],
    }


CIVIC_PROFILE_SELECT = """SELECT location, location_ar, location_en, civic_type, population, government_ar, government_en,
    governor_ar, governor_en, tax_rate, security, prosperity, loyalty, supply_ar, supply_en,
    demand_ar, demand_en, market_tier, households, workforce, food_days, treasury_copper,
    maintenance_copper, debt_copper, last_settled_turn FROM civic_profiles"""


def get_civic_profiles(language="ar"):
    conn = get_connection()
    rows = conn.execute(CIVIC_PROFILE_SELECT + " ORDER BY population DESC").fetchall()
    conn.close()
    return [_civic_row_to_dict(row, language) for row in rows]


def get_civic_profile(location, language="ar"):
    conn = get_connection()
    row = conn.execute(CIVIC_PROFILE_SELECT + " WHERE location = ?", (location,)).fetchone()
    conn.close()
    return _civic_row_to_dict(row, language) if row else None


def get_local_market(location, language="ar"):
    lang = _language(language)
    profile = get_civic_profile(location, lang)
    if not profile:
        return None
    conn = get_connection()
    rows = conn.execute(
        """SELECT good_id, name_ar, name_en, description_ar, description_en, base_price_copper,
                  sell_factor, origin, category, price_multiplier, stock
           FROM local_market_goods WHERE location = ? ORDER BY base_price_copper * price_multiplier""",
        (location,),
    ).fetchall()
    conn.close()
    tax_multiplier = 1 + (profile["tax_rate"] / 100)
    items = []
    for row in rows:
        buy_price = max(1, round(row[5] * row[9] * tax_multiplier))
        items.append({
            "good_id": row[0], "name": row[2] if lang == "en" else row[1],
            "description": row[4] if lang == "en" else row[3], "origin": row[7], "category": row[8],
            "stock": row[10], "buy_price_copper": buy_price,
            "sell_price_copper": max(1, int(buy_price * row[6])), "price_multiplier": row[9],
        })
    return {"location": profile, "items": items, "currency": "copper" if lang == "en" else "نحاس"}


def _shop_label(shop_type, language):
    spec = SHOP_TYPES.get(shop_type, SHOP_TYPES["market_stall"])
    lang = _language(language)
    return spec[f"label_{lang}"], spec[f"description_{lang}"]


def _eligible_shop_specs(profile):
    options = []
    for shop_type, spec in SHOP_TYPES.items():
        allowed_types = spec["location_types"]
        if profile["tier"] < spec["min_tier"]:
            continue
        if allowed_types and profile["type"] not in allowed_types:
            continue
        options.append((shop_type, spec))
    return options


def _shop_opening_cost(profile, spec):
    return int(spec["base_cost"] + profile["tier"] * 30 + profile["tax_rate"] * 6)


def _shop_net_profit(profile, shop_type, level):
    spec = SHOP_TYPES[shop_type]
    # Revenue grows with market depth, security and prosperity.  Rent and local
    # commission rise with tax and size, so a rich city is profitable but never free.
    gross_factor = (0.64 + profile["tier"] * 0.18 + profile["prosperity"] / 250 + profile["security"] / 420)
    gross = max(1, int(spec["base_profit"] * level * gross_factor))
    rent = max(2, profile["tier"] * level * 2 + profile["tax_rate"] // 2)
    commission = max(1, int(gross * (0.06 + profile["tax_rate"] / 500)))
    return gross, rent, commission, max(1, gross - rent - commission)


def get_shop_options(location, language="ar"):
    profile = get_civic_profile(location, language)
    if not profile:
        return None
    lang = _language(language)
    options = []
    for shop_type, spec in _eligible_shop_specs(profile):
        gross, rent, commission, net = _shop_net_profit(profile, shop_type, 1)
        options.append({
            "shop_type": shop_type,
            "label": spec[f"label_{lang}"],
            "description": spec[f"description_{lang}"],
            "opening_cost_copper": _shop_opening_cost(profile, spec),
            "estimated_turn_profit_copper": net,
            "rent_copper": rent,
            "commission_copper": commission,
        })
    return {"location": profile, "options": options}


def get_player_shops(language="ar"):
    lang = _language(language)
    conn = get_connection()
    rows = conn.execute(
        """SELECT ps.shop_id, ps.location, ps.shop_type, ps.level, ps.daily_profit, ps.opened_turn,
                  ps.last_settled_turn, ps.status, cp.location_ar, cp.location_en, cp.prosperity,
                  cp.security, cp.tax_rate, cp.market_tier
           FROM player_shops ps JOIN civic_profiles cp ON cp.location = ps.location
           ORDER BY ps.opened_turn, ps.shop_id"""
    ).fetchall()
    conn.close()
    shops = []
    for row in rows:
        label, description = _shop_label(row[2], lang)
        shops.append({
            "shop_id": row[0], "location": row[1], "name": row[9] if lang == "en" else row[8],
            "shop_type": row[2], "shop_type_label": label, "shop_description": description,
            "level": row[3], "daily_profit": row[4], "opened_turn": row[5],
            "last_settled_turn": row[6], "status": row[7], "prosperity": row[10],
            "security": row[11], "tax_rate": row[12], "tier": row[13],
        })
    return shops


def _append_civic_ledger_entry(conn, *, idempotency_key, turn_number, location, entry_type, delta_copper, memo):
    duplicate = conn.execute(
        "SELECT entry_id, treasury_after FROM civic_ledger WHERE idempotency_key = ?", (idempotency_key,)
    ).fetchone()
    if duplicate:
        return {"entry_id": duplicate[0], "treasury_after": duplicate[1], "duplicate": True}
    treasury = conn.execute("SELECT treasury_copper FROM civic_profiles WHERE location = ?", (location,)).fetchone()
    if not treasury:
        raise ValueError("لا يوجد سجل مالي مدني لهذا الموقع.")
    after = max(0, int(treasury[0]) + int(delta_copper))
    cursor = conn.execute(
        """INSERT INTO civic_ledger (idempotency_key, turn_number, location, entry_type, delta_copper, treasury_after, memo)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (idempotency_key, int(turn_number), location, entry_type, int(delta_copper), after, memo),
    )
    conn.execute("UPDATE civic_profiles SET treasury_copper = ?, updated_at = CURRENT_TIMESTAMP WHERE location = ?", (after, location))
    return {"entry_id": cursor.lastrowid, "treasury_after": after, "duplicate": False}


def open_player_shop(location, shop_type, turn_number):
    location = str(location or "").strip()
    shop_type = str(shop_type or "").strip().lower()
    if not location or len(location) > 100 or shop_type not in SHOP_TYPES:
        raise ValueError("بيانات افتتاح المتجر غير صالحة.")
    profile = get_civic_profile(location, "ar")
    if not profile:
        raise ValueError("لا يملك هذا الموقع ملفًا مدنيًا يسمح بالترخيص.")
    spec = SHOP_TYPES[shop_type]
    if (shop_type, spec) not in _eligible_shop_specs(profile):
        raise ValueError("هذا النوع من المتاجر لا يطابق طبيعة هذا الموقع أو رتبة سوقه.")
    cost = _shop_opening_cost(profile, spec)
    gross, rent, commission, estimate = _shop_net_profit(profile, shop_type, 1)
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT shop_id FROM player_shops WHERE location = ?", (location,)).fetchone()
        if existing:
            raise ValueError("لديك متجر مسجّل في هذا الموقع بالفعل.")
        entry = _append_ledger_entry(
            conn, -cost, "shop_license", turn_number=int(turn_number), counterparty=profile["governor"],
            location=location, reference_type="player_shop", reference_id=location,
            memo=f"رخصة افتتاح {spec['label_ar']}", idempotency_key=f"shop-opening:{location}",
        )
        cursor = conn.execute(
            """INSERT INTO player_shops (location, shop_type, level, daily_profit, opened_turn, last_settled_turn, status)
               VALUES (?, ?, 1, ?, ?, ?, 'open')""",
            (location, shop_type, estimate, int(turn_number), int(turn_number)),
        )
        _append_civic_ledger_entry(
            conn, idempotency_key=f"shop-license:{location}", turn_number=int(turn_number), location=location,
            entry_type="shop_license", delta_copper=cost, memo=f"رسم رخصة متجر اللاعب: {spec['label_ar']}",
        )
        conn.commit()
        return {
            "shop_id": cursor.lastrowid, "location": location, "shop_type": shop_type,
            "opening_cost_copper": cost, "estimated_turn_profit_copper": estimate,
            "wallet": {"balance_copper": entry["balance_after"], "denominations": _denomination_breakdown(entry["balance_after"])},
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def settle_civic_turn(turn_number):
    """Settle every city once per narrative turn and post player-shop income atomically.

    This deliberately uses compact, bounded formulas rather than random values:
    residents can react to food, taxes and paid maintenance, while markets move
    slowly enough for the player to understand why a price or profit changed.
    """
    turn_number = int(turn_number)
    if turn_number < 1:
        return {"turn": turn_number, "settled_locations": 0, "shops": [], "total_shop_profit_copper": 0}
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(CIVIC_PROFILE_SELECT + " WHERE last_settled_turn < ? ORDER BY location", (turn_number,)).fetchall()
        settlements, shop_results, total_profit = 0, [], 0
        for row in rows:
            profile = _civic_row_to_dict(row, "ar")
            location = profile["location"]
            tax_income = max(12, profile["households"] * profile["tax_rate"] // 8)
            toll_income = max(8, profile["tier"] * 18 + profile["workforce"] // 2500)
            public_income = tax_income + toll_income
            maintenance = max(1, profile["maintenance_copper"])
            net_public = public_income - maintenance
            _append_civic_ledger_entry(
                conn, idempotency_key=f"civic-public:{location}:{turn_number}", turn_number=turn_number,
                location=location, entry_type="public_settlement", delta_copper=net_public,
                memo=f"ضرائب ورسوم {public_income} ناقص صيانة {maintenance}",
            )
            food_change = 1 if profile["prosperity"] >= 55 and profile["security"] >= 55 else -1
            food_days = max(0, min(120, profile["food_days"] + food_change))
            security_delta = 1 if net_public >= 0 and food_days >= 18 else -1
            prosperity_delta = 1 if net_public > maintenance // 3 and food_days >= 24 else (-1 if food_days < 12 else 0)
            loyalty_delta = -1 if profile["tax_rate"] >= 10 or food_days < 12 else (1 if security_delta > 0 and profile["tax_rate"] <= 5 else 0)
            population_delta = 1 if (turn_number % 3 == 0 and food_days >= 28 and profile["security"] >= 70 and profile["prosperity"] >= 65) else (-1 if food_days < 8 else 0)
            population = max(250, profile["population"] + population_delta)
            households = max(1, population // 5)
            workforce = max(1, population * 55 // 100)
            security = max(0, min(100, profile["security"] + security_delta))
            prosperity = max(0, min(100, profile["prosperity"] + prosperity_delta))
            loyalty = max(0, min(100, profile["loyalty"] + loyalty_delta))
            conn.execute(
                """UPDATE civic_profiles SET population=?, households=?, workforce=?, food_days=?, security=?,
                   prosperity=?, loyalty=?, last_settled_turn=?, updated_at=CURRENT_TIMESTAMP WHERE location=?""",
                (population, households, workforce, food_days, security, prosperity, loyalty, turn_number, location),
            )
            restock = max(1, profile["tier"] + prosperity // 32 - (1 if security < 50 else 0))
            price_shift = (-0.01 if prosperity >= 75 and food_days >= 24 else 0.0) + (0.02 if food_days < 15 else 0.0) + (0.01 if security < 50 else 0.0)
            conn.execute(
                """UPDATE local_market_goods SET stock = MIN(99, MAX(0, stock + ?)),
                   price_multiplier = MIN(1.65, MAX(0.60, price_multiplier + ?)), updated_at=CURRENT_TIMESTAMP
                   WHERE location = ?""",
                (restock, price_shift, location),
            )
            shops = conn.execute(
                "SELECT shop_id, shop_type, level FROM player_shops WHERE location = ? AND status = 'open' AND last_settled_turn < ?",
                (location, turn_number),
            ).fetchall()
            updated_profile = {**profile, "prosperity": prosperity, "security": security, "food_days": food_days}
            for shop_id, shop_type, level in shops:
                gross, rent, commission, net_profit = _shop_net_profit(updated_profile, shop_type, level)
                entry = _append_ledger_entry(
                    conn, net_profit, "shop_profit", turn_number=turn_number,
                    counterparty=profile["governor"], location=location, reference_type="player_shop",
                    reference_id=str(shop_id), memo=f"ربح {SHOP_TYPES[shop_type]['label_ar']} بعد إيجار {rent} وعمولة {commission}",
                    idempotency_key=f"shop-profit:{shop_id}:{turn_number}",
                )
                _append_civic_ledger_entry(
                    conn, idempotency_key=f"shop-local-fee:{shop_id}:{turn_number}", turn_number=turn_number,
                    location=location, entry_type="shop_fees", delta_copper=rent + commission,
                    memo=f"إيجار وعمولة متجر اللاعب ({gross} إجمالي)",
                )
                conn.execute(
                    """UPDATE player_shops SET daily_profit=?, last_settled_turn=?, updated_at=CURRENT_TIMESTAMP
                       WHERE shop_id=?""", (net_profit, turn_number, shop_id)
                )
                shop_results.append({"shop_id": shop_id, "location": location, "profit_copper": net_profit,
                                     "gross_copper": gross, "rent_copper": rent, "commission_copper": commission,
                                     "duplicate": entry["duplicate"]})
                total_profit += net_profit
            settlements += 1
        conn.commit()
        return {"turn": turn_number, "settled_locations": settlements, "shops": shop_results,
                "total_shop_profit_copper": total_profit}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _denomination_breakdown(balance_copper):
    remaining = int(balance_copper or 0)
    crowns, remaining = divmod(remaining, 100)
    silvers, copper = divmod(remaining, 10)
    return {"crown": crowns, "silver": silvers, "copper": copper}


def _append_ledger_entry(conn, delta_copper, entry_type, *, turn_number=None, counterparty=None,
                         location=None, reference_type=None, reference_id=None, memo=None,
                         idempotency_key=None):
    if not isinstance(delta_copper, int) or delta_copper == 0:
        raise ValueError("يجب أن تكون قيمة القيد المالي عددًا صحيحًا غير صفري.")
    if idempotency_key:
        duplicate = conn.execute(
            "SELECT entry_id, delta_copper, balance_after FROM economic_ledger WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if duplicate:
            return {"entry_id": duplicate[0], "delta_copper": duplicate[1], "balance_after": duplicate[2], "duplicate": True}
    current_balance = conn.execute("SELECT balance_copper FROM wallet WHERE id = 1").fetchone()[0]
    new_balance = current_balance + delta_copper
    if new_balance < 0:
        raise ValueError("الرصيد لا يكفي لإتمام هذه المعاملة.")
    cursor = conn.execute(
        """INSERT INTO economic_ledger
           (idempotency_key, turn_number, entry_type, delta_copper, balance_after, counterparty, location, reference_type, reference_id, memo)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (idempotency_key, turn_number, entry_type, delta_copper, new_balance, counterparty, location, reference_type, reference_id, memo),
    )
    conn.execute("UPDATE wallet SET balance_copper = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (new_balance,))
    return {"entry_id": cursor.lastrowid, "delta_copper": delta_copper, "balance_after": new_balance, "duplicate": False}


def get_wallet():
    conn = get_connection()
    balance = conn.execute("SELECT balance_copper FROM wallet WHERE id = 1").fetchone()[0]
    conn.close()
    return {"balance_copper": balance, "denominations": _denomination_breakdown(balance)}


def get_ledger_entries(limit=20):
    conn = get_connection()
    rows = conn.execute(
        """SELECT entry_id, turn_number, entry_type, delta_copper, balance_after, counterparty, location, reference_type, reference_id, memo, created_at
           FROM economic_ledger ORDER BY entry_id DESC LIMIT ?""", (max(1, min(int(limit), 100)),)
    ).fetchall()
    conn.close()
    return [
        {"entry_id": r[0], "turn_number": r[1], "entry_type": r[2], "delta_copper": r[3], "balance_after": r[4],
         "counterparty": r[5], "location": r[6], "reference_type": r[7], "reference_id": r[8], "memo": r[9], "created_at": r[10]}
        for r in rows
    ]


def record_wallet_transaction(delta_copper, entry_type, *, turn_number=None, counterparty=None,
                              location=None, reference_type=None, reference_id=None, memo=None,
                              idempotency_key=None):
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        result = _append_ledger_entry(conn, int(delta_copper), entry_type, turn_number=turn_number,
                                      counterparty=counterparty, location=location, reference_type=reference_type,
                                      reference_id=reference_id, memo=memo, idempotency_key=idempotency_key)
        conn.commit()
        return {**result, "wallet": {"balance_copper": result["balance_after"], "denominations": _denomination_breakdown(result["balance_after"])}}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_market_goods():
    conn = get_connection()
    rows = conn.execute(
        """SELECT g.good_id, g.name, g.description, g.base_price_copper, g.sell_factor, g.origin, g.category,
                  ms.quantity, ptg.quantity
           FROM trade_goods g JOIN merchant_stock ms ON ms.good_id = g.good_id
           JOIN player_trade_goods ptg ON ptg.good_id = g.good_id ORDER BY g.base_price_copper"""
    ).fetchall()
    conn.close()
    return [
        {"good_id": r[0], "name": r[1], "description": r[2], "buy_price_copper": r[3],
         "sell_price_copper": max(1, int(r[3] * r[4])), "origin": r[5], "category": r[6],
         "merchant_quantity": r[7], "player_quantity": r[8]}
        for r in rows
    ]


def trade_good(good_id, quantity, side, turn_number=None, location="سوق أشفيل"):
    if side not in {"buy", "sell"}:
        raise ValueError("اتجاه التجارة غير صالح.")
    if not isinstance(quantity, int) or quantity <= 0 or quantity > 99:
        raise ValueError("كمية التجارة يجب أن تكون بين 1 و99.")
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT g.good_id, g.name, g.base_price_copper, g.sell_factor, ms.quantity, ptg.quantity
               FROM trade_goods g JOIN merchant_stock ms ON ms.good_id = g.good_id
               JOIN player_trade_goods ptg ON ptg.good_id = g.good_id WHERE g.good_id = ?""", (good_id,)
        ).fetchone()
        if not row:
            raise ValueError("هذه السلعة غير موجودة في السوق.")
        good_id, name, buy_price, sell_factor, merchant_quantity, player_quantity = row
        if side == "buy":
            if merchant_quantity < quantity:
                raise ValueError("مخزون التاجر لا يكفي لهذه الكمية.")
            amount = -(buy_price * quantity)
            entry_type, counterparty = "trade_buy", "سماسرة أشفيل"
            conn.execute("UPDATE merchant_stock SET quantity = quantity - ?, updated_at = CURRENT_TIMESTAMP WHERE good_id = ?", (quantity, good_id))
            conn.execute("UPDATE player_trade_goods SET quantity = quantity + ? WHERE good_id = ?", (quantity, good_id))
        else:
            if player_quantity < quantity:
                raise ValueError("لا تملك كمية كافية من هذه السلعة.")
            amount = max(1, int(buy_price * sell_factor)) * quantity
            entry_type, counterparty = "trade_sell", "سماسرة أشفيل"
            conn.execute("UPDATE merchant_stock SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP WHERE good_id = ?", (quantity, good_id))
            conn.execute("UPDATE player_trade_goods SET quantity = quantity - ? WHERE good_id = ?", (quantity, good_id))
        entry = _append_ledger_entry(
            conn, amount, entry_type, turn_number=turn_number, counterparty=counterparty, location=location,
            reference_type="trade_good", reference_id=good_id, memo=f"{side}: {quantity} × {name}",
        )
        conn.commit()
        return {"side": side, "good_id": good_id, "name": name, "quantity": quantity, "amount_copper": amount,
                "entry": entry, "wallet": {"balance_copper": entry["balance_after"], "denominations": _denomination_breakdown(entry["balance_after"])}}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_economy_dashboard():
    wallet = get_wallet()
    return {
        "wallet": wallet,
        "ledger": get_ledger_entries(limit=16),
        "market": get_market_goods(),
        "currency_standard": {
            "unit": "نحاس",
            "crown_in_copper": 100,
            "silver_in_copper": 10,
            "policy": "الرصيد يكتب بالنحاس داخل النظام؛ التيجان والفضة والنحاس صيغ عرض فقط.",
        },
    }


def update_player_state(**fields):
    if not fields:
        return
    conn = get_connection()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE player_state SET {set_clause} WHERE id = 1",
        tuple(fields.values())
    )
    conn.commit()
    conn.close()


def get_behavior_scores():
    conn = get_connection()
    rows = conn.execute("SELECT name, value FROM behavior_scores").fetchall()
    conn.close()
    return {name: value for name, value in rows}


def adjust_behavior_score(name, delta):
    if name not in BEHAVIOR_COUNTERS or not delta:
        return
    conn = get_connection()
    conn.execute(
        "UPDATE behavior_scores SET value = MAX(0, MIN(100, value + ?)) WHERE name = ?",
        (delta, name)
    )
    conn.commit()
    conn.close()


def get_factions():
    conn = get_connection()
    rows = conn.execute(
        "SELECT name, trust, fear, loyalty, leverage FROM factions ORDER BY name"
    ).fetchall()
    conn.close()
    return [
        {"name": r[0], "trust": r[1], "fear": r[2], "loyalty": r[3], "leverage": r[4]}
        for r in rows
    ]


def upsert_faction_shift(name, trust=0, fear=0, loyalty=0, leverage=0):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO factions (name) VALUES (?)", (name,)
    )
    conn.execute(
        """
        UPDATE factions SET
            trust = MAX(0, MIN(100, trust + ?)),
            fear = MAX(0, MIN(100, fear + ?)),
            loyalty = MAX(0, MIN(100, loyalty + ?)),
            leverage = MAX(0, MIN(100, leverage + ?))
        WHERE name = ?
        """,
        (trust, fear, loyalty, leverage, name)
    )
    conn.commit()
    conn.close()


def get_retainers():
    conn = get_connection()
    rows = conn.execute(
        "SELECT name, loyalty, morale, trust, respect, status, assignment, location FROM retainers ORDER BY name"
    ).fetchall()
    conn.close()
    return [
        {
            "name": r[0], "loyalty": r[1], "morale": r[2], "trust": r[3],
            "respect": r[4], "status": r[5], "assignment": r[6], "location": r[7]
        }
        for r in rows
    ]


def get_character_directory(language="ar"):
    """Return a read-only directory of known characters and verified presence.

    The registry is the source of identity and presence truth. Atlas lord data and
    retainer metrics are joined when available, while unknown dynamic characters
    remain visible with their canonical campaign text.
    """
    language = "en" if language == "en" else "ar"
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT r.canonical_name, r.character_type, r.home_location, r.home_region,
               r.biography, r.added_turn,
               p.current_location, p.availability, p.destination,
               p.available_at_minute, p.reason,
               wl.slug, wl.title, wl.house, wl.allegiance, wl.disposition,
               wl.public_agenda, wl.secret, wl.discovered,
               rt.loyalty, rt.morale, rt.trust, rt.respect,
               rt.status, rt.assignment
        FROM character_registry r
        LEFT JOIN character_presence p ON p.canonical_name = r.canonical_name
        LEFT JOIN world_lords wl ON wl.name = r.canonical_name
        LEFT JOIN retainers rt ON rt.name = r.canonical_name
        ORDER BY CASE r.character_type
            WHEN 'lord' THEN 0
            WHEN 'retainer' THEN 1
            WHEN 'civic_governor' THEN 2
            ELSE 3 END,
            r.canonical_name
        """
    ).fetchall()
    conn.close()

    location_names_en_reverse = {label: key for key, label in LOCATION_NAMES_EN.items()}

    def local_location(value):
        if not value:
            return value
        if language == "en":
            translated_location = ATLAS_LOCATION_TEXT_EN.get(value)
            if translated_location:
                return translated_location[0]
            return LOCATION_NAMES_EN.get(value, value)
        if value in LOCATION_NAMES_AR:
            return LOCATION_NAMES_AR[value]
        return location_names_en_reverse.get(value, value)

    def local_region(value):
        if not value:
            return value
        if language == "en":
            return REGION_NAMES_EN.get(value, value)
        return REGION_NAMES_AR.get(value, value)

    def local_presence_reason(value):
        if not value:
            return value
        if language == "en":
            return PRESENCE_REASONS_EN.get(value, RETAINER_ASSIGNMENTS_EN.get(value, value))
        return PRESENCE_REASONS_AR.get(value, RETAINER_ASSIGNMENTS_AR.get(value, value))

    def local_assignment(value):
        if not value:
            return value
        if language == "en":
            return RETAINER_ASSIGNMENTS_EN.get(value, value)
        return RETAINER_ASSIGNMENTS_AR.get(value, value)

    def local_character_type(value):
        if not value:
            return value
        labels = CHARACTER_TYPES_EN if language == "en" else CHARACTER_TYPES_AR
        return labels.get(value, value)

    characters = []
    for row in rows:
        (
            canonical_name, character_type, home_location, home_region,
            biography, added_turn, current_location, availability, destination,
            available_at_minute, reason, lord_slug, lord_title, lord_house,
            allegiance, disposition, public_agenda, secret, discovered,
            loyalty, morale, trust, respect, retainer_status, assignment,
        ) = row
        lord_translation = ATLAS_LORDS_EN.get(lord_slug) if language == "en" else None
        display_name = lord_translation.get("name") if lord_translation else canonical_name
        display_title = (lord_translation or {}).get("title") or lord_title or local_character_type(character_type)
        display_house = (lord_translation or {}).get("house") or lord_house or ""
        raw_biography = (lord_translation or {}).get("biography") or biography or ""
        display_biography = raw_biography if lord_translation else local_presence_reason(raw_biography)
        display_agenda = (lord_translation or {}).get("public_agenda") or public_agenda or ""
        display_disposition = (lord_translation or {}).get("disposition") or disposition or ""
        display_secret = (lord_translation or {}).get("secret") or secret or ""
        characters.append({
            "canonical_name": canonical_name,
            "name": display_name,
            "type": character_type,
            "title": display_title,
            "house": display_house,
            "home_location": local_location(home_location),
            "home_region": local_region(home_region),
            "location": local_location(current_location or home_location),
            "availability": availability or "active",
            "destination": local_location(destination),
            "available_at_minute": available_at_minute,
            "available_at": _format_campaign_time(available_at_minute) if available_at_minute is not None else None,
            "reason": local_presence_reason(reason),
            "biography": display_biography,
            "agenda": display_agenda,
            "disposition": display_disposition,
            "secret": display_secret if discovered else "",
            "discovered": bool(discovered) if lord_slug else True,
            "added_turn": added_turn,
            "portrait_slug": lord_slug or "",
            "retainer": {
                "loyalty": loyalty,
                "morale": morale,
                "trust": trust,
                "respect": respect,
                "status": retainer_status,
                "assignment": local_assignment(assignment),
            } if retainer_status is not None else None,
        })
    return characters


def upsert_retainer_shift(name, loyalty=0, morale=0, trust=0, respect=0,
                           assignment=None, location=None, status=None):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO retainers (name) VALUES (?)", (name,)
    )
    conn.execute(
        """
        UPDATE retainers SET
            loyalty = MAX(0, MIN(100, loyalty + ?)),
            morale = MAX(0, MIN(100, morale + ?)),
            trust = MAX(0, MIN(100, trust + ?)),
            respect = MAX(0, MIN(100, respect + ?))
        WHERE name = ?
        """,
        (loyalty, morale, trust, respect, name)
    )
    if assignment is not None:
        conn.execute("UPDATE retainers SET assignment = ? WHERE name = ?", (assignment, name))
    if location is not None:
        conn.execute("UPDATE retainers SET location = ? WHERE name = ?", (location, name))
    if status is not None:
        conn.execute("UPDATE retainers SET status = ? WHERE name = ?", (status, name))
    conn.commit()
    conn.close()


def get_quests(status=None):
    conn = get_connection()
    if status:
        rows = conn.execute(
            "SELECT quest_id, title, description, status, objectives, involved_characters, "
            "involved_factions, location, deadline, discovered_info FROM quests WHERE status = ?",
            (status,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT quest_id, title, description, status, objectives, involved_characters, "
            "involved_factions, location, deadline, discovered_info FROM quests"
        ).fetchall()
    conn.close()
    return [
        {
            "quest_id": r[0], "title": r[1], "description": r[2], "status": r[3],
            "objectives": r[4], "involved_characters": r[5], "involved_factions": r[6],
            "location": r[7], "deadline": r[8], "discovered_info": r[9]
        }
        for r in rows
    ]


def upsert_quest(quest_id, turn_number, **fields):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO quests (quest_id, title) VALUES (?, ?)",
        (quest_id, fields.get("title", quest_id))
    )
    if fields:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(
            f"UPDATE quests SET {set_clause}, updated_turn = ? WHERE quest_id = ?",
            (*fields.values(), turn_number, quest_id)
        )
    conn.commit()
    conn.close()


def get_holdings():
    conn = get_connection()
    rows = conn.execute(
        "SELECT name, prosperity, security, population, wealth, food_supply, "
        "military_strength, loyalty, governor, active_problems FROM holdings ORDER BY name"
    ).fetchall()
    conn.close()
    return [
        {
            "name": r[0], "prosperity": r[1], "security": r[2], "population": r[3],
            "wealth": r[4], "food_supply": r[5], "military_strength": r[6],
            "loyalty": r[7], "governor": r[8], "active_problems": r[9]
        }
        for r in rows
    ]


def upsert_holding_shift(name, **deltas):
    conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO holdings (name) VALUES (?)", (name,))
    numeric_fields = (
        "prosperity", "security", "population", "wealth",
        "food_supply", "military_strength", "loyalty"
    )
    for field in numeric_fields:
        if field in deltas and deltas[field]:
            conn.execute(
                f"UPDATE holdings SET {field} = MAX(0, MIN(100, {field} + ?)) WHERE name = ?",
                (deltas[field], name)
            )
    conn.commit()
    conn.close()


def get_world_clock():
    conn = get_connection()
    row = conn.execute(
        "SELECT absolute_minutes, day, month, year, season, hour, minute FROM world_clock WHERE id = 1"
    ).fetchone()
    conn.close()
    if not row:
        return _calendar_from_minutes(8 * 60)
    clock = _calendar_from_minutes(row[0])
    # Keep persisted calendar values visible for legacy callers while ensuring
    # the minute timestamp is the legal source of truth.
    clock.update({"day": row[1], "month": row[2], "year": row[3], "season": row[4], "hour": row[5], "minute": row[6]})
    clock["display"] = _format_campaign_time(clock["absolute_minutes"])
    return clock


def advance_world_clock(days=1):
    """Compatibility wrapper; new callers should use `advance_campaign_time`."""
    days = max(0, int(days or 0))
    if not days:
        return get_world_clock()
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        before = get_campaign_minutes(conn)
        after = before + days * MINUTES_PER_DAY
        calendar = _calendar_from_minutes(after)
        conn.execute(
            "UPDATE world_clock SET absolute_minutes=?, day=?, month=?, year=?, season=?, hour=?, minute=? WHERE id=1",
            (after, calendar["day"], calendar["month"], calendar["year"], calendar["season"], calendar["hour"], calendar["minute"]),
        )
        conn.commit()
        return calendar
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_event(turn_number, event_type, title, summary, consequences_json):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO event_log (turn_number, event_type, title, summary, consequences)
        VALUES (?, ?, ?, ?, ?)
        """,
        (turn_number, event_type, title, summary, consequences_json)
    )
    conn.commit()
    conn.close()


def get_recent_events(limit=10):
    conn = get_connection()
    rows = conn.execute(
        "SELECT turn_number, event_type, title, summary, consequences, created_at "
        "FROM event_log ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [
        {
            "turn": r[0], "event_type": r[1], "title": r[2],
            "summary": r[3], "consequences": r[4], "created_at": r[5]
        }
        for r in rows
    ]


def get_traits():
    conn = get_connection()
    rows = conn.execute(
        "SELECT key, display_name, description, unlock_turn, unlock_reason FROM traits"
    ).fetchall()
    conn.close()
    return [
        {"key": r[0], "display_name": r[1], "description": r[2], "unlock_turn": r[3], "unlock_reason": r[4]}
        for r in rows
    ]


def unlock_trait(key, display_name, description, turn_number, reason):
    conn = get_connection()
    conn.execute(
        """
        INSERT OR IGNORE INTO traits (key, display_name, description, unlock_turn, unlock_reason)
        VALUES (?, ?, ?, ?, ?)
        """,
        (key, display_name, description, turn_number, reason)
    )
    conn.commit()
    conn.close()


# -----------------------------------------------------------------
# PHASE 4: persistent continental atlas, lore, and political figures
# -----------------------------------------------------------------


def init_phase4_atlas_tables(conn):
    """زرع أطلس ألدينمير بشكل idempotent من دون المساس بتقدم الحملة."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS world_regions (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            x REAL NOT NULL,
            y REAL NOT NULL,
            description TEXT NOT NULL,
            lore TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS world_lords (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            house TEXT,
            seat TEXT,
            region TEXT,
            allegiance TEXT,
            disposition TEXT,
            public_agenda TEXT,
            secret TEXT,
            biography TEXT,
            discovered INTEGER NOT NULL DEFAULT 0,
            added_turn INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS world_lore (
            slug TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            region TEXT,
            era TEXT,
            keywords TEXT,
            body TEXT NOT NULL,
            discovered INTEGER NOT NULL DEFAULT 0,
            added_turn INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS world_factions (
            name TEXT PRIMARY KEY,
            region TEXT,
            description TEXT NOT NULL,
            discovered INTEGER NOT NULL DEFAULT 1
        )
    """)

    for region in REGIONS:
        conn.execute(
            """
            INSERT INTO world_regions (slug, name, kind, x, y, description, lore)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name, kind=excluded.kind, x=excluded.x, y=excluded.y,
                description=excluded.description, lore=excluded.lore
            """,
            (region["slug"], region["name"], region["kind"], region["x"], region["y"], region["description"], region["lore"]),
        )

    for name, region, x, y, description, kind, discovered in LOCATIONS:
        conn.execute(
            """
            INSERT INTO map_locations (name, region, x, y, description, kind, discovered)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                region=excluded.region, x=excluded.x, y=excluded.y,
                description=excluded.description, kind=excluded.kind,
                discovered=MAX(map_locations.discovered, excluded.discovered)
            """,
            (name, region, x, y, description, kind, discovered),
        )

    for lord in LORDS:
        conn.execute(
            """
            INSERT INTO world_lords
            (slug, name, title, house, seat, region, allegiance, disposition, public_agenda, secret, biography, discovered)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name, title=excluded.title, house=excluded.house, seat=excluded.seat,
                region=excluded.region, allegiance=excluded.allegiance, disposition=excluded.disposition,
                public_agenda=excluded.public_agenda, secret=excluded.secret, biography=excluded.biography,
                discovered=MAX(world_lords.discovered, excluded.discovered)
            """,
            (lord["slug"], lord["name"], lord["title"], lord["house"], lord["seat"], lord["region"], lord["allegiance"], lord["disposition"], lord["public_agenda"], lord["secret"], lord["biography"], lord["discovered"]),
        )

    for entry in LORE_ENTRIES:
        conn.execute(
            """
            INSERT INTO world_lore (slug, category, title, region, era, keywords, body, discovered)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                category=excluded.category, title=excluded.title, region=excluded.region, era=excluded.era,
                keywords=excluded.keywords, body=excluded.body,
                discovered=MAX(world_lore.discovered, excluded.discovered)
            """,
            (entry["slug"], entry["category"], entry["title"], entry["region"], entry["era"], entry["keywords"], entry["body"], entry["discovered"]),
        )

    for faction in WORLD_FACTIONS:
        conn.execute(
            """
            INSERT INTO world_factions (name, region, description)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET region=excluded.region, description=excluded.description
            """,
            (faction["name"], faction["region"], faction["description"]),
        )


# PHASE 2: appearance bible, mastery sub-trees, persistent map
# -----------------------------------------------------------------

MASTERY_SPECIALIZATIONS = {
    "weapons_mastery": ["Vanguard Command", "Battlefield Discipline", "Siege Warfare"],
    "dueling_mastery": ["Personal Duelist", "Riposte Doctrine", "Champion's Footwork"],
    "trade_mastery": ["Black Market Procurement", "Maritime Logistics", "Crown Tariffs"],
    "conversation_mastery": ["Royal Court Rhetoric", "Peasant Populism", "Listening for Leverage"],
    "strategy_mastery": ["Campaign Planning", "Countermarch", "Siege Calculus"],
    "leadership_mastery": ["Command Presence", "Rally the Line", "Civic Mandate"],
    "exploration_mastery": ["Trail Reading", "Wilderness Sense", "Hidden Roads"],
    "intrigue_mastery": ["Subterfuge & Secrets", "Counterintelligence", "Whisper Networks"],
}

DEFAULT_MAP_LOCATIONS = [
    # name, region, x, y, description, kind, discovered
    ("Ashvale Hold", "Ashvale", 0.34, 0.51, "Seat of House Mudsbane.", "seat", 1),
    ("Mudroot", "Ashvale", 0.28, 0.58, "Moayed's home village.", "settlement", 1),
    ("Millbrook Crossing", "Ashvale", 0.46, 0.25, "The river crossing where the founding battle took place.", "settlement", 1),
    ("Port of Windmere", "Coast", 0.11, 0.63, "Coastal trade town.", "port", 1),
    ("Halgrove Field", "Southeast Road", 0.62, 0.75, "Seat of allied Lord Halgrove.", "crown", 1),
    ("The Capital", "Crownlands", 0.86, 0.81, "Seat of the crown.", "crown", 1),
    ("The March", "North", 0.62, 0.10, "Kaine's home ground.", "hostile", 1),
    ("Eastern Gentry Lands", "East", 0.72, 0.45, "Minor, unaligned lesser lords.", "unknown", 1),
]


def init_phase2_tables(conn):

    conn.execute("""
        CREATE TABLE IF NOT EXISTS character_appearance (
            name TEXT PRIMARY KEY,
            canonical_appearance TEXT,
            current_outfit TEXT,
            updated_turn INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS mastery_specializations (
            mastery_name TEXT NOT NULL,
            specialization TEXT NOT NULL,
            unlocked INTEGER NOT NULL DEFAULT 0,
            unlocked_turn INTEGER,
            PRIMARY KEY (mastery_name, specialization)
        )
    """)
    for mastery_name, specs in MASTERY_SPECIALIZATIONS.items():
        for spec in specs:
            conn.execute(
                "INSERT OR IGNORE INTO mastery_specializations (mastery_name, specialization) VALUES (?, ?)",
                (mastery_name, spec)
            )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS map_locations (
            name TEXT PRIMARY KEY,
            region TEXT,
            x REAL NOT NULL,
            y REAL NOT NULL,
            description TEXT,
            kind TEXT DEFAULT 'settlement',
            discovered INTEGER NOT NULL DEFAULT 1,
            added_turn INTEGER
        )
    """)
    for name, region, x, y, description, kind, discovered in DEFAULT_MAP_LOCATIONS:
        conn.execute(
            """
            INSERT OR IGNORE INTO map_locations
            (name, region, x, y, description, kind, discovered)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, region, x, y, description, kind, discovered)
        )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'misc',
            quantity INTEGER NOT NULL DEFAULT 1,
            description TEXT,
            equipped INTEGER NOT NULL DEFAULT 0,
            added_turn INTEGER
        )
    """)

    # Additive migration: item stat columns (damage/armor_rating/value/
    # weight/effect/slot) were added after the inventory table already
    # existed for some installs. ALTER TABLE ADD COLUMN only runs for
    # columns that aren't already there, so this never touches existing
    # rows or data.
    existing_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(inventory)").fetchall()
    }
    item_stat_columns = {
        "damage": "INTEGER",
        "armor_rating": "INTEGER",
        "value": "INTEGER DEFAULT 0",
        "weight": "REAL DEFAULT 0",
        "effect": "TEXT",
        "slot": "TEXT",
    }
    for column_name, column_type in item_stat_columns.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE inventory ADD COLUMN {column_name} {column_type}")

    conn.commit()


def get_inventory():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT item_id, name, category, quantity, description, equipped,
               damage, armor_rating, value, weight, effect, slot
        FROM inventory ORDER BY category, name
        """
    ).fetchall()
    conn.close()
    return [
        {
            "item_id": r[0], "name": r[1], "category": r[2],
            "quantity": r[3], "description": r[4], "equipped": bool(r[5]),
            "damage": r[6], "armor_rating": r[7], "value": r[8] or 0,
            "weight": r[9] or 0, "effect": r[10], "slot": r[11],
        }
        for r in rows
    ]


def add_inventory_item(name, category="misc", quantity=1, description="", turn_number=None,
                        damage=None, armor_rating=None, value=0, weight=0.0,
                        effect=None, slot=None):
    conn = get_connection()
    existing = conn.execute(
        "SELECT item_id, quantity FROM inventory WHERE name = ? AND category = ?",
        (name, category)
    ).fetchone()
    if existing:
        # Stacking an item you already have: bump quantity only. Stats
        # on an established item are treated as canon, not overwritten
        # by a second mention.
        conn.execute(
            "UPDATE inventory SET quantity = quantity + ? WHERE item_id = ?",
            (quantity, existing[0])
        )
    else:
        conn.execute(
            """
            INSERT INTO inventory
            (name, category, quantity, description, added_turn,
             damage, armor_rating, value, weight, effect, slot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, category, quantity, description, turn_number,
             damage, armor_rating, value, weight, effect, slot)
        )
    conn.commit()
    conn.close()


def remove_inventory_item(name, quantity=1):
    conn = get_connection()
    existing = conn.execute(
        "SELECT item_id, quantity FROM inventory WHERE name = ?",
        (name,)
    ).fetchone()
    if not existing:
        conn.close()
        return
    item_id, current_qty = existing
    remaining = current_qty - quantity
    if remaining <= 0:
        conn.execute("DELETE FROM inventory WHERE item_id = ?", (item_id,))
    else:
        conn.execute("UPDATE inventory SET quantity = ? WHERE item_id = ?", (remaining, item_id))
    conn.commit()
    conn.close()


DEFAULT_STARTING_EQUIPMENT = [
    # name, category, description, damage, armor_rating, value, weight, effect, slot
    ("Salt-treated Coastal Armor", "armor",
     "Mid-weight armor etched with the Mudsbane sigil, crafted by Mira in Windmere.",
     None, 35, 220, 18.0, None, "chest"),
    ("Mudsbane Longsword", "weapon",
     "A well-balanced main sword forged by Mira, the grey wolf etched into the crossguard.",
     14, None, 180, 6.0, None, "weapon"),
    ("Twin Roothook Daggers", "weapon",
     "A paired set of dual-wield daggers, quick and balanced for close work.",
     8, None, 90, 2.5, None, "offhand"),
]


def seed_starting_equipment_if_empty(turn_number=None):
    """
    Seeds Moayed's known canon equipment (established in the Iron
    Path memories -- Mira's armor and blades from Windmere) if the
    inventory table is currently empty. Safe to call on every
    startup: it only acts when there's nothing there yet, so it
    never duplicates items or overwrites anything a real playthrough
    has already added.
    """
    if get_inventory():
        return

    for name, category, description, damage, armor_rating, value, weight, effect, slot in DEFAULT_STARTING_EQUIPMENT:
        add_inventory_item(
            name, category, 1, description, turn_number,
            damage=damage, armor_rating=armor_rating,
            value=value, weight=weight, effect=effect, slot=slot
        )


def set_item_equipped(item_id, equipped):
    """
    Equips or unequips an item. If equipping, any other equipped item
    in the same slot is automatically unequipped first (one item per
    slot), mirroring how gear slots normally work.
    """
    conn = get_connection()

    if equipped:
        row = conn.execute("SELECT slot FROM inventory WHERE item_id = ?", (item_id,)).fetchone()
        slot = row[0] if row else None
        if slot:
            conn.execute(
                "UPDATE inventory SET equipped = 0 WHERE slot = ? AND item_id != ?",
                (slot, item_id)
            )

    conn.execute(
        "UPDATE inventory SET equipped = ? WHERE item_id = ?",
        (1 if equipped else 0, item_id)
    )
    conn.commit()
    conn.close()
    conn.close()


def get_appearance(name):
    conn = get_connection()
    row = conn.execute(
        "SELECT canonical_appearance, current_outfit FROM character_appearance WHERE name = ?",
        (name,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "name": name,
        "canonical_appearance": json.loads(row[0]) if row[0] else {},
        "current_outfit": json.loads(row[1]) if row[1] else {},
    }


def get_all_appearances():
    conn = get_connection()
    rows = conn.execute(
        "SELECT name, canonical_appearance, current_outfit FROM character_appearance"
    ).fetchall()
    conn.close()
    return [
        {
            "name": r[0],
            "canonical_appearance": json.loads(r[1]) if r[1] else {},
            "current_outfit": json.loads(r[2]) if r[2] else {},
        }
        for r in rows
    ]


def set_canonical_appearance(name, appearance_dict, turn_number):
    """
    Sets the canonical appearance ONLY IF one doesn't already exist,
    or merges new fields into unset ("unknown") slots. Established
    canonical details are never silently overwritten -- call
    update_outfit() for clothing changes instead.
    """
    existing = get_appearance(name)

    if existing and existing["canonical_appearance"]:
        merged = dict(existing["canonical_appearance"])
        for key, value in (appearance_dict or {}).items():
            if not merged.get(key) or merged.get(key) == "unknown":
                merged[key] = value
        final = merged
    else:
        final = appearance_dict or {}

    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO character_appearance (name) VALUES (?)",
        (name,)
    )
    conn.execute(
        "UPDATE character_appearance SET canonical_appearance = ?, updated_turn = ? WHERE name = ?",
        (json.dumps(final), turn_number, name)
    )
    conn.commit()
    conn.close()


def update_outfit(name, outfit_dict, turn_number):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO character_appearance (name) VALUES (?)",
        (name,)
    )
    conn.execute(
        "UPDATE character_appearance SET current_outfit = ?, updated_turn = ? WHERE name = ?",
        (json.dumps(outfit_dict or {}), turn_number, name)
    )
    conn.commit()
    conn.close()


def get_mastery_specializations(mastery_name=None):
    conn = get_connection()
    if mastery_name:
        rows = conn.execute(
            "SELECT mastery_name, specialization, unlocked, unlocked_turn "
            "FROM mastery_specializations WHERE mastery_name = ?",
            (mastery_name,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT mastery_name, specialization, unlocked, unlocked_turn FROM mastery_specializations"
        ).fetchall()
    conn.close()
    return [
        {"mastery_name": r[0], "specialization": r[1], "unlocked": bool(r[2]), "unlocked_turn": r[3]}
        for r in rows
    ]


def unlock_specialization(mastery_name, specialization, turn_number):
    conn = get_connection()
    conn.execute(
        """
        UPDATE mastery_specializations
        SET unlocked = 1, unlocked_turn = ?
        WHERE mastery_name = ? AND specialization = ? AND unlocked = 0
        """,
        (turn_number, mastery_name, specialization)
    )
    changed = conn.total_changes
    conn.commit()
    conn.close()
    return changed > 0


def get_map_locations(discovered_only=True):
    conn = get_connection()
    query = "SELECT name, region, x, y, description, kind, discovered, added_turn FROM map_locations"
    if discovered_only:
        query += " WHERE discovered = 1"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [
        {
            "name": r[0], "region": r[1], "x": r[2], "y": r[3],
            "description": r[4], "kind": r[5], "discovered": bool(r[6]),
            "added_turn": r[7], "dynamic": r[7] is not None,
        }
        for r in rows
    ]


def _atlas_rows(query, params=()):
    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_atlas_data(include_hidden=True, lang="ar"):
    """إرجاع العالم المرئي للواجهة مع تمييز المعرفة المكشوفة عن الأسرار."""
    region_rows = _atlas_rows(
        "SELECT slug, name, kind, x, y, description, lore FROM world_regions ORDER BY name"
    )
    lord_query = (
        "SELECT slug, name, title, house, seat, region, allegiance, disposition, public_agenda, secret, biography, discovered, added_turn "
        "FROM world_lords" + ("" if include_hidden else " WHERE discovered = 1") + " ORDER BY discovered DESC, name"
    )
    lore_query = (
        "SELECT slug, category, title, region, era, keywords, body, discovered, added_turn FROM world_lore" +
        ("" if include_hidden else " WHERE discovered = 1") + " ORDER BY discovered DESC, category, title"
    )
    faction_rows = _atlas_rows("SELECT name, region, description, discovered FROM world_factions ORDER BY name")
    lords = _atlas_rows(lord_query)
    lore = _atlas_rows(lore_query)
    payload = {
        "world": WORLD,
        "history": [{"title": t, "era": e, "summary": s} for t, e, s in HISTORY],
        "regions": [
            {"slug": r[0], "name": r[1], "kind": r[2], "x": r[3], "y": r[4], "description": r[5], "lore": r[6]}
            for r in region_rows
        ],
        "locations": get_map_locations(discovered_only=False),
        "lords": [
            {"slug": r[0], "name": r[1], "title": r[2], "house": r[3], "seat": r[4], "region": r[5],
             "allegiance": r[6], "disposition": r[7], "public_agenda": r[8], "secret": r[9],
             "biography": r[10], "discovered": bool(r[11]), "added_turn": r[12], "dynamic": r[12] is not None}
            for r in lords
        ],
        "lore": [
            {"slug": r[0], "category": r[1], "title": r[2], "region": r[3], "era": r[4], "keywords": r[5],
             "body": r[6], "discovered": bool(r[7]), "added_turn": r[8], "dynamic": r[8] is not None}
            for r in lore
        ],
        "factions": [
            {"name": r[0], "region": r[1], "description": r[2], "discovered": bool(r[3])}
            for r in faction_rows
        ],
    }
    return localize_atlas_payload(payload, "en" if lang == "en" else "ar")


def add_world_lord(slug, name, title, region, turn_number, house="", seat="", allegiance="unknown", disposition="unknown", public_agenda="", secret="", biography="", discovered=False):
    """نقطة إدخال آمنة للورد الذي يولده السرد في المستقبل."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO world_lords
        (slug, name, title, house, seat, region, allegiance, disposition, public_agenda, secret, biography, discovered, added_turn)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET discovered=MAX(world_lords.discovered, excluded.discovered)
        """,
        (slug, name, title, house, seat, region, allegiance, disposition, public_agenda, secret, biography, int(discovered), turn_number),
    )
    conn.commit()
    conn.close()


def add_world_lore(slug, category, title, region, era, keywords, body, turn_number, discovered=True):
    """نقطة إدخال آمنة لاكتشافات السرد الجديدة، من دون الكتابة فوق قانون العالم القائم."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO world_lore (slug, category, title, region, era, keywords, body, discovered, added_turn)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET discovered=MAX(world_lore.discovered, excluded.discovered)
        """,
        (slug, category, title, region, era, keywords, body, int(discovered), turn_number),
    )
    conn.commit()
    conn.close()


def add_map_location(name, region, x, y, description, kind, turn_number, discovered=True):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO map_locations (name, region, x, y, description, kind, discovered, added_turn)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            discovered = excluded.discovered
        """,
        (name, region, x, y, description, kind, int(discovered), turn_number)
    )
    conn.commit()
    conn.close()


def discover_location(name):
    conn = get_connection()
    conn.execute(
        "UPDATE map_locations SET discovered = 1 WHERE name = ?",
        (name,)
    )
    conn.commit()
    conn.close()


def save_memory(scene_id, category, content):

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO memories
        (scene_id, category, content)
        VALUES (?, ?, ?)
        """,
        (scene_id, category, content)
    )

    conn.commit()
    conn.close()


# -----------------------------------------------------------------
# Character stats (weapon mastery, trade mastery, conversation
# mastery, and any custom masteries the player adds).
#
# Leveling curve: level N requires N * 100 xp to advance to N + 1.
# -----------------------------------------------------------------

def get_character_stats():

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT name, display_name, level, xp, description
        FROM character_stats
        ORDER BY id
        """
    ).fetchall()

    conn.close()

    return [
        {
            "name": row[0],
            "display_name": row[1],
            "level": row[2],
            "xp": row[3],
            "xp_needed": row[2] * 100,
            "description": row[4] or ""
        }
        for row in rows
    ]


def get_stat(name):

    stats = get_character_stats()

    for stat in stats:
        if stat["name"] == name:
            return stat

    return None


def add_custom_stat(name, display_name, description=""):

    conn = get_connection()

    conn.execute(
        """
        INSERT OR IGNORE INTO character_stats
        (name, display_name, level, xp, description)
        VALUES (?, ?, 1, 0, ?)
        """,
        (name, display_name, description)
    )

    conn.commit()
    conn.close()


def add_stat_xp(name, amount):
    """
    Adds xp to a named stat, rolling over into level-ups.
    Returns the updated stat dict (with a 'leveled_up' flag)
    or None if the stat doesn't exist.
    """

    conn = get_connection()

    row = conn.execute(
        "SELECT level, xp FROM character_stats WHERE name = ?",
        (name,)
    ).fetchone()

    if not row:
        conn.close()
        return None

    level, xp = row
    xp += amount

    leveled_up = False

    while xp >= level * 100:
        xp -= level * 100
        level += 1
        leveled_up = True

    conn.execute(
        """
        UPDATE character_stats
        SET level = ?, xp = ?, updated_at = CURRENT_TIMESTAMP
        WHERE name = ?
        """,
        (level, xp, name)
    )

    conn.commit()
    conn.close()

    return {
        "name": name,
        "level": level,
        "xp": xp,
        "leveled_up": leveled_up
    }


def set_stat_level(name, level):

    conn = get_connection()

    conn.execute(
        "UPDATE character_stats SET level = ?, xp = 0 WHERE name = ?",
        (level, name)
    )

    conn.commit()
    conn.close()

# -----------------------------------------------------------------
# PHASE 3: military core — armies, battles, loot
#
# Design principle (per the architecture review): the database is
# authoritative for troop counts and casualties. Gemini never picks
# these numbers -- it can only signal that a battle happened (via
# state_evaluator's battle_trigger), and military.py's resolve_battle()
# computes the actual math deterministically. This keeps combat
# numbers consistent across turns even 100+ turns later, instead of
# depending on the model "remembering" what it said.
# -----------------------------------------------------------------

def init_phase3_tables(conn):

    conn.execute("""
        CREATE TABLE IF NOT EXISTS armies (
            army_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            faction TEXT,
            location TEXT,
            total_troops INTEGER NOT NULL DEFAULT 0,
            wounded_troops INTEGER NOT NULL DEFAULT 0,
            morale INTEGER NOT NULL DEFAULT 70,
            organization INTEGER NOT NULL DEFAULT 70,
            food_days INTEGER NOT NULL DEFAULT 14,
            commander TEXT,
            status TEXT DEFAULT 'active',
            updated_turn INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS battles (
            battle_id INTEGER PRIMARY KEY AUTOINCREMENT,
            turn_number INTEGER,
            location TEXT,
            attacker_name TEXT,
            defender_name TEXT,
            attacker_start INTEGER,
            defender_start INTEGER,
            attacker_end INTEGER,
            defender_end INTEGER,
            attacker_casualties INTEGER,
            defender_casualties INTEGER,
            victor TEXT,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS loot_piles (
            loot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            battle_id INTEGER,
            location TEXT,
            gold INTEGER DEFAULT 0,
            items_json TEXT,
            claimed INTEGER NOT NULL DEFAULT 0,
            created_turn INTEGER
        )
    """)

    conn.commit()


def get_armies():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT army_id, name, faction, location, total_troops, wounded_troops,
               morale, organization, food_days, commander, status
        FROM armies ORDER BY name
        """
    ).fetchall()
    conn.close()
    return [
        {
            "army_id": r[0], "name": r[1], "faction": r[2], "location": r[3],
            "total_troops": r[4], "wounded_troops": r[5], "morale": r[6],
            "organization": r[7], "food_days": r[8], "commander": r[9], "status": r[10]
        }
        for r in rows
    ]


def get_army_by_name(name):
    for army in get_armies():
        if army["name"].lower() == name.lower():
            return army
    return None


def upsert_army(name, turn_number, **fields):
    """
    Creates the army if it doesn't exist, or applies DELTAS to
    total_troops/wounded_troops/morale/organization/food_days if
    given (positional changes, not absolute overwrites) -- so a
    battle applying "-37 troops" doesn't require re-reading the
    current count first. Non-numeric fields (location, commander,
    status, faction) are set directly, not delta'd.

    On the call that actually CREATES the army (first mention), the
    numeric fields are treated as absolute starting values instead
    of deltas -- otherwise a fresh army starting from schema defaults
    (0 troops, 70 morale) plus a delta would land somewhere the
    caller never intended.
    """
    conn = get_connection()
    cursor = conn.execute(
        "INSERT OR IGNORE INTO armies (name, updated_turn) VALUES (?, ?)",
        (name, turn_number)
    )
    just_created = cursor.rowcount > 0

    delta_fields = ("total_troops", "wounded_troops", "morale", "organization", "food_days")
    for field in delta_fields:
        if field in fields and fields[field]:
            floor = 0
            ceiling = 999999 if field in ("total_troops", "wounded_troops", "food_days") else 100
            if just_created:
                clamped = max(floor, min(ceiling, fields[field]))
                conn.execute(f"UPDATE armies SET {field} = ? WHERE name = ?", (clamped, name))
            else:
                conn.execute(
                    f"UPDATE armies SET {field} = MAX({floor}, MIN({ceiling}, {field} + ?)) WHERE name = ?",
                    (fields[field], name)
                )

    direct_fields = ("location", "commander", "status", "faction")
    for field in direct_fields:
        if field in fields and fields[field] is not None:
            conn.execute(f"UPDATE armies SET {field} = ? WHERE name = ?", (fields[field], name))

    conn.execute("UPDATE armies SET updated_turn = ? WHERE name = ?", (turn_number, name))
    conn.commit()
    conn.close()


def record_battle(turn_number, location, attacker_name, defender_name,
                   attacker_start, defender_start, attacker_end, defender_end,
                   attacker_casualties, defender_casualties, victor, summary):
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO battles
        (turn_number, location, attacker_name, defender_name,
         attacker_start, defender_start, attacker_end, defender_end,
         attacker_casualties, defender_casualties, victor, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (turn_number, location, attacker_name, defender_name,
         attacker_start, defender_start, attacker_end, defender_end,
         attacker_casualties, defender_casualties, victor, summary)
    )
    battle_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return battle_id


def get_battles(limit=20):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT battle_id, turn_number, location, attacker_name, defender_name,
               attacker_start, defender_start, attacker_end, defender_end,
               attacker_casualties, defender_casualties, victor, summary
        FROM battles ORDER BY battle_id DESC LIMIT ?
        """,
        (limit,)
    ).fetchall()
    conn.close()
    return [
        {
            "battle_id": r[0], "turn": r[1], "location": r[2],
            "attacker_name": r[3], "defender_name": r[4],
            "attacker_start": r[5], "defender_start": r[6],
            "attacker_end": r[7], "defender_end": r[8],
            "attacker_casualties": r[9], "defender_casualties": r[10],
            "victor": r[11], "summary": r[12]
        }
        for r in rows
    ]


def create_loot_pile(battle_id, location, gold, items, turn_number):
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO loot_piles (battle_id, location, gold, items_json, created_turn)
        VALUES (?, ?, ?, ?, ?)
        """,
        (battle_id, location, gold, json.dumps(items or []), turn_number)
    )
    loot_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return loot_id


def get_loot_piles(unclaimed_only=False):
    conn = get_connection()
    query = "SELECT loot_id, battle_id, location, gold, items_json, claimed, created_turn FROM loot_piles"
    if unclaimed_only:
        query += " WHERE claimed = 0"
    query += " ORDER BY loot_id DESC"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [
        {
            "loot_id": r[0], "battle_id": r[1], "location": r[2], "gold": r[3],
            "items": json.loads(r[4]) if r[4] else [], "claimed": bool(r[5]), "created_turn": r[6]
        }
        for r in rows
    ]


def claim_loot_pile(loot_id, turn_number=None):
    """Claims a loot pile exactly once and posts its currency to the ledger atomically."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT gold, items_json FROM loot_piles WHERE loot_id = ? AND claimed = 0",
            (loot_id,),
        ).fetchone()
        if not row:
            conn.rollback()
            return None

        gold, items_json = int(row[0] or 0), row[1]
        items = json.loads(items_json) if items_json else []
        conn.execute("UPDATE loot_piles SET claimed = 1 WHERE loot_id = ? AND claimed = 0", (loot_id,))
        wallet = None
        if gold:
            entry = _append_ledger_entry(
                conn, gold, "battle_loot", turn_number=turn_number, counterparty="غنائم ساحة القتال",
                reference_type="loot_pile", reference_id=str(loot_id), memo="تحصيل غنيمة عسكرية",
                idempotency_key=f"loot-pile-{loot_id}",
            )
            wallet = {"balance_copper": entry["balance_after"], "denominations": _denomination_breakdown(entry["balance_after"])}

        for item in items:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            name, category = str(item["name"])[:100], str(item.get("category", "misc"))[:20]
            quantity, description = max(1, int(item.get("quantity", 1))), str(item.get("description", ""))[:200]
            existing = conn.execute("SELECT item_id FROM inventory WHERE name = ? AND category = ?", (name, category)).fetchone()
            if existing:
                conn.execute("UPDATE inventory SET quantity = quantity + ? WHERE item_id = ?", (quantity, existing[0]))
            else:
                conn.execute("INSERT INTO inventory (name, category, quantity, description, added_turn) VALUES (?, ?, ?, ?, ?)", (name, category, quantity, description, turn_number))
        conn.commit()
        return {"gold": gold, "items": items, "wallet": wallet or get_wallet()}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# -----------------------------------------------------------------
# PHASE 3b: character scene index
#
# For each scene, tracks which characters were actually PRESENT
# (active on the page) versus merely MENTIONED (referenced but not
# there). This gives Gemini a character's real appearance history to
# check against, instead of relying only on keyword-scored memory
# search, which can miss things a character-specific lookup wouldn't.
# -----------------------------------------------------------------

def init_phase3b_tables(conn):

    conn.execute("""
        CREATE TABLE IF NOT EXISTS character_mentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_name TEXT NOT NULL,
            scene_id INTEGER NOT NULL,
            turn_number INTEGER,
            role TEXT DEFAULT 'mentioned',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(scene_id) REFERENCES scenes(id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_character_mentions_name
        ON character_mentions(character_name)
    """)

    conn.commit()


def record_character_mention(character_name, scene_id, turn_number, role="mentioned"):
    character_name = (character_name or "").strip()
    if not character_name:
        return

    conn = get_connection()

    # Avoid duplicate rows for the same character in the same scene;
    # "present" should win over "mentioned" if both get recorded.
    existing = conn.execute(
        "SELECT id, role FROM character_mentions WHERE character_name = ? AND scene_id = ?",
        (character_name, scene_id)
    ).fetchone()

    if existing:
        if role == "present" and existing[1] != "present":
            conn.execute(
                "UPDATE character_mentions SET role = ? WHERE id = ?",
                (role, existing[0])
            )
            conn.commit()
    else:
        conn.execute(
            """
            INSERT INTO character_mentions (character_name, scene_id, turn_number, role)
            VALUES (?, ?, ?, ?)
            """,
            (character_name, scene_id, turn_number, role)
        )
        conn.commit()

    conn.close()


def get_character_scene_history(character_name, limit=20):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT character_mentions.turn_number, character_mentions.role,
               scenes.player_action, scenes.ai_response
        FROM character_mentions
        JOIN scenes ON character_mentions.scene_id = scenes.id
        WHERE character_mentions.character_name = ?
        ORDER BY character_mentions.turn_number ASC
        LIMIT ?
        """,
        (character_name, limit)
    ).fetchall()
    conn.close()
    return [
        {
            "turn": r[0], "role": r[1],
            "player_action": r[2], "ai_response": r[3]
        }
        for r in rows
    ]


def get_known_character_names():
    """
    All distinct character names the game currently knows about, from
    every source that names one: appearance records, retainers,
    CHARACTER-category memories (parsed using the "Name: fact"
    convention that extract_memories/seed_story.py both use), and
    anything already logged in character_mentions. Used to detect
    which characters a new player action is actually about.
    """
    conn = get_connection()
    names = set()

    for row in conn.execute("SELECT name FROM character_appearance"):
        names.add(row[0])
    for row in conn.execute("SELECT name FROM retainers"):
        names.add(row[0])
    for row in conn.execute("SELECT DISTINCT character_name FROM character_mentions"):
        names.add(row[0])

    for row in conn.execute(
        "SELECT DISTINCT content FROM memories WHERE category = 'CHARACTER'"
    ):
        content = row[0] or ""
        if ":" in content:
            candidate = content.split(":", 1)[0].strip()
            # Guard against overly long "names" from malformed entries
            # (a real name is a handful of words, not a full sentence).
            if candidate and len(candidate) <= 40 and len(candidate.split()) <= 5:
                names.add(candidate)

    conn.close()
    return sorted(n for n in names if n)


def backfill_character_mentions_from_scenes():
    """
    One-time (safe to re-run) scan of existing scenes against the
    known character-name list, so scenes written before this feature
    existed still get indexed. Retroactive matches are always marked
    'mentioned' (not 'present') since we can't reliably tell the
    difference from text alone after the fact -- going forward, the
    state evaluator marks this properly per turn.
    """
    conn = get_connection()
    scenes = conn.execute(
        "SELECT id, turn_number, player_action, ai_response FROM scenes"
    ).fetchall()
    conn.close()

    names = get_known_character_names()
    if not names or not scenes:
        return 0

    added = 0
    for scene_id, turn_number, player_action, ai_response in scenes:
        combined = f"{player_action}\n{ai_response}".lower()
        for name in names:
            first_name = name.split()[0].lower()
            if len(first_name) >= 3 and first_name in combined:
                before = get_connection()
                exists = before.execute(
                    "SELECT 1 FROM character_mentions WHERE character_name = ? AND scene_id = ?",
                    (name, scene_id)
                ).fetchone()
                before.close()
                if not exists:
                    record_character_mention(name, scene_id, turn_number, role="mentioned")
                    added += 1

    return added


# -----------------------------------------------------------------
# One-time backfill: populate the structured Phase 1-3 tables
# (retainers, factions, quests, holdings, one garrison army, a few
# event-log entries) from what's ACTUALLY established in the seeded
# Iron Path canon (scenes + CHARACTER/WORLD/QUEST/EVENT memories).
#
# This is deliberately conservative: numbers are either (a) directly
# stated in the source text (e.g. "roughly forty-three soldiers"),
# or (b) a moderate, clearly-inferred default consistent with how
# the story describes things (a stable, well-governed hold). Nothing
# here invents precise figures the story never established. Player
# behavior_scores and mastery levels are intentionally left alone --
# inferring "how diplomatic was this playthrough" from a compressed
# scene log is too interpretive to state as fact.
#
# Idempotent: skips entirely if retainers are already populated, so
# it's safe to call on every startup.
# -----------------------------------------------------------------

def backfill_structured_state_from_canon():
    if get_retainers():
        return False  # already backfilled (or organically populated) -- do nothing

    # ---------------- retainers ----------------
    # (loyalty, morale, trust, respect, assignment, location) --
    # values are moderate defaults reflecting an established, loyal
    # inner circle; not stated as exact numbers anywhere in canon.
    # Set directly as absolute starting values (upsert_retainer_shift
    # is delta-only and would stack on top of schema defaults).
    retainer_seed = [
        ("Isolde", 85, 80, 90, 85, "Spy network & diplomacy", "Ashvale Hold"),
        ("Wren", 90, 85, 85, 80, "Archery training", "Ashvale Hold"),
        ("Edrin", 80, 75, 75, 70, "Ward, training in archery and swordsmanship", "Ashvale Hold"),
        ("Harn", 85, 80, 85, 80, "Internal affairs: walls, food, village outreach", "Ashvale Hold"),
        ("Doss", 80, 75, 75, 80, "Garrison commander", "Ashvale Hold"),
        ("Corren", 85, 75, 80, 75, "Riding to the Capital with defector evidence", "En route to the Capital"),
        ("Tomas", 80, 70, 80, 75, "Leads Roots, operating against Kaine in the March", "The March"),
        ("Maren", 75, 75, 75, 80, "Village elder, community counsel", "Mudroot"),
        ("Mira", 60, 70, 65, 70, "Master blacksmith, relocating her forge to Ashvale", "Windmere (relocating)"),
        ("Beck", 55, 60, 50, 45, "Pardoned soldier, integrated into the garrison under Doss", "Ashvale Hold"),
    ]
    conn = get_connection()
    for name, loyalty, morale, trust, respect, assignment, location in retainer_seed:
        conn.execute("INSERT OR IGNORE INTO retainers (name) VALUES (?)", (name,))
        conn.execute(
            """
            UPDATE retainers SET
                loyalty = ?, morale = ?, trust = ?, respect = ?,
                assignment = ?, location = ?
            WHERE name = ?
            """,
            (loyalty, morale, trust, respect, assignment, location, name)
        )
    conn.commit()
    conn.close()

    # ---------------- factions ----------------
    # trust/fear/loyalty/leverage reflecting the established
    # relationship state at Turn 170 -- moderate values, not exact
    # canon numbers (none were ever stated). Set directly as absolute
    # starting values (upsert_faction_shift is delta-only and would
    # stack on top of schema defaults instead of setting them).
    faction_seed = [
        ("Windmere", 65, 5, 30, 20),
        ("Salt Compact", 60, 10, 20, 35),
        ("House Voss", 55, 0, 10, 5),
        ("House Halgrove", 70, 0, 40, 10),
        ("Crown of Aldenmere", 60, 5, 15, 10),
    ]
    conn = get_connection()
    for name, trust, fear, loyalty, leverage in faction_seed:
        conn.execute("INSERT OR IGNORE INTO factions (name) VALUES (?)", (name,))
        conn.execute(
            "UPDATE factions SET trust = ?, fear = ?, loyalty = ?, leverage = ? WHERE name = ?",
            (trust, fear, loyalty, leverage, name)
        )
    conn.commit()
    conn.close()

    # ---------------- holdings ----------------
    # Same absolute-vs-delta fix as above.
    conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO holdings (name) VALUES (?)", ("Ashvale Hold",))
    conn.execute(
        """
        UPDATE holdings SET
            prosperity = 68, security = 62, food_supply = 70,
            military_strength = 55, loyalty = 75, governor = ?
        WHERE name = ?
        """,
        ("Harn", "Ashvale Hold")
    )
    conn.commit()
    conn.close()

    # ---------------- quests ----------------
    quest_seed = [
        ("ashvale_claim", "Claim to Ashvale Hold",
         "The crown formally recognized Moayed's claim to Ashvale hold and referred Kaine to the crown council.",
         "completed"),
        ("kaines_hearing", "Kaine's Crown Hearing",
         "Kaine bribed an undersecretary to move his hearing up to five days, trying to outrun the evidence against him.",
         "active"),
        ("corren_capital_ride", "Corren's Ride to the Capital",
         "Corren rides hard for the capital with defector ledgers and witness affidavits before the hearing closes.",
         "active"),
        ("roots_operation", "Roots' Operation Against Kaine",
         "Tomas and Roots operate in the March against Kaine's exposed weakness, with the exact action left to their judgment.",
         "active"),
        ("windmere_ratification", "Windmere Trade Ratification",
         "The timber/shipbuilding/salt trade agreement with Windmere and the Salt Compact awaits council ratification.",
         "active"),
        ("mira_relocation", "Mira's Relocation",
         "Master blacksmith Mira is relocating her forge from Windmere to Ashvale hold.",
         "active"),
        ("wren_edrin_betrothal", "Wren & Edrin's Betrothal",
         "Wren and Edrin remain betrothed but unmarried, both asking to be genuinely consulted when it's arranged.",
         "active"),
        ("third_saboteur", "The Third Saboteur",
         "A captured saboteur is held alive in the dungeon as a potential source or bargaining piece.",
         "active"),
        ("continental_ambition", "Long-Term Ambition: Continental Power",
         "Moayed's private ambition, confessed only to Isolde: to eventually become emperor of the continent, beginning with a trade state.",
         "active"),
    ]
    for quest_id, title, description, status in quest_seed:
        upsert_quest(quest_id, 170, title=title, description=description, status=status)

    # ---------------- armies ----------------
    # 150 is a reasoned estimate, not a stated exact number -- but
    # it's grounded in EVERY troop source the story actually
    # establishes, not just the two easiest ones to count:
    #   ~70  original Ashvale garrison, surrendered intact at the
    #        Baron's fall (Turn 50) and absorbed as "the core of a
    #        new garrison"
    #   ~25  Doss's surviving mercenary company from before the
    #        mutiny ("his broken company")
    #   ~43  mercenary defectors from Kaine's column (the one hard
    #        number the text gives directly)
    #   ~6   Beck and his five pardoned men
    #   ~6   rounding / militia contribution from the five villages
    #        that pledged loyalty at Turn 90
    # These sum to ~150. Still an estimate, since no turn ever musters
    # the whole garrison at once -- but it accounts for every
    # established source instead of only the two most explicit ones.
    upsert_army(
        "Ashvale Garrison", 170,
        total_troops=150, morale=65, organization=60, food_days=14,
        location="Ashvale Hold", commander="Doss", faction="player", status="active"
    )

    # ---------------- event log ----------------
    # A handful of the clearest discrete EVENT memories, tied to the
    # scene checkpoint turns they actually happened at.
    event_seed = [
        (50, "EVENT", "Fall of Ashvale Hold",
         "Moayed personally killed Baron Corvin Ashvale and seized Ashvale hold."),
        (70, "EVENT", "Mercenary Mutiny",
         "Kaine's mercenary column was made to mutiny; roughly forty-three soldiers, including Corren, defected."),
        (130, "EVENT", "Crown Recognizes Ashvale Claim",
         "The crown formally recognized Moayed's claim and referred Kaine to the crown council for conspiracy."),
        (140, "EVENT", "Roots Formed",
         "A six-man deniable operations squad, Roots, was formed under Tomas after Kaine's men sabotaged the granary."),
        (150, "EVENT", "Windmere Dockside Standoff Resolved",
         "A confrontation with Salt Compact soldiers at Windmere was resolved through negotiation, winning trade terms and a favor."),
        (170, "EVENT", "Kaine Flees, Hearing Moved Up",
         "Kaine's hearing was moved up through bribery and he fled his own seat with a small escort."),
    ]
    for turn, event_type, title, summary in event_seed:
        log_event(turn, event_type, title, summary, "{}")

    return True


def fix_garrison_undercount():
    """
    One-off correction: an earlier version of the backfill only
    counted the ~43 mutiny defectors and Beck's 5 men toward the
    Ashvale Garrison's troop count (48 total), missing the original
    Ashvale garrison itself, Doss's pre-mutiny company, and village
    militia contributions -- all separately established in canon.
    Corrects an existing garrison entry still showing that undercount
    up to the more complete ~150 estimate. Safe to call on every
    startup: only acts if the old wrong value is still present, so it
    naturally becomes a no-op forever after the first correct run.
    """
    army = get_army_by_name("Ashvale Garrison")
    if army and army["total_troops"] == 48:
        conn = get_connection()
        conn.execute(
            "UPDATE armies SET total_troops = 150 WHERE name = ?",
            ("Ashvale Garrison",)
        )
        conn.commit()
        conn.close()
        return True
    return False


# -----------------------------------------------------------------
# PHASE 7: character presence, movement, and historically grounded context
# -----------------------------------------------------------------


def _normalise_character_token(value):
    """Normalise Arabic/Latin name variants for alias lookups only."""
    text = str(value or "").strip().casefold()
    text = re.sub(r"[ًٌٍَُِّْـ]", "", text)
    text = text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ڤ": "ف", "گ": "ك"}))
    return re.sub(r"[^\w\s]", "", text).strip()


def init_phase7_presence_tables(conn):
    """Create the legal character-presence ledger and seed it from canon."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS character_registry (
            canonical_name TEXT PRIMARY KEY,
            character_type TEXT NOT NULL DEFAULT 'named_npc',
            home_location TEXT,
            home_region TEXT,
            biography TEXT,
            added_turn INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS character_aliases (
            alias_key TEXT PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            FOREIGN KEY(canonical_name) REFERENCES character_registry(canonical_name)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS character_presence (
            canonical_name TEXT PRIMARY KEY,
            current_location TEXT,
            availability TEXT NOT NULL DEFAULT 'active'
                CHECK (availability IN ('active', 'traveling', 'remote', 'captured', 'missing', 'dead')),
            destination TEXT,
            available_turn INTEGER NOT NULL DEFAULT 0,
            reason TEXT,
            updated_turn INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(canonical_name) REFERENCES character_registry(canonical_name)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS character_movements (
            movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT NOT NULL,
            from_location TEXT,
            to_location TEXT NOT NULL,
            depart_turn INTEGER NOT NULL,
            arrival_turn INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'arrived', 'cancelled')),
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(canonical_name) REFERENCES character_registry(canonical_name)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_character_movements_active ON character_movements(canonical_name, status, arrival_turn)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS campaign_context (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_location TEXT NOT NULL DEFAULT 'Ashvale Hold',
            updated_turn INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT OR IGNORE INTO campaign_context (id, current_location) VALUES (1, 'Ashvale Hold')")
    sync_character_registry(conn)
    conn.commit()


def _registry_upsert(conn, canonical_name, character_type, home_location=None, home_region=None, biography=None, aliases=(), added_turn=0):
    canonical_name = str(canonical_name or "").strip()[:90]
    if not canonical_name:
        return None
    conn.execute(
        """INSERT INTO character_registry (canonical_name, character_type, home_location, home_region, biography, added_turn)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(canonical_name) DO UPDATE SET
             character_type=excluded.character_type,
             home_location=COALESCE(character_registry.home_location, excluded.home_location),
             home_region=COALESCE(character_registry.home_region, excluded.home_region),
             biography=COALESCE(character_registry.biography, excluded.biography)""",
        (canonical_name, character_type, home_location, home_region, biography, int(added_turn or 0)),
    )
    for alias in set((canonical_name, *aliases)):
        alias_key = _normalise_character_token(alias)
        if alias_key:
            conn.execute(
                "INSERT OR IGNORE INTO character_aliases (alias_key, canonical_name) VALUES (?, ?)",
                (alias_key, canonical_name),
            )
    return canonical_name


def sync_character_registry(conn=None):
    """Idempotently map retainers, atlas lords, and civic governors into legal identities."""
    owns_connection = conn is None
    conn = conn or get_connection()
    retainers = conn.execute("SELECT name, status, location, assignment FROM retainers").fetchall()
    retainer_by_first = {str(row[0]).split()[0].casefold(): row for row in retainers if row[0]}
    for name, status, location, assignment in retainers:
        canonical = _registry_upsert(conn, name, "retainer", location, None, assignment, aliases=(name,))
        conn.execute(
            """INSERT OR IGNORE INTO character_presence
               (canonical_name, current_location, availability, reason, updated_turn)
               VALUES (?, ?, ?, ?, 0)""",
            (canonical, location or "Ashvale Hold", status if status in {"active", "traveling", "remote", "captured", "missing", "dead"} else "active", assignment),
        )
    for name, seat, region, biography in conn.execute("SELECT name, seat, region, biography FROM world_lords"):
        canonical = _registry_upsert(conn, name, "lord", seat, region, biography, aliases=(name,))
        conn.execute(
            "INSERT OR IGNORE INTO character_presence (canonical_name, current_location, availability, reason, updated_turn) VALUES (?, ?, 'active', 'atlas seat', 0)",
            (canonical, seat or "Unknown"),
        )
    for location, governor_ar, governor_en in conn.execute("SELECT location, governor_ar, governor_en FROM civic_profiles"):
        match = retainer_by_first.get(str(governor_en).split()[0].casefold())
        canonical = str(match[0]) if match else str(governor_en or governor_ar)
        canonical = _registry_upsert(conn, canonical, "civic_governor", location, None, None, aliases=(governor_en, governor_ar))
        conn.execute(
            "INSERT OR IGNORE INTO character_presence (canonical_name, current_location, availability, reason, updated_turn) VALUES (?, ?, 'active', 'civic office', 0)",
            (canonical, location),
        )
    if owns_connection:
        conn.commit()
        conn.close()


def get_campaign_location():
    conn = get_connection()
    row = conn.execute("SELECT current_location, updated_turn FROM campaign_context WHERE id = 1").fetchone()
    conn.close()
    return {"location": row[0], "updated_turn": row[1]} if row else {"location": "Ashvale Hold", "updated_turn": 0}


def _complete_due_movements(conn, current_minutes=None):
    """Complete only movements whose internal arrival time has actually passed."""
    current_minutes = get_campaign_minutes(conn) if current_minutes is None else int(current_minutes)
    due = conn.execute(
        "SELECT movement_id, canonical_name, to_location FROM character_movements WHERE status = 'planned' AND arrival_at_minute <= ?",
        (current_minutes,),
    ).fetchall()
    for movement_id, canonical_name, to_location in due:
        conn.execute("UPDATE character_movements SET status = 'arrived' WHERE movement_id = ?", (movement_id,))
        conn.execute(
            """UPDATE character_presence SET current_location = ?, availability = 'active', destination = NULL,
               available_at_minute = ?, reason = 'arrived', updated_at_minute = ?, updated_at = CURRENT_TIMESTAMP
               WHERE canonical_name = ?""",
            (to_location, current_minutes, current_minutes, canonical_name),
        )


def resolve_character_name(name):
    key = _normalise_character_token(name)
    if not key:
        return None
    conn = get_connection()
    row = conn.execute("SELECT canonical_name FROM character_aliases WHERE alias_key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else None


def _referenced_characters(action):
    action_key = _normalise_character_token(action)
    if not action_key:
        return []
    conn = get_connection()
    rows = conn.execute("SELECT alias_key, canonical_name FROM character_aliases").fetchall()
    conn.close()
    found = []
    padded = f" {action_key} "
    for alias_key, canonical_name in rows:
        if len(alias_key) >= 3 and (f" {alias_key} " in padded or alias_key in action_key):
            if canonical_name not in found:
                found.append(canonical_name)
    return found[:8]


def _direct_interaction_requested(action):
    text = _normalise_character_token(action)
    terms = ("قابل", "تحدث", "استدعي", "استدع", "اطلب حضور", "واجه", "اسال", "meet", "speak", "summon", "call", "confront", "ask")
    return any(term in text for term in terms)


def _remote_contact_requested(action):
    text = _normalise_character_token(action)
    terms = ("رساله", "ارسل", "مراسل", "خطاب", "message", "letter", "send word", "envoy")
    return any(term in text for term in terms)


def get_interaction_preflight(player_action, turn_number=None):
    """Return a deterministic verdict before a narrative model may stage a meeting.

    `turn_number` remains accepted for legacy call sites, but availability is
    determined exclusively by the campaign's internal timestamp.
    """
    sync_character_registry()
    referenced = _referenced_characters(player_action)
    if not referenced:
        return {"blocked": False, "targets": [], "campaign": get_campaign_location(), "message": None}
    campaign = get_campaign_location()
    conn = get_connection()
    current_minutes = get_campaign_minutes(conn)
    _complete_due_movements(conn, current_minutes)
    rows = []
    for canonical in referenced:
        row = conn.execute(
            """SELECT r.canonical_name, r.character_type, r.home_location, r.home_region, r.biography,
                      p.current_location, p.availability, p.destination, p.available_at_minute, p.reason
               FROM character_registry r JOIN character_presence p ON p.canonical_name = r.canonical_name
               WHERE r.canonical_name = ?""",
            (canonical,),
        ).fetchone()
        if row:
            rows.append({"name": row[0], "type": row[1], "home_location": row[2], "home_region": row[3], "biography": row[4],
                         "location": row[5], "availability": row[6], "destination": row[7], "available_at_minute": row[8],
                         "available_at": _format_campaign_time(row[8]), "reason": row[9]})
    conn.commit()
    conn.close()
    wants_direct = _direct_interaction_requested(player_action)
    wants_remote = _remote_contact_requested(player_action)
    blocked_targets = []
    if wants_direct and not wants_remote:
        for target in rows:
            legal = target["availability"] == "active" and target["location"] == campaign["location"]
            if not legal:
                blocked_targets.append(target)
    message = None
    if blocked_targets:
        details = "; ".join(
            f"{target['name']} is {target['availability']} at {target['location'] or 'an unknown location'}"
            + (f" and is expected at {target['destination']} around {target['available_at']}" if target.get("destination") else "")
            for target in blocked_targets
        )
        message = f"A direct meeting cannot occur yet: {details}. A message, envoy, or journey may be attempted instead."
    return {"blocked": bool(blocked_targets), "targets": rows, "campaign": campaign, "message": message, "remote": wants_remote}


def build_character_history_context(player_action, turn_number=None, scene_limit=80):
    """Build model context from verified identity, presence, all public wars, and recorded personal scenes."""
    preflight = get_interaction_preflight(player_action, turn_number)
    clock = get_world_clock()
    targets = preflight["targets"]
    wars = get_historical_wars("en")
    war_text = "\n".join(f"- {war['year']} | {war['name']}: {war['summary']} Legacy: {war['legacy']} Regions: {war['regions']}" for war in wars)
    blocks = [
        "VERIFIED CAMPAIGN POSITION: " + preflight["campaign"]["location"] + " | CURRENT INTERNAL TIME: " + clock["display"],
        "PUBLIC KINGDOM HISTORY (authoritative):\n" + (war_text or "No historical wars are registered."),
    ]
    for target in targets:
        history = get_character_scene_history(target["name"], limit=scene_limit)
        scenes = []
        for item in history:
            action = str(item["player_action"] or "")[:280]
            response = str(item["ai_response"] or "")[:520]
            scenes.append(f"Scene #{item['turn']} [{item['role']}]: Player={action} | Outcome={response}")
        availability = f"{target['availability']} at {target['location'] or 'unknown'}"
        if target.get("destination"):
            availability += f"; destination {target['destination']} expected around {target['available_at']}"
        blocks.append(
            f"CHARACTER DOSSIER — {target['name']} ({target['type']}):\n"
            f"Home: {target['home_location'] or 'unknown'}; Region: {target['home_region'] or 'unknown'}; {availability}.\n"
            f"Biography/role: {target['biography'] or target['reason'] or 'No additional biography recorded.'}\n"
            f"Complete recorded scene history ({len(history)} records):\n" + ("\n".join(scenes) or "No prior scene record.")
        )
    if preflight["blocked"]:
        blocks.append("HARD PRESENCE RULE: " + preflight["message"] + " Do not narrate the blocked character as physically present.")
    elif targets:
        blocks.append("HARD PRESENCE RULE: Only characters marked active at the verified campaign position may be physically present. Others may be mentioned or contacted remotely only when the player explicitly uses a remote channel.")
    return "\n\n".join(blocks), preflight


def validate_and_record_character_presence(scene_id, turn_number, present_names, mentioned_names, scene_location=None, presence_updates=None, current_minutes=None):
    """Validate scene presence and approved movements using the internal campaign clock."""
    conn = get_connection()
    sync_character_registry(conn)
    current_minutes = get_campaign_minutes(conn) if current_minutes is None else int(current_minutes)
    _complete_due_movements(conn, current_minutes)
    campaign = conn.execute("SELECT current_location FROM campaign_context WHERE id = 1").fetchone()
    legal_location = str(scene_location or (campaign[0] if campaign else "Ashvale Hold")).strip()
    known_locations = {row[0] for row in conn.execute("SELECT name FROM map_locations").fetchall()}
    if legal_location not in known_locations:
        legal_location = campaign[0] if campaign else "Ashvale Hold"
    accepted, rejected, mentioned = [], [], []
    for raw_name in (present_names or [])[:15]:
        canonical = resolve_character_name(raw_name)
        if not canonical:
            rejected.append({"name": str(raw_name)[:90], "reason": "unregistered character cannot be made present without a legal registration update"})
            continue
        row = conn.execute("SELECT current_location, availability FROM character_presence WHERE canonical_name = ?", (canonical,)).fetchone()
        if row and row[1] == "active" and row[0] == legal_location:
            accepted.append(canonical)
        else:
            rejected.append({"name": canonical, "reason": f"verified as {row[1] if row else 'unavailable'} at {row[0] if row else 'unknown'}, not at {legal_location}"})
    for raw_name in (mentioned_names or [])[:15]:
        canonical = resolve_character_name(raw_name)
        mentioned.append(canonical or str(raw_name).strip()[:90])
    for update in (presence_updates or [])[:6]:
        if not isinstance(update, dict) or update.get("type") != "MOVE":
            continue
        canonical = resolve_character_name(update.get("name"))
        destination = str(update.get("to_location", "")).strip()[:90]
        if not canonical or destination not in known_locations:
            continue
        origin = conn.execute("SELECT current_location, availability FROM character_presence WHERE canonical_name = ?", (canonical,)).fetchone()
        if not origin or origin[1] != "active":
            continue
        try:
            travel_minutes = int(update.get("travel_minutes"))
        except (TypeError, ValueError):
            # Legacy proposals may still provide travel_turns.  Convert their
            # intent to hours rather than treating a turn as a date unit.
            try:
                travel_minutes = int(update.get("travel_turns", 1) or 1) * 6 * MINUTES_PER_HOUR
            except (TypeError, ValueError):
                travel_minutes = 6 * MINUTES_PER_HOUR
        travel_minutes = max(30, min(4 * MINUTES_PER_DAY, travel_minutes))
        arrival_minutes = current_minutes + travel_minutes
        conn.execute("UPDATE character_movements SET status = 'cancelled' WHERE canonical_name = ? AND status = 'planned'", (canonical,))
        conn.execute(
            """INSERT INTO character_movements
               (canonical_name, from_location, to_location, depart_turn, arrival_turn, depart_at_minute, arrival_at_minute, reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (canonical, origin[0], destination, turn_number, turn_number, current_minutes, arrival_minutes,
             str(update.get("reason", "narrative movement"))[:200]),
        )
        conn.execute(
            """UPDATE character_presence SET availability = 'traveling', destination = ?, available_at_minute = ?,
               reason = ?, updated_turn = ?, updated_at_minute = ? WHERE canonical_name = ?""",
            (destination, arrival_minutes, "in transit", turn_number, current_minutes, canonical),
        )
    conn.commit()
    conn.close()
    for name in accepted:
        record_character_mention(name, scene_id, turn_number, role="present")
    for name in mentioned:
        record_character_mention(name, scene_id, turn_number, role="mentioned")
    return {"scene_location": legal_location, "accepted": accepted, "rejected": rejected, "mentioned": mentioned,
            "current_minutes": current_minutes, "current_time": _format_campaign_time(current_minutes)}


def get_character_presence_snapshot():
    return get_character_time_snapshot()


# -----------------------------------------------------------------
# PHASE 8: continuous campaign time
# -----------------------------------------------------------------

MINUTES_PER_HOUR = 60
MINUTES_PER_DAY = 24 * MINUTES_PER_HOUR
DAYS_PER_MONTH = 30
MONTHS_PER_YEAR = 12
SEASONS = ("Winter", "Spring", "Summer", "Autumn")


def _add_column_if_missing(conn, table, column, definition):
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _calendar_from_minutes(absolute_minutes):
    absolute_minutes = max(0, int(absolute_minutes or 0))
    world_day_index, minute_of_day = divmod(absolute_minutes, MINUTES_PER_DAY)
    year_index, day_of_year = divmod(world_day_index, DAYS_PER_MONTH * MONTHS_PER_YEAR)
    month_index, day_index = divmod(day_of_year, DAYS_PER_MONTH)
    return {
        "absolute_minutes": absolute_minutes,
        "day": day_index + 1,
        "month": month_index + 1,
        "year": year_index + 1,
        "season": SEASONS[(month_index // 3) % len(SEASONS)],
        "hour": minute_of_day // MINUTES_PER_HOUR,
        "minute": minute_of_day % MINUTES_PER_HOUR,
        "minute_of_day": minute_of_day,
        "world_day": world_day_index + 1,
    }


def _format_campaign_time(absolute_minutes):
    clock = _calendar_from_minutes(absolute_minutes)
    return f"Day {clock['day']}, Month {clock['month']}, Year {clock['year']} — {clock['hour']:02d}:{clock['minute']:02d}"


def init_phase8_continuous_time_tables(conn):
    """Migrate legacy turn-based time fields into a continuous internal clock.

    Scene turn numbers remain audit identifiers.  They are intentionally not used
    by this layer to determine dates, travel arrival, civic income, or availability.
    """
    _add_column_if_missing(conn, "world_clock", "absolute_minutes", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "world_clock", "hour", "INTEGER NOT NULL DEFAULT 8")
    _add_column_if_missing(conn, "world_clock", "minute", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "character_presence", "available_at_minute", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "character_presence", "updated_at_minute", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "character_movements", "depart_at_minute", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "character_movements", "arrival_at_minute", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "civic_profiles", "last_settled_minute", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "player_shops", "last_settled_minute", "INTEGER NOT NULL DEFAULT 0")

    clock_row = conn.execute("SELECT day, absolute_minutes FROM world_clock WHERE id = 1").fetchone()
    if clock_row:
        legacy_day, stored_minutes = int(clock_row[0] or 1), int(clock_row[1] or 0)
        # Legacy day-only campaigns are anchored at 08:00 rather than midnight.
        absolute_minutes = stored_minutes if stored_minutes > 0 else max(0, legacy_day - 1) * MINUTES_PER_DAY + 8 * MINUTES_PER_HOUR
        calendar = _calendar_from_minutes(absolute_minutes)
        conn.execute(
            """UPDATE world_clock SET absolute_minutes=?, day=?, month=?, year=?, season=?, hour=?, minute=? WHERE id=1""",
            (absolute_minutes, calendar["day"], calendar["month"], calendar["year"], calendar["season"], calendar["hour"], calendar["minute"]),
        )
        # A legacy active character is available at the migration instant.  A legacy
        # traveler keeps a conservative future ETA, rather than materialising early.
        conn.execute(
            """UPDATE character_presence
               SET available_at_minute = CASE
                 WHEN availability = 'traveling' AND available_at_minute <= 0
                   THEN ? + MAX(60, COALESCE(available_turn, 1) * 60)
                 WHEN available_at_minute <= 0 THEN ?
                 ELSE available_at_minute END,
               updated_at_minute = CASE WHEN updated_at_minute <= 0 THEN ? ELSE updated_at_minute END""",
            (absolute_minutes, absolute_minutes, absolute_minutes),
        )
        conn.execute(
            """UPDATE character_movements
               SET depart_at_minute = CASE WHEN depart_at_minute <= 0 THEN ? ELSE depart_at_minute END,
                   arrival_at_minute = CASE WHEN arrival_at_minute <= 0
                     THEN ? + MAX(60, COALESCE(arrival_turn, 1) * 60)
                     ELSE arrival_at_minute END""",
            (absolute_minutes, absolute_minutes),
        )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_character_movements_time ON character_movements(canonical_name, status, arrival_at_minute)")
    conn.commit()


def get_campaign_minutes(conn=None):
    owns_connection = conn is None
    conn = conn or get_connection()
    row = conn.execute("SELECT absolute_minutes FROM world_clock WHERE id = 1").fetchone()
    value = int(row[0] or 0) if row else 0
    if owns_connection:
        conn.close()
    return value


def _explicit_time_request(action, current_minutes):
    """Interpret player-requested waiting / time jumps without relying on a turn count."""
    text = _normalise_character_token(action)
    duration_patterns = (
        (r"(?:انتظر|انتظار|بعد)\s+(\d+)\s*(?:دقيقه|دقائق|minutes?|mins?)", 1),
        (r"(?:انتظر|انتظار|بعد)\s+(\d+)\s*(?:ساعه|ساعات|hours?|hrs?)", MINUTES_PER_HOUR),
        (r"(?:انتظر|انتظار|بعد)\s+(\d+)\s*(?:يوم|ايام|days?)", MINUTES_PER_DAY),
        (r"(?:انتظر|انتظار|بعد)\s+(\d+)\s*(?:شهر|اشهر|months?)", DAYS_PER_MONTH * MINUTES_PER_DAY),
    )
    for pattern, multiplier in duration_patterns:
        match = re.search(pattern, text)
        if match:
            minutes = max(1, min(365 * MINUTES_PER_DAY, int(match.group(1)) * multiplier))
            return {"minutes": minutes, "mode": "explicit_wait", "reason": "player-requested wait"}
    if any(term in text for term in ("شهر كامل", "full month", "a month")):
        return {"minutes": DAYS_PER_MONTH * MINUTES_PER_DAY, "mode": "explicit_wait", "reason": "player-requested full month"}
    if any(term in text for term in ("حتي الفجر", "حتى الفجر", "until dawn")):
        target = 6 * MINUTES_PER_HOUR
        today = current_minutes - (current_minutes % MINUTES_PER_DAY) + target
        if today <= current_minutes:
            today += MINUTES_PER_DAY
        return {"minutes": today - current_minutes, "mode": "explicit_jump", "reason": "wait until dawn"}
    if any(term in text for term in ("حتي الغروب", "حتي المساء", "حتى الغروب", "حتى المساء", "until dusk", "until evening")):
        target = 18 * MINUTES_PER_HOUR
        today = current_minutes - (current_minutes % MINUTES_PER_DAY) + target
        if today <= current_minutes:
            today += MINUTES_PER_DAY
        return {"minutes": today - current_minutes, "mode": "explicit_jump", "reason": "wait until evening"}
    match = re.search(r"(?:حتي الساعه|الي الساعه|حتى الساعه|الى الساعه|until)\s*(\d{1,2})(?::(\d{2}))?", text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            target = hour * MINUTES_PER_HOUR + minute
            today = current_minutes - (current_minutes % MINUTES_PER_DAY) + target
            if today <= current_minutes:
                today += MINUTES_PER_DAY
            return {"minutes": today - current_minutes, "mode": "explicit_jump", "reason": "player-requested clock time"}
    return None


def estimate_action_minutes(action, proposed_minutes=None):
    """Deterministically assign a modest in-world duration to a normal action."""
    if proposed_minutes is not None:
        try:
            return max(1, min(12 * MINUTES_PER_HOUR, int(proposed_minutes)))
        except (TypeError, ValueError):
            pass
    text = _normalise_character_token(action)
    if any(term in text for term in ("سافر", "رحله", "travel", "journey", "اركب", "march")):
        return 6 * MINUTES_PER_HOUR
    if any(term in text for term in ("معركه", "قتال", "حصار", "battle", "fight", "siege")):
        return 8 * MINUTES_PER_HOUR
    if any(term in text for term in ("حقق", "ابحث", "درب", "تفاوض", "investigate", "search", "train", "negotiate")):
        return 30
    return 10


def advance_campaign_time(action, proposed_minutes=None):
    """Advance the legal campaign clock by a natural or explicitly requested duration."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        before = get_campaign_minutes(conn)
        explicit = _explicit_time_request(action, before)
        duration = explicit["minutes"] if explicit else estimate_action_minutes(action, proposed_minutes)
        mode = explicit["mode"] if explicit else "natural_action"
        reason = explicit["reason"] if explicit else "system-estimated action duration"
        after = before + duration
        calendar = _calendar_from_minutes(after)
        conn.execute(
            """UPDATE world_clock SET absolute_minutes=?, day=?, month=?, year=?, season=?, hour=?, minute=? WHERE id=1""",
            (after, calendar["day"], calendar["month"], calendar["year"], calendar["season"], calendar["hour"], calendar["minute"]),
        )
        conn.commit()
        return {"before_minutes": before, "after_minutes": after, "elapsed_minutes": duration,
                "mode": mode, "reason": reason, "clock": calendar,
                "display": _format_campaign_time(after)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def settle_civic_time(current_minutes):
    """Settle cities once for each completed in-world day, never once per scene."""
    current_minutes = max(0, int(current_minutes or 0))
    current_day = current_minutes // MINUTES_PER_DAY
    if current_day < 1:
        return {"world_day": current_day + 1, "settled_days": 0, "settled_locations": 0, "shops": [], "total_shop_profit_copper": 0}
    conn = get_connection()
    row = conn.execute("SELECT COALESCE(MIN(last_settled_minute), 0) FROM civic_profiles").fetchone()
    last_settled_day = int((row[0] or 0) // MINUTES_PER_DAY)
    conn.close()
    summaries = []
    for settlement_day in range(max(1, last_settled_day + 1), current_day + 1):
        # The legacy function is retained for formulas and schema compatibility;
        # its input is now a world-day identifier, never a narrative turn number.
        summary = settle_civic_turn(settlement_day)
        settlement_minute = settlement_day * MINUTES_PER_DAY
        conn = get_connection()
        try:
            conn.execute("UPDATE civic_profiles SET last_settled_minute = MAX(last_settled_minute, ?)", (settlement_minute,))
            conn.execute("UPDATE player_shops SET last_settled_minute = MAX(last_settled_minute, ?)", (settlement_minute,))
            conn.commit()
        finally:
            conn.close()
        summaries.append(summary)
    return {
        "world_day": current_day + 1,
        "settled_days": len(summaries),
        "settled_locations": sum(item["settled_locations"] for item in summaries),
        "shops": [shop for item in summaries for shop in item["shops"]],
        "total_shop_profit_copper": sum(item["total_shop_profit_copper"] for item in summaries),
    }


def get_character_time_snapshot():
    conn = get_connection()
    rows = conn.execute(
        "SELECT canonical_name, current_location, availability, destination, available_at_minute, reason FROM character_presence ORDER BY canonical_name"
    ).fetchall()
    conn.close()
    return [
        {"name": row[0], "location": row[1], "availability": row[2], "destination": row[3],
         "available_at_minute": row[4], "available_at": _format_campaign_time(row[4]), "reason": row[5]}
        for row in rows
    ]


def refresh_due_character_movements(current_minutes=None):
    """Apply all movement arrivals due at the supplied internal timestamp."""
    conn = get_connection()
    try:
        current_minutes = get_campaign_minutes(conn) if current_minutes is None else int(current_minutes)
        due = conn.execute(
            "SELECT canonical_name, to_location, arrival_at_minute FROM character_movements WHERE status = 'planned' AND arrival_at_minute <= ?",
            (current_minutes,),
        ).fetchall()
        _complete_due_movements(conn, current_minutes)
        conn.commit()
        return [
            {"name": row[0], "location": row[1], "arrived_at": _format_campaign_time(row[2])}
            for row in due
        ]
    finally:
        conn.close()
