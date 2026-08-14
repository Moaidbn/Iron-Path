"""Regression tests for history-aware, location-constrained character interaction.

Run this module only against a disposable campaign database.  It creates no
fixtures in the shipped campaign when executed in a copied project directory.
"""

from database import (
    build_character_history_context,
    get_character_presence_snapshot,
    get_connection,
    get_interaction_preflight,
    get_map_locations,
    get_turn_count,
    initialize_database,
    save_scene,
    validate_and_record_character_presence,
)
from offline_engine import OfflineRPGGame
from app import create_app


def set_campaign_location(location):
    conn = get_connection()
    conn.execute(
        "UPDATE campaign_context SET current_location = ?, updated_turn = 0 WHERE id = 1",
        (location,),
    )
    conn.commit()
    conn.close()


def main():
    initialize_database()
    snapshot = get_character_presence_snapshot()
    assert snapshot, "The canonical registry should seed at least one known character."
    map_names = {row["name"] for row in get_map_locations(discovered_only=False)}

    movable = next(
        (row for row in snapshot if row["availability"] == "active" and row["location"] in map_names),
        None,
    )
    assert movable, "Expected a canonical active character at a known atlas location."
    destination = next(name for name in map_names if name != movable["location"])
    set_campaign_location(movable["location"])
    turn = get_turn_count() + 1

    # A verified local character may be present; a MOVE marks them travelling
    # instead of teleporting them to the destination.
    scene_id = save_scene(turn, "اختبار انتقال قانوني", "مشهد اختبار لا يُشحن مع الحملة.")
    result = validate_and_record_character_presence(
        scene_id,
        turn,
        [movable["name"]],
        [],
        movable["location"],
        [{
            "type": "MOVE",
            "name": movable["name"],
            "to_location": destination,
            "travel_turns": 2,
            "reason": "regression test",
        }],
    )
    assert movable["name"] in result["accepted"], result

    after_move = next(row for row in get_character_presence_snapshot() if row["name"] == movable["name"])
    assert after_move["availability"] == "traveling", after_move
    assert after_move["location"] == movable["location"], after_move
    assert after_move["destination"] == destination, after_move

    # A direct request while the named character travels must be blocked before
    # narrative generation; the context must still include the full public war ledger.
    action = f"قابل {movable['name']} الآن"
    preflight = get_interaction_preflight(action, turn)
    assert preflight["blocked"], preflight
    context, context_preflight = build_character_history_context(action, turn)
    assert context_preflight["blocked"], context_preflight
    assert "PUBLIC KINGDOM HISTORY (authoritative):" in context, context
    assert movable["name"] in context, context
    assert "HARD PRESENCE RULE:" in context, context

    # The offline engine returns the constrained outcome, not a fabricated meeting.
    game = OfflineRPGGame()
    output = game.play_turn(action)
    assert "لا يظهر أحد من العدم" in output["response"], output["response"]
    assert output.get("presence", output.get("character_presence", {})) is not None

    # The player's HTTP route must expose the same constrained outcome.
    client = create_app().test_client()
    http_response = client.post("/play", json={"action": action})
    assert http_response.status_code == 200, http_response.get_data(as_text=True)
    payload = http_response.get_json()
    assert "لا يظهر أحد من العدم" in payload["response"], payload
    assert payload["is_command"] is False, payload

    print("Presence/context regression tests passed.")


if __name__ == "__main__":
    main()
