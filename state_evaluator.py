"""
state_evaluator.py

Runs after a narrative scene is generated. Asks Gemini to propose a
structured JSON state-change package (canon facts, XP, behavior
deltas, faction/retainer shifts, quest updates, holding changes,
whether this turn was a decisive/important event).

This module ONLY produces and loosely sanitizes a Python dict.
It never touches SQLite. state_manager.py is responsible for
validating ranges and applying everything.
"""

import json


EVALUATOR_MODEL = "gemini-3.5-flash-lite"

# Fields we accept in the proposal; anything else Gemini invents
# is dropped rather than trusted.
TOP_LEVEL_KEYS = (
    "canon_facts", "xp_awards", "behavior_changes", "faction_shifts",
    "retainer_shifts", "trait_candidates", "quest_updates",
    "inventory_changes", "economic_entries", "holding_changes", "world_changes",
    "important_event", "decisive_action", "event_type",
    "event_title", "event_summary", "appearance_updates",
    "map_updates", "actions", "army_changes", "battle_trigger",
    "characters_present", "characters_mentioned", "presence_updates", "world_lord_updates", "world_lore_updates",
    "elapsed_minutes"
)

EMPTY_PROPOSAL = {
    "canon_facts": [],
    "xp_awards": {},
    "behavior_changes": {},
    "faction_shifts": {},
    "retainer_shifts": {},
    "trait_candidates": [],
    "quest_updates": [],
    "inventory_changes": {"added": [], "removed": []},
    "economic_entries": [],
    "holding_changes": {},
    "world_changes": [],
    "important_event": False,
    "decisive_action": False,
    "event_type": None,
    "event_title": None,
    "event_summary": None,
    "appearance_updates": [],
    "map_updates": [],
    "actions": [],
    "army_changes": {},
    "battle_trigger": None,
    "characters_present": [],
    "characters_mentioned": [],
    "presence_updates": [],
    "world_lord_updates": [],
    "world_lore_updates": [],
    "elapsed_minutes": None,
}


EVALUATOR_PROMPT_TEMPLATE = """
You are the STATE EVALUATOR for a persistent medieval political RPG.

You do NOT write narrative. You read a scene that has already been
written and decide what mechanical state changed as a result.

CONTEXT (for reference, already established -- do not repeat it as
new canon):
{context}

THE SCENE THAT JUST HAPPENED:
{scene}

Return ONLY valid JSON, no markdown fences, no commentary, matching
exactly this structure:

{{
  "canon_facts": [{{"category": "CHARACTER", "fact": "short new fact"}}],
  "xp_awards": {{"Weapons": 0, "Trade": 0, "Conversation": 0}},
  "behavior_changes": {{
    "mercy": 0, "cruelty": 0, "diplomacy": 0, "intimidation": 0,
    "deception": 0, "honesty": 0, "aggression": 0, "pragmatism": 0,
    "generosity": 0, "ambition": 0, "loyalty": 0, "manipulation": 0,
    "risk_taking": 0
  }},
  "faction_shifts": {{"FactionName": {{"trust": 0, "fear": 0, "loyalty": 0, "leverage": 0}}}},
  "retainer_shifts": {{"CharacterName": {{"loyalty": 0, "morale": 0, "trust": 0, "respect": 0}}}},
  "trait_candidates": [],
  "quest_updates": [{{"quest_id": "short_slug", "title": "Title", "status": "active", "description": "..."}}],
  "inventory_changes": {{
    "added": [
      {{"name": "Steel Longsword", "category": "weapon", "quantity": 1,
        "description": "A well-balanced arming sword.", "damage": 12,
        "value": 85, "weight": 4.5, "effect": null, "slot": "weapon"}},
      {{"name": "Boiled Leather Cuirass", "category": "armor", "quantity": 1,
        "description": "Hardened leather, banded at the chest.", "armor_rating": 18,
        "value": 60, "weight": 12, "effect": null, "slot": "chest"}}
    ],
    "removed": []
  }},
  "economic_entries": [
    {{"amount_copper": 0, "entry_type": "story_reward", "counterparty": "Named counterparty", "location": "Known location", "memo": "Short reason"}}
  ],
  "holding_changes": {{"HoldingName": {{"prosperity": 0, "security": 0}}}},
  "world_changes": [],
  "elapsed_minutes": null,
  "important_event": false,
  "decisive_action": false,
  "event_type": null,
  "event_title": null,
  "event_summary": null,
  "appearance_updates": [
    {{"name": "CharacterName", "type": "canonical", "fields": {{"hair_color": "black"}}}},
    {{"name": "CharacterName", "type": "outfit", "fields": {{"cloak": "a captured officer's cloak"}}}}
  ],
  "map_updates": [
    {{"type": "ADD_LOCATION", "name": "Blackstone Pass", "region": "Northern Ashvale",
      "x": 0.62, "y": 0.31, "description": "A narrow mountain passage.", "kind": "settlement"}}
  ],
  "actions": [
    {{"label": "Confront the undersecretary", "type": "CONVERSATION", "requirements": [], "risk": "HIGH"}}
  ],
  "army_changes": {{
    "Mudsbane Field Army": {{"location": "Millbrook Crossing", "commander": "Doss"}}
  }},
  "battle_trigger": null,
  "characters_present": ["Isolde", "Wren"],
  "characters_mentioned": ["Kaine"],
  "presence_updates": [
    {"type": "MOVE", "name": "Isolde", "to_location": "Known location", "travel_minutes": 360, "reason": "Explicitly departed in this scene"}
  ],
  "world_lord_updates": [
    {{"type": "ADD_LORD", "name": "New Lord Name", "title": "Lord of ...", "house": "House ...",
      "seat": "A newly named place", "region": "known region slug or name", "allegiance": "independent",
      "disposition": "wary", "public_agenda": "A short visible goal", "secret": "A short secret if explicitly revealed",
      "biography": "One concise identity note", "discovered": true}}
  ],
  "world_lore_updates": [
    {{"type": "ADD_LORE", "category": "discovery", "title": "Name of a new discovery", "region": "known region slug or name",
      "era": "current age", "keywords": ["short", "tags"], "body": "One durable lore fact newly established in this scene.", "discovered": true}}
  ]
}}

Rules:
- Only include factions/retainers/holdings that were actually meaningfully
  involved in THIS scene. Omit everything else (empty objects, not zeros
  for entities not involved).
- xp_awards, behavior_changes: small integers, usually 0. Most fields
  stay 0 most turns. Never award XP or shift behavior for things that
  didn't happen on the page.
- Only set "important_event" or "decisive_action" to true for genuinely
  significant turns (major combat, betrayal, death, faction-changing
  decision, level-up-worthy moment, major discovery, major loss/gain).
  Most ordinary turns should have both false.
- If important_event or decisive_action is true, fill in event_type,
  event_title, and a 1-2 sentence event_summary. Otherwise leave them null.
- canon_facts should be genuinely new, durable facts -- not a summary
  of the whole scene.
- trait_candidates is just your opinion for the record; it does not
  grant anything by itself.
- army_changes: only for non-combat changes -- an army marching
  somewhere, gaining/losing a commander, recruits joining, supplies
  changing. Use "location"/"commander" for direct facts and
  "total_troops"/"morale"/"organization"/"food_days" as DELTAS (e.g.
  200 recruits joining is {{"total_troops": 200}}, not a restated
  total). NEVER include army casualty numbers here.
- battle_trigger: set this ONLY when the scene depicts an actual
  battle or armed clash between two named forces. You do NOT decide
  who wins or how many die -- that is computed deterministically by
  the game engine after your response, specifically so combat stays
  consistent across turns. Provide only:
  {{"attacker": "Army or force name", "defender": "Army or force name",
    "terrain": "open_field|forest|hills|river_crossing|fortified|urban",
    "weather": "clear|rain|storm|snow|fog"}}
  If the armies aren't yet tracked by exact name, use the most specific
  name the scene gives them (e.g. "Kaine's mercenary company"). Leave
  battle_trigger null for skirmishes involving a handful of named
  individuals rather than organized forces -- those are just narrative.
- characters_present: named characters who were actively on the page
  this scene -- speaking, acting, physically there. characters_mentioned:
  named characters referenced or talked about but not actually present.
  Use each character's established name consistently (the same form
  used elsewhere in this state package) so their history stays linked
  under one identity rather than splitting across name variants. Only
  include named individuals, not generic NPCs ("a guard", "the
  innkeeper") unless the scene actually gives them a name.
- elapsed_minutes: optional non-negative integer estimating only the active in-scene duration, normally 5-240 minutes. Never use it to skip a night, day, journey, or calendar period. Explicit player wait/jump language is parsed and authorized by Python, which overrides this value.
- presence_updates: use ONLY for a named, already-established character whose departure and destination are explicit in the scene. A MOVE schedules travel; it does not teleport anyone. Never create a presence update for a newly invented name, and never mark a travelling, captive, missing, remote, or dead character as present. If the supplied context says a character is unavailable or elsewhere, they MUST remain mentioned only; do not put them in characters_present.
- economic_entries: ONLY use when actual money changed hands in the scene. amount_copper is a signed INTEGER: positive for money received, negative for a paid cost. Use a small amount grounded in the scene; never invent a large windfall. Provide a clear entry_type (for example: story_trade_profit, quest_reward, toll_paid, bribe_paid) and a concise memo. The system blocks overdrafts and records each accepted entry once. NEVER represent currency, coins, crowns, silver, or money as an inventory item; leave them out of inventory_changes entirely.
- inventory_changes "added": only include "damage" for weapons and
  "armor_rating" for wearable armor -- never both on the same item, and
  omit the field entirely (not 0) for items where it doesn't apply.
  "slot" must be one of: head, chest, hands, feet, weapon, accessory, or
  omitted for items that aren't equippable (books, letters, coin, etc).
  "value" is the item's worth in gold/coin, "weight" is in arbitrary
  weight units. Base these numbers on how the item is actually described
  in the scene (a masterwork blade rates higher than a rusted one) --
  don't assign arbitrary numbers disconnected from the narrative. Only
  add items that were actually acquired on the page.
- appearance_updates: "canonical" fields are PERMANENT physical traits
  (hair, scars, build, etc.) -- only include a field here the FIRST time
  it is ever established on the page, never to casually redescribe an
  existing character differently. "outfit" fields are current clothing
  and change freely as the story dictates. Do not invent appearance
  details that were not actually described in the scene.
- map_updates: only propose ADD_LOCATION when the scene actually
  discovers or explicitly names a new place. x and y are fractional
  coordinates (0.0-1.0) roughly matching its position relative to
  Ashvale (0.34, 0.51) and the other known locations. Do not
  regenerate or move existing locations.
- world_lord_updates: use ADD_LORD only when this scene establishes a genuinely NEW, named lord or political figure with durable relevance. Never use it for a person already in CONTEXT or for a generic NPC. It is ADDITIVE ONLY: never revise an established lord, house, faction, seat, or historical fact. At most 2 entries; leave empty in ordinary scenes.
- world_lore_updates: use ADD_LORE only when the scene discovers a durable new treaty, local custom, artifact history, legend, rumor, or chronicle fact that is not already in CONTEXT. Categories are exactly: chronicle, legend, rumor, treaty, artifact, custom, discovery. It is ADDITIVE ONLY and at most 2 entries; leave empty in ordinary scenes.
- actions: ONLY populate this list when important_event or
  decisive_action is true. Provide 2-4 short, distinct options relevant
  to the player's current masteries, traits, retainers, and situation.
  This is never a replacement for free-form input -- leave it empty on
  ordinary turns.
"""


def build_evaluator_prompt(context_text, scene_text):
    return EVALUATOR_PROMPT_TEMPLATE.format(
        context=context_text or "(no additional context)",
        scene=scene_text
    )


def _clean_json_text(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()
    return text


def evaluate_state_changes(client, context_text, scene_text):
    """
    Calls Gemini for a structured state-change proposal.
    Returns a dict shaped like EMPTY_PROPOSAL on any failure --
    callers can always trust the shape, even if empty.
    """

    prompt = build_evaluator_prompt(context_text, scene_text)

    try:
        response = client.models.generate_content(
            model=EVALUATOR_MODEL,
            contents=prompt
        )
    except Exception as error:
        print("State evaluator call failed:", error)
        return dict(EMPTY_PROPOSAL)

    text = _clean_json_text(response.text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        print("State evaluator returned invalid JSON; ignoring this turn's state proposal.")
        return dict(EMPTY_PROPOSAL)

    if not isinstance(parsed, dict):
        return dict(EMPTY_PROPOSAL)

    # Keep only recognized top-level keys, fall back to empty defaults
    # for anything missing or malformed.
    cleaned = dict(EMPTY_PROPOSAL)

    for key in TOP_LEVEL_KEYS:
        if key in parsed:
            cleaned[key] = parsed[key]

    return cleaned
