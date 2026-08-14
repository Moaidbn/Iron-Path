import re
from collections import Counter

from database import get_connection


STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on",
    "for", "with", "from", "at", "by", "is", "are", "was",
    "were", "be", "been", "has", "have", "had", "that",
    "this", "it", "as", "into", "after", "before", "about",
    "their", "his", "her", "its", "they", "them", "he", "she",
    "you", "your", "i", "we", "our", "but", "not"
}


def tokenize(text):
    words = re.findall(
        r"[A-Za-zÀ-ÿ0-9']+",
        text.lower()
    )

    return [
        word
        for word in words
        if word not in STOP_WORDS
        and len(word) > 2
    ]


def score_text(query, document):
    query_words = tokenize(query)
    document_words = tokenize(document)

    if not query_words or not document_words:
        return 0

    query_counts = Counter(query_words)
    document_counts = Counter(document_words)

    score = 0

    for word, count in query_counts.items():
        if word in document_counts:
            score += min(count, 3) * min(
                document_counts[word],
                5
            )

    query_lower = query.lower()
    document_lower = document.lower()

    if query_lower in document_lower:
        score += 15

    for word in set(query_words):
        if len(word) >= 5 and word in document_lower:
            score += 2

    return score


def search_memories(query, limit=12):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            memories.id,
            memories.scene_id,
            memories.category,
            memories.content,
            scenes.turn_number
        FROM memories
        LEFT JOIN scenes
            ON memories.scene_id = scenes.id
        """
    ).fetchall()

    conn.close()

    scored = []

    for row in rows:
        memory_id = row[0]
        scene_id = row[1]
        category = row[2]
        content = row[3]
        turn_number = row[4]

        score = score_text(query, content)

        if score > 0:
            if category == "PLAYER":
                score += 2
            elif category == "CHARACTER":
                score += 3
            elif category == "QUEST":
                score += 3
            elif category == "EVENT":
                score += 2

            scored.append(
                (
                    score,
                    turn_number or 0,
                    category,
                    content
                )
            )

    scored.sort(
        key=lambda x: (x[0], x[1]),
        reverse=True
    )

    return [
        {
            "score": item[0],
            "turn": item[1],
            "category": item[2],
            "content": item[3]
        }
        for item in scored[:limit]
    ]


def search_scenes(query, limit=6):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            id,
            turn_number,
            player_action,
            ai_response
        FROM scenes
        """
    ).fetchall()

    conn.close()

    scored = []

    for row in rows:
        scene_id = row[0]
        turn_number = row[1]
        player_action = row[2]
        ai_response = row[3]

        combined = (
            f"{player_action}\n"
            f"{ai_response}"
        )

        score = score_text(
            query,
            combined
        )

        if score > 0:
            scored.append(
                (
                    score,
                    turn_number,
                    scene_id,
                    player_action,
                    ai_response
                )
            )

    scored.sort(
        key=lambda x: (x[0], x[1]),
        reverse=True
    )

    return [
        {
            "score": item[0],
            "turn": item[1],
            "scene_id": item[2],
            "player_action": item[3],
            "ai_response": item[4]
        }
        for item in scored[:limit]
    ]


def build_memory_context(query):
    memories = search_memories(
        query,
        limit=12
    )

    scenes = search_scenes(
        query,
        limit=4
    )

    context = []

    if memories:
        context.append(
            "RELEVANT LONG-TERM MEMORIES:"
        )

        for memory in memories:
            context.append(
                f"[{memory['category']}] "
                f"{memory['content']}"
            )

    if scenes:
        context.append(
            "\nRELEVANT HISTORICAL SCENES:"
        )

        for scene in scenes:
            context.append(
                f"\n--- Turn {scene['turn']} ---\n"
                f"Player: {scene['player_action']}\n"
                f"Game Master: {scene['ai_response']}"
            )

    if not context:
        return "No specific older memories were found."

    return "\n".join(context)


def extract_memories(client, scene):
    import json

    prompt = f"""
You are the memory manager for a persistent fantasy RPG.

Analyze this newly completed scene.

Extract ONLY facts that should persist into future turns.

Use these categories:

PLAYER
CHARACTER
WORLD
QUEST
ITEM
EVENT
LOCATION

Prioritize:

- character relationships
- important character decisions
- secrets
- promises
- quests
- political developments
- important items
- inventory changes
- major events
- permanent consequences
- important locations
- changes to the player's status
- unresolved plot threads

Do NOT summarize ordinary prose.

Do NOT create memories for trivial descriptions.

Return ONLY valid JSON.

Format:

[
  {{
    "category": "CHARACTER",
    "content": "Captain Marcus now distrusts Moayed."
  }}
]

If nothing important happened, return [].

SCENE:

{scene}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    text = response.text.strip()

    if text.startswith("```"):
        text = text.replace(
            "```json",
            ""
        )
        text = text.replace(
            "```",
            ""
        )
        text = text.strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        print(
            "Warning: Gemini returned invalid memory JSON."
        )
        return []


def save_extracted_memories(
    scene_id,
    memories
):
    from database import save_memory

    for memory in memories:
        category = memory.get(
            "category",
            "EVENT"
        )

        content = memory.get(
            "content",
            ""
        ).strip()

        if content:
            save_memory(
                scene_id,
                category,
                content
            )


def extract_skill_progress(client, scene, known_stats):
    """
    Asks Gemini whether the player's action this turn meaningfully
    exercised any tracked character stat (e.g. fighting exercises
    weapons_mastery, bartering exercises trade_mastery, persuading
    or deceiving in dialogue exercises conversation_mastery).

    Returns a list of {"skill": <internal name>, "xp_gain": int,
    "reason": str} dicts. XP is awarded conservatively and only for
    meaningful, on-page use -- not for every turn automatically.
    """
    import json

    if not known_stats:
        return []

    stat_lines = "\n".join(
        f"- {stat['name']} ({stat['display_name']}): {stat['description']}"
        for stat in known_stats
    )

    prompt = f"""
You are the skill-progression tracker for a persistent fantasy RPG.

TRACKED CHARACTER STATS (use the exact internal name in your answer):

{stat_lines}

Analyze the scene below and decide whether the PLAYER's own action
this turn meaningfully exercised any of these stats. Examples:
fighting or dueling exercises a weapons/combat stat, bartering or
negotiating trade terms exercises a trade stat, persuading, lying
convincingly, or reading a room in dialogue exercises a
conversation/social stat.

Award xp conservatively:
- 0: the stat was not meaningfully used this turn
- 3 to 8: routine, low-stakes use
- 10 to 20: a difficult, risky, or impressive use

Do not invent uses that did not happen on the page. Do not award xp
to a stat just because it exists. Most turns should touch zero or
one stat, occasionally two.

Return ONLY valid JSON, with this exact format and nothing else:

[
  {{"skill": "weapons_mastery", "xp_gain": 8, "reason": "short reason"}}
]

If nothing qualifies, return [].

SCENE:

{scene}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    text = response.text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        print(
            "Warning: Gemini returned invalid skill JSON."
        )
        return []