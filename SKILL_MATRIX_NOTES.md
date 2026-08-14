# Skill Matrix and Deterministic XP Policy

## Purpose

This update makes progression **deterministic and local**. The Game Master may describe the consequence of an action, but it cannot select a mastery, grant XP, or modify campaign mechanics. `offline_engine.py` classifies the submitted player action, constructs the allowed `xp_awards`, and `state_manager.py` accepts only known mastery keys before writing to SQLite.

## Action-to-mastery matrix

| Action category | English examples | Arabic examples | XP awards per completed action | Notes |
|---|---|---|---:|---|
| Movement | `walk toward Isolde` | `امش نحو إيزولد` | None | Movement and arrival alone never award mastery XP. |
| Rest / recovery | `rest at camp` | `استرح في المعسكر` | None | Recovery is not a mastery exercise. |
| Exploration | `search the ruined road` | `استكشف الطريق القديم` | Exploration +8 | Searching, scouting, route reading, or discovery. |
| Conversation / diplomacy | `talk to Isolde` | `تحدث مع إيزولد` | Conversation +10 | A verified character meeting retains its deliberate special reward of Conversation +8. |
| Trade / negotiation | `trade grain at the market` | `تاجر في السوق` | Trade +10; Conversation +3 | Commerce earns trade XP; negotiation is a limited secondary skill. |
| One-on-one duel | `challenge the guard to a duel` | `تحدى الحارس في مبارزة` | Dueling +12 | Personal timing, positioning, and counters; no automatic battlefield weapons XP. |
| Field combat | `fight the raiders` | `قاتل الغزاة` | Weapons +10; Strategy +4 | Tactical combat practice, not a personal duel. |
| Battle command | `command the army in battle` | `قد الجيش في المعركة` | Weapons +9; Strategy +8; Leadership +5 | Large-scale battle action involving troops and command. |
| Planning / strategy | `plan a fallback strategy` | `خطط لاستراتيجية بديلة` | Strategy +10; Leadership +6 | Planning routes, contingencies, supplies, formations, or campaign decisions. |
| Leadership | `lead the garrison` | `قد الحامية` | Leadership +10 | Directing people, holding authority, morale, or cohesion. |
| Intrigue | `spy on the court` | `تجسس على البلاط` | Intrigue +10; Conversation +4 | Spying, deception, leverage, or covert social work. |

## Guardrails

1. Only the local `ActionProfile` creates `xp_awards`; narration is never trusted as a source of progression.
2. `state_manager.py` maps only explicit short keys (`weapons`, `dueling`, `trade`, `conversation`, `strategy`, `leadership`, `exploration`, `intrigue`) to known SQLite mastery rows.
3. Unknown, malformed, zero, or negative awards are ignored.
4. A maximum of 25 XP may be applied to any one mastery in a single action.
5. Movement and rest have an empty award map and cannot become important campaign events merely because of turn numbering.
6. Detection prioritizes explicit battle and planning language above ambiguous short command words, including Arabic wording.

## Masteries added to the campaign registry

| Mastery | Role |
|---|---|
| Weapons Mastery | General battlefield combat and weapons use. |
| Dueling Mastery | One-on-one combat, footwork, timing, and counters. |
| Trade Mastery | Commerce, deals, tariffs, and market activity. |
| Conversation Mastery | Persuasion, reading people, and dialogue. |
| Strategy Mastery | Planning campaigns, tactics, positioning, and contingencies. |
| Leadership Mastery | Directing people, morale, authority, and cohesion. |
| Exploration Mastery | Routes, searching, locations, and travel survival. |
| Intrigue Mastery | Spying, deception, leverage, and covert action. |

## Verification completed

- Python syntax validation for `offline_engine.py`, `state_manager.py`, `database.py`, and `app.py`.
- Deterministic classification test covering all categories above in Arabic and English.
- SQLite integration test on a temporary database, verifying the exact mastery deltas and confirming that unrelated masteries do not change.
- No campaign SQLite database was modified during testing.

## Testing on Windows

Restart the game after replacing the code files, then submit one action from each category. The event card shows the actual persisted awards. A walk or rest action must show no XP card; a trade action should show both Trade and the smaller Conversation award; planning should show Strategy and Leadership.

Existing XP is intentionally not recalculated automatically. Correcting historical entries requires a reviewed migration so valid XP is not removed.
