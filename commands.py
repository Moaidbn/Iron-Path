"""
commands.py

Out-of-character "director" commands.

These let the player address the ENGINE directly instead of
always speaking into the fiction. Anything typed starting with
"/" is treated as a meta-command: it is answered straight from
the database (fast, deterministic, no Gemini call) except for
/recap, which asks Gemini for an explicitly out-of-character
summary rather than an in-character reply.

Returns a dict: {"is_command": True, "kind": ..., "response": ...}
or {"is_command": False} if the input isn't a recognized command.
"""

import re

from database import (
    get_recent_scenes,
    get_turn_count,
    get_connection,
    get_character_stats,
    add_custom_stat,
    set_stat_level,
    get_player_state,
    get_factions,
    get_retainers,
    get_quests,
    get_holdings,
    get_world_clock,
    get_traits,
    get_recent_events,
    get_appearance,
    get_all_appearances,
    get_map_locations,
    get_mastery_specializations,
    get_armies,
    get_battles,
    get_loot_piles,
    get_character_scene_history,
    get_known_character_names,
)
from memory import search_memories, build_memory_context
from appearance import format_appearance_for_prompt


def _slugify(text):
    key = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return key or "stat"


HELP_TEXT = """Available commands:

/stats                        - turn count and quest status
/char                          - character sheet (masteries & levels)
/addskill <name> [| desc]      - add a new custom mastery, starts at Level 1
/setskill <name> <level>       - manually set a mastery's level
/factions                      - trust/fear/loyalty/leverage per faction
/retainers                     - loyalty/morale/trust/respect per retainer
/quests                        - active/completed/failed quests
/holdings                      - prosperity/security/loyalty per holding
/traits                        - unlocked traits
/specializations                - mastery sub-tree unlocks (Level 5+)
/appearance <name>              - canonical appearance & current outfit
/seen <name>                    - a character's full scene appearance history
/map                            - known locations
/world                         - current world clock
/armies                        - army roster, troop counts, morale
/battles [n]                   - recent battle results (default 5)
/loot                          - unclaimed loot piles
/events [n]                    - recent decisive/important events (default 5)
/history [n]                   - last n scenes verbatim (default 5)
/memories <query>              - raw memory search, unfiltered by prose
/memory <query>                - alias for /memories
/recap                         - out-of-character summary of where things stand
/help                          - this list

Anything else is treated as an in-character action."""


def is_command(text):
    return text.strip().startswith("/")


def _all_memories_grouped():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT category, content, scene_id
        FROM memories
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    grouped = {}

    for category, content, scene_id in rows:
        grouped.setdefault(category, []).append(content)

    return grouped


def handle_stats():
    turn_count = get_turn_count()
    grouped = _all_memories_grouped()

    lines = [f"Turn count: {turn_count}"]

    for category in ("PLAYER", "CHARACTER", "QUEST", "LOCATION", "WORLD", "ITEM", "EVENT"):
        count = len(grouped.get(category, []))
        if count:
            lines.append(f"{category}: {count} tracked")

    open_quests = grouped.get("QUEST", [])

    if open_quests:
        lines.append("")
        lines.append("Open threads:")
        for quest in open_quests[:8]:
            lines.append(f"  - {quest}")

    return "\n".join(lines)


def handle_history(arg):
    try:
        limit = int(arg) if arg else 5
    except ValueError:
        limit = 5

    limit = max(1, min(limit, 25))

    scenes = get_recent_scenes(limit=limit)

    if not scenes:
        return "No scenes recorded yet."

    parts = []

    for turn, action, response in scenes:
        parts.append(
            f"--- Turn {turn} ---\n"
            f"Player: {action}\n"
            f"GM: {response}"
        )

    return "\n\n".join(parts)


def handle_memories(query):
    query = query.strip()

    if not query:
        return "Usage: /memories <search term>"

    results = search_memories(query, limit=20)

    if not results:
        return f"No memories matched '{query}'."

    lines = [f"Memory search: '{query}' ({len(results)} results)", ""]

    for item in results:
        lines.append(
            f"[{item['category']}] (turn {item['turn']}, score {item['score']}) {item['content']}"
        )

    return "\n".join(lines)


def handle_recap(client, model_name="gemini-3.5-flash-lite"):
    context = build_memory_context("current situation state summary")
    recent = get_recent_scenes(limit=6)

    recent_text = ""
    for turn, action, response in recent:
        recent_text += f"\nTurn {turn}\nPlayer: {action}\nGM: {response}\n"

    prompt = f"""
You are summarizing a persistent RPG's current state for the PLAYER,
out of character. Do not roleplay, do not write prose narration, do
not speak as any NPC. Produce a plain factual status summary only.

Long-term memory context:
{context}

Recent scenes:
{recent_text}

Write a concise, objective bullet-point recap covering:
- Where the player and party currently are
- Active threads / unresolved quests
- Key NPC states relevant right now

No narration, no dialogue, no "you" addressed by a character -- just
a dry factual status report.
"""

    response = client.models.generate_content(
        model=model_name,
        contents=prompt
    )

    return response.text.strip()


def handle_character():
    stats = get_character_stats()

    if not stats:
        return "No character stats tracked yet. Use /addskill to create one."

    lines = ["CHARACTER SHEET", ""]

    for stat in stats:
        xp_needed = stat["xp_needed"] or 1
        filled = int(round((stat["xp"] / xp_needed) * 10))
        filled = max(0, min(filled, 10))
        bar = "\u25a0" * filled + "\u25a1" * (10 - filled)

        lines.append(
            f"{stat['display_name']} — Level {stat['level']}  [{bar}]  "
            f"{stat['xp']}/{xp_needed} xp"
        )

        if stat["description"]:
            lines.append(f"    {stat['description']}")

        lines.append("")

    return "\n".join(lines).rstrip()


def handle_addskill(arg):
    arg = arg.strip()

    if not arg:
        return "Usage: /addskill <Display Name> | <optional description>"

    if "|" in arg:
        display_name, description = [p.strip() for p in arg.split("|", 1)]
    else:
        display_name, description = arg, ""

    if not display_name:
        return "Usage: /addskill <Display Name> | <optional description>"

    key = _slugify(display_name)

    existing = get_character_stats()
    if any(s["name"] == key for s in existing):
        return f"'{display_name}' is already tracked. Use /char to view it."

    add_custom_stat(key, display_name, description)

    return f"Added new mastery: {display_name} (starts at Level 1)."


def handle_setskill(arg):
    parts = arg.strip().split()

    if len(parts) < 2:
        return "Usage: /setskill <name> <level>"

    *name_parts, level_str = parts
    name_query = " ".join(name_parts).strip().lower()

    try:
        level = int(level_str)
    except ValueError:
        return "Level must be a whole number."

    if level < 1:
        return "Level must be at least 1."

    stats = get_character_stats()

    match = next(
        (
            s for s in stats
            if s["name"] == _slugify(name_query)
            or s["display_name"].lower() == name_query
        ),
        None
    )

    if not match:
        return f"No mastery matching '{name_query}' found. Use /char to see tracked stats."

    set_stat_level(match["name"], level)

    return f"{match['display_name']} set to Level {level}."


def handle_factions():
    factions = get_factions()
    if not factions:
        return "No factions tracked yet. They appear as the story involves them."
    lines = ["FACTIONS", ""]
    for f in factions:
        lines.append(
            f"{f['name']}: trust {f['trust']}/100, fear {f['fear']}/100, "
            f"loyalty {f['loyalty']}/100, leverage {f['leverage']}/100"
        )
    return "\n".join(lines)


def handle_retainers():
    retainers = get_retainers()
    if not retainers:
        return "No retainers tracked yet."
    lines = ["RETAINERS", ""]
    for r in retainers:
        line = (
            f"{r['name']} ({r['status']}): loyalty {r['loyalty']}, morale {r['morale']}, "
            f"trust {r['trust']}, respect {r['respect']}"
        )
        if r["assignment"]:
            line += f" — assignment: {r['assignment']}"
        if r["location"]:
            line += f" — location: {r['location']}"
        lines.append(line)
    return "\n".join(lines)


def handle_quests():
    quests = get_quests()
    if not quests:
        return "No quests tracked yet."
    lines = ["QUESTS", ""]
    for status in ("active", "completed", "failed", "abandoned", "hidden"):
        matching = [q for q in quests if q["status"] == status]
        if not matching:
            continue
        lines.append(f"-- {status.upper()} --")
        for q in matching:
            lines.append(f"[{q['quest_id']}] {q['title']}")
            if q["description"]:
                lines.append(f"    {q['description']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def handle_holdings():
    holdings = get_holdings()
    if not holdings:
        return "No holdings tracked yet."
    lines = ["HOLDINGS", ""]
    for h in holdings:
        lines.append(
            f"{h['name']}: prosperity {h['prosperity']}, security {h['security']}, "
            f"loyalty {h['loyalty']}, military {h['military_strength']}, "
            f"food supply {h['food_supply']}"
        )
        if h["governor"]:
            lines.append(f"    Governor: {h['governor']}")
        if h["active_problems"]:
            lines.append(f"    Active problems: {h['active_problems']}")
    return "\n".join(lines)


def handle_traits():
    traits = get_traits()
    if not traits:
        return "No traits unlocked yet. Traits emerge from consistent behavior over time."
    lines = ["TRAITS", ""]
    for t in traits:
        lines.append(f"{t['display_name']} (Turn {t['unlock_turn']})")
        if t["description"]:
            lines.append(f"    {t['description']}")
    return "\n".join(lines)


def handle_world():
    clock = get_world_clock()
    player = get_player_state()
    lines = [
        f"Day {clock['day']}, Month {clock['month']}, Year {clock['year']} ({clock['season']})",
    ]
    if player:
        lines.append("")
        lines.append(
            f"Player Level {player['level']} | Reputation {player['reputation']}/100 | "
            f"Wealth {player['wealth']} | Political Influence {player['political_influence']} | "
            f"Military Influence {player['military_influence']}"
        )
    return "\n".join(lines)


def handle_armies():
    armies = get_armies()
    if not armies:
        return "No armies tracked yet."

    lines = ["ARMIES", ""]
    for a in armies:
        lines.append(f"{a['name']} ({a['faction'] or 'unaligned'})")
        lines.append(
            f"    Troops: {a['total_troops']} ({a['wounded_troops']} wounded)  |  "
            f"Morale {a['morale']}  |  Organization {a['organization']}  |  "
            f"Food {a['food_days']} days"
        )
        location_line = f"    At: {a['location'] or 'unknown'}"
        if a["commander"]:
            location_line += f"  |  Commander: {a['commander']}"
        lines.append(location_line)
        lines.append(f"    Status: {a['status']}")
        lines.append("")

    return "\n".join(lines).rstrip()


def handle_battles(arg):
    try:
        limit = int(arg) if arg else 5
    except ValueError:
        limit = 5
    limit = max(1, min(limit, 25))

    battles = get_battles(limit=limit)
    if not battles:
        return "No battles recorded yet."

    lines = ["RECENT BATTLES", ""]
    for b in battles:
        lines.append(f"[Turn {b['turn']}] {b['attacker_name']} vs {b['defender_name']}")
        if b["location"]:
            lines.append(f"    Location: {b['location']}")
        lines.append(
            f"    {b['attacker_name']}: {b['attacker_start']} -> {b['attacker_end']} "
            f"({b['attacker_casualties']} casualties)"
        )
        lines.append(
            f"    {b['defender_name']}: {b['defender_start']} -> {b['defender_end']} "
            f"({b['defender_casualties']} casualties)"
        )
        lines.append(f"    Victor: {b['victor']}")
        lines.append("")

    return "\n".join(lines).rstrip()


def handle_loot():
    piles = get_loot_piles(unclaimed_only=True)
    if not piles:
        return "No unclaimed loot. Check the Hall's Military tab to claim any you find."

    lines = ["UNCLAIMED LOOT", ""]
    for p in piles:
        lines.append(f"[Loot #{p['loot_id']}] at {p['location'] or 'unknown location'} (Turn {p['created_turn']})")
        if p["gold"]:
            lines.append(f"    Gold: {p['gold']}")
        for item in p["items"]:
            qty = item.get("quantity", 1)
            lines.append(f"    - {item.get('name', 'item')}" + (f" x{qty}" if qty > 1 else ""))
        lines.append("    (claim via the Hall's Military tab)")
        lines.append("")

    return "\n".join(lines).rstrip()


def handle_events(arg):
    try:
        limit = int(arg) if arg else 5
    except ValueError:
        limit = 5
    limit = max(1, min(limit, 25))

    events = get_recent_events(limit=limit)
    if not events:
        return "No decisive or important events logged yet."

    lines = ["RECENT EVENTS", ""]
    for e in events:
        lines.append(f"[Turn {e['turn']}] {e['title']} ({e['event_type']})")
        if e["summary"]:
            lines.append(f"    {e['summary']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def handle_specializations():
    specs = get_mastery_specializations()
    if not specs:
        return "No specialization trees tracked yet."

    lines = ["MASTERY SPECIALIZATIONS", ""]
    by_mastery = {}
    for s in specs:
        by_mastery.setdefault(s["mastery_name"], []).append(s)

    for mastery_name, group in by_mastery.items():
        lines.append(mastery_name.replace("_", " ").title() + ":")
        for s in group:
            mark = "\u2713 unlocked" if s["unlocked"] else "locked (needs Level 5)"
            lines.append(f"  - {s['specialization']} — {mark}")
        lines.append("")

    return "\n".join(lines).rstrip()


def handle_appearance(arg):
    name = arg.strip()

    if not name:
        all_records = get_all_appearances()
        if not all_records:
            return "No character appearances recorded yet."
        names = ", ".join(r["name"] for r in all_records)
        return f"Recorded appearances: {names}\n\nUsage: /appearance <name>"

    record = get_appearance(name)

    if not record or not (record["canonical_appearance"] or record["current_outfit"]):
        return f"No appearance recorded for '{name}' yet."

    formatted = format_appearance_for_prompt(record)
    return formatted or f"No appearance recorded for '{name}' yet."


def handle_seen(arg):
    name = arg.strip()

    if not name:
        known = get_known_character_names()
        if not known:
            return "No characters indexed yet."
        return f"Known characters: {', '.join(known)}\n\nUsage: /seen <name>"

    history = get_character_scene_history(name, limit=30)

    if not history:
        return f"No scene history found for '{name}' yet. Check spelling, or try /seen with no name to list known characters."

    lines = [f"SCENE HISTORY: {name}", ""]
    for h in history:
        action_preview = (h["player_action"] or "")[:80]
        lines.append(f"Turn {h['turn']} ({h['role']}) — {action_preview}")

    return "\n".join(lines)


def handle_map():
    locations = get_map_locations(discovered_only=True)
    if not locations:
        return "No locations discovered yet."

    lines = ["KNOWN LOCATIONS", ""]
    for loc in locations:
        lines.append(f"{loc['name']} ({loc['kind']}, {loc['region']})")
        if loc["description"]:
            lines.append(f"    {loc['description']}")

    return "\n".join(lines)


def dispatch(text, client=None):
    """
    Parses a /command and returns {"is_command": True, "response": str}
    or {"is_command": False} if not a recognized command syntax.
    """

    stripped = text.strip()

    if not stripped.startswith("/"):
        return {"is_command": False}

    parts = stripped[1:].split(None, 1)
    cmd = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("help", ""):
        return {"is_command": True, "kind": "help", "response": HELP_TEXT}

    if cmd == "stats":
        return {"is_command": True, "kind": "stats", "response": handle_stats()}

    if cmd in ("char", "character", "sheet"):
        return {"is_command": True, "kind": "character", "response": handle_character()}

    if cmd == "addskill":
        return {"is_command": True, "kind": "addskill", "response": handle_addskill(arg)}

    if cmd == "setskill":
        return {"is_command": True, "kind": "setskill", "response": handle_setskill(arg)}

    if cmd == "factions":
        return {"is_command": True, "kind": "factions", "response": handle_factions()}

    if cmd == "retainers":
        return {"is_command": True, "kind": "retainers", "response": handle_retainers()}

    if cmd == "quests":
        return {"is_command": True, "kind": "quests", "response": handle_quests()}

    if cmd == "holdings":
        return {"is_command": True, "kind": "holdings", "response": handle_holdings()}

    if cmd == "traits":
        return {"is_command": True, "kind": "traits", "response": handle_traits()}

    if cmd == "specializations":
        return {"is_command": True, "kind": "specializations", "response": handle_specializations()}

    if cmd == "appearance":
        return {"is_command": True, "kind": "appearance", "response": handle_appearance(arg)}

    if cmd == "seen":
        return {"is_command": True, "kind": "seen", "response": handle_seen(arg)}

    if cmd == "map":
        return {"is_command": True, "kind": "map", "response": handle_map()}

    if cmd == "world":
        return {"is_command": True, "kind": "world", "response": handle_world()}

    if cmd == "armies":
        return {"is_command": True, "kind": "armies", "response": handle_armies()}

    if cmd == "battles":
        return {"is_command": True, "kind": "battles", "response": handle_battles(arg)}

    if cmd == "loot":
        return {"is_command": True, "kind": "loot", "response": handle_loot()}

    if cmd == "events":
        return {"is_command": True, "kind": "events", "response": handle_events(arg)}

    if cmd == "history":
        return {"is_command": True, "kind": "history", "response": handle_history(arg)}

    if cmd in ("memories", "memory"):
        return {"is_command": True, "kind": "memories", "response": handle_memories(arg)}

    if cmd == "recap":
        if client is None:
            return {
                "is_command": True,
                "kind": "error",
                "response": "Recap requires the story engine's Gemini client; none was provided."
            }
        return {"is_command": True, "kind": "recap", "response": handle_recap(client)}

    return {
        "is_command": True,
        "kind": "unknown",
        "response": f"Unknown command: /{cmd}\n\n{HELP_TEXT}"
    }
