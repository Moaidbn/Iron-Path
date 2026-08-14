
"""
game.py

Main RPG engine.

Uses:
- Gemini for story generation
- SQLite for complete history
- Local memory search
- No ChromaDB
"""
import os

from dotenv import load_dotenv
from google import genai

from database import (
    initialize_database,
    get_recent_scenes,
    get_turn_count,
    save_scene,
    get_character_stats,
    get_player_state,
    get_factions,
    get_retainers,
    get_quests,
    get_holdings,
    get_world_clock,
    get_traits,
    get_all_appearances,
    get_map_locations,
    get_mastery_specializations,
    seed_starting_equipment_if_empty,
    get_armies,
    get_known_character_names,
    get_character_scene_history,
    backfill_character_mentions_from_scenes,
    backfill_structured_state_from_canon,
    fix_garrison_undercount,
    build_character_history_context as build_presence_context,
)

from memory import build_memory_context
from state_evaluator import evaluate_state_changes
from state_manager import apply_state_changes
from appearance import format_all_appearances_for_prompt

load_dotenv()


# ---------------------------------------------------------
# Game Master prompt
# ---------------------------------------------------------

GAME_MASTER_PROMPT = """
You are the Game Master of a persistent, interactive fantasy RPG,
"The Iron Path".

The player controls the protagonist, Lord Moayed Mudsbane.

The player alone decides what the protagonist does. NEVER decide the
player's actions for them.

You control: NPCs, enemies, kingdoms, politics, factions, economy,
weather, locations, combat, consequences, mysteries, and world events.

Maintain strict continuity. The provided memories, historical scenes,
and CURRENT GAME STATE (factions, retainers, quests, holdings, world
clock, traits) are CANON. Never contradict established facts unless
the story explicitly explains why something changed. If the state
package doesn't mention something, it is not yet established -- don't
invent major permanent facts that belong in canon without letting
them emerge from play.

Continue the existing story rather than restarting it. Do not restart
or retell the old story, and do not summarize the past. Begin from the
current situation as described in RECENT STORY and CURRENT GAME STATE.

NPCs have their own motivations. The world continues to move even when Moayed
is not present. A VERIFIED CHARACTER CONTEXT is supplied for any known character
implicated by the player's action. It is a hard constraint: never narrate a
character as physically present unless that context marks them active at the
verified campaign position. A character who is travelling, remote, captured,
missing, dead, or elsewhere may be mentioned, or contacted only through an
explicit remote channel; they may never appear, answer in person, or act at the
scene. Never teleport a character or invent their presence to make an action
convenient. Do not make every event revolve around
the player. Allow plans to fail, allow NPCs to lie, allow enemies to
adapt. Actions have realistic consequences. Keep political and
military events coherent. Use established relationships.

The player's CHARACTER STATS and TRAITS shape how PLAUSIBLE and how
WELL-EXECUTED the player's attempted actions are:

- Higher mastery in a relevant skill, or a relevant active trait,
  means attempts in that domain go more smoothly or succeed against
  tougher odds.
- Lower mastery means attempts are more likely to be clumsy, partial,
  or to draw complications, without being punishing for its own sake.
- Weave this into the prose naturally. Never state numbers, levels,
  or percentages inside the story -- show it through outcomes, NPC
  reactions, and how events unfold instead.
- A high-mastery character can still fail against a hard or unlucky
  situation; a low-mastery character can still succeed at something
  easy. Stats and traits shift the odds, they don't guarantee outcomes.

FACTION state (trust/fear/loyalty/leverage) and RETAINER state
(loyalty/morale/trust/respect) should visibly inform how NPCs behave
toward the player -- e.g. high trust + low fear reads as genuine
cooperation, low trust + high fear reads as reluctant obedience.

CHARACTER APPEARANCES provided in the state package are canonical and
PERMANENT. Never redescribe a character's established physical traits
differently than given. Current outfits may change as the story
dictates -- narrate clothing changes explicitly when they happen
rather than silently switching a character's described appearance.

Write immersive fantasy prose. Do not write the player's actions or
dialogue for them. Do not give the player choices unless they
naturally arise in the scene. End at a point where the player can
decide what to do next.
"""


def _format_state_package(character_stats, player_state, factions,
                           retainers, quests, holdings, world_clock, traits,
                           appearances, map_locations, specializations, armies):

    stats_text = "\n".join(
        f"- {s['display_name']}: Level {s['level']} ({s['xp']}/{s['xp_needed']} xp) — {s['description']}"
        for s in character_stats
    ) or "None tracked yet."

    unlocked_specs = [s for s in specializations if s["unlocked"]]
    specs_text = "\n".join(
        f"- {s['specialization']} (under {s['mastery_name'].replace('_', ' ')})"
        for s in unlocked_specs
    ) or "None unlocked yet (unlocks at mastery Level 5)."

    player_text = (
        f"Level {player_state['level']} | Reputation {player_state['reputation']}/100 | "
        f"Wealth {player_state['wealth']} | Political Influence {player_state['political_influence']} | "
        f"Military Influence {player_state['military_influence']}"
        if player_state else "Not yet initialized."
    )

    factions_text = "\n".join(
        f"- {f['name']}: trust {f['trust']}, fear {f['fear']}, loyalty {f['loyalty']}, leverage {f['leverage']}"
        for f in factions
    ) or "No factions tracked yet."

    retainers_text = "\n".join(
        f"- {r['name']}: loyalty {r['loyalty']}, morale {r['morale']}, trust {r['trust']}, "
        f"respect {r['respect']}, status {r['status']}"
        + (f", assignment: {r['assignment']}" if r['assignment'] else "")
        for r in retainers
    ) or "No retainers tracked yet."

    active_quests = [q for q in quests if q["status"] == "active"]
    quests_text = "\n".join(
        f"- [{q['quest_id']}] {q['title']}: {q['description'] or ''}"
        for q in active_quests
    ) or "No active quests tracked yet."

    holdings_text = "\n".join(
        f"- {h['name']}: prosperity {h['prosperity']}, security {h['security']}, "
        f"loyalty {h['loyalty']}, military {h['military_strength']}"
        for h in holdings
    ) or "No holdings tracked yet."

    clock_text = f"Day {world_clock['day']}, Month {world_clock['month']}, Year {world_clock['year']} ({world_clock['season']})"

    traits_text = "\n".join(
        f"- {t['display_name']}: {t['description']}"
        for t in traits
    ) or "None unlocked yet."

    appearances_text = format_all_appearances_for_prompt(appearances)

    known_locations_text = ", ".join(loc["name"] for loc in map_locations) or "None recorded yet."

    armies_text = "\n".join(
        f"- {a['name']} ({a['faction'] or 'unaligned'}): {a['total_troops']} troops "
        f"({a['wounded_troops']} wounded), morale {a['morale']}, organization {a['organization']}, "
        f"{a['food_days']} days of food, at {a['location'] or 'unknown location'}"
        + (f", commanded by {a['commander']}" if a['commander'] else "")
        for a in armies
    ) or "No armies tracked yet."

    return f"""
CHARACTER STATS:
{stats_text}

MASTERY SPECIALIZATIONS:
{specs_text}

PLAYER STATE:
{player_text}

ACTIVE TRAITS:
{traits_text}

FACTIONS:
{factions_text}

RETAINERS:
{retainers_text}

ACTIVE QUESTS:
{quests_text}

HOLDINGS:
{holdings_text}

ARMIES (these exact troop numbers are AUTHORITATIVE -- if you narrate
troop counts, casualties, or army strength, they must be consistent
with these figures; do not invent different numbers):
{armies_text}

WORLD CLOCK:
{clock_text}

CHARACTER APPEARANCES (canonical -- never contradict):
{appearances_text}

KNOWN MAP LOCATIONS:
{known_locations_text}
"""


def _build_character_history_context(player_action, recent_scenes):
    """
    Detects which known characters are actually relevant to this
    turn (named in the player's action, or present in the last few
    scenes) and pulls each one's real scene-appearance history from
    the character_mentions index -- so Gemini can check a character's
    established arc directly instead of relying only on keyword-
    scored memory search, which can miss things.
    """
    known_names = get_known_character_names()
    if not known_names:
        return "No character history indexed yet."

    search_text = player_action.lower()
    for _, old_action, old_response in recent_scenes[-2:]:
        search_text += " " + old_action.lower() + " " + old_response.lower()

    relevant_names = []
    for name in known_names:
        first_name = name.split()[0].lower()
        if len(first_name) >= 3 and first_name in search_text:
            relevant_names.append(name)

    if not relevant_names:
        return "No specific character history relevant to this turn."

    blocks = []
    for name in relevant_names[:5]:
        history = get_character_scene_history(name, limit=6)
        if not history:
            continue
        turns_summary = "; ".join(
            f"Turn {h['turn']} ({h['role']})" for h in history
        )
        blocks.append(f"- {name}: appeared in {turns_summary}")

    return "\n".join(blocks) if blocks else "No specific character history relevant to this turn."


class RPGGame:

    def __init__(self):

        initialize_database()
        seed_starting_equipment_if_empty(get_turn_count())
        backfill_character_mentions_from_scenes()
        backfill_structured_state_from_canon()
        fix_garrison_undercount()

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY was not found. "
                "Check your .env file."
            )

        self.client = genai.Client(
            api_key=api_key
        )
    # -----------------------------------------------------
    # Generate a turn
    # -----------------------------------------------------

    def play_turn(self, player_action):

        turn_number = get_turn_count() + 1
        presence_context, presence_preflight = build_presence_context(player_action, turn_number)
        if presence_preflight.get("blocked"):
            detail = presence_preflight.get("message") or "The requested character is not legally available here."
            ai_response = (
                "يتوقف طلبك عند حدٍّ لا تسمح الحملة بتجاوزه: " + detail + " "
                "لا يظهر أحد من العدم ولا تُختصر المسافات في السجل. يمكنك إرسال رسالة أو مبعوث، أو السفر إلى المكان الصحيح، أو انتظار وصول الشخصية."
            )
            blocked_proposal = {
                "canon_facts": [{"category": "CHARACTER", "fact": "منع سجل الحضور لقاءً مباشرًا غير ممكن في هذا الدور."}],
                "characters_present": [],
                "characters_mentioned": [target.get("name") for target in presence_preflight.get("targets", [])],
                "presence_updates": [], "xp_awards": {}, "behavior_changes": {}, "faction_shifts": {},
                "retainer_shifts": {}, "quest_updates": [], "holding_changes": {}, "world_changes": [],
                "inventory_changes": {"added": [], "removed": []}, "economic_entries": [], "army_changes": {},
                "battle_trigger": None, "appearance_updates": [], "map_updates": [], "actions": [],
                "important_event": False, "decisive_action": False, "event_type": "CHARACTER",
                "event_title": "سجل الحضور", "event_summary": "رُفض لقاء يخالف موقع الشخصية أو حالتها.",
            }
            scene_id = save_scene(turn_number, player_action, ai_response)
            state_summary = apply_state_changes(blocked_proposal, scene_id, turn_number, player_action=player_action)
            return {
                "turn": turn_number, "response": ai_response, "level_ups": [],
                "new_traits": state_summary.get("new_traits", []),
                "new_specializations": state_summary.get("new_specializations", []),
                "new_locations": state_summary.get("new_locations", []),
                "battle": None, "loot_created": None,
                "civic_settlement": state_summary.get("civic_settlement"),
                "time_progression": state_summary.get("time_progression"),
                "arrived_characters": state_summary.get("arrived_characters", []),
                "presence": state_summary.get("character_presence"),
                "event": {"important": False, "decisive": False, "type": "CHARACTER", "title": "سجل الحضور", "summary": "رُفض لقاء غير قانوني."},
            }

        # ---------------------------------------------
        # Search long-term memory
        # ---------------------------------------------

        memory_context = build_memory_context(
            player_action
        )

        # ---------------------------------------------
        # Get immediate recent history
        # ---------------------------------------------

        recent_scenes = get_recent_scenes(
            limit=6
        )

        recent_context = ""

        for (
            old_turn,
            old_action,
            old_response
        ) in recent_scenes:

            recent_context += f"""

SCENE #{old_turn}

PLAYER:
{old_action}

GAME MASTER:
{old_response}

"""

        # ---------------------------------------------
        # Current persistent game state
        # ---------------------------------------------

        character_stats = get_character_stats()
        player_state = get_player_state()
        factions = get_factions()
        retainers = get_retainers()
        quests = get_quests()
        holdings = get_holdings()
        world_clock = get_world_clock()
        traits = get_traits()
        appearances = get_all_appearances()
        map_locations = get_map_locations(discovered_only=True)
        specializations = get_mastery_specializations()
        armies = get_armies()

        state_package = _format_state_package(
            character_stats, player_state, factions,
            retainers, quests, holdings, world_clock, traits,
            appearances, map_locations, specializations, armies
        )

        character_history_context = presence_context

        # ---------------------------------------------
        # Build Gemini prompt
        # ---------------------------------------------

        prompt = f"""
SCENE IDENTIFIER (audit only; not a time unit):

{turn_number}


{state_package}


CHARACTER APPEARANCE HISTORY (scenes each relevant character has
actually been present in or mentioned in -- use this to keep their
arc consistent; do not contradict a character's established pattern
of where they've been or what they've done):

{character_history_context}


LONG-TERM MEMORY:

{memory_context}


RECENT STORY:

{recent_context}


PLAYER'S NEW ACTION:

{player_action}


Continue the story from exactly this point.

Do not restart the story.

Do not summarize the past.

Only narrate what happens as a consequence of the
player's current action.
"""

        # ---------------------------------------------
        # Generate story
        # ---------------------------------------------

        response = self.client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[
                GAME_MASTER_PROMPT,
                prompt
            ]
        )

        ai_response = response.text.strip()

        # ---------------------------------------------
        # Save COMPLETE scene
        # ---------------------------------------------

        scene_id = save_scene(
            turn_number,
            player_action,
            ai_response
        )

        scene_for_memory = f"""
SCENE #{turn_number}

PLAYER:
{player_action}

GAME MASTER:
{ai_response}
"""

        # ---------------------------------------------
        # Unified state evaluation
        #
        # One Gemini call proposes canon facts, XP, behavior
        # deltas, faction/retainer shifts, quest/holding
        # updates, and whether this was a decisive/important
        # turn. Python (state_manager.py) validates and is the
        # only thing that writes it to SQLite. This replaces
        # the previous two separate extraction calls.
        # ---------------------------------------------

        state_summary = {
            "canon_facts_saved": 0, "xp_awarded": {}, "faction_shifts": {},
            "retainer_shifts": {}, "quests_updated": [], "holdings_updated": [],
            "new_traits": [], "new_specializations": [], "appearance_updates": [],
            "new_locations": [], "actions": [], "important_event": False,
            "decisive_action": False, "event_title": None, "event_summary": None,
            "event_type": None, "army_updates": [], "battle": None, "loot_created": None,
        }

        try:

            proposal = evaluate_state_changes(
                self.client,
                state_package,
                scene_for_memory
            )

            state_summary = apply_state_changes(
                proposal,
                scene_id,
                turn_number,
                player_action=player_action
            )

        except Exception as error:

            # State evaluation failing should never break the
            # story turn itself -- the narrative already saved.

            print(
                "State evaluation failed:",
                error
            )

        level_ups = [
            {"name": stat_key, "level": info["level"]}
            for stat_key, info in state_summary.get("xp_awarded", {}).items()
            if info.get("leveled_up")
        ]

        # ---------------------------------------------
        # Return scene immediately
        # ---------------------------------------------

        return {
            "turn": turn_number,
            "response": ai_response,
            "level_ups": level_ups,
            "new_traits": state_summary.get("new_traits", []),
            "new_specializations": state_summary.get("new_specializations", []),
            "new_locations": state_summary.get("new_locations", []),
            "battle": state_summary.get("battle"),
            "loot_created": state_summary.get("loot_created"),
            "civic_settlement": state_summary.get("civic_settlement"),
            "time_progression": state_summary.get("time_progression"),
            "arrived_characters": state_summary.get("arrived_characters", []),
            "event": {
                "important": state_summary.get("important_event", False),
                "decisive": state_summary.get("decisive_action", False),
                "type": state_summary.get("event_type"),
                "title": state_summary.get("event_title"),
                "summary": state_summary.get("event_summary"),
                "faction_shifts": state_summary.get("faction_shifts", {}),
                "retainer_shifts": state_summary.get("retainer_shifts", {}),
                "xp_awarded": state_summary.get("xp_awarded", {}),
                "quests_updated": state_summary.get("quests_updated", []),
                "actions": state_summary.get("actions", []),
            } if (state_summary.get("important_event") or state_summary.get("decisive_action")) else None,
        }


