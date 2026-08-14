"""محرك تشغيل محلي للعبة «طريق الحديد».

يبقي التقدم في SQLite ويستخدم طبقة التحقق الموجودة في state_manager، لذلك
تظل اللعبة قابلة للعب دون مفتاح خدمة سرد خارجية.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Any

from database import (
    backfill_character_mentions_from_scenes,
    backfill_structured_state_from_canon,
    fix_garrison_undercount,
    get_recent_scenes,
    get_turn_count,
    get_character_scene_history,
    get_interaction_preflight,
    initialize_database,
    save_scene,
    seed_starting_equipment_if_empty,
)
from state_manager import apply_state_changes
from nvidia_gm import NvidiaNemotronGameMaster


@dataclass(frozen=True)
class ActionProfile:
    key: str
    label: str
    xp_key: str
    xp: int
    behavior: dict[str, int]
    event_type: str
    bonus_xp: tuple[tuple[str, int], ...] = ()

    def awards(self) -> dict[str, int]:
        awards = {}
        if self.xp_key and self.xp > 0:
            awards[self.xp_key] = self.xp
        for key, amount in self.bonus_xp:
            if key and amount > 0:
                awards[key] = awards.get(key, 0) + amount
        return awards


PROFILES = {
    # Movement is not mastery practice. The narrator can describe a meeting,
    # but only the local action profile is allowed to award progression.
    "movement": ActionProfile("movement", "حركة", "", 0, {}, "MOVEMENT"),
    "explore": ActionProfile("explore", "استكشاف", "exploration", 8, {"risk_taking": 2, "ambition": 1}, "DISCOVERY"),
    "diplomacy": ActionProfile("diplomacy", "محادثة ودبلوماسية", "conversation", 10, {"diplomacy": 3, "honesty": 1}, "INTRIGUE"),
    "dueling": ActionProfile("dueling", "مبارزة فردية", "dueling", 12, {"aggression": 2, "risk_taking": 1}, "DUEL"),
    "combat": ActionProfile("combat", "قتال ميداني", "weapons", 10, {"aggression": 3}, "BATTLE", (("strategy", 4),)),
    "battle": ActionProfile("battle", "معركة وقيادة ميدانية", "weapons", 9, {"aggression": 3, "ambition": 1}, "BATTLE", (("strategy", 8), ("leadership", 5))),
    "planning": ActionProfile("planning", "تخطيط واستراتيجية", "strategy", 10, {"pragmatism": 2, "ambition": 2}, "STRATEGY", (("leadership", 6),)),
    "leadership": ActionProfile("leadership", "قيادة", "leadership", 10, {"ambition": 2, "loyalty": 1}, "LEADERSHIP"),
    "trade": ActionProfile("trade", "تجارة", "trade", 10, {"pragmatism": 2, "ambition": 2}, "ECONOMY", (("conversation", 3),)),
    "rest": ActionProfile("rest", "تأمل", "", 0, {"mercy": 1, "loyalty": 1}, "RECOVERY"),
    "intrigue": ActionProfile("intrigue", "مكيدة", "intrigue", 10, {"deception": 3, "manipulation": 2}, "INTRIGUE", (("conversation", 4),)),
    # Generic decisions do not constitute a mastery exercise by themselves.
    "default": ActionProfile("default", "قرار", "", 0, {"ambition": 1}, "EVENT"),
}

TRIGGERS = {
    # Explicit movement must win before a character name or broader action word.
    "movement": ("امش", "مشي", "تحرك", "اقترب", "اتجه", "اسلك", "انتقل", "move", "walk", "walk to", "go toward", "go to", "head to", "approach"),
    "dueling": ("مبارزة", "نزال", "تحدى", "تحدي", "واحدا لواحد", "واحد إلى واحد", "duel", "one-on-one", "one on one", "challenge to a duel", "fencing"),
    "planning": ("خطط", "خطة", "خطه", "تخطيط", "استراتيجية", "استراتيجي", "خطة معركة", "خطة بديلة", "رتب", "نسق", "plan", "planning", "strategy", "strategic", "devise", "contingency", "coordinate"),
    "battle": ("معركة", "معركه", "جيش", "كتيبة", "كتيبه", "قيادة القوات", "battle", "army", "regiment", "command the troops", "field command"),
    "leadership": ("قد", "قيادة", "أمر الجنود", "احشد", "ارفع المعنويات", "اجمع رجالك", "lead", "leadership", "rally", "inspire", "organize the men"),
    "explore": ("استكشف", "ابحث", "فتش", "سافر", "رحلة", "explore", "search", "travel", "investigate"),
    "diplomacy": ("تفاوض", "تحدث", "حاور", "حديث", "كلم", "قابل", "رسالة", "صلح", "أقنع", "negotiate", "speak", "talk", "chat", "meet", "parley", "persuade", "dialogue"),
    "combat": ("هاجم", "قاتل", "سيف", "كمين", "حارب", "دافع", "attack", "fight", "combat", "ambush", "defend"),
    "trade": ("اشتر", "بع", "تاجر", "سوق", "ضريبة", "قافلة", "buy", "sell", "trade", "market", "caravan"),
    "rest": ("استرح", "نم", "تأمل", "عسكر", "rest", "sleep", "camp", "recover"),
    "intrigue": ("تجسس", "اكذب", "ابتز", "خدعة", "سم", "spy", "lie", "blackmail", "trick", "poison"),
}

LOCATIONS = [
    ("ميناء الرماد", "الساحل الشمالي", 0.22, 0.72, "ميناء صغير تلتقي فيه السفن والهمسات القادمة من البحر.", "port"),
    ("غابة الصفصاف الأسود", "تلال الغرب", 0.35, 0.41, "غابة كثيفة تخفي طرقًا أقدم من حدود الممالك.", "wilderness"),
    ("دير النجم الغارق", "المرتفعات الشرقية", 0.72, 0.30, "أبراج مهدمة ينسبها الرعاة إلى رهبان يتحدثون مع النجوم.", "ruin"),
    ("سوق درب النحاس", "السهول الوسطى", 0.56, 0.61, "مفترق طرقٍ تساوم فيه القوافل على الأخبار قبل البضائع.", "settlement"),
]

EN_LOCATION_NAMES = {
    "ميناء الرماد": "Ash Harbor",
    "غابة الصفصاف الأسود": "Black Willow Forest",
    "دير النجم الغارق": "Sunken Star Monastery",
    "سوق درب النحاس": "Copper Road Market",
}
EN_REGIONS = {
    "الساحل الشمالي": "Northern Coast",
    "تلال الغرب": "Western Hills",
    "المرتفعات الشرقية": "Eastern Highlands",
    "السهول الوسطى": "Central Plains",
}
EN_FINDS = {"خريطة ممزقة": "a torn map", "عملة قديمة": "an old coin", "ريشة سوداء": "a black feather", "مفتاح نحاسي": "a copper key"}
EN_SPEAKERS = {"السيدة سُهى، وكيلة الميناء": "Lady Suha, the harbor agent", "القبطان نادر": "Captain Nader", "المستشار إيلان": "Counselor Ilan"}


def _language_code(value):
    return "en" if str(value or "ar").strip().lower().startswith("en") else "ar"


class OfflineRPGGame:
    """محرك حالة حتمي مع راوٍ NVIDIA اختياري وfallback محلي كامل."""

    mode = "local"
    client = None

    def __init__(self) -> None:
        initialize_database()
        seed_starting_equipment_if_empty(get_turn_count())
        backfill_character_mentions_from_scenes()
        backfill_structured_state_from_canon()
        fix_garrison_undercount()
        self.narrator = NvidiaNemotronGameMaster()
        self.mode = self.narrator.mode

    @property
    def narration_status(self) -> str:
        return self.narrator.last_status

    @property
    def narration_latency_ms(self) -> int | None:
        return self.narrator.last_latency_ms

    @property
    def narration_context_mode(self) -> str:
        return self.narrator._context_mode()

    @property
    def narration_finish_reason(self) -> str | None:
        return self.narrator.last_finish_reason

    @property
    def narration_prompt_chars(self) -> int | None:
        return self.narrator.last_prompt_chars

    @staticmethod
    def _profile_for(action: str) -> ActionProfile:
        # Arabic spelling often varies by hamza/ta marbuta and may include tashkeel.
        lowered = action.casefold()
        normalized = re.sub(r"[ًٌٍَُِّْـ]", "", lowered)
        normalized = normalized.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"}))

        def matches(trigger: str) -> bool:
            candidate = re.sub(r"[ًٌٍَُِّْـ]", "", trigger.casefold())
            candidate = candidate.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"}))
            # Phrases may occur inside a natural sentence; short words need
            # boundaries so a token such as Arabic "قد" cannot match randomly.
            if " " in candidate or len(candidate) > 3:
                return candidate in normalized
            return re.search(rf"(?<!\w){re.escape(candidate)}(?!\w)", normalized) is not None

        for key, words in TRIGGERS.items():
            if any(matches(word) for word in words):
                return PROFILES[key]
        return PROFILES["default"]

    @staticmethod
    def _clean_action(action: str) -> str:
        return re.sub(r"\s+", " ", action).strip()[:280]

    def _scene(self, action: str, profile: ActionProfile, turn: int, language: str = "ar") -> tuple[str, dict[str, Any]]:
        language = _language_code(language)
        seed = sum(ord(c) for c in action) + turn * 37
        location_name, region, x, y, location_desc, kind = LOCATIONS[(turn - 1) % len(LOCATIONS)]
        consequence = [
            "تترك القرار متعمدًا مفتوحًا؛ فالطريق لا يكافئ من يظن أنه أحكم قبضته على كل شيء.",
            "لكن شاهدًا صامتًا يلتقط تفصيلًا صغيرًا قد يتحول لاحقًا إلى دينٍ أو دليل.",
            "وفي خلفية المشهد، تتحرك قوى أخرى قبل أن يكتمل صدى اختيارك.",
        ][seed % 3]
        proposal: dict[str, Any] = {
            "canon_facts": [{"category": "EVENT", "fact": f"في المشهد #{turn} اختار مويّد: {action}"}],
            "characters_present": [], "characters_mentioned": [],
            # XP is derived exclusively from the deterministic local profile;
            # the narrator never decides which mastery advances.
            "xp_awards": profile.awards(), "behavior_changes": profile.behavior,
            "faction_shifts": {}, "retainer_shifts": {}, "quest_updates": [], "holding_changes": {},
            "world_changes": [], "inventory_changes": {"added": [], "removed": []},
            "economic_entries": [], "army_changes": {}, "battle_trigger": None, "appearance_updates": [], "map_updates": [],
            # A regular movement/rest turn never becomes a campaign event just
            # because its turn number is divisible by three.
            "important_event": turn % 3 == 0 and profile.key not in {"movement", "rest"}, "decisive_action": profile.key in {"dueling", "combat", "battle", "planning", "leadership", "intrigue"},
            "event_type": profile.event_type, "event_title": None, "event_summary": None, "actions": [],
        }
        if turn == 1:
            proposal["quest_updates"].append({
                "quest_id": "iron-seal", "title": "ختم الحديد المكسور",
                "description": "اعثر على صاحب الرسالة المشفرة قبل أن تصل إلى المجلس الملكي.",
                "status": "active", "location": "ميناء الرماد",
                "objectives": ["تتبع علامة الشمع الأسود", "تحديد حامل الرسالة"],
            })

        if profile.key == "movement":
            proposal["event_title"] = "خطوة على الطريق"
            proposal["event_summary"] = f"تحركت نحو {location_name} من دون ممارسة مهارة أو اتخاذ قرار اجتماعي."
            narrative = f"تتابع السير نحو {location_name}. يتبدل صوت الطريق تحت قدميك، وتبقى عيناك على ما أمامك من دون أن يتحول التنقل وحده إلى وعد أو مواجهة. {consequence}"
        elif profile.key == "explore":
            find = ["خريطة ممزقة", "عملة قديمة", "ريشة سوداء", "مفتاح نحاسي"][seed % 4]
            proposal["inventory_changes"]["added"].append({"name": find, "category": "quest" if turn == 1 else "misc", "quantity": 1, "description": f"عُثر عليها قرب {location_name}.", "value": 12 + (seed % 9)})
            proposal["map_updates"].append({"type": "ADD_LOCATION", "name": location_name, "region": region, "x": x, "y": y, "description": location_desc, "kind": kind})
            proposal["event_title"] = "اكتشاف على الحافة"
            proposal["event_summary"] = f"قادك بحثك إلى {location_name}، حيث وجدت {find} ودليلًا على حركةٍ لا تُرى."
            narrative = f"تأخذك خطوتك إلى {location_name}. لا يلفت المكان الانتباه من بعيد، لكن أثرًا حديثًا بين التراب والحصى يرفض أن يكون مصادفة.\n\nبعد بحثٍ صبور، تقع يدك على {find}. ليست قيمته في مادته، بل في العلامة المحفورة عليه؛ إنها ذاتها التي وصفتها الرسالة المكسورة. {consequence}"
        elif profile.key == "diplomacy":
            speaker = ["السيدة سُهى، وكيلة الميناء", "القبطان نادر", "المستشار إيلان"][seed % 3]
            proposal["faction_shifts"] = {"تجار الرماد": {"trust": 5, "fear": -1, "loyalty": 2, "leverage": 1}}
            proposal["retainer_shifts"] = {"رائف": {"trust": 3, "respect": 2, "loyalty": 1, "morale": 1}}
            proposal["characters_present"] = [speaker]
            proposal["event_title"] = "وعد بشروط"
            proposal["event_summary"] = f"أثمر حديثك مع {speaker} عن خيطٍ جديد، لكنه يضعك في مواجهة التزام غير مريح."
            narrative = f"في القاعة الباردة، لا يردّ **{speaker}** على قرارك بعجلة. يُترك للصمت أن يعمل أولًا، ثم تُعرض عليك معلومة مقابل وعد لا يمكن التراجع عنه بسهولة.\n\nتخرج من اللقاء ومعك اسمٌ جديد يستحق المتابعة، ومعه التزام يراقبك أكثر مما تراقبه. {consequence}"
        elif profile.key == "dueling":
            proposal["event_title"] = "نزال على حافة الطريق"
            proposal["event_summary"] = "اختبرت مبارزة فردية توقيتك ومسافتك وقدرتك على قراءة الخصم."
            narrative = f"ينسحب الضجيج من حولك حتى لا يبقى بينك وبين خصمك إلا المسافة والنَفَس. لا تنقذ الصفوف المتراصة أحدًا هنا؛ كل خطوة، وكل خدعة، وكل لحظة تردد تُحسب عليك أو لك. تنتهي الجولة قبل أن يحسمها الغضب، ويترك النزال درسًا لا تمنحه المسيرات الطويلة. {consequence}"
        elif profile.key == "planning":
            proposal["event_title"] = "خريطة قبل المسير"
            proposal["event_summary"] = "حوّل التخطيط المسبق المخاطر إلى بدائل واضحة وربط الاستراتيجية بالقيادة."
            narrative = f"تفرد الخرائط فوق الطاولة، وتضع أمام كل طريق كلفته وبديله. لا تتحرك القوات بعد؛ أنت تختبر ما سيحدث إذا تأخر الإمداد، أو انكشف الجناح، أو اضطررت إلى التراجع دون أن تفقد زمام المبادرة. حين ترفع رأسك، صار للغد أكثر من طريق واحد. {consequence}"
        elif profile.key == "leadership":
            proposal["event_title"] = "صوت يحمل الصفوف"
            proposal["event_summary"] = "رفعت القيادة الواضحة تماسك من يتبعونك وربطت الأمر بالمسؤولية."
            narrative = f"لا تحتاج إلى الصراخ كي يسمعك المعسكر. تشرح الغاية، توزع المسؤولية، وتترك لكل قائد مساحة يتحمل فيها نتيجة قراره. يتغير الوقوف حولك قبل أن تتغير الرايات؛ فالقيادة تبدأ حين يثق الناس بأن الأمر لن يتبدل عند أول خوف. {consequence}"
        elif profile.key in {"combat", "battle"}:
            foe = "سرايا الملح"
            proposal["army_changes"] = {
                "حرس مويّد": {"total_troops": 120, "morale": 72, "organization": 68, "food_days": 12, "faction": "player", "location": "ممر الرماد", "commander": "مويّد"},
                foe: {"total_troops": 94, "morale": 58, "organization": 54, "food_days": 8, "faction": "raiders", "location": "ممر الرماد", "commander": "سالم الأجرد"},
            }
            proposal["battle_trigger"] = {"attacker": "حرس مويّد", "defender": foe, "terrain": "hills", "weather": "overcast", "location": "ممر الرماد"}
            proposal["event_title"] = "اختبار ممر الرماد"
            proposal["event_summary"] = "يختبر اشتباك قصير تماسك الحرس وتُسجّل نتائجه بالأرقام في سجل الحملة."
            narrative = "ترتفع صيحة من بين الصخور قبل أن تنغلق الفجوة. يتحول القرار إلى أمرٍ واضح، وتتحرك الصفوف لا كحشدٍ غاضب، بل كوحدةٍ تعرف أين تقف.\n\nلن يُحسم ميزان الممر بالخطب؛ يسجّل سجل الحملة ما بقي وما فُقد، ويظل الغبار شاهدًا على الثمن. " + consequence
        elif profile.key == "trade":
            gain = 18 + (seed % 15)
            proposal["holding_changes"] = {"دار مويّد": {"prosperity": 3, "food_supply": 2, "loyalty": 1}}
            proposal["faction_shifts"] = {"تجار الرماد": {"trust": 3, "fear": 0, "loyalty": 1, "leverage": 4}}
            gain_copper = gain * 10
            proposal["economic_entries"].append({"amount_copper": gain_copper, "entry_type": "story_trade_profit", "counterparty": "تجار الرماد", "location": location_name, "memo": "ربح من صفقة محسوبة في السوق."})
            proposal["event_title"] = "مكسب محسوب"
            proposal["event_summary"] = f"حققت الصفقة {gain} قطعة فضية ({gain_copper} نحاسًا) وعززت نفوذك لدى التجار."
            narrative = f"في السوق، لا تتكلم الأيدي التي تعدّ النقود بقدر ما تتكلم العيون التي تراقب الصفقة. تقبل العرض بعد أن تحوّل الغموض إلى شروط مكتوبة، ويُسجّل دفتر الحساب **{gain} قطعة فضية** في محفظتك.\n\nيكسب بيتك بعض الهدوء، لكن كل ربحٍ يجذب من يريد أن يعرف مصدره. {consequence}"
        elif profile.key == "rest":
            proposal["retainer_shifts"] = {"رائف": {"morale": 4, "trust": 1, "loyalty": 1, "respect": 0}}
            proposal["event_title"] = "ليل بلا رايات"
            proposal["event_summary"] = "أخذت الحملة نفسًا قصيرًا، واستعاد الحرس بعضًا من تماسكه."
            narrative = f"للمرة الأولى منذ أيام، لا يطلب منك أحد قرارًا قبل أن يبرد الجمر. تستغل الساعات الهادئة لتفحص الخرائط وتسمع ما لا يقوله رائف حين تكون الأبواب مفتوحة.\n\nلا تختفي المخاطر، لكنها تصبح قابلة للعدّ بدل أن تكون ظلًا على الجدار. {consequence}"
        elif profile.key == "intrigue":
            proposal["faction_shifts"] = {"حرس المدينة": {"trust": -2, "fear": 5, "loyalty": -1, "leverage": 4}}
            proposal["event_title"] = "ثمن الهمس"
            proposal["event_summary"] = "نجحت الخطة في كشف مدخل جديد، لكن شبهةً بدأت تتشكل في دوائر الحرس."
            narrative = f"تُسلَّم الرسالة من يدٍ إلى يد بلا ختمٍ ولا اسم. تتبع ردود الفعل بدل الكلمات، وحين يتغير حارس البوابة مرتين في ساعة واحدة تعرف أن الطعم التُقط.\n\nيفتح الهمس بابًا لم يكن مفتوحًا، لكنه يترك خلفه أثرًا لا يمحوه المطر بسهولة. {consequence}"
        else:
            proposal["event_title"] = "خطوة على طريق الحديد"
            proposal["event_summary"] = "غيّر قرارك توازن اللحظة وفتح سياقًا جديدًا للحملة."
            narrative = f"تُنفّذ قرارك: {action}. يتردد صداه في المعسكر أكثر مما توقعت، ليس لأن أحدًا فهم غايتك كاملة، بل لأن الجميع رأى أنك اخترت الحركة بدل الانتظار.\n\nتصل قبل الغروب إشارة صغيرة من جهة لا ينبغي أن تعرف مكانك. {consequence}"

        if language == "en":
            en_location = EN_LOCATION_NAMES.get(location_name, location_name)
            en_find = EN_FINDS.get(find, find) if profile.key == "explore" else ""
            en_consequence = [
                "You leave the decision deliberately open; the road does not reward anyone who believes they can control every outcome.",
                "Yet a silent witness notices a small detail that may later become a debt or a clue.",
                "Beyond the scene, other forces move before the echo of your choice has faded.",
            ][seed % 3]
            if profile.key == "movement":
                proposal["event_title"] = "A Step on the Road"
                proposal["event_summary"] = f"You moved toward {en_location} without practising a mastery or making a social commitment."
                narrative = f"You continue toward {en_location}. The sound of the road changes beneath your feet, and your attention remains fixed on what lies ahead; travel alone is neither a promise nor a confrontation. {en_consequence}"
            elif profile.key == "explore":
                proposal["event_title"] = "A Discovery at the Edge"
                proposal["event_summary"] = f"Your search led to {en_location}, where you found {en_find} and evidence of an unseen movement."
                narrative = f"Your step takes you to {en_location}. The place draws little attention from afar, but a recent mark among the dirt and gravel refuses to be coincidence.\n\nAfter a patient search, your hand closes around {en_find}. Its value lies not in the material, but in the mark carved into it—the same mark described in the broken message. {en_consequence}"
            elif profile.key == "diplomacy":
                en_speaker = EN_SPEAKERS.get(speaker, speaker)
                proposal["event_title"] = "A Promise with Conditions"
                proposal["event_summary"] = f"Your conversation with {en_speaker} opened a new lead, but placed an uncomfortable obligation before you."
                narrative = f"In the cold hall, **{en_speaker}** does not answer your decision in haste. Silence is allowed to do its work before a piece of information is offered in exchange for a promise that cannot easily be withdrawn.\n\nYou leave with a name worth pursuing and an obligation that watches you more closely than you watch it. {en_consequence}"
            elif profile.key == "dueling":
                proposal["event_title"] = "A Narrow Duel"
                proposal["event_summary"] = "A one-on-one contest tested timing, distance, and your reading of the opponent."
                narrative = f"The noise falls away until only distance and breath remain between you and your opponent. No formation can save either fighter here; each step, feint, and hesitation is counted. The exchange ends before anger can decide it, leaving a lesson that a long march could never teach. {en_consequence}"
            elif profile.key == "planning":
                proposal["event_title"] = "The Map Before the March"
                proposal["event_summary"] = "Careful planning turned risk into alternatives and connected strategy to leadership."
                narrative = f"You spread the maps across the table and assign a cost and fallback to every route. The troops do not move yet; you test what happens if supplies fail, a flank is exposed, or retreat becomes necessary without surrendering the initiative. When you look up, tomorrow has more than one path. {en_consequence}"
            elif profile.key == "leadership":
                proposal["event_title"] = "A Voice That Carries"
                proposal["event_summary"] = "Clear leadership strengthened cohesion and tied authority to responsibility."
                narrative = f"You do not need to shout for the camp to hear you. You explain the purpose, distribute responsibility, and leave each captain room to carry the result of a decision. The people around you change their stance before the banners do; leadership begins when others trust that the order will not change at the first sign of fear. {en_consequence}"
            elif profile.key in {"combat", "battle"}:
                proposal["event_title"] = "The Ash Pass Trial"
                proposal["event_summary"] = "A clash tested weapons, battlefield judgment, and the cohesion of the guard."
                narrative = "A cry rises from between the rocks before the gap closes. The decision becomes a clear order, and the ranks move not as an angry crowd, but as a unit that knows where it stands.\n\nThe pass will not be settled by speeches; the campaign record will note what remained and what was lost, while the dust bears witness to the price. " + en_consequence
            elif profile.key == "trade":
                proposal["event_title"] = "A Calculated Gain"
                proposal["event_summary"] = f"The deal earned {gain} silver pieces ({gain_copper} copper) and strengthened your influence among the traders."
                narrative = f"In the market, the hands counting coins speak less loudly than the eyes watching the deal. You accept the offer after turning uncertainty into written terms, and the ledger records **{gain} silver pieces** in your purse.\n\nYour house gains a little peace, but every profit attracts someone who wants to know its source. {en_consequence}"
            elif profile.key == "rest":
                proposal["event_title"] = "A Night Without Banners"
                proposal["event_summary"] = "The campaign drew a brief breath, and the guard recovered some of its cohesion."
                narrative = f"For the first time in days, no one asks you for a decision before the embers cool. You use the quiet hours to inspect the maps and hear what Raif does not say when the doors are open.\n\nThe dangers do not disappear, but they become countable instead of remaining a shadow on the wall. {en_consequence}"
            elif profile.key == "intrigue":
                proposal["event_title"] = "The Price of a Whisper"
                proposal["event_summary"] = "The plan revealed a new entrance, but suspicion began to form within the guard's circles."
                narrative = f"The message passes from hand to hand without seal or name. You follow reactions rather than words, and when the gate guard changes twice in a single hour, you know the bait has been taken.\n\nA whisper opens a door that was not open before, but leaves a trace that rain will not easily erase. {en_consequence}"
            else:
                proposal["event_title"] = "A Step Along the Iron Road"
                proposal["event_summary"] = "Your decision shifted the balance of the moment and opened a new thread for the campaign."
                narrative = f"You carry out your chosen decision. Its echo travels farther through the camp than you expected—not because anyone understood your purpose completely, but because everyone saw that you chose movement over waiting.\n\nBefore sunset, a small signal arrives from a direction that should not know your position. {en_consequence}"

        if proposal["important_event"] or proposal["decisive_action"]:
            proposal["actions"] = [
                {"label": "تتبّع الخيط فورًا", "type": "explore", "risk": "MEDIUM", "requirements": []},
                {"label": "اطلب مشورة رائف", "type": "diplomacy", "risk": "LOW", "requirements": []},
                {"label": "أمّن المعسكر قبل التحرك", "type": "rest", "risk": "LOW", "requirements": []},
            ]
            if language == "en":
                proposal["actions"] = [
                    {"label": "Follow the lead immediately", "type": "explore", "risk": "MEDIUM", "requirements": []},
                    {"label": "Ask Raif for counsel", "type": "diplomacy", "risk": "LOW", "requirements": []},
                    {"label": "Secure the camp before moving", "type": "rest", "risk": "LOW", "requirements": []},
                ]
        return narrative, proposal

    def _blocked_interaction_scene(self, action: str, preflight: dict[str, Any], language: str = "ar") -> tuple[str, dict[str, Any]]:
        language = _language_code(language)
        targets = preflight.get("targets", [])
        names = "، ".join(target.get("name", "الشخص المعني") for target in targets) or "الشخص المعني"
        detail = preflight.get("message") or "لا تسمح سجلات الحضور بهذا اللقاء الآن."
        narrative = (
            f"تتوقف قبل أن يتحول طلبك إلى ادعاءٍ لا يسانده سجل الحملة. {detail} "
            "لا يظهر أحد من العدم، ولا يُنقل شخص بين الأمكنة بلا رحلة مسجلة. "
            "يمكنك إرسال رسالة أو مبعوث، أو السفر إلى موقعه، أو الانتظار حتى تكتمل حركته."
        )
        proposal = {
            "canon_facts": [{"category": "CHARACTER", "fact": f"تعذر لقاء {names} في هذا الوقت بسبب قيود الحضور والموقع."}],
            "characters_present": [], "characters_mentioned": [target.get("name") for target in targets],
            # A blocked request is a ledger correction, not a completed
            # conversation; it must not grant Conversation Mastery XP.
            "xp_awards": {}, "behavior_changes": {"pragmatism": 1},
            "faction_shifts": {}, "retainer_shifts": {}, "quest_updates": [], "holding_changes": {},
            "world_changes": [], "inventory_changes": {"added": [], "removed": []}, "economic_entries": [],
            "army_changes": {}, "battle_trigger": None, "appearance_updates": [], "map_updates": [],
            "presence_updates": [], "important_event": False, "decisive_action": False,
            "event_type": "CHARACTER", "event_title": "سجل الحضور", "event_summary": "منع السجل لقاءً لا ينسجم مع موقع الشخصية وحالتها.", "actions": [],
        }
        if language == "en":
            narrative = (
                "You stop before turning your request into a claim unsupported by the campaign ledger. "
                "The attendance record does not authorize this meeting at the present time. "
                "No one appears from nowhere, and no character is moved between places without a recorded journey. "
                "You can send a message or an envoy, travel to the character's location, or wait for the movement to be completed."
            )
            proposal["event_title"] = "The Presence Ledger"
            proposal["event_summary"] = "The ledger prevented a meeting inconsistent with the character's location and current status."
        return narrative, proposal

    def _present_character_scene(self, action: str, target: dict[str, Any], turn: int, language: str = "ar") -> tuple[str, dict[str, Any]]:
        language = _language_code(language)
        name = target["name"]
        history = get_character_scene_history(name, limit=80)
        history_note = "لا توجد له مواجهة مسجلة معك بعد" if not history else f"يحمل سجل العلاقة بينكما {len(history)} مشهدًا موثقًا"
        role_note = target.get("biography") or target.get("reason") or target.get("type", "شخصية معروفة")
        narrative = (
            f"تلتقي **{name}** في {target.get('location') or 'الموقع الحالي'}، لا كشخص استُدعي من فراغ، بل لأنه موجود هنا فعلًا. "
            f"{role_note}. {history_note}؛ لذلك لا يتعامل مع طلبك كأنه أول كلام بينكما. "
            f"يصغي إلى قولك: «{action}»، ثم يرد بحذر يوافق تاريخه وموقعه والتزاماته الحالية، ويطلب منك تحديد الثمن أو الوعد الذي تقبله قبل أن يمضي الأمر أبعد."
        )
        if language == "en":
            history_note_en = "There is no recorded confrontation between you yet." if not history else f"The relationship ledger holds {len(history)} documented scenes."
            narrative = (
                f"You meet **{name}** at the current location, not as someone summoned from nowhere, but because the character is truly present here. "
                f"Their history and role are known to the campaign. {history_note_en} The character therefore does not treat your request as the first exchange between you. "
                f"They listen to your words, then answer with caution shaped by their history, location, and current obligations, asking you to name the price or promise you are willing to accept before the matter goes further."
            )
        proposal = {
            "canon_facts": [{"category": "CHARACTER", "fact": f"جرى تفاعل مباشر موثق مع {name} في المشهد #{turn}."}],
            "characters_present": [name], "characters_mentioned": [], "presence_updates": [],
            "xp_awards": {"conversation": 8}, "behavior_changes": {"diplomacy": 2},
            "faction_shifts": {}, "retainer_shifts": {}, "quest_updates": [], "holding_changes": {},
            "world_changes": [], "inventory_changes": {"added": [], "removed": []}, "economic_entries": [],
            "army_changes": {}, "battle_trigger": None, "appearance_updates": [], "map_updates": [],
            "important_event": False, "decisive_action": False, "event_type": "CHARACTER",
            "event_title": f"لقاء مع {name}" if language == "ar" else f"Meeting with {name}",
            "event_summary": f"استند الحوار إلى سجل {name} وحضوره القانوني في الموقع." if language == "ar" else f"The conversation used {name}'s history and verified presence at the location.", "actions": [],
        }
        return narrative, proposal

    def play_turn(self, player_action: str, language: str = "ar") -> dict[str, Any]:
        language = _language_code(language)
        action = self._clean_action(player_action)
        if not action:
            raise ValueError("اكتب قرارًا أو فعلًا قبل إرساله.")
        turn = get_turn_count() + 1
        preflight = get_interaction_preflight(action, turn)
        profile = self._profile_for(action)
        if preflight.get("blocked"):
            narrative, proposal = self._blocked_interaction_scene(action, preflight, language)
        elif preflight.get("targets") and self._profile_for(action).key == "diplomacy" and not preflight.get("remote"):
            narrative, proposal = self._present_character_scene(action, preflight["targets"][0], turn, language)
        else:
            narrative, proposal = self._scene(action, profile, turn, language)

        # تُحسم الحالة محليًا؛ API لا يتلقى إلا الحقائق المحسوبة ويعيد صياغة السرد.
        narrative, suggested_actions = self.narrator.narrate(
            action=action,
            turn=turn,
            language=language,
            proposal=proposal,
            fallback_narrative=narrative,
        )
        if suggested_actions:
            proposal["actions"] = suggested_actions
        scene_id = save_scene(turn, action, narrative)
        summary = apply_state_changes(proposal, scene_id, turn, player_action=action)
        level_ups = [{"name": name, "level": item["level"]} for name, item in summary.get("xp_awarded", {}).items() if item.get("leveled_up")]
        return {
            "turn": turn, "response": narrative, "level_ups": level_ups,
            "new_traits": summary.get("new_traits", []), "new_specializations": summary.get("new_specializations", []),
            "new_locations": summary.get("new_locations", []), "battle": summary.get("battle"), "loot_created": summary.get("loot_created"),
            "civic_settlement": summary.get("civic_settlement"),
            "time_progression": summary.get("time_progression"),
            "arrived_characters": summary.get("arrived_characters", []),
            "event": {
                "important": summary.get("important_event", False), "decisive": summary.get("decisive_action", False),
                "type": summary.get("event_type"), "title": summary.get("event_title"), "summary": summary.get("event_summary"),
                "faction_shifts": summary.get("faction_shifts", {}), "retainer_shifts": summary.get("retainer_shifts", {}),
                "xp_awarded": summary.get("xp_awarded", {}), "quests_updated": summary.get("quests_updated", []), "actions": summary.get("actions", []),
            } if (summary.get("important_event") or summary.get("decisive_action")) else None,
        }

    def recap(self, language: str = "ar") -> str:
        language = _language_code(language)
        scenes = get_recent_scenes(limit=5)
        if not scenes:
            fallback = "The campaign has not begun. Enter your first decision to open the starting scene." if language == "en" else "لم تبدأ الحملة بعد. اكتب أول قرار لتفتح المشهد الافتتاحي."
            return self.narrator.recap(language=language, fallback_recap=fallback)
        lines = ["Campaign Recap", ""] if language == "en" else ["ملخص الحملة", ""]
        for turn, action, response in scenes:
            opening = re.sub(r"\s+", " ", response).strip()[:145]
            label = "Scene" if language == "en" else "المشهد"
            lines.append(f"{label} #{turn}: {action}\n{opening}…")
        fallback = "\n\n".join(lines)
        return self.narrator.recap(language=language, fallback_recap=fallback)
