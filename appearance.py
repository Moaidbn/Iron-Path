"""
appearance.py

Formatting helpers for the Character Appearance Bible. The actual
storage lives in database.py (get_appearance / set_canonical_appearance
/ update_outfit) so it stays consistent with how every other piece of
state is persisted -- this module just shapes it for prompts and
for the /appearance command.

Canonical appearance details, once set, are treated as fixed. Only
update_outfit() should change on a normal basis (clothing changes are
state transitions, not appearance rewrites). set_canonical_appearance()
only fills in fields that are still "unknown" -- it will not overwrite
an established detail.
"""

APPEARANCE_FIELDS = [
    "age", "gender", "height", "build", "skin_tone", "face_shape",
    "hair_color", "hairstyle", "eye_color", "facial_hair", "scars",
    "tattoos", "distinguishing_marks", "typical_expression", "posture",
    "voice", "heraldry", "colors",
]

OUTFIT_FIELDS = [
    "clothing", "armor", "cloak", "boots", "gloves", "jewelry",
    "weapons", "accessories", "condition",
]


def format_appearance_for_prompt(appearance_record):
    """
    appearance_record: dict from database.get_appearance(name), or None.
    Returns a short block of text for the GM prompt. Only includes
    fields that are actually known -- never invents placeholders.
    """

    if not appearance_record:
        return None

    canon = appearance_record.get("canonical_appearance") or {}
    outfit = appearance_record.get("current_outfit") or {}

    known_traits = [
        f"{field.replace('_', ' ')}: {canon[field]}"
        for field in APPEARANCE_FIELDS
        if canon.get(field) and canon[field] != "unknown"
    ]

    known_outfit = [
        f"{field}: {outfit[field]}"
        for field in OUTFIT_FIELDS
        if outfit.get(field) and outfit[field] != "unknown"
    ]

    if not known_traits and not known_outfit:
        return None

    lines = [f"{appearance_record['name']}:"]
    if known_traits:
        lines.append("  Appearance -- " + "; ".join(known_traits))
    if known_outfit:
        lines.append("  Current outfit -- " + "; ".join(known_outfit))

    return "\n".join(lines)


def format_all_appearances_for_prompt(all_appearances):
    blocks = [
        format_appearance_for_prompt(record)
        for record in all_appearances
    ]
    blocks = [b for b in blocks if b]

    if not blocks:
        return "No canonical appearances recorded yet."

    return "\n".join(blocks)
