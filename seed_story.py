"""
seed_story.py

One-time migration script: loads "The Iron Path" story so far into
the existing database.py schema (scenes + memories), so the
Game Master can resume play from exactly where it left off.

Run once:

    python seed_story.py

It is safe to re-run against a fresh data/ directory, but running it
twice against the same database.db will duplicate rows -- delete
data/story.db first if you want a clean reseed.
"""

from database import (
    initialize_database,
    save_scene,
    save_memory,
)

# ---------------------------------------------------------------------
# 1. CONDENSED SCENE LOG
#    Each entry compresses several real turns into one checkpoint scene.
#    turn_number is left sparse (10s) so you can later insert real
#    turn-by-turn history between checkpoints without renumbering.
# ---------------------------------------------------------------------

SCENES = [
    (10, "Investigate the war camp found near Millbrook Crossing after the Baron doubles the levy.",
     "The player, a peasant of Mudroot named Moayed, scouts a war camp bearing an unknown black-wolf "
     "banner. He tracks the company to a larger camp near the river, then withdraws to warn the village "
     "rather than risk discovery."),

    (20, "Use stolen arrows and the village elder to bait Baron Ashvale's men and Kaine's mercenary company into fighting each other.",
     "Moayed engineers a clash between Baron Ashvale's garrison and Lord Kaine's mercenary company at "
     "Millbrook Crossing. Both sides bleed each other badly overnight. At dawn, Moayed's archer Tomas kills "
     "the wounded mercenary company's officer in a way that frames Ashvale's men, then Moayed's villagers "
     "ambush and wipe out the weakened Ashvale garrison, appearing to the mercenaries as rescuers."),

    (30, "Negotiate with the mercenary sergeant Doss; offer refuge from Lord Kaine in exchange for aid.",
     "Doss, the surviving mercenary sergeant, agrees to ally with Moayed after learning Kaine would likely "
     "sacrifice his broken company to save face. Moayed proposes disguising his villagers in dead Ashvale "
     "soldiers' armor to infiltrate the Baron's manor directly."),

    (40, "Infiltrate Ashvale's manor disguised as returning soldiers; summon all officers to the hall.",
     "The disguised party bluffs its way through the gate. Harn (posing as the returning captain) summons "
     "the Baron's officers to hear terms from the 'captured' Doss. Moayed puts a blade to Baron Corvin "
     "Ashvale's throat in his own hall, and the disarmed garrison and household surrender."),

    (50, "Execute Baron Ashvale personally; imprison his family pending judgment; address the assembled garrison and villagers.",
     "Moayed kills Corvin Ashvale himself. He imprisons the Baroness Isolde, her son Edrin (12), and an "
     "elder relative rather than executing them, and declares Ashvale's fate will be decided by the "
     "villagers he wronged. He takes the name Moayed Mudsbane and adopts a grey-wolf-and-roots sigil."),

    (60, "Negotiate terms with Baroness Isolde: political marriage, her son's future, and her family's political connections.",
     "Isolde secures her son's safety and her own standing through negotiation rather than coercion, "
     "trading her family's noble connections and counsel for a formal (initially political) marriage to "
     "Moayed and recognition as Lady Mudsbane."),

    (70, "Formalize Doss's mercenary company as the foundation of a standing army; discover Ashvale's secret correspondence with Lord Kaine.",
     "Doss's surviving company becomes the core of a new garrison. Letters are found proving Ashvale and "
     "Kaine staged the Millbrook incident together to justify the doubled levy and cover a private debt "
     "Ashvale owed Kaine -- corruption, not a real border threat."),

    (90, "Send a formal council (Harn, Doss, Isolde, later Corren) to manage internal affairs, spying, and army-building; recruit nearby villages.",
     "A working council forms: Harn manages walls/food/villages, Isolde builds a spy network and manages "
     "diplomacy, Doss manages the garrison. Five villages under old Ashvale writ pledge loyalty after "
     "hearing of fair land-share terms replacing Ashvale's extractive taxation."),

    (110, "Petition the crown with Kaine's incriminating letters, paired with a formal claim to legitimate the succession.",
     "Lady Isolde drafts a formal petition to the crown exposing the Ashvale-Kaine conspiracy and "
     "requesting recognition of Moayed's claim to Ashvale hold. Magistrate Aldric Venn is dispatched to "
     "investigate, interviews the household and villagers, and forms a favorable private opinion of "
     "Moayed's governance."),

    (130, "Host a full gathering of lesser lords timed to receive the crown's verdict in front of them; the verdict arrives.",
     "The crown formally recognizes Moayed as rightful lord of Ashvale hold, voids Kaine's debt claim as "
     "corruptly obtained, and refers Kaine to the crown council to answer for conspiracy. Several lesser "
     "lords pledge deeper alliance on the spot. Moayed privately confesses to Isolde an ambition beyond "
     "the crown itself: to build toward becoming emperor of the continent."),

    (140, "Handle a covert reprisal: Kaine's hired men sabotage the granary; interrogate the captured saboteurs.",
     "Captain Corren (a former Kaine officer who defected earlier) confirms via interrogation that Kaine "
     "paid the saboteurs and is separately trying to bribe influence at the capital ahead of his hearing. "
     "Moayed authorizes Tomas to build 'Roots,' a small deniable squad for assassination, sabotage, and "
     "dirty work the open court can never be seen doing."),

    (150, "Travel to Port of Windmere with Isolde, Wren, and Corren to investigate selling Greywood timber to shipwrights.",
     "En route, the party pardons and recruits a band of ex-Kaine soldiers turned bandits (led by Beck) "
     "after a road confrontation. At Windmere, a dockside clash with Salt Compact soldiers is resolved "
     "through negotiation instead of violence, winning a future favor from Compact Factor Aldous Renn. "
     "Moayed frames his ambition to Renn explicitly as building 'a trade state,' not a conquest."),

    (160, "Negotiate a formal trade agreement (timber, shipbuilding stake, salt) with Windmere and the Salt Compact; recruit a master smith.",
     "Isolde negotiates a structured trade deal: standing Greywood ironwood timber contracts, partial "
     "ownership stakes in ships built from that timber, Compact shipping rights, and expanded salt "
     "production -- pending Windmere council ratification. Blacksmith Mira agrees to relocate to Ashvale "
     "hold. A rumor surfaces of a distant southern trade route, 'the Far Crossing,' and a captain named "
     "Ilsbeth Voro who sails it."),

    (170, "Receive urgent word en route home: Kaine's crown hearing has been moved up and Kaine has fled his own seat.",
     "Isolde's spy network reveals Kaine bribed a capital undersecretary, Pellin Ashcroft, to move his "
     "hearing up to five days -- too soon for Corren and the defectors to be gathered as witnesses under "
     "normal timing -- and that Kaine has departed his March lands with a small escort, destination "
     "unknown. Moayed splits the party: Corren rides hard for the capital with evidence and defector "
     "testimony, while a rider carries orders back to Harn and Tomas to move against Kaine's now-exposed "
     "weakness, explicitly leaving Roots' exact action to their judgment."),
]

# ---------------------------------------------------------------------
# 2. CATEGORIZED MEMORIES
#    Each tuple is (scene_index_into_SCENES, category, content).
#    scene_index is 0-based and maps to the SCENES list above so the
#    memory gets attached to the real scene_id once scenes are saved.
# ---------------------------------------------------------------------

MEMORIES = [
    # PLAYER
    (10, "PLAYER", "The player is Lord Moayed Mudsbane, born a peasant of Mudroot village."),
    (10, "PLAYER", "Title: Lord of Ashvale hold, crown-recognized. Sigil: a grey wolf's head rising from tangled roots, House Mudsbane."),
    (10, "PLAYER", "Married to Isolde (formerly Baroness Ashvale) in a marriage that began as political necessity and has grown into a real partnership."),
    (10, "PLAYER", "Stated long-term ambition, confessed privately to Isolde: not to remain a mere lord, but to eventually become emperor of the continent, beginning with building 'a trade state.'"),
    (10, "PLAYER", "Wears mid-weight, salt-treated coastal armor with the Mudsbane sigil etched into the shoulder plate, plus a main sword and a dual-wield dagger, all forged by Mira."),

    # CHARACTER
    (5, "CHARACTER", "Isolde: widow of Baron Corvin Ashvale, now Lady Mudsbane. Sharp political negotiator, runs the hold's spy network, genuinely partnered with Moayed rather than merely bound to him."),
    (5, "CHARACTER", "Wren: Moayed's younger sister. Capable fighter and archer-in-training, present at the manor's fall, betrothed (unmarried, unhurried) to Edrin."),
    (5, "CHARACTER", "Edrin: Isolde's son by the slain Baron Ashvale, age 12, ward and heir-presumptive, being trained in archery and swordsmanship, genuinely loyal to Moayed."),
    (7, "CHARACTER", "Harn: former soldier, Moayed's most trusted advisor, manages internal affairs, walls, food, and village outreach."),
    (7, "CHARACTER", "Doss: mercenary sergeant, former captain of a free company contracted to Lord Kaine, defected after Millbrook Crossing, now trains and commands the garrison."),
    (11, "CHARACTER", "Corren: former captain under Lord Kaine, defected after his own men mutinied against him (a mutiny secretly engineered by Moayed's side), now a fully loyal officer overseeing village defense."),
    (11, "CHARACTER", "Tomas: scout and archer, trained villager marksmen, now leads 'Roots,' a secret 6-man squad for deniable dirty work."),
    (9, "CHARACTER", "Maren: elder of Mudroot village, respected community leader."),
    (5, "CHARACTER", "Baron Corvin Ashvale: former tyrant lord of Ashvale hold, killed personally by Moayed after his conspiracy with Lord Kaine was exposed."),
    (7, "CHARACTER", "Lord Reventh Kaine: rival northern lord, conspired with Ashvale to stage a false border incident and extort levies; now facing a crown hearing for conspiracy, financially strained, militarily gutted after his company defected, and has fled his own seat with a small escort."),
    (10, "CHARACTER", "Magistrate Aldric Venn: crown investigator who recommended in Moayed's favor; privately warned that a cornered Kaine becomes more dangerous once he has nothing left to lose."),
    (12, "CHARACTER", "Corbin Voss: observer for House Voss, a merchant family owed debt by the Ashvale estate; cautiously friendly, negotiating in good faith."),
    (10, "CHARACTER", "Lord Petyr Halgrove: minor lord of Halgrove Field who pledged alliance and is staying as an observed guest; withdrew an earlier marriage proposal upon learning Moayed's household was already settled."),
    (12, "CHARACTER", "Harbor-Reeve Sella Cray: pragmatic leader of Port of Windmere's council."),
    (12, "CHARACTER", "Factor Aldous Renn: Salt Compact representative; owes Moayed a future favor after a dockside incident involving Compact Captain Ress; increasingly interested in Moayed's 'trade state' framing."),
    (12, "CHARACTER", "Mira: master coastal blacksmith from Windmere, agreed to relocate her forge to Ashvale hold within the season."),
    (12, "CHARACTER", "Beck: former Kaine soldier turned desperate bandit, pardoned and recruited into Moayed's garrison along with five of his men after a road confrontation."),
    (12, "CHARACTER", "Captain Ilsbeth Voro: rumored ship captain said to sail 'the Far Crossing,' a distant southern trade route beyond normal Compact reach; not yet met."),

    # WORLD
    (0, "WORLD", "The setting is the Kingdom of Aldenmere, described from the start as aging and quietly crumbling -- its throne has not yet directly entered the story."),
    (0, "WORLD", "The Greywood: dense old-growth forest surrounding Ashvale hold and Mudroot; now formally claimed as hold property, with a monopoly on timber and hunting rights."),
    (1, "WORLD", "River Ashen and Millbrook Crossing: the river and crossing where the founding battle of the story took place."),
    (12, "WORLD", "Port of Windmere: coastal town on the western edge of Moayed's known reach, loosely governed by a town council under Harbor-Reeve Sella Cray."),
    (12, "WORLD", "The Salt Compact: a merchant shipping consortium controlling much of the southern coastal trade; watches inland power shifts warily and now owes Moayed a favor."),
    (8, "WORLD", "Eastern Gentry lands: minor, unaligned lesser lords across the River Ashen, not yet engaged."),
    (10, "WORLD", "Halgrove Field: modest holding to the southeast, along the road to the capital, seat of allied Lord Halgrove."),
    (10, "WORLD", "The Capital: seat of the crown, several days southeast of Ashvale hold."),
    (7, "WORLD", "House Voss: a wealthy merchant family based near the capital, owed a debt by the Ashvale estate, cautiously exploring partnership rather than pressing the claim."),
    (12, "WORLD", "'The Far Crossing': a rumored trade route south, past waters the Salt Compact doesn't fully control -- unexplored, a loose thread for future story."),

    # QUEST (open/unresolved threads)
    (13, "QUEST", "Kaine's crown hearing has been moved up to five days from the discovery of the letter, reportedly through a bribed capital undersecretary named Pellin Ashcroft, to rush judgment before Moayed's evidence and witnesses can be properly presented."),
    (13, "QUEST", "Corren is riding hard for the capital with defector witnesses to testify at Kaine's hearing before it is rushed to a close."),
    (13, "QUEST", "A rider has been sent to Harn and Tomas at Ashvale hold with orders to compile evidence of Kaine's granary sabotage and to act on Kaine's current weakness and exposure -- deliberately leaving the extent of that action, including possible use of the Roots squad, to their judgment."),
    (12, "QUEST", "Windmere's council is expected to formally ratify the timber/shipbuilding/salt trade terms within about a week of the visit."),
    (12, "QUEST", "Mira the blacksmith is expected to relocate her forge to Ashvale hold within the season."),
    (6, "QUEST", "Wren and Edrin remain betrothed but unmarried; both have asked to be genuinely consulted rather than simply informed when the marriage is actually arranged."),
    (11, "QUEST", "A third captured saboteur is being held alive in the dungeon as a potential source or bargaining piece, deliberately not executed."),
    (10, "QUEST", "Long-term ambition, not yet acted on: expand influence east and west beyond current borders, and eventually pursue continental-scale power."),

    # ITEM
    (10, "ITEM", "A ring carved from Greywood ironwood, etched with the Mudsbane sigil, was gifted to Magistrate Venn as a departure gift; he wears it and has pledged to speak honestly of its origin."),
    (11, "ITEM", "A coin stamped with Lord Kaine's private wolf's-head mark was recovered from captured saboteurs as evidence of his involvement in the granary sabotage."),
    (12, "ITEM", "New personal armor and weapons: mid-weight, salt-treated coastal armor etched with the Mudsbane sigil, plus a main sword and a paired dual-wield dagger, all crafted by Mira in Windmere."),

    # EVENT (major, permanent consequences)
    (5, "EVENT", "Moayed personally killed Baron Corvin Ashvale in his own hall and seized Ashvale hold."),
    (10, "EVENT", "The crown formally recognized Moayed's claim to Ashvale hold, voided Kaine's debt claim as corruptly obtained, and referred Kaine to the crown council to answer for conspiracy -- delivered publicly in front of an assembled gathering of lesser lords."),
    (11, "EVENT", "Kaine's mercenary column was made to mutiny against its own captain through an engineered scandal, resulting in the wholesale defection of roughly forty-three soldiers (including Corren) into Moayed's service without open battle."),
    (11, "EVENT", "'Roots,' a six-man deniable operations squad for assassination, sabotage, and covert action, was formed under Tomas after Kaine's men sabotaged the hold's granary."),
    (12, "EVENT", "A dockside confrontation with Salt Compact soldiers at Windmere was resolved through negotiation rather than violence, winning trade terms and a standing favor instead of open conflict."),
    (13, "EVENT", "Kaine's hearing was abruptly moved up through bribery, and Kaine fled his own seat with a small escort; his current location is unknown."),

    # LOCATION
    (5, "LOCATION", "Ashvale hold: Moayed's seat of power, formerly Baron Ashvale's manor, now bearing the Mudsbane wolf-and-roots banners."),
    (0, "LOCATION", "Mudroot: Moayed's home village, now fully loyal and resettled within Ashvale hold's protection."),
]

# ---------------------------------------------------------------------
# 3. RUN THE MIGRATION
# ---------------------------------------------------------------------

def run():
    initialize_database()

    print()
    print("======================================")
    print("      THE IRON PATH MIGRATION")
    print("======================================")
    print()

    # -------------------------------------------------
    # Save all historical scenes
    # -------------------------------------------------

    scene_ids_by_turn = {}

    for turn_number, player_action, ai_response in SCENES:

        scene_id = save_scene(
            turn_number,
            player_action,
            ai_response
        )

        scene_ids_by_turn[turn_number] = scene_id

        print(
            f"Saved scene turn={turn_number} -> id={scene_id}"
        )

    # -------------------------------------------------
    # Convert the memory references used by your file.
    #
    # Your MEMORIES use checkpoint numbers:
    #
    # 0  = Turn 10
    # 1  = Turn 20
    # ...
    # 10 = Turn 110
    # 11 = Turn 120
    # 12 = Turn 130
    # 13 = Turn 140 / later checkpoint references
    #
    # Some of the data uses the actual turn number instead,
    # such as 10, 11 and 12.
    #
    # We resolve them safely below.
    # -------------------------------------------------

    def resolve_scene_reference(reference):

        # First: direct checkpoint turn.
        if reference in scene_ids_by_turn:
            return scene_ids_by_turn[reference]

        # Second: original zero-based scene index.
        if 0 <= reference < len(SCENES):

            turn_number = SCENES[reference][0]

            return scene_ids_by_turn[turn_number]

        # Third: checkpoint numbering used by the original
        # memory comments.
        #
        # Example:
        # 0 -> Turn 10
        # 1 -> Turn 20
        # ...
        checkpoint_turn = (reference + 1) * 10

        if checkpoint_turn in scene_ids_by_turn:
            return scene_ids_by_turn[checkpoint_turn]

        # If we reach this point, attach the memory to the
        # latest scene rather than crashing.
        latest_turn = max(scene_ids_by_turn.keys())

        print(
            f"Warning: could not resolve memory reference "
            f"{reference}. Attaching to Turn {latest_turn}."
        )

        return scene_ids_by_turn[latest_turn]

    # -------------------------------------------------
    # Save memories
    # -------------------------------------------------

    memory_count = 0

    for scene_reference, category, content in MEMORIES:

        scene_id = resolve_scene_reference(
            scene_reference
        )

        save_memory(
            scene_id,
            category,
            content
        )

        memory_count += 1

    # -------------------------------------------------
    # Finished
    # -------------------------------------------------

    print()
    print("======================================")
    print("             MIGRATION DONE")
    print("======================================")
    print()

    print(
        f"Scenes imported: {len(SCENES)}"
    )

    print(
        f"Memories imported: {memory_count}"
    )

    print(
        "Latest checkpoint: Turn 170"
    )

    print()
    print(
        "ChromaDB was NOT used."
    )

    print(
        "No embedding model was downloaded."
    )

    print()
    print(
        "The Iron Path is ready to continue."
    )

    print()




if __name__ == "__main__":
    run()
