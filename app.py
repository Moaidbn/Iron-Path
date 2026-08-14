"""خادم لعبة طريق الحديد المحسّنة."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

from commands import dispatch, is_command  # noqa: E402
from database import (  # noqa: E402
    claim_loot_pile,
    get_all_appearances,
    get_atlas_data,
    get_armies,
    get_battles,
    get_character_stats,
    get_character_directory,
    get_civic_profile,
    get_civic_profiles,
    get_economy_dashboard,
    get_historical_wars,
    get_local_market,
    get_factions,
    get_holdings,
    get_inventory,
    get_loot_piles,
    get_map_locations,
    get_mastery_specializations,
    get_player_state,
    get_player_shops,
    get_shop_options,
    open_player_shop,
    get_quests,
    get_retainers,
    get_traits,
    get_turn_count,
    get_ui_strings,
    get_world_clock,
    set_item_equipped,
    trade_good,
)
from offline_engine import OfflineRPGGame  # noqa: E402


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["JSON_AS_ASCII"] = False
    app.json.ensure_ascii = False
    game = OfflineRPGGame()

    @app.get("/")
    def index():
        return render_template("index.html", engine_mode=game.mode)

    @app.get("/health")
    def health():
        return jsonify({
            "status": "ok",
            "engine": game.mode,
            "narration_status": game.narration_status,
            "narration_latency_ms": game.narration_latency_ms,
            "narration_context_mode": game.narration_context_mode,
            "narration_finish_reason": game.narration_finish_reason,
            "narration_prompt_chars": game.narration_prompt_chars,
            "turn": get_turn_count(),
        })

    @app.get("/dashboard-data")
    def dashboard_data():
        try:
            return jsonify({
                "character_stats": get_character_stats(),
                "player_state": get_player_state(),
                "specializations": get_mastery_specializations(),
                "traits": get_traits(),
                "factions": get_factions(),
                "retainers": get_retainers(),
                "quests": get_quests(),
                "holdings": get_holdings(),
                "inventory": get_inventory(),
                "world_clock": get_world_clock(),
                "appearances": get_all_appearances(),
                "armies": get_armies(),
                "battles": get_battles(limit=15),
                "loot_piles": get_loot_piles(),
                "economy": get_economy_dashboard(),
                "turn_count": get_turn_count(),
                "engine_mode": game.mode,
                "narration_status": game.narration_status,
                "narration_latency_ms": game.narration_latency_ms,
                "narration_context_mode": game.narration_context_mode,
                "narration_finish_reason": game.narration_finish_reason,
                "narration_prompt_chars": game.narration_prompt_chars,
            })
        except Exception as exc:
            app.logger.exception("Could not load dashboard")
            return jsonify({"error": f"تعذر تحميل لوحة الحملة: {exc}"}), 500

    @app.get("/characters-data")
    def characters_data():
        try:
            language = requested_language()
            return jsonify({"language": language, "characters": get_character_directory(language)})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Could not load character directory")
            return jsonify({"error": f"تعذر تحميل سجل الشخصيات: {exc}"}), 500

    @app.get("/map-data")
    def map_data():
        try:
            return jsonify(get_atlas_data(include_hidden=True, lang=requested_language()))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Could not load atlas")
            return jsonify({"error": f"تعذر تحميل أطلس العالم: {exc}"}), 500

    def requested_language():
        language = request.args.get("lang", "ar").strip().lower()
        if language not in {"ar", "en"}:
            raise ValueError("اللغة المدعومة هي ar أو en فقط.")
        return language

    @app.get("/localization-data")
    def localization_data():
        try:
            return jsonify(get_ui_strings(requested_language()))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/history-data")
    def history_data():
        try:
            language = requested_language()
            return jsonify({"language": language, "wars": get_historical_wars(language)})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Could not load history")
            return jsonify({"error": f"تعذر تحميل تاريخ الحروب: {exc}"}), 500

    @app.get("/civics-data")
    def civics_data():
        try:
            language = requested_language()
            location = request.args.get("location", "").strip()
            if location:
                if len(location) > 100:
                    return jsonify({"error": "اسم الموقع طويل على نحو غير صالح."}), 400
                profile = get_civic_profile(location, language)
                if not profile:
                    return jsonify({"error": "لا يوجد ملف مدني لهذا الموقع."}), 404
                return jsonify({"language": language, "profile": profile})
            return jsonify({"language": language, "profiles": get_civic_profiles(language)})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Could not load civics")
            return jsonify({"error": f"تعذر تحميل ملفات المدن: {exc}"}), 500

    @app.get("/local-market")
    def local_market_data():
        try:
            language = requested_language()
            location = request.args.get("location", "").strip()
            if not location or len(location) > 100:
                return jsonify({"error": "اختر موقعًا صالحًا للسوق المحلي."}), 400
            market = get_local_market(location, language)
            if not market:
                return jsonify({"error": "لا يوجد سوق محلي لهذا الموقع."}), 404
            return jsonify({"language": language, "market": market})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Could not load local market")
            return jsonify({"error": f"تعذر تحميل السوق المحلي: {exc}"}), 500

    @app.get("/shop-options")
    def shop_options_data():
        try:
            language = requested_language()
            location = request.args.get("location", "").strip()
            if not location or len(location) > 100:
                return jsonify({"error": "اختر موقعًا صالحًا لترخيص المتجر."}), 400
            options = get_shop_options(location, language)
            if not options:
                return jsonify({"error": "لا توجد رخص تجارية متاحة لهذا الموقع."}), 404
            return jsonify({"language": language, **options})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Could not load shop options")
            return jsonify({"error": f"تعذر تحميل رخص المتجر: {exc}"}), 500

    @app.get("/player-shops")
    def player_shops_data():
        try:
            language = requested_language()
            return jsonify({"language": language, "shops": get_player_shops(language)})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Could not load player shops")
            return jsonify({"error": f"تعذر تحميل متاجر اللاعب: {exc}"}), 500

    @app.post("/open-shop")
    def open_shop():
        data = request.get_json(silent=True) or {}
        location = str(data.get("location", "")).strip()
        shop_type = str(data.get("shop_type", "")).strip().lower()
        if not location or len(location) > 100 or not shop_type or len(shop_type) > 40:
            return jsonify({"error": "بيانات افتتاح المتجر غير صالحة."}), 400
        try:
            result = open_player_shop(location, shop_type, get_turn_count())
            return jsonify({"shop": result, "shops": get_player_shops(requested_language()), "economy": get_economy_dashboard()})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Could not open player shop")
            return jsonify({"error": f"تعذر افتتاح المتجر: {exc}"}), 500

    @app.get("/economy-data")
    def economy_data():
        try:
            return jsonify(get_economy_dashboard())
        except Exception as exc:
            app.logger.exception("Could not load economy")
            return jsonify({"error": f"تعذر تحميل دفتر التجارة: {exc}"}), 500

    @app.post("/trade")
    def trade():
        data = request.get_json(silent=True) or {}
        good_id = str(data.get("good_id", "")).strip().lower()
        side = str(data.get("side", "")).strip().lower()
        quantity = data.get("quantity")
        if not good_id or len(good_id) > 40 or not all(ch.isalnum() or ch in "_-" for ch in good_id):
            return jsonify({"error": "معرّف السلعة غير صالح."}), 400
        if side not in {"buy", "sell"} or not isinstance(quantity, int) or isinstance(quantity, bool):
            return jsonify({"error": "بيانات صفقة السوق غير صالحة."}), 400
        try:
            result = trade_good(good_id, quantity, side, get_turn_count())
            return jsonify({"trade": result, "economy": get_economy_dashboard()})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Trade failed")
            return jsonify({"error": f"تعذر إتمام الصفقة: {exc}"}), 500

    @app.post("/equip-item")
    def equip_item():
        data = request.get_json(silent=True) or {}
        item_id = data.get("item_id")
        if not isinstance(item_id, int):
            return jsonify({"error": "معرّف العنصر غير صالح."}), 400
        try:
            equipped = bool(data.get("equipped"))
            set_item_equipped(item_id, equipped)
            return jsonify({"item_id": item_id, "equipped": equipped, "inventory": get_inventory()})
        except Exception as exc:
            app.logger.exception("Could not equip item")
            return jsonify({"error": f"تعذر تغيير تجهيز العنصر: {exc}"}), 500

    @app.post("/claim-loot")
    def claim_loot():
        data = request.get_json(silent=True) or {}
        loot_id = data.get("loot_id")
        if not isinstance(loot_id, int):
            return jsonify({"error": "معرّف الغنيمة غير صالح."}), 400
        try:
            claimed = claim_loot_pile(loot_id, get_turn_count())
            if claimed is None:
                return jsonify({"error": "هذه الغنيمة غير متاحة الآن."}), 400
            return jsonify({"claimed": claimed, "inventory": get_inventory(), "loot_piles": get_loot_piles(), "economy": get_economy_dashboard()})
        except Exception as exc:
            app.logger.exception("Could not claim loot")
            return jsonify({"error": f"تعذر جمع الغنيمة: {exc}"}), 500

    @app.post("/play")
    def play():
        data = request.get_json(silent=True) or {}
        action = str(data.get("action", "")).strip()
        language = str(data.get("language", "ar")).strip().lower()
        if language not in {"ar", "en"}:
            language = "ar"
        if not action:
            return jsonify({"error": "اكتب فعلًا أو قرارًا قبل الإرسال."}), 400
        if len(action) > 500:
            return jsonify({"error": "اجعل القرار أقصر من 500 حرف."}), 400

        if is_command(action):
            try:
                if action.casefold().strip() == "/recap":
                    result = {"kind": "recap", "response": game.recap(language=language)}
                else:
                    result = dispatch(action, client=None)
                return jsonify({"is_command": True, "kind": result.get("kind", "command"), "response": result["response"]})
            except Exception as exc:
                app.logger.exception("Command failed")
                return jsonify({"error": f"تعذر تنفيذ الأمر: {exc}"}), 500

        try:
            result = game.play_turn(action, language=language)
            return jsonify({"is_command": False, **result})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Turn failed")
            return jsonify({"error": f"تعذر إتمام الدور. حاول مجددًا: {exc}"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5011")), debug=os.getenv("FLASK_DEBUG") == "1")
