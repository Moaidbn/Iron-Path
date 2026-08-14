"""بيانات ألدينمير الموسعة: التاريخ الثنائي والحوكمة والأسواق المحلية."""

from __future__ import annotations

UI = {
    "ar": {
        "atlas": "أطلس ألدينمير",
        "history": "تاريخ الحروب",
        "civics": "شؤون المدن",
        "trade": "التجارة والدفتر",
        "player_shops": "متاجري",
        "language": "اللغة",
        "arabic": "العربية",
        "english": "English",
        "population": "السكان",
        "government": "الإدارة",
        "tax": "الضريبة السوقية",
        "security": "الأمن",
        "prosperity": "الازدهار",
        "supply": "المعروض المميز",
        "demand": "الطلب المحلي",
        "open_shop": "افتتاح متجر",
        "shop_status": "حالة المتجر",
        "daily_profit": "ربح الدورة",
        "ledger": "دفتر القيود",
        "war_legacy": "الأثر الباقي",
        "local_market": "السوق المحلي",
        "no_shop": "لا يوجد متجر للاعب في هذا الموقع بعد.",
        "owned_shop": "متجر اللاعب",
        "market_tier": "رتبة السوق",
        "governor": "الحاكم المدني",
        "fortress_command": "قيادة الحصن",
        "resident_mood": "رضا السكان",
        "last_settlement": "آخر تسوية",
        "currency": "العملة",
        "loyalty": "الولاء",
        "morale": "المعنويات",
        "trust": "الثقة",
        "respect": "الاحترام",
    },
    "en": {
        "atlas": "Atlas of Aldenmere",
        "history": "Wars & History",
        "civics": "Civic Affairs",
        "trade": "Trade & Ledger",
        "player_shops": "My Shops",
        "language": "Language",
        "arabic": "العربية",
        "english": "English",
        "population": "Population",
        "government": "Government",
        "tax": "Market tax",
        "security": "Security",
        "prosperity": "Prosperity",
        "supply": "Signature supply",
        "demand": "Local demand",
        "open_shop": "Open shop",
        "shop_status": "Shop status",
        "daily_profit": "Turn profit",
        "ledger": "Ledger",
        "war_legacy": "Enduring legacy",
        "local_market": "Local market",
        "no_shop": "No player shop exists at this location yet.",
        "owned_shop": "Player-owned shop",
        "market_tier": "Market tier",
        "governor": "Civil governor",
        "fortress_command": "Fortress command",
        "resident_mood": "Resident sentiment",
        "last_settlement": "Last settlement",
        "currency": "Currency",
        "loyalty": "Loyalty",
        "morale": "Morale",
        "trust": "Trust",
        "respect": "Respect",
    },
}

# These events are canonical public history. Private consequences can be discovered by the game engine later.
HISTORICAL_WARS = [
    {
        "slug": "war_of_sundered_banners",
        "year": "312–319 A.F.",
        "name_ar": "حرب الرايات الممزقة",
        "name_en": "The War of Sundered Banners",
        "summary_ar": "انهارت الوصاية الملكية بعد موت أوريان الثالث بلا وريث معلن. سبعة بيوت مسلحة فرضت رسومها على الجسور والمرافئ، فصار القمح رهينة والسفر خيانة محتملة.",
        "summary_en": "The royal regency collapsed after Aurian III died without an acknowledged heir. Seven armed houses taxed bridges and ports, turning grain and travel into political weapons.",
        "legacy_ar": "أنشأت الحرب حق المدن في انتخاب مجالس مخازنها، لكنها منحت الحصون حق تفتيش القوافل في أوقات الطوارئ.",
        "legacy_en": "The war created a city right to elect granary councils, yet granted fortresses emergency inspection powers over caravans.",
        "regions": "أشفيل، التاج، الساحل", "regions_en": "Ashvale, Crownlands, Western Coast",
    },
    {
        "slug": "bronze_gate_siege",
        "year": "341 A.F.",
        "name_ar": "حصار بوابة البرونز",
        "name_en": "The Siege of Bronzegate",
        "summary_ar": "حاصرت جيوش الملح بوابة البرونز سبعة أشهر لتقطع طريق الحديد. اختار الحدادون صب قنوات ماء داخل الجدار بدل الاستسلام، فانقلبت الأنفاق على المهاجمين عند ذوبان الجليد.",
        "summary_en": "Salt armies besieged Bronzegate for seven months to sever the iron road. The smiths cast water channels into the wall; when the thaw came, the tunnels turned against the attackers.",
        "legacy_ar": "منذ ذلك الحين تُدار مناجم الشرق بتدقيق مزدوج بين نقابة الحدادين وخزانة التاج، وتبقى أسعار الحديد حساسة لأي إنذار حدودي.",
        "legacy_en": "Since then, eastern mines have required dual audit by the smiths' guild and Crown treasury, making iron prices sensitive to every border alert.",
        "regions": "البوابة الشرقية، تاج الصقيع", "regions_en": "Eastern Gate, Frostward",
    },
    {
        "slug": "wolfcrown_succession",
        "year": "356–360 A.F.",
        "name_ar": "حرب خلافة تاج الذئب",
        "name_en": "The Wolfcrown Succession War",
        "summary_ar": "رفضت قبائل الشمال اعتراف التاج بوصيٍّ من السهول. انتهت الحرب بمعاهدة الثلج والحديد التي أبقت القضاء العشائري محليًا وربطت الحاميات الشمالية بتمويل مشترك.",
        "summary_en": "Northern clans refused the Crown's plains-born regent. The War ended in the Snow-and-Iron Compact, preserving clan courts while funding northern garrisons jointly.",
        "legacy_ar": "تفسر المعاهدة اختلاف ضريبة الحراسة في الشمال وحرص السكان على أن يكون قائد الحصن من أهل الإقليم.",
        "legacy_en": "The Compact explains the North's distinct watch levy and its insistence that fortress commanders belong to the region.",
        "regions": "تاج الذئب، المسيرة الشمالية", "regions_en": "Frostward, Northern March",
    },
    {
        "slug": "ashvale_reclamation",
        "year": "372 A.F.",
        "name_ar": "استرداد رماد الوادي",
        "name_en": "The Ashvale Reclamation",
        "summary_ar": "أحرقت عصابات المرتزقة مخازن الوادي لتجويع خصومها. وحّدت القرى مواسمها وفتحت سجلات بذور مشتركة؛ وانتصر التحالف حين فشل المرتزقة في شراء القمح من سكان منظمين.",
        "summary_en": "Mercenary bands burned valley granaries to starve their rivals. Villages pooled seasons and opened shared seed ledgers; the alliance won when organized residents refused to sell grain.",
        "legacy_ar": "ولدت من الحرب سجلات البذور، وحصص الاحتياطي، وحق القرى في مراجعة ضرائب الحاكم عند نقص المحصول.",
        "legacy_en": "The war birthed seed ledgers, reserve quotas, and a village right to review a governor's taxes after failed harvests.",
        "regions": "أشفيل، ممر ميلبروك", "regions_en": "Ashvale, Millbrook Crossing",
    },
    {
        "slug": "windmere_privateers",
        "year": "381–383 A.F.",
        "name_ar": "حرب قراصنة ويندمير",
        "name_en": "The Windmere Privateer War",
        "summary_ar": "استأجرت بيوت التجارة قراصنة لفرض رسوم خفية على الملح والزجاج. أجبر تحالف صائدي البحر والمرافئ التاج على نشر سجل علني للرسوم والمزادات البحرية.",
        "summary_en": "Merchant houses hired privateers to impose hidden tolls on salt and glass. A coalition of sea wardens and ports forced the Crown to publish a public register of duties and naval auctions.",
        "legacy_ar": "صارت المرافئ أغنى مدن القارة وأكثرها تدقيقًا؛ ويتغيّر هامش الملح والزجاج فيها بحسب سلامة الممرات البحرية.",
        "legacy_en": "Ports became the continent's richest and most audited cities; their salt and glass margins now move with sea-lane security.",
        "regions": "ويندمير، ساحل الزجاج", "regions_en": "Windmere, Glass Coast",
    },
]

# Population, taxation and institutions are deliberately approximate civic simulation inputs—not real-world claims.
CIVIC_PROFILES = [
    {
        "location": "Ashvale Hold", "location_ar": "حصن رماد الوادي", "location_en": "Ashvale Hold", "type": "fortress-city",
        "population": 18200, "government_ar": "مجلس الحصن ووكلاء القرى", "government_en": "Fortress council and village stewards",
        "governor_ar": "إيزولد مودسبين", "governor_en": "Isolde Mudsbane", "tax_rate": 6, "security": 82, "prosperity": 61, "loyalty": 73,
        "supply_ar": "حبوب الاحتياطي والجلود", "supply_en": "Reserve grain and hides", "demand_ar": "الحديد وأدوات الحصار", "demand_en": "Iron and siege tools", "tier": 3,
    },
    {
        "location": "Mudroot", "location_ar": "مودروت", "location_en": "Mudroot", "type": "village-market",
        "population": 4100, "government_ar": "مجلس البذور", "government_en": "Seed council", "governor_ar": "العمدة هانا روت", "governor_en": "Mayor Hanna Root", "tax_rate": 3, "security": 58, "prosperity": 54, "loyalty": 81,
        "supply_ar": "شعير وبذور ولبن", "supply_en": "Barley, seed and dairy", "demand_ar": "ملح وأقمشة", "demand_en": "Salt and cloth", "tier": 1,
    },
    {
        "location": "Millbrook Crossing", "location_ar": "معبر ميلبروك", "location_en": "Millbrook Crossing", "type": "river-town",
        "population": 9600, "government_ar": "نقابة العبّارات ومأمور التاج", "government_en": "Ferry guild and Crown reeve", "governor_ar": "المأمور دارن ميل", "governor_en": "Reeve Daren Mill", "tax_rate": 5, "security": 68, "prosperity": 66, "loyalty": 64,
        "supply_ar": "أسماك النهر وأخشاب الجسر", "supply_en": "River fish and bridge timber", "demand_ar": "النحاس والحراسة", "demand_en": "Copper and guard contracts", "tier": 2,
    },
    {
        "location": "Port of Windmere", "location_ar": "ميناء ويندمير", "location_en": "Port of Windmere", "type": "port-city",
        "population": 32400, "government_ar": "ديوان المرفأ ومجلس التجار", "government_en": "Harbor office and merchant council", "governor_ar": "سيلين فوس", "governor_en": "Selene Voss", "tax_rate": 8, "security": 72, "prosperity": 86, "loyalty": 52,
        "supply_ar": "ملح وزجاج وتوابل بحرية", "supply_en": "Salt, glass and sea spices", "demand_ar": "حبوب وسلاح للحراسة", "demand_en": "Grain and watch arms", "tier": 4,
    },
    {
        "location": "قلعة برونزغيت", "location_ar": "بوابة البرونز", "location_en": "Bronzegate", "type": "fortress-mine",
        "population": 14700, "government_ar": "نقابة الحدادين وخزانة التاج", "government_en": "Smiths' guild and Crown treasury", "governor_ar": "ريڤنث كاين", "governor_en": "Reventh Kaine", "tax_rate": 7, "security": 88, "prosperity": 70, "loyalty": 57,
        "supply_ar": "حديد خام وأدوات", "supply_en": "Raw iron and tools", "demand_ar": "غذاء ودواء", "demand_en": "Food and medicine", "tier": 3,
    },
    {
        "location": "قلعة سيفرلوك", "location_ar": "سيفرلوك", "location_en": "Severlock", "type": "fortress-market",
        "population": 11900, "government_ar": "قائد الحصن ومجلس الطريق", "government_en": "Fortress commander and road council", "governor_ar": "مارا كراي", "governor_en": "Marra Cray", "tax_rate": 6, "security": 84, "prosperity": 58, "loyalty": 61,
        "supply_ar": "خيول ورماح", "supply_en": "Horses and spears", "demand_ar": "علف وملح", "demand_en": "Fodder and salt", "tier": 2,
    },
    {
        "location": "قلعة وولفكراون", "location_ar": "قلعة تاج الذئب", "location_en": "Wolfcrown", "type": "northern-fortress",
        "population": 8300, "government_ar": "محكمة العشائر وحامية التاج", "government_en": "Clan court and Crown garrison", "governor_ar": "أستريد وولفكراون", "governor_en": "Astrid Wolfcrown", "tax_rate": 4, "security": 90, "prosperity": 49, "loyalty": 76,
        "supply_ar": "فراء وخشب صنوبر", "supply_en": "Furs and pine timber", "demand_ar": "ملح وزيت مصابيح", "demand_en": "Salt and lamp oil", "tier": 2,
    },
    {
        "location": "Halgrove Field", "location_ar": "سهول هالغروف", "location_en": "Halgrove Field", "type": "estate-town",
        "population": 12800, "government_ar": "محكمة الأرضاء وديوان المحاصيل", "government_en": "Landholders' court and harvest office", "governor_ar": "لورد هالغروف", "governor_en": "Lord Halgrove", "tax_rate": 5, "security": 63, "prosperity": 75, "loyalty": 59,
        "supply_ar": "قمح ونبيذ", "supply_en": "Wheat and wine", "demand_ar": "أدوات ومرافقة قوافل", "demand_en": "Tools and caravan escorts", "tier": 3,
    },
    {
        "location": "The Capital", "location_ar": "العاصمة", "location_en": "The Capital", "type": "capital-city",
        "population": 68100, "government_ar": "ديوان التاج ومجلس المدن", "government_en": "Crown chancery and city council", "governor_ar": "الوصي الملكي", "governor_en": "The Royal Regent", "tax_rate": 9, "security": 79, "prosperity": 91, "loyalty": 48,
        "supply_ar": "منسوجات وسجلات قانونية", "supply_en": "Textiles and legal records", "demand_ar": "حديد وغذاء وفرو", "demand_en": "Iron, food and furs", "tier": 5,
    },
]

# English display names for atlas locations whose canonical campaign key is Arabic.
# The map keeps its canonical key; the civic API selects this label in English mode.
LOCATION_NAMES_EN = {
    "حصن جسر الرماد": "Ashbridge Fort", "بلدة هولموك": "Holmuck Town", "مرسى بريل": "Brill Quay",
    "مدينة إيلدنهول": "Eldenhall City", "قلعة برونزغيت": "Bronzegate Castle", "سوق الساعات السبع": "Seven-Hour Market",
    "مزارع ميرافيل": "Miravel Farms", "برج السراج": "Lantern Tower", "قلعة بلاكستيب": "Blackstep Castle",
    "مدينة ريڤنفورد": "Ravenford City", "حصن العرصة التسعة": "Nine-Yard Fort", "مدينة سالتمارش": "Saltmarsh City",
    "قلعة رأس العاصفة": "Stormhead Fort", "مرفأ الأصداف الخمس": "Five-Shell Harbor", "قرية بلاكهولم": "Blackholm Village",
    "مدينة ڤيلوري": "Velory City", "قلعة هارتستان": "Heartstone Castle", "مانور ثورنويت": "Thornwheat Manor",
    "سوق كيلن": "Kiln Market", "برج لورك": "Lark Tower", "بوابة الحطابين": "Woodcutters' Gate",
    "قرية لونغشيد": "Longshade Village", "مدينة شمس القنوات": "Canal-Sun City", "قلعة سيفرلوك": "Severlock Castle",
    "ميناء دورابيل": "Dorabel Port", "سوق ورد الرماد": "Ashrose Market", "أبراج النمل الأبيض": "Termite Towers",
    "قلعة وولفكراون": "Wolfcrown Castle", "مدينة هيلغلاس": "Hillglass City", "حصن الممر الأبيض": "White Pass Fort",
    "مناجم إيرونفيل": "Ironvale Mines", "مخيم ثلجبارد": "Snowbard Camp", "جزيرة كالدرا": "Kaldra Isle",
    "منارة أوريون": "Orion Lighthouse",
}

# Arabic labels for the small set of canonical atlas keys that are English in
# the campaign seed, plus transient travel labels used by the character register.
# These are display-only maps; canonical keys remain unchanged for joins and APIs.
LOCATION_NAMES_AR = {
    "Ashvale Hold": "حصن آشڤيل",
    "Halgrove Field": "سهول هالغروف",
    "Windmere (relocating)": "ويندمير (في طور الانتقال)",
    "Mudroot": "جذر الطين",
    "Millbrook Crossing": "معبر ميلبروك",
    "The Capital": "العاصمة",
    "The March": "المسيرات",
    "Port of Windmere": "ميناء ويندمير",
    "Eastern Gentry Lands": "إقطاعيات الشرق",
    "En route to the Capital": "في الطريق إلى العاصمة",
}

REGION_NAMES_AR = {
    "ashvale": "رماد الوادي",
    "crownlands": "أراضي التاج",
    "wolf_march": "مسيرات الذئب",
    "western_coast": "الساحل الغربي",
    "eastern_gentry": "إقطاعيات الشرق",
    "greywood": "غريوود العتيق",
    "southern_reach": "المدى الجنوبي",
    "frostward": "تاج الصقيع",
    "far_crossing": "العبور البعيد",
}

REGION_NAMES_EN = {
    "ashvale": "Ashvale March",
    "crownlands": "Crownlands",
    "wolf_march": "Wolf March",
    "western_coast": "Western Coast",
    "eastern_gentry": "Eastern Gentry",
    "greywood": "Ancient Greywood",
    "southern_reach": "Southern Reach",
    "frostward": "Frostward Crown",
    "far_crossing": "Far Crossing",
}

PRESENCE_REASONS_AR = {
    "atlas seat": "مقعد الأطلس",
    "retainer assignment": "تكليف مرافق",
    "traveling": "في رحلة",
    "captured": "أسير أو أسيرة",
    "active": "حاضر",
    "civic office": "منصب مدني",
    "dead": "متوفى أو متوفاة",
}

PRESENCE_REASONS_EN = {
    "atlas seat": "Atlas seat",
    "retainer assignment": "Retainer assignment",
    "civic office": "Civic office",
    "traveling": "Traveling",
    "captured": "Captured",
    "missing": "Missing",
    "remote": "Remote",
    "active": "Present",
    "dead": "Dead",
}

RETAINER_ASSIGNMENTS_AR = {
    "Spy network & diplomacy": "شبكة التجسس والدبلوماسية",
    "Archery training": "تدريب الرماية",
    "Ward, training in archery and swordsmanship": "الحراسة والتدريب على الرماية والمبارزة",
    "Internal affairs: walls, food, village outreach": "الشؤون الداخلية: الأسوار والغذاء والتواصل مع القرى",
    "Garrison commander": "قائد الحامية",
    "Riding to the Capital with defector evidence": "متجه إلى العاصمة ومعه أدلة منشق",
    "Leads Roots, operating against Kaine in the March": "يقود الجذور ويعمل ضد كاين في المسيرات",
    "Village elder, community counsel": "شيخ القرية ومستشار شؤون المجتمع",
    "Master blacksmith, relocating her forge to Ashvale": "كبيرة الحدادين وتنقل ورشتها إلى آشڤيل",
    "Pardoned soldier, integrated into the garrison under Doss": "جندي معفوّ عنه اندمج في الحامية تحت قيادة دوس",
}

CHARACTER_TYPES_AR = {
    "lord": "لورد",
    "retainer": "مرافق",
    "civic_governor": "حاكم مدني",
}

CHARACTER_TYPES_EN = {
    "lord": "Lord",
    "retainer": "Companion",
    "civic_governor": "Civic Governor",
}

RETAINER_ASSIGNMENTS_EN = {
    "Spy network & diplomacy": "Spy network and diplomacy",
    "Archery training": "Archery training",
    "Ward, training in archery and swordsmanship": "Ward; archery and swordsmanship training",
    "Internal affairs: walls, food, village outreach": "Internal affairs: walls, food, and village outreach",
    "Garrison commander": "Garrison commander",
    "Riding to the Capital with defector evidence": "Riding to the Capital with defector evidence",
    "Leads Roots, operating against Kaine in the March": "Leads the Roots against Kaine in the March",
    "Village elder, community counsel": "Village elder and community counsel",
    "Master blacksmith, relocating her forge to Ashvale": "Master blacksmith relocating her forge to Ashvale",
    "Pardoned soldier, integrated into the garrison under Doss": "Pardoned soldier integrated into Doss's garrison",
}

GOODS = [
    ("barley", "شعير الوادي", "Ashvale barley", "حبوب متينة من حقول أشفيل.", "Hardy grain from Ashvale fields.", 4, 0.65, "Ashvale", "food"),
    ("salt", "ملح ويندمير", "Windmere salt", "ملح بحري محفوظ في صناديق ممهورة.", "Sea salt kept in stamped crates.", 12, 0.68, "Windmere", "food"),
    ("iron", "حديد البوابة", "Bronzegate iron", "حديد خام مصدّق من نقابة الحدادين.", "Guild-certified raw iron.", 26, 0.70, "Bronzegate", "material"),
    ("fur", "فراء الشمال", "Northern furs", "فراء كثيف يحتاجه أهل الساحل والسهول.", "Dense furs prized by coast and plains.", 21, 0.66, "Wolfcrown", "luxury"),
    ("glass", "زجاج المد", "Tideglass", "زجاج ساحلي أزرق يدفع نخب العاصمة ثمنه.", "Blue coastal glass coveted by capital elites.", 34, 0.64, "Windmere", "luxury"),
    ("timber", "خشب الصنوبر", "Pine timber", "خشب شمالي جاف للبناء والسفن.", "Dry northern timber for building and ships.", 9, 0.67, "Wolfcrown", "material"),
    ("wine", "نبيذ هالغروف", "Halgrove wine", "نبيذ قمح-العنب للعقود والمآدب.", "Wheat-grape wine for contracts and feasts.", 18, 0.63, "Halgrove", "luxury"),
    ("tools", "أدوات مطروقة", "Forged tools", "عدة حدادين ومزارعين من بوابة البرونز.", "Smith and farm implements from Bronzegate.", 17, 0.69, "Bronzegate", "material"),
]

# Available goods and price multiplier in copper. An origin has the lowest multiplier, while a deficit market costs more.
MARKET_CATALOG = {
    "Ashvale Hold": {"barley": 0.78, "salt": 1.22, "iron": 1.13, "timber": 0.94, "tools": 1.05},
    "Mudroot": {"barley": 0.74, "salt": 1.32, "timber": 1.04, "tools": 1.25},
    "Millbrook Crossing": {"barley": 0.93, "salt": 1.10, "timber": 0.82, "iron": 1.16},
    "Port of Windmere": {"salt": 0.72, "glass": 0.77, "wine": 0.94, "barley": 1.18, "fur": 1.24},
    "قلعة برونزغيت": {"iron": 0.73, "tools": 0.75, "barley": 1.24, "salt": 1.18, "wine": 1.16},
    "قلعة سيفرلوك": {"timber": 0.96, "iron": 1.08, "salt": 1.16, "fur": 0.92, "tools": 1.04},
    "قلعة وولفكراون": {"fur": 0.71, "timber": 0.74, "salt": 1.34, "glass": 1.42, "wine": 1.36},
    "Halgrove Field": {"barley": 0.82, "wine": 0.75, "tools": 1.14, "iron": 1.19, "salt": 1.05},
    "The Capital": {"glass": 0.92, "wine": 0.91, "tools": 1.09, "iron": 1.12, "fur": 1.28, "barley": 1.17},
}


def translated(profile: dict, language: str) -> dict:
    """Return civic fields in the selected supported language."""
    lang = "en" if language == "en" else "ar"
    return {
        "location": profile["location"],
        "name": profile[f"location_{lang}"],
        "type": profile["type"],
        "population": profile["population"],
        "government": profile[f"government_{lang}"],
        "governor": profile[f"governor_{lang}"],
        "tax_rate": profile["tax_rate"],
        "security": profile["security"],
        "prosperity": profile["prosperity"],
        "loyalty": profile["loyalty"],
        "supply": profile[f"supply_{lang}"],
        "demand": profile[f"demand_{lang}"],
        "tier": profile["tier"],
    }


# Read-time English localization for the hand-authored atlas.  Canonical campaign
# values remain in Arabic in SQLite, so future dynamic discoveries retain their
# original text until the narrative engine supplies a localized counterpart.
ATLAS_WORLD_EN = {
    "name": "The Continent of Aldenmere",
    "tagline": "Ancient realms fracture between an aging crown, rising trade routes, and promises buried beneath ash.",
    "current_year": "417 After Unification",
    "current_age": "The Quiet Ash Age",
    "premise": "Lord Moayed Mudsbane stands at a historical turning point: a house born from a peasant revolt, a crown strong in decrees yet weak at its edges, and a continent where trade may redraw borders faster than armies.",
}

ATLAS_REGIONS_EN = {
    "ashvale": {"name": "Ashvale", "description": "Grey forests and narrow farms around the Ashen River; the home of House Mudsbane and the campaign's beginning.", "lore": "The valley was a worn fief of House Ashvale until Moayed's uprising cast it down. Memory remains sharp here, so everyday justice matters more than slogans."},
    "crownlands": {"name": "Crownlands", "description": "Fertile plains crossed by roads to the capital and the king's archives.", "lore": "The court lives on the legacy of the old Unification. Seals and offices abound, yet merchant families widen their influence through every crack."},
    "wolf_march": {"name": "The Wolf Marches", "description": "Windy highlands and frontier forts disputed by remnants of Lord Kaine's forces and local masters.", "lore": "The Marches were never one land; every tower claims the memory of a different war. Since Kaine fled, the vacuum has become more dangerous than any declared foe."},
    "western_coast": {"name": "Western Coast", "description": "Fogbound ports, salt works, and town councils that treat the sea as a law parallel to the Crown.", "lore": "Coastfolk measure years by sunken ships and surviving caravans, not kings. Here the Salt Compact watches every political rise as though it were a shipping contract."},
    "eastern_gentry": {"name": "Eastern Gentry", "description": "Limestone hills, vineyards, and small houses obsessed with lineage and rights of passage.", "lore": "No one family united these lands, only a fragile hall of compacts. Brief invasions and old debts offer greater opportunities here than great battles."},
    "greywood": {"name": "Old Greywood", "description": "An ancient ironwood forest with stone paths older than the kingdom of Aldenmere itself.", "lore": "Monastic records say the roots remember the names of those who die beneath them. Woodcutters know the forest does not forgive anyone who takes more than they can carry."},
    "southern_reach": {"name": "Southern Reach", "description": "A hot delta of salt fields and market towns reached by merchants before armies.", "lore": "Delta princes contend over canal duties while watching a distant route beyond the strait called the Far Crossing."},
    "frostward": {"name": "Frostward", "description": "Dark mountains, snowy passes, and silver mines guarded by castles that do not open in winter.", "lore": "The Crown's sovereignty over Frostward holds only on paper. Residents owe loyalty to the roads that remain open and to whoever owns the salt stores."},
    "far_crossing": {"name": "The Far Crossing", "description": "A strait and distant islands beyond the Salt Compact's usual routes.", "lore": "The Far Crossing appears on court maps only as an ornamented blank. Every ship that returns carries a rare commodity and a contradictory tale."},
}

ATLAS_LOCATION_TEXT_EN = {
    "Ashvale Hold": ("Ashvale Hold", "The seat of House Mudsbane, a stone keep above the Ashen River bearing the wolf-and-roots sigil."),
    "Mudroot": ("Mudroot", "Moayed's home village; the heart of popular memory and new loyalty."),
    "Millbrook Crossing": ("Millbrook Crossing", "The river crossing that saw the founding battle and the fall of the Ashvale garrison."),
    "حصن جسر الرماد": ("Ashbridge Fort", "An old customs tower controlling caravan traffic over the river."),
    "بلدة هولموك": ("Holmuck Town", "A town of mills and fields, and the first real test of the new grain-ration policy."),
    "مرسى بريل": ("Brill Quay", "A small river quay through which timber slips away to the coast."),
    "دير الجذر النائم": ("Sleeping Root Monastery", "An abandoned monastery whose monks built a stone well over an inscription that cannot be translated."),
    "The Capital": ("The Capital", "The capital, where the throne sits and offices compete to be the first to read the messages."),
    "مدينة إيلدنهول": ("Eldenhall City", "A city of records and courts from which five royal roads branch."),
    "قلعة برونزغيت": ("Bronzegate Castle", "The toll fort on the road to the capital; its bronze gate weighs more than a wagon of wheat."),
    "سوق الساعات السبع": ("Seven-Hour Market", "A caravan city whose markets close for only seven hours each week."),
    "دير القلم الأبيض": ("White Pen Monastery", "A monastic archive preserving copies of compacts some families refuse to acknowledge."),
    "مزارع ميرافيل": ("Miravel Farms", "Granaries that feed the royal garrison through winter."),
    "برج السراج": ("Lantern Tower", "A river beacon that receives the capital's ships and watches the duties."),
    "The March": ("The March", "The ancestral land of Lord Reventh Kaine; tense after his flight and the collapse of his network."),
    "قلعة بلاكستيب": ("Blackstep Castle", "A stepped castle carved into basalt; its garrison has no settled master now."),
    "مدينة ريڤنفورد": ("Ravenford City", "A horse-market city whose residents pay protection to whoever imposes it first."),
    "حصن العرصة التسعة": ("Nine-Yard Fort", "Nine small towers of which only five remain inhabited."),
    "وادي الغرابين": ("Raven Vale", "A narrow valley where fugitives and mercenaries gather in the morning mist."),
    "دير الراية المقطوعة": ("Broken Banner Monastery", "A fortified monastery that grants sanctuary under an old law which does not recognize political crimes."),
    "Port of Windmere": ("Port of Windmere", "Windmere's council city and the key to the timber and salt trade."),
    "مدينة سالتمارش": ("Saltmarsh City", "A salt-work city where the Salt Compact's interests meet pearl fishers."),
    "قلعة رأس العاصفة": ("Stormhead Fort", "A lighthouse-fort above a black cliff, taxing ships that survive the storm."),
    "مرفأ الأصداف الخمس": ("Five-Shell Harbor", "A small bay known for boatbuilders and letter smugglers."),
    "قرية بلاكهولم": ("Blackholm Village", "A fishing village whose people distrust every contract without the seal of Windmere's council."),
    "برج مارينز ووتش": ("Mariner's Watch", "A sea-watch tower abandoned by the royal garrison after an old plague."),
    "Eastern Gentry Lands": ("Eastern Gentry Lands", "Hills of unaffiliated small houses, where almost every road is private property."),
    "مدينة ڤيلوري": ("Velory City", "A city of vineyards and inheritance courts; its nobles prefer witnesses to swords."),
    "قلعة هارتستان": ("Heartstone Castle", "A limestone castle with larger wine stores than weapon stores."),
    "مانور ثورنويت": ("Thornwheat Manor", "A fortified manor surrounded by thorn hedges and medicinal gardens."),
    "دير الشمس المنكسرة": ("Broken Sun Monastery", "A small house of learning that studies pre-Unification maps and hides some of their pages."),
    "سوق كيلن": ("Kiln Market", "A weekly pottery market from which wagons depart laden with clay and secret letters."),
    "برج لورك": ("Lark Tower", "A river watchtower held by a family with no formal title and immense wealth."),
    "غابة غريوود": ("Greywood Forest", "A dense ironwood forest: Moayed's wealth and the source of borderfolk's fear."),
    "بوابة الحطابين": ("Woodcutters' Gate", "A timber-trade fence through which no caravan is meant to pass without a cutting record."),
    "حصن إيلك هول": ("Elk Hall Fort", "An abandoned hunting fort guarding a pass toward the northern foothills."),
    "بحيرة المرآة السوداء": ("Black Mirror Lake", "A silent lake where travelers see lights that never draw nearer."),
    "دير الغصن الحديدي": ("Ironbough Monastery", "A working monastery tending rare saplings and owing an old debt to House Voss."),
    "قرية لونغشيد": ("Longshade Village", "A frontier village that knows every trail suitable for a small party but not a wagon."),
    "مدينة شمس القنوات": ("Canal-Sun City", "A delta capital of tangled canals where irrigation rights are auctioned."),
    "قلعة سيفرلوك": ("Severlock Castle", "A castle controlling a water lock that decides the harvest of entire towns."),
    "ميناء دورابيل": ("Dorabel Port", "A hot port where salt ships meet boats bound for the Far Crossing."),
    "سوق ورد الرماد": ("Ashrose Market", "A spice and textile market where port intelligence is included in the price of goods."),
    "دير السد الأول": ("First Dam Monastery", "An engineering sanctuary guarding canal charts built by pre-Unification kings."),
    "أبراج النمل الأبيض": ("Termite Towers", "Three earthen towers in salt country; each proclaims a different king."),
    "قلعة وولفكراون": ("Wolfcrown Castle", "A mountain castle above a silver mine; the true gate of the north."),
    "مدينة هيلغلاس": ("Hillglass City", "A mining city kept warm by furnace smoke when the roads freeze."),
    "حصن الممر الأبيض": ("White Pass Fort", "A military tower open for only six months, selling warm water at the price of weapons."),
    "دير جليد الصدى": ("Echo-Ice Monastery", "Monks keep the names of those lost in the mountains and demand payment for the knowledge."),
    "مناجم إيرونفيل": ("Ironvale Mines", "Silver and iron mines under a guild that recognizes no borders."),
    "مخيم ثلجبارد": ("Snowbard Camp", "The last safe camp before slopes that do not appear on summer maps."),
    "جزيرة كالدرا": ("Kaldra Isle", "A free island where ships dock when they do not wish to be asked about their cargo."),
    "منارة أوريون": ("Orion Lighthouse", "A distant lighthouse that burns blue on nights when unknown ships arrive."),
    "مضيق الأختام السبعة": ("Seven Seals Strait", "A sea passage whose ships need seven duties or seven lies to cross it."),
    "جزيرة الريح الأخيرة": ("Last Wind Isle", "A storm island inhabited only by lighthouse keepers and emergency stores."),
}

ATLAS_LORDS_EN = {
    "moayed": {"name": "Moayed Mudsbane", "title": "Lord of Ashvale", "house": "House Mudsbane", "seat": "Ashvale Hold", "disposition": "The player ruler", "public_agenda": "Build a fair, strong trading state from Ashvale.", "secret": "He dreams of unifying the continent beneath a new crown that will not repeat the old one's corruption.", "biography": "A former farmer who overthrew Baron Ashvale and won the Crown's recognition. His legitimacy is tested every day in the harvest and in justice as surely as by the sword."},
    "isolde": {"name": "Isolde Mudsbane", "title": "Lady of Ashvale", "house": "Mudsbane / formerly Ashvale", "seat": "Ashvale Hold", "disposition": "A steadfast ally", "public_agenda": "Protect the new house's legitimacy and expand its diplomatic network.", "secret": "She keeps a list of nobles who supported her in the past and fears they will demand their price soon.", "biography": "A former baroness, Moayed's wife and his political partner. She manages the letters and eyes that never appear in councils."},
    "reventh_kaine": {"name": "Reventh Kaine", "title": "Fugitive Lord of the Wolf Marches", "house": "House Kaine", "seat": "The March", "disposition": "A volatile adversary", "public_agenda": "Avoid trial and reclaim what remains of his influence.", "secret": "He knows the details of an old debt binding members of the Crown Council to the Salt Compact.", "biography": "The architect of the conspiracy that created the Millbrook crisis. He lost his army and his ranks, but not his web of debts and fear."},
    "petyr_halgrove": {"name": "Petyr Halgrove", "title": "Lord of Halgrove Field", "house": "House Halgrove", "seat": "Halgrove Field", "disposition": "A wary ally", "public_agenda": "Secure the road between Ashvale and the capital.", "secret": "He fears Moayed's prosperity will swallow his small trade before his family grows strong.", "biography": "A minor lord with a trusted voice in local assemblies. His alliance with Moayed is sincere, but his interests never rest."},
    "selene_voss": {"name": "Selene Voss", "title": "Lady of the Silver House", "house": "House Voss", "seat": "Lark Tower", "disposition": "A cautious merchant", "public_agenda": "Turn noble debts into lasting legal influence.", "secret": "She secretly funds an expedition for a lost archive of royal debt.", "biography": "Heiress to the eastern Voss branch. She says she does not wage war, yet her ledgers have toppled more houses than armies."},
    "osric_veyl": {"name": "Osric Veyl", "title": "Count of Velory", "house": "House Veyl", "seat": "Velory City", "disposition": "A hesitant aristocrat", "public_agenda": "Keep the Gentry Council independent of the capital.", "secret": "His eldest child owes the Salt Compact after a failed sea wager.", "biography": "A learned count who prefers courts to wars, though the loss of his inheritance drives him toward harsh decisions."},
    "marra_cray": {"name": "Marra Cray", "title": "Warden of Windmere Council", "house": "Windmere Council", "seat": "Port of Windmere", "disposition": "A trade partner", "public_agenda": "Ratify a timber-and-ships agreement without making the port subject to any lord.", "secret": "She holds a ship's log proving that Kaine dealt with pirates years before his crisis.", "biography": "She succeeded Sella Cray as interim council leader during a health crisis. She does not inherit the office; she secures it anew each morning by vote."},
    "aldrus_renn": {"name": "Aldrus Renn", "title": "Factor of the Salt Compact", "house": "The Salt Compact", "seat": "Saltmarsh City", "disposition": "A conditional friend", "public_agenda": "Secure salt, timber and new shipping routes without open war.", "secret": "He receives letters from a Far Crossing captain who has not returned for two years.", "biography": "A sea factor who never raises his voice; he prefers his opponent to discover too late that the contract was against them."},
    "maelin_sun": {"name": "Maelin Sun", "title": "Lady of Canal-Sun", "house": "House Sun", "seat": "Canal-Sun City", "disposition": "Ambitious", "public_agenda": "Expand delta authority over tolls and canals.", "secret": "She knows an old dam is cracking and conceals it so land prices do not collapse.", "biography": "Nominal ruler of the delta towns; her power lies in water and tax records, not castles."},
    "damir_sever": {"name": "Damir Sever", "title": "Master of Severlock", "house": "House Sever", "seat": "Severlock Castle", "disposition": "Pragmatic", "public_agenda": "Keep the water lock outside any capital's control.", "secret": "He sold canal charts to an unknown buyer from the Far Crossing.", "biography": "A guard lord who effectively controls Southern Reach's harvest; he sells stability to those who can pay for it."},
    "astrid_wolfcrown": {"name": "Astrid Wolfcrown", "title": "Lady of Frostward", "house": "House Wolfcrown", "seat": "Wolfcrown Castle", "disposition": "Independent", "public_agenda": "Protect the mines and open White Pass before winter.", "secret": "She seeks a missing heir who could ignite an old dispute over the throne.", "biography": "A forthright mountain ruler who dislikes court titles; she weighs people by their stores and promises in a storm."},
    "brohm_helglass": {"name": "Brohm Helglass", "title": "Foreman of the Mining Guild", "house": "Helglass Guild", "seat": "Hillglass City", "disposition": "Armed neutral", "public_agenda": "Sell silver and iron to any buyer who pays and protects caravans.", "secret": "A buried entrance beneath his mine leads to tunnels from before Unification.", "biography": "A guild leader who commands more workers than many lords command soldiers."},
    "cassian_valor": {"name": "Cassian Valor", "title": "Keeper of the Royal Banner", "house": "The Crown", "seat": "Bronzegate Castle", "disposition": "Official observer", "public_agenda": "Keep the royal road safe and prevent a new private war.", "secret": "He is reviewing an old royal order granting a conditional right to command Crown armies if the heir is absent.", "biography": "An officer without grand noble pretensions, known for incorruptible records; that is why many in the capital despise him."},
    "lyra_thorn": {"name": "Lyra Thorn", "title": "Lady of Thornwheat Manor", "house": "House Thorn", "seat": "Thornwheat Manor", "disposition": "Friendly ambiguity", "public_agenda": "Unite smaller gentry houses in a defensive league.", "secret": "Her house owes an old protection debt to Broken Sun Monastery in exchange for a document unread for a generation.", "biography": "A young politician who knows the value of courtesies and poisons in equal measure."},
    "ilsbeth_voro": {"name": "Ilsbeth Voro", "title": "Captain of the Far Crossing", "house": "Voro Fleet", "seat": "Kaldra Isle", "disposition": "Unknown", "public_agenda": "Open a sea route beyond the Salt Compact's rule.", "secret": "She hides a passenger descended from a royal line that fell before Unification.", "biography": "Her name is a harbor rumor, but every rumor of her arrives with goods nobody else possesses."},
}

ATLAS_HISTORY_EN = {
    "قبل التوحيد: زمن الرايات الصغيرة": {"title": "Before Unification: The Age of Little Banners", "era": "-430 to 0", "summary": "Aldenmere was a mosaic of river towns, mountain castles, and independent ports. No one held power beyond a road or a harvest, yet wars over tolls never ceased."},
    "التوحيد الأول": {"title": "The First Unification", "era": "0 to 94", "summary": "King Alden I gathered seven banners beneath one road law and unified taxes. He founded the capital and Bronzegate, paying with promises of independence that remained alive on the margins."},
    "قرن الطرق والفضة": {"title": "The Century of Roads and Silver", "era": "95 to 251", "summary": "Mines and ports expanded wealth, while House Voss and the Salt Compact became powers that financed the state without wearing a crown."},
    "حروب الممرات": {"title": "The Pass Wars", "era": "252 to 338", "summary": "Long cold seasons sparked conflict over the passes of Frostward and the Wolf Marches. The Crown won on maps, but granted frontier commanders powers it never recovered."},
    "عهد الأختام الصامتة": {"title": "The Age of Silent Seals", "era": "339 to 404", "summary": "Kings disappeared from the roads as judges and clerks grew more present. Bribery became faster than siege, and debts became cause enough for war to hide its name."},
    "عصر الرماد الهادئ": {"title": "The Quiet Ash Age", "era": "405 to 417", "summary": "Ashvale fell, Moayed Mudsbane rose, Kaine fled, and coastal trade tightened. The continent does not yet know whether it faces a new state or a slow civil war."},
}

ATLAS_LORE_EN = {
    "lore-ashvale-fall": {"category": "Event", "title": "The Fall of Ashvale", "era": "417 After Unification", "keywords": "Moayed,Ashvale,legitimacy,revolt", "body": "House Mudsbane did not begin with a lineage or a royal festival, but with a garrison drained at Millbrook and a palace gate opened by deceit. The Crown's later recognition did not erase the fact that farmers decided that morning."},
    "lore-roots": {"category": "Organization", "title": "The Roots", "era": "The current age", "keywords": "Tomas,espionage,covert operations", "body": "The Roots are a small team absent from the public record. House Mudsbane justifies them by fearing the politics its guards cannot see, yet risks becoming the thing it resists."},
    "lore-salt-compact": {"category": "Faction", "title": "The Salt Compact", "era": "The Century of Roads and Silver", "keywords": "trade,ships,Windmere,salt", "body": "The Compact is a union of shares, not a kingdom. It pretends neutrality because every king needs salt more than a victory hymn; it cannot be defeated in battle, yet sometimes loses to a single signature."},
    "lore-white-pen": {"category": "Secret", "title": "The White Pen Copies", "era": "The Age of Silent Seals", "keywords": "archive,Crown,documents", "body": "It is said the White Pen monks preserve not only official copies, but the first wording of compacts before they were revised to favor the powerful."},
    "lore-frost-oath": {"category": "Oath", "title": "The Frostward Oath", "era": "The Pass Wars", "keywords": "mountains,silver,White Pass", "body": "Every ruler who tries to impose a winter tax on Frostward learns the same rule: you do not own the pass unless you can feed those who guard it."},
    "lore-seven-seals": {"category": "Legend", "title": "The Seven Seals", "era": "Undated", "keywords": "sea,Far Crossing,treasure", "body": "Sailors tell of seven broken seals that secure a passage through the strait. The old ones meant not wax seals, but seven promises whose price is paid by whoever returns from the sea."},
    "lore-broken-sun": {"category": "Relic", "title": "Broken Sun Monastery", "era": "Before Unification", "keywords": "maps,east,monks", "body": "Eastern monks copy maps whose borders do not resemble the Crown's. On one, a stone road leaves the forest and ends beneath the capital itself."},
    "lore-water-lock": {"category": "Dispute", "title": "The Severlock Water Lock", "era": "The Quiet Ash Age", "keywords": "delta,canals,taxes", "body": "The water lock at Severlock can flood fields or dry them. Its keeper does not legally own the delta's land, but truly owns the moment of harvest."},
}

ATLAS_FACTIONS_EN = {
    "مجلس إقطاعيات الشرق": {"name": "Eastern Gentry Council", "description": "A fragile gathering of small houses guarding their privileges with documents and marriages."},
    "نقابة هيلغلاس": {"name": "Helglass Guild", "description": "A union of workers and financiers that holds the keys to the northern mines."},
    "رابطة الملح": {"name": "The Salt Compact", "description": "A mercantile coalition whose ships carry salt, news, and leverage between the coasts."},
    "الجذور": {"name": "The Roots", "description": "A quiet Ashvale network that works where formal guards cannot see."},
    "ديوان التاج": {"name": "The Crown Chancery", "description": "The capital's clerks and seals, powerful wherever records decide ownership."},
}


def localize_atlas_payload(payload: dict, language: str) -> dict:
    """Return a localized copy of the canonical atlas read model without mutating campaign records."""
    if language != "en":
        return payload

    from copy import deepcopy
    localized = deepcopy(payload)
    localized["world"] = {**localized.get("world", {}), **ATLAS_WORLD_EN}

    for region in localized.get("regions", []):
        translation = ATLAS_REGIONS_EN.get(region.get("slug"))
        if translation:
            region.update(translation)

    for location in localized.get("locations", []):
        location["canonical_name"] = location.get("name")
        translation = ATLAS_LOCATION_TEXT_EN.get(location.get("name"))
        if translation:
            location["name"], location["description"] = translation

    for lord in localized.get("lords", []):
        lord["canonical_seat"] = lord.get("seat")
        translation = ATLAS_LORDS_EN.get(lord.get("slug"))
        if translation:
            lord.update(translation)

    for event in localized.get("history", []):
        translation = ATLAS_HISTORY_EN.get(event.get("title"))
        if translation:
            event.update(translation)

    for entry in localized.get("lore", []):
        translation = ATLAS_LORE_EN.get(entry.get("slug"))
        if translation:
            entry.update(translation)

    for faction in localized.get("factions", []):
        translation = ATLAS_FACTIONS_EN.get(faction.get("name"))
        if translation:
            faction.update(translation)

    return localized
