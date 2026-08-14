"""
state_manager.py

Takes the (already loosely-shaped) proposal from state_evaluator.py,
validates every value against hard rules, and is the ONLY module
that writes state-managed tables to SQLite.

Nothing here trusts Gemini's numbers blindly:
- XP awards are clamped to a sane per-turn ceiling and can't go negative.
- Behavior/faction/retainer/holding deltas are clamped per-turn and the
  underlying columns are clamped 0-100 at the DB layer as a second net.
- Trait unlocks are NEVER taken from Gemini's trait_candidates directly;
  they are recomputed deterministically via traits.py.
- Unknown or malformed quest/holding entries are skipped, not guessed at.
"""

import json
import re

from database import (
    save_memory,
    add_stat_xp,
    adjust_behavior_score,
    get_behavior_scores,
    upsert_faction_shift,
    upsert_retainer_shift,
    upsert_quest,
    upsert_holding_shift,
    get_traits,
    unlock_trait,
    log_event,
    advance_campaign_time,
    settle_civic_time,
    refresh_due_character_movements,
    get_appearance,
    set_canonical_appearance,
    update_outfit,
    get_map_locations,
    add_map_location,
    get_character_stats,
    get_mastery_specializations,
    unlock_specialization,
    add_inventory_item,
    remove_inventory_item,
    get_army_by_name,
    upsert_army,
    record_battle,
    create_loot_pile,
    validate_and_record_character_presence,
    get_atlas_data,
    add_world_lord,
    add_world_lore,
    record_wallet_transaction,
)

from traits import evaluate_trait_unlocks
from mastery import evaluate_specialization_unlocks
from military import resolve_battle, generate_loot

MAX_XP_PER_STAT_PER_TURN = 25
MAX_BEHAVIOR_DELTA_PER_TURN = 8
MAX_FACTION_DELTA_PER_TURN = 15
MAX_RETAINER_DELTA_PER_TURN = 15
MAX_HOLDING_DELTA_PER_TURN = 10
MAX_WORLD_LORDS_PER_TURN = 2
MAX_WORLD_LORE_PER_TURN = 2
ALLOWED_WORLD_LORE_CATEGORIES = {"chronicle", "legend", "rumor", "treaty", "artifact", "custom", "discovery"}

MASTERY_KEY_MAP = {
    "weapons": "weapons_mastery",
    "dueling": "dueling_mastery",
    "duel": "dueling_mastery",
    "trade": "trade_mastery",
    "conversation": "conversation_mastery",
    "strategy": "strategy_mastery",
    "planning": "strategy_mastery",
    "leadership": "leadership_mastery",
    "command": "leadership_mastery",
    "exploration": "exploration_mastery",
    "explore": "exploration_mastery",
    "intrigue": "intrigue_mastery",
}


def _clamp(value, low, high):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 0
    return max(low, min(high, value))


def _world_slug(value, prefix, turn_number):
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-")
    if not cleaned:
        cleaned = "entry"
    return f"{prefix}-{cleaned[:36]}-{turn_number}"


def apply_state_changes(proposal, scene_id, turn_number, player_action="", elapsed_minutes=None):
    """
    Applies a validated proposal to the database.
    Returns a summary dict describing what actually changed, so the
    caller (game.py) can hand structured info back to the frontend
    (level-ups, new traits, event panel data).
    """

    summary = {
        "canon_facts_saved": 0,
        "xp_awarded": {},
        "faction_shifts": {},
        "retainer_shifts": {},
        "quests_updated": [],
        "holdings_updated": [],
        "new_traits": [],
        "new_specializations": [],
        "appearance_updates": [],
        "new_locations": [],
        "new_lords": [],
        "new_lore": [],
        "economic_entries": [],
        "civic_settlement": None,
        "time_progression": None,
        "arrived_characters": [],
        "character_presence": {"scene_location": None, "accepted": [], "rejected": [], "mentioned": []},
        "actions": [],
        "important_event": bool(proposal.get("important_event")),
        "decisive_action": bool(proposal.get("decisive_action")),
        "event_title": proposal.get("event_title"),
        "event_summary": proposal.get("event_summary"),
        "event_type": proposal.get("event_type"),
    }

    # ---------------- canon facts ----------------
    for fact in proposal.get("canon_facts", []) or []:
        if not isinstance(fact, dict):
            continue
        category = str(fact.get("category", "EVENT")).upper()[:20]
        content = str(fact.get("fact", "")).strip()
        if content:
            save_memory(scene_id, category, content)
            summary["canon_facts_saved"] += 1

    # ---------------- character presence and movement ----------------
    # Presence is never trusted from a narrative proposal.  The ledger verifies
    # canonical identity, current availability, and the campaign location before
    # it allows a character to be indexed as physically present in this scene.
    summary["character_presence"] = validate_and_record_character_presence(
        scene_id,
        turn_number,
        proposal.get("characters_present", []) or [],
        proposal.get("characters_mentioned", []) or [],
        proposal.get("scene_location"),
        proposal.get("presence_updates", []) or [],
    )

    # ---------------- XP ----------------
    for raw_name, amount in (proposal.get("xp_awards", {}) or {}).items():
        key = MASTERY_KEY_MAP.get(str(raw_name).strip().lower())
        if not key:
            continue
        clamped = _clamp(amount, 0, MAX_XP_PER_STAT_PER_TURN)
        if clamped <= 0:
            continue
        result = add_stat_xp(key, clamped)
        if result:
            summary["xp_awarded"][key] = {
                "gained": clamped,
                "level": result["level"],
                "leveled_up": result["leveled_up"],
            }

    if summary["xp_awarded"]:
        fresh_stats = get_character_stats()
        fresh_specs = get_mastery_specializations()
        for mastery_name, specialization in evaluate_specialization_unlocks(
            fresh_stats, fresh_specs, turn_number
        ):
            if unlock_specialization(mastery_name, specialization, turn_number):
                summary["new_specializations"].append({
                    "mastery_name": mastery_name,
                    "specialization": specialization,
                })

    # ---------------- behavior ----------------
    for name, delta in (proposal.get("behavior_changes", {}) or {}).items():
        clamped = _clamp(delta, -MAX_BEHAVIOR_DELTA_PER_TURN, MAX_BEHAVIOR_DELTA_PER_TURN)
        if clamped:
            adjust_behavior_score(str(name).strip().lower(), clamped)

    # ---------------- factions ----------------
    for name, deltas in (proposal.get("faction_shifts", {}) or {}).items():
        if not isinstance(deltas, dict):
            continue
        name = str(name).strip()
        if not name:
            continue
        trust = _clamp(deltas.get("trust", 0), -MAX_FACTION_DELTA_PER_TURN, MAX_FACTION_DELTA_PER_TURN)
        fear = _clamp(deltas.get("fear", 0), -MAX_FACTION_DELTA_PER_TURN, MAX_FACTION_DELTA_PER_TURN)
        loyalty = _clamp(deltas.get("loyalty", 0), -MAX_FACTION_DELTA_PER_TURN, MAX_FACTION_DELTA_PER_TURN)
        leverage = _clamp(deltas.get("leverage", 0), -MAX_FACTION_DELTA_PER_TURN, MAX_FACTION_DELTA_PER_TURN)
        if trust or fear or loyalty or leverage:
            upsert_faction_shift(name, trust, fear, loyalty, leverage)
            summary["faction_shifts"][name] = {
                "trust": trust, "fear": fear, "loyalty": loyalty, "leverage": leverage
            }

    # ---------------- retainers ----------------
    for name, deltas in (proposal.get("retainer_shifts", {}) or {}).items():
        if not isinstance(deltas, dict):
            continue
        name = str(name).strip()
        if not name:
            continue
        loyalty = _clamp(deltas.get("loyalty", 0), -MAX_RETAINER_DELTA_PER_TURN, MAX_RETAINER_DELTA_PER_TURN)
        morale = _clamp(deltas.get("morale", 0), -MAX_RETAINER_DELTA_PER_TURN, MAX_RETAINER_DELTA_PER_TURN)
        trust = _clamp(deltas.get("trust", 0), -MAX_RETAINER_DELTA_PER_TURN, MAX_RETAINER_DELTA_PER_TURN)
        respect = _clamp(deltas.get("respect", 0), -MAX_RETAINER_DELTA_PER_TURN, MAX_RETAINER_DELTA_PER_TURN)
        if loyalty or morale or trust or respect:
            upsert_retainer_shift(name, loyalty, morale, trust, respect)
            summary["retainer_shifts"][name] = {
                "loyalty": loyalty, "morale": morale, "trust": trust, "respect": respect
            }

    # ---------------- quests ----------------
    for quest in proposal.get("quest_updates", []) or []:
        if not isinstance(quest, dict):
            continue
        quest_id = str(quest.get("quest_id", "")).strip()
        if not quest_id:
            continue
        fields = {}
        for key in ("title", "description", "status", "location", "deadline", "discovered_info"):
            if key in quest and quest[key] is not None:
                fields[key] = str(quest[key])[:500]
        if "objectives" in quest:
            try:
                fields["objectives"] = json.dumps(quest["objectives"])
            except (TypeError, ValueError):
                pass
        upsert_quest(quest_id, turn_number, **fields)
        summary["quests_updated"].append(quest_id)

    # ---------------- holdings ----------------
    for name, deltas in (proposal.get("holding_changes", {}) or {}).items():
        if not isinstance(deltas, dict):
            continue
        name = str(name).strip()
        if not name:
            continue
        clamped_deltas = {
            field: _clamp(deltas[field], -MAX_HOLDING_DELTA_PER_TURN, MAX_HOLDING_DELTA_PER_TURN)
            for field in ("prosperity", "security", "population", "wealth",
                          "food_supply", "military_strength", "loyalty")
            if field in deltas
        }
        if any(clamped_deltas.values()):
            upsert_holding_shift(name, **clamped_deltas)
            summary["holdings_updated"].append(name)

    # ---------------- economy ----------------
    # Narrative may propose only a small, bounded cash movement.  Every accepted
    # movement receives an idempotency key tied to its scene, so replaying a turn
    # can never credit or debit the same money twice.
    for index, raw_entry in enumerate((proposal.get("economic_entries", []) or [])[:4]):
        if not isinstance(raw_entry, dict):
            continue
        amount = _clamp(raw_entry.get("amount_copper", 0), -500, 500)
        if not amount:
            continue
        entry_type = str(raw_entry.get("entry_type", "story_reward")).strip().lower()[:40]
        if not entry_type or not re.fullmatch(r"[a-z_]+", entry_type):
            entry_type = "story_reward"
        try:
            entry = record_wallet_transaction(
                amount, entry_type, turn_number=turn_number,
                counterparty=str(raw_entry.get("counterparty", "") or "")[:80] or None,
                location=str(raw_entry.get("location", "") or "")[:80] or None,
                reference_type="scene", reference_id=str(scene_id),
                memo=str(raw_entry.get("memo", "") or "قرار سردي")[:200],
                idempotency_key=f"scene-{scene_id}-economy-{index}",
            )
            summary["economic_entries"].append({"amount_copper": amount, "entry_type": entry_type, "wallet": entry["wallet"]})
        except ValueError:
            # A story cannot create debt or silently overdraw the wallet.
            continue

    # ---------------- inventory ----------------
    VALID_SLOTS = {"head", "chest", "hands", "feet", "weapon", "offhand", "accessory"}

    summary["inventory_changes"] = {"added": [], "removed": []}
    inv_changes = proposal.get("inventory_changes", {}) or {}

    for item in (inv_changes.get("added", []) or [])[:10]:
        if isinstance(item, str):
            name, category, qty, desc = item.strip(), "misc", 1, ""
            damage = armor_rating = None
            value, weight, effect, slot = 0, 0.0, None, None
        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            category = str(item.get("category", "misc"))[:20]
            qty = _clamp(item.get("quantity", 1), 1, 9999)
            desc = str(item.get("description", ""))[:200]

            damage = item.get("damage")
            damage = _clamp(damage, 0, 500) if damage is not None else None

            armor_rating = item.get("armor_rating")
            armor_rating = _clamp(armor_rating, 0, 500) if armor_rating is not None else None

            value = _clamp(item.get("value", 0), 0, 999999)

            try:
                weight = max(0.0, min(500.0, float(item.get("weight", 0) or 0)))
            except (TypeError, ValueError):
                weight = 0.0

            effect = item.get("effect")
            effect = str(effect)[:200] if effect else None

            slot = str(item.get("slot", "")).strip().lower() or None
            if slot not in VALID_SLOTS:
                slot = None
        else:
            continue

        if not name:
            continue

        # Compatibility guard for older narrative proposals: currencies are
        # ledger movements, never stackable inventory items.
        if category.casefold() in {"currency", "coin", "money"}:
            try:
                entry = record_wallet_transaction(
                    qty, "legacy_story_currency", turn_number=turn_number, reference_type="scene",
                    reference_id=str(scene_id), memo=f"ترحيل مكافأة نقدية: {name}",
                    idempotency_key=f"scene-{scene_id}-legacy-currency-{len(summary['inventory_changes']['added'])}",
                )
                summary["economic_entries"].append({"amount_copper": qty, "entry_type": "legacy_story_currency", "wallet": entry["wallet"]})
            except ValueError:
                pass
            continue

        add_inventory_item(
            name, category, qty, desc, turn_number,
            damage=damage, armor_rating=armor_rating,
            value=value, weight=weight, effect=effect, slot=slot
        )
        summary["inventory_changes"]["added"].append(name)

    for item in (inv_changes.get("removed", []) or [])[:10]:
        if isinstance(item, str):
            name, qty = item.strip(), 1
        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            qty = _clamp(item.get("quantity", 1), 1, 9999)
        else:
            continue
        if not name:
            continue
        remove_inventory_item(name, qty)
        summary["inventory_changes"]["removed"].append(name)

    # ---------------- armies (non-combat changes) ----------------
    summary["army_updates"] = []
    for name, changes in (proposal.get("army_changes", {}) or {}).items():
        if not isinstance(changes, dict):
            continue
        name = str(name).strip()
        if not name:
            continue

        clean_changes = {}
        for field in ("total_troops", "wounded_troops", "morale", "organization", "food_days"):
            if field in changes:
                clean_changes[field] = _clamp(changes[field], -5000, 5000)
        for field in ("location", "commander", "status", "faction"):
            if field in changes and changes[field]:
                clean_changes[field] = str(changes[field])[:80]

        if clean_changes:
            upsert_army(name, turn_number, **clean_changes)
            summary["army_updates"].append(name)

    # ---------------- battle resolution (deterministic, Python-owned) ----------------
    summary["battle"] = None
    summary["loot_created"] = None

    trigger = proposal.get("battle_trigger")
    if isinstance(trigger, dict) and trigger.get("attacker") and trigger.get("defender"):
        attacker_name = str(trigger["attacker"])[:80]
        defender_name = str(trigger["defender"])[:80]
        terrain = str(trigger.get("terrain", "open_field"))
        weather = str(trigger.get("weather", "clear"))

        # Ensure both sides exist in the armies table (a scene may
        # name an enemy force that was never explicitly tracked yet;
        # give it a plausible default rather than skipping the battle).
        attacker = get_army_by_name(attacker_name)
        if not attacker:
            upsert_army(attacker_name, turn_number, total_troops=100, morale=60, organization=60)
            attacker = get_army_by_name(attacker_name)

        defender = get_army_by_name(defender_name)
        if not defender:
            upsert_army(defender_name, turn_number, total_troops=100, morale=60, organization=60)
            defender = get_army_by_name(defender_name)

        result = resolve_battle(attacker, defender, terrain=terrain, weather=weather)

        upsert_army(attacker_name, turn_number, total_troops=-result["attacker_casualties"])
        upsert_army(defender_name, turn_number, total_troops=-result["defender_casualties"])

        victor_name = attacker_name if result["victor"] == "attacker" else (
            defender_name if result["victor"] == "defender" else "none"
        )

        battle_id = record_battle(
            turn_number, trigger.get("location") or "", attacker_name, defender_name,
            result["attacker_start"], result["defender_start"],
            result["attacker_end"], result["defender_end"],
            result["attacker_casualties"], result["defender_casualties"],
            victor_name,
            f"{attacker_name} vs {defender_name} at {terrain}, {weather} weather."
        )

        summary["battle"] = {
            "battle_id": battle_id,
            "attacker_name": attacker_name, "defender_name": defender_name,
            "attacker_casualties": result["attacker_casualties"],
            "defender_casualties": result["defender_casualties"],
            "attacker_end": result["attacker_end"], "defender_end": result["defender_end"],
            "victor": victor_name,
        }

        # Loot only gets created when the PLAYER-faction side won.
        # It's generated from the losing side's casualties (their
        # abandoned gear), and the player still has to claim it --
        # but if the player's own army lost, there's no loot pile at
        # all: you don't get to plunder your own dead.
        winner_army = attacker if result["victor"] == "attacker" else (
            defender if result["victor"] == "defender" else None
        )
        winner_is_player = bool(winner_army and (winner_army.get("faction") or "").lower() == "player")

        loser_casualties = (
            result["defender_casualties"] if result["victor"] == "attacker"
            else result["attacker_casualties"] if result["victor"] == "defender"
            else 0
        )
        loser_start = (
            result["defender_start"] if result["victor"] == "attacker"
            else result["attacker_start"] if result["victor"] == "defender"
            else 0
        )
        if winner_is_player and loser_casualties > 0:
            loot = generate_loot(loser_casualties, loser_start)
            if loot["gold"] or loot["items"]:
                loot_id = create_loot_pile(
                    battle_id, trigger.get("location") or "", loot["gold"], loot["items"], turn_number
                )
                summary["loot_created"] = {"loot_id": loot_id, **loot}

    # ---------------- appearance (canon-preserving) ----------------
    for update in proposal.get("appearance_updates", []) or []:
        if not isinstance(update, dict):
            continue
        name = str(update.get("name", "")).strip()
        update_type = update.get("type")
        fields = update.get("fields")
        if not name or not isinstance(fields, dict) or not fields:
            continue

        clean_fields = {
            str(k)[:40]: str(v)[:200]
            for k, v in fields.items()
        }

        if update_type == "canonical":
            set_canonical_appearance(name, clean_fields, turn_number)
            summary["appearance_updates"].append({"name": name, "type": "canonical", "fields": clean_fields})
        elif update_type == "outfit":
            existing = get_appearance(name)
            merged_outfit = dict(existing["current_outfit"]) if existing else {}
            merged_outfit.update(clean_fields)
            update_outfit(name, merged_outfit, turn_number)
            summary["appearance_updates"].append({"name": name, "type": "outfit", "fields": clean_fields})

    # ---------------- map expansion ----------------
    known_location_names = {loc["name"] for loc in get_map_locations(discovered_only=False)}

    for update in proposal.get("map_updates", []) or []:
        if not isinstance(update, dict):
            continue
        if update.get("type") != "ADD_LOCATION":
            continue
        name = str(update.get("name", "")).strip()
        if not name or name in known_location_names:
            continue
        try:
            x = max(0.0, min(1.0, float(update.get("x", 0.5))))
            y = max(0.0, min(1.0, float(update.get("y", 0.5))))
        except (TypeError, ValueError):
            continue
        add_map_location(
            name,
            str(update.get("region", ""))[:60],
            x, y,
            str(update.get("description", ""))[:300],
            str(update.get("kind", "settlement"))[:30],
            turn_number
        )
        known_location_names.add(name)
        summary["new_locations"].append(name)

    # ---------------- living world expansion (additive only) ----------------
    atlas = get_atlas_data(include_hidden=True)
    known_lord_names = {str(lord.get("name", "")).casefold() for lord in atlas.get("lords", [])}
    for raw in (proposal.get("world_lord_updates", []) or [])[:MAX_WORLD_LORDS_PER_TURN]:
        if not isinstance(raw, dict) or raw.get("type") != "ADD_LORD":
            continue
        name = str(raw.get("name", "")).strip()[:90]
        title = str(raw.get("title", "")).strip()[:80]
        if not name or not title or name.casefold() in known_lord_names:
            continue
        slug = _world_slug(name, "dyn-lord", turn_number)
        add_world_lord(
            slug=slug, name=name, title=title,
            region=str(raw.get("region", "غير محدد"))[:60], turn_number=turn_number,
            house=str(raw.get("house", ""))[:80], seat=str(raw.get("seat", ""))[:90],
            allegiance=str(raw.get("allegiance", "مستقل"))[:60], disposition=str(raw.get("disposition", "متحفّظ"))[:60],
            public_agenda=str(raw.get("public_agenda", ""))[:240], secret=str(raw.get("secret", ""))[:280],
            biography=str(raw.get("biography", ""))[:420], discovered=bool(raw.get("discovered", True)),
        )
        known_lord_names.add(name.casefold())
        summary["new_lords"].append(name)

    known_lore_titles = {str(item.get("title", "")).casefold() for item in atlas.get("lore", [])}
    for raw in (proposal.get("world_lore_updates", []) or [])[:MAX_WORLD_LORE_PER_TURN]:
        if not isinstance(raw, dict) or raw.get("type") != "ADD_LORE":
            continue
        title = str(raw.get("title", "")).strip()[:120]
        body = str(raw.get("body", "")).strip()[:600]
        category = str(raw.get("category", "discovery")).casefold().strip()
        if not title or not body or title.casefold() in known_lore_titles or category not in ALLOWED_WORLD_LORE_CATEGORIES:
            continue
        slug = _world_slug(title, "dyn-lore", turn_number)
        keywords = raw.get("keywords", [])
        if isinstance(keywords, list):
            keywords = ", ".join(str(item)[:35] for item in keywords[:6])
        add_world_lore(
            slug=slug, category=category, title=title, region=str(raw.get("region", ""))[:60],
            era=str(raw.get("era", "العصر الحالي"))[:80], keywords=str(keywords)[:220], body=body,
            turn_number=turn_number, discovered=bool(raw.get("discovered", True)),
        )
        known_lore_titles.add(title.casefold())
        summary["new_lore"].append(title)

    # ---------------- suggested actions (important turns only) ----------------
    if summary["important_event"] or summary["decisive_action"]:
        for action in (proposal.get("actions", []) or [])[:4]:
            if not isinstance(action, dict):
                continue
            label = str(action.get("label", "")).strip()
            if not label:
                continue
            summary["actions"].append({
                "label": label[:120],
                "type": str(action.get("type", ""))[:40],
                "risk": str(action.get("risk", ""))[:20],
                "requirements": [str(r)[:60] for r in (action.get("requirements") or [])][:4],
            })

    # ---------------- traits (deterministic, Python-owned) ----------------
    current_scores = get_behavior_scores()
    already_unlocked = {t["key"] for t in get_traits()}
    newly_unlocked = evaluate_trait_unlocks(current_scores, already_unlocked)

    for trait in newly_unlocked:
        unlock_trait(
            trait["key"], trait["display_name"], trait["description"],
            turn_number, "behavior thresholds met"
        )
        summary["new_traits"].append(trait)

    # ---------------- continuous campaign time and civic settlement ----------------
    # A scene is still identified by a turn number for auditing, but its duration
    # is determined in-world from the player action (or an explicit wait/jump),
    # never by assuming that a scene consumes one whole day.
    requested_minutes = elapsed_minutes if elapsed_minutes is not None else proposal.get("elapsed_minutes")
    summary["time_progression"] = advance_campaign_time(player_action, requested_minutes)
    summary["arrived_characters"] = refresh_due_character_movements(
        summary["time_progression"]["after_minutes"]
    )
    summary["civic_settlement"] = settle_civic_time(summary["time_progression"]["after_minutes"])

    # ---------------- event log ----------------
    if summary["important_event"] or summary["decisive_action"]:
        log_event(
            turn_number,
            summary["event_type"] or "EVENT",
            summary["event_title"] or "Untitled Event",
            summary["event_summary"] or "",
            json.dumps({
                "xp_awarded": summary["xp_awarded"],
                "faction_shifts": summary["faction_shifts"],
                "retainer_shifts": summary["retainer_shifts"],
                "quests_updated": summary["quests_updated"],
                "new_traits": [t["key"] for t in summary["new_traits"]],
                "new_specializations": summary["new_specializations"],
                "new_locations": summary["new_locations"],
                "character_presence": summary["character_presence"],
                "actions": summary["actions"],
            })
        )

    return summary
