# XP Engine Fix — Movement Must Not Grant Conversation Mastery

## What was wrong

The active runtime engine is `offline_engine.py`, not the narrative model. Before this fix, the deterministic action profiles assigned **Conversation Mastery XP** to three action categories that do not necessarily exercise conversation:

| Action category | Old behavior | Why it was wrong |
|---|---:|---|
| Ordinary movement / unrecognized action | +7 Conversation XP | Walking and generic choices are not dialogue practice. |
| Exploration / travel | +8 Conversation XP | Moving, travelling, or investigating a place is not automatically social skill use. |
| Rest / recovery | +5 Conversation XP | Resting is a campaign-state action, not a conversation exercise. |
| Blocked meeting request | +2 Conversation XP | A meeting refused by the presence ledger did not occur. |

This behavior was deterministic and happened **before** the NVIDIA Game Master rewrote the prose. The model was not the source of the XP award.

## Fixed policy

| Player action | Engine classification | Mastery XP |
|---|---|---:|
| `walk toward Isolde`, `move`, `approach`, Arabic movement equivalents | Movement | None |
| `travel`, `explore`, `search`, Arabic exploration equivalents | Exploration | None |
| `talk to Isolde`, `speak`, `negotiate`, Arabic dialogue equivalents | Diplomacy | Conversation XP |
| `attack`, `fight`, `battle` | Combat | Weapons XP |
| `buy`, `sell`, `trade`, `market` | Trade | Trade XP |
| `rest`, `sleep`, `camp` | Recovery | None |
| Generic decision | Default | None |

The engine also now returns the local verified character-meeting scene correctly when an explicit conversation targets a character who is physically present.

## Tests completed

The fix was tested without changing the campaign database:

1. Deterministic profile test: movement, travel, dialogue, combat, trade, rest, and default actions were classified correctly.
2. Temporary SQLite integration test: `walk toward Isolde` left `conversation_mastery` at `0`, while `talk to Isolde` correctly added `8` Conversation Mastery XP through the verified character-meeting path.

## Update on Windows

1. Back up `data\story.db` before replacing any files.
2. Replace `offline_engine.py` with the updated version from this package, or replace the project files while preserving `.env` and `data\story.db`.
3. Restart the server:

```powershell
cd "C:\Users\medom\desktop\AI_RPG"
python app.py
```

4. Test `walk toward Isolde`. The event panel must not list Conversation Mastery XP.
5. Test `talk to Isolde` or `speak with Isolde`. Conversation Mastery XP may appear only when a real dialogue action is completed.

## Existing XP already awarded

This patch prevents future incorrect awards. It deliberately does **not** subtract existing XP automatically, because historical turns can contain a mixture of valid dialogue XP and invalid movement XP. A campaign-specific correction should be made only after reviewing the affected turn log and taking a database backup.
