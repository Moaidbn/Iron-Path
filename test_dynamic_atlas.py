"""Smoke test for additive dynamic atlas updates; it cleans its own test rows."""
from database import get_atlas_data, get_connection, initialize_database
from state_manager import apply_state_changes

TEST_TURN = 999_999


def main():
    initialize_database()
    proposal = {
        "world_lord_updates": [{
            "type": "ADD_LORD",
            "name": "اختبار لورد الأطلس",
            "title": "حارس البوابة النحاسية",
            "house": "بيت الاختبار",
            "seat": "بوابة الاختبار",
            "region": "ashvale",
            "allegiance": "مستقل",
            "disposition": "حذر",
            "public_agenda": "حماية قافلة علمية",
            "secret": "لا يُحتفظ ببيانات الاختبار بعد الفحص.",
            "biography": "شخصية اختبار عابرة للتحقق من عقد الإضافة.",
            "discovered": True,
        }],
        "world_lore_updates": [{
            "type": "ADD_LORE",
            "category": "discovery",
            "title": "سجل اختبار الأطلس",
            "region": "ashvale",
            "era": "العصر الحالي",
            "keywords": ["اختبار", "أطلس"],
            "body": "معلومة اختبارية للتحقق من إلحاق Lore جديد دون تعديل قانون العالم الأصلي.",
            "discovered": True,
        }],
    }
    try:
        summary = apply_state_changes(proposal, scene_id=0, turn_number=TEST_TURN)
        atlas = get_atlas_data(include_hidden=True)
        lord_names = {item["name"] for item in atlas["lords"]}
        lore_titles = {item["title"] for item in atlas["lore"]}
        assert summary["new_lords"] == ["اختبار لورد الأطلس"], summary
        assert summary["new_lore"] == ["سجل اختبار الأطلس"], summary
        assert "اختبار لورد الأطلس" in lord_names
        assert "سجل اختبار الأطلس" in lore_titles
        print("DYNAMIC_ATLAS_OK", summary)
    finally:
        conn = get_connection()
        conn.execute("DELETE FROM world_lords WHERE added_turn = ?", (TEST_TURN,))
        conn.execute("DELETE FROM world_lore WHERE added_turn = ?", (TEST_TURN,))
        conn.commit()
        conn.close()


if __name__ == "__main__":
    main()
