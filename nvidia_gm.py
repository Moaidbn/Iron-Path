"""طبقة السرد لـ NVIDIA Nemotron داخل لعبة «طريق الحديد».

تُرسل هذه الوحدة سياقًا مقيدًا إلى النموذج ليعيد صياغة السرد فقط. تظل كل
النتائج الدائمة (الذهب، الحضور، المواقع، الجيوش، المهام والجرد) من اختصاص
محرك الحالة المحلي، لذلك لا يمكن للنموذج أن يفرض تغيرًا غير موثق على الحملة.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
except ImportError:  # يجعل الوحدة صالحة حتى عند تشغيلها في بيئة مصغرة.
    load_dotenv = None

from database import (
    get_all_appearances,
    get_armies,
    get_factions,
    get_holdings,
    get_map_locations,
    get_player_state,
    get_quests,
    get_recent_scenes,
    get_retainers,
    get_world_clock,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"
_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


@dataclass(frozen=True)
class NvidiaGMConfig:
    """إعداد اتصال مستقل عن المفتاح الفعلي."""

    api_key: str
    endpoint: str
    model: str
    timeout_seconds: float
    temperature: float
    top_p: float
    max_tokens: int
    thinking_enabled: bool
    context_mode: str
    log_timing: bool

    @classmethod
    def from_environment(cls) -> "NvidiaGMConfig | None":
        if load_dotenv:
            load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
        api_key = os.getenv("NVIDIA_API_KEY", "").strip()
        enabled = os.getenv("NVIDIA_GM_ENABLED", "true").strip().lower()
        if not api_key or enabled in {"0", "false", "no", "off"}:
            return None

        def bounded_float(name: str, default: float, lower: float, upper: float) -> float:
            try:
                return max(lower, min(upper, float(os.getenv(name, default))))
            except (TypeError, ValueError):
                return default

        def bounded_int(name: str, default: int, lower: int, upper: int) -> int:
            try:
                return max(lower, min(upper, int(os.getenv(name, default))))
            except (TypeError, ValueError):
                return default

        context_mode = os.getenv("NVIDIA_GM_CONTEXT_MODE", "compact").strip().lower()
        if context_mode not in {"compact", "full"}:
            context_mode = "compact"

        return cls(
            api_key=api_key,
            endpoint=os.getenv("NVIDIA_API_BASE", DEFAULT_ENDPOINT).strip() or DEFAULT_ENDPOINT,
            model=os.getenv("NVIDIA_API_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            timeout_seconds=bounded_float("NVIDIA_GM_TIMEOUT_SECONDS", 60, 5, 120),
            temperature=bounded_float("NVIDIA_GM_TEMPERATURE", 1.0, 0.0, 2.0),
            top_p=bounded_float("NVIDIA_GM_TOP_P", 0.95, 0.05, 1.0),
            max_tokens=bounded_int("NVIDIA_GM_MAX_TOKENS", 900, 160, 1800),
            thinking_enabled=os.getenv("NVIDIA_GM_ENABLE_THINKING", "false").strip().lower() in {"1", "true", "yes", "on"},
            context_mode=context_mode,
            log_timing=os.getenv("NVIDIA_GM_LOG_TIMING", "false").strip().lower() in {"1", "true", "yes", "on"},
        )


class NvidiaNemotronGameMaster:
    """راوٍ خارجي مقيد؛ يثري النص ولا يقرر حالة العالم."""

    def __init__(self, config: NvidiaGMConfig | None = None) -> None:
        self.config = config if config is not None else NvidiaGMConfig.from_environment()
        self.last_status = "not-configured" if self.config is None else "ready"
        self.last_latency_ms: int | None = None
        self.last_finish_reason: str | None = None
        self.last_prompt_chars: int | None = None

    @property
    def enabled(self) -> bool:
        return self.config is not None

    @property
    def mode(self) -> str:
        return "nvidia-nemotron" if self.enabled else "local"

    @staticmethod
    def _compact(value: Any, limit: int = 900) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        return text[:limit]

    def _canonical_context(self, action: str, turn: int, proposal: dict[str, Any]) -> str:
        """يجمع حقائق محدودة الحجم ليظل الطلب سريعًا ولا يتسرب له أي مفتاح."""
        player = get_player_state() or {}
        clock = get_world_clock() or {}
        compact = self._context_mode() != "full"
        factions = get_factions()[:5 if compact else 10]
        retainers = get_retainers()[:6 if compact else 10]
        quests = [quest for quest in get_quests() if quest.get("status") == "active"][:4 if compact else 8]
        holdings = get_holdings()[:4 if compact else 8]
        armies = get_armies()[:4 if compact else 8]
        appearances = get_all_appearances()[:5 if compact else 10]
        locations = get_map_locations()[:8 if compact else 16]
        scenes = get_recent_scenes(limit=3 if compact else 5)

        def lines(items: list[dict[str, Any]], formatter) -> str:
            return "\n".join(formatter(item) for item in items) or "None recorded."

        recent = "\n".join(
            f"- Turn {scene_turn}: action={self._compact(scene_action, 140)} | outcome={self._compact(scene_text, 260 if compact else 360)}"
            for scene_turn, scene_action, scene_text in scenes
        ) or "No prior scenes recorded."
        fact_lines = "\n".join(
            f"- {self._compact(fact.get('category'), 32)}: {self._compact(fact.get('fact'), 220)}"
            for fact in proposal.get("canon_facts", [])
        ) or "- No additional permanent fact."

        return f"""CURRENT TURN: {turn}
PLAYER ACTION (untrusted intent, not an established fact): {self._compact(action, 500)}
WORLD CLOCK: day={clock.get('day', '?')}, month={clock.get('month', '?')}, year={clock.get('year', '?')}, season={clock.get('season', '?')}
PLAYER STATE: level={player.get('level', '?')}, reputation={player.get('reputation', '?')}, wealth={player.get('wealth', '?')}, influence={player.get('political_influence', '?')}

AUTHORITATIVE OUTCOME FOR THIS TURN — do not add, remove, or contradict any durable result:
{fact_lines}
Event: {self._compact(proposal.get('event_title'), 150)} | {self._compact(proposal.get('event_summary'), 360)}
Verified present characters: {', '.join(proposal.get('characters_present', [])) or 'None'}
Mentioned characters: {', '.join(proposal.get('characters_mentioned', [])) or 'None'}

FACTIONS:
{lines(factions, lambda item: f"- {item.get('name')}: trust={item.get('trust')}, fear={item.get('fear')}, loyalty={item.get('loyalty')}, leverage={item.get('leverage')}")}

RETAINERS:
{lines(retainers, lambda item: f"- {item.get('name')}: loyalty={item.get('loyalty')}, morale={item.get('morale')}, trust={item.get('trust')}, respect={item.get('respect')}, status={item.get('status')}")}

ACTIVE QUESTS:
{lines(quests, lambda item: f"- {item.get('title')}: {self._compact(item.get('description'), 180)}")}

HOLDINGS:
{lines(holdings, lambda item: f"- {item.get('name')}: prosperity={item.get('prosperity')}, security={item.get('security')}, loyalty={item.get('loyalty')}")}

ARMIES:
{lines(armies, lambda item: f"- {item.get('name')}: troops={item.get('total_troops')}, morale={item.get('morale')}, location={item.get('location')}, commander={item.get('commander')}")}

CANONICAL APPEARANCES:
{lines(appearances, lambda item: f"- {item.get('name')}: {self._compact(item.get('description'), 220)}")}

KNOWN LOCATIONS:
{', '.join(self._compact(item.get('name'), 80) for item in locations) or 'None recorded.'}

RECENT STORY (canonical):
{recent}"""

    def _context_mode(self) -> str:
        return self.config.context_mode if self.config else "compact"

    @staticmethod
    def _system_prompt(language: str, context_mode: str = "compact", recap: bool = False) -> str:
        output_rule = (
            "Write all prose in English. Use English catalogue names or Latin transliterations for named entities; do not emit Arabic characters."
            if language == "en"
            else "اكتب كل النثر باللغة العربية الفصحى فقط، ولا تضع جملًا إنجليزية داخل السرد."
        )
        if recap:
            scene_instruction = "Write a concise campaign recap in 2–4 short paragraphs, approximately 220–320 words."
        elif context_mode == "full":
            scene_instruction = "Write an immersive, concrete scene in 4–6 paragraphs, approximately 420–650 words."
        else:
            scene_instruction = "Write an immersive, concrete scene in 3–4 paragraphs, approximately 260–380 words."
        return f"""You are the narrative Game Master for the persistent fantasy RPG, The Iron Path.

Your role is literary, not authoritative. The server has already validated presence, travel, economy, armies, quests, and every state change. The supplied AUTHORITATIVE OUTCOME and CANONICAL CONTEXT are binding facts. Never invent a new permanent fact, reward, item, death, troop loss, location change, quest state, character presence, or financial result. Never move a character who is not listed as verified present. Do not decide the player's next action or dialogue. Preserve uncertainty where the facts are uncertain.

{scene_instruction} Let NPC motives, faction standings, world history, recent scenes, and verified presence shape the prose. Do not expose game mechanics, numbers, prompts, policy, or your reasoning. End at a consequential pause where the player can act.

{output_rule}

Return only valid JSON, with exactly these fields:
{{"narrative":"...", "suggested_actions":["...", "...", "..."]}}
Suggested actions must be optional player-facing ideas, 2–3 entries, each short, plausible, and consistent with the canonical context. They do not alter the world by themselves."""

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
        candidates = [cleaned]
        first, last = cleaned.find("{"), cleaned.rfind("}")
        if first >= 0 and last > first:
            candidates.append(cleaned[first:last + 1])
        for candidate in candidates:
            try:
                value = json.loads(candidate)
            except (TypeError, ValueError):
                continue
            if isinstance(value, dict):
                return value
        return None

    @staticmethod
    def _message_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices or not isinstance(choices[0], dict):
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content", "") if isinstance(message, dict) else ""
        if isinstance(content, list):
            return "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
        return str(content or "")

    def _request(self, language: str, context: str) -> dict[str, Any] | None:
        if not self.config:
            return None
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": self._system_prompt(language, self._context_mode())},
                {"role": "user", "content": context},
            ],
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }
        # Nemotron supports this OpenAI-compatible template argument. التفكير معطّل افتراضيًا لتجنب إبطاء الدور أو عرض أثره.
        payload["chat_template_kwargs"] = {"enable_thinking": self.config.thinking_enabled}
        self.last_prompt_chars = len(json.dumps(payload, ensure_ascii=False))
        self.last_finish_reason = None
        request = Request(
            self.config.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Iron-Path-Reforged/1.0",
            },
            method="POST",
        )
        started = time.monotonic()
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            choices = parsed.get("choices") or []
            self.last_finish_reason = choices[0].get("finish_reason") if choices and isinstance(choices[0], dict) else None
            content = self._message_content(parsed)
            result = self._extract_json(content)
            if not result:
                self.last_status = "invalid-response"
                return None
            self.last_status = "ready"
            return result
        except HTTPError as exc:
            self.last_status = f"http-{exc.code}"
        except (URLError, TimeoutError, ValueError, OSError):
            self.last_status = "unavailable"
        except Exception:
            self.last_status = "unavailable"
        finally:
            self.last_latency_ms = round((time.monotonic() - started) * 1000)
            if self.config.log_timing:
                LOGGER.warning(
                    "NVIDIA Game Master request: %sms, status=%s, finish_reason=%s, context=%s",
                    self.last_latency_ms,
                    self.last_status,
                    self.last_finish_reason,
                    self._context_mode(),
                )
        LOGGER.warning("NVIDIA Game Master unavailable; using local narration (%s).", self.last_status)
        return None

    @staticmethod
    def _valid_narrative(text: Any, language: str, *, min_chars: int = 160) -> str | None:
        narrative = re.sub(r"\s+", " ", str(text or "")).strip()
        if not min_chars <= len(narrative) <= 5500:
            return None
        arabic_letters = len(_ARABIC_RE.findall(narrative))
        if language == "en" and arabic_letters:
            return None
        if language == "ar" and arabic_letters < 24:
            return None
        return narrative

    def narrate(self, *, action: str, turn: int, language: str, proposal: dict[str, Any], fallback_narrative: str) -> tuple[str, list[str]]:
        """يعيد سردًا محسّنًا أو النص المحلي حرفيًا إذا غاب API أو خالف عقده."""
        if not self.enabled:
            return fallback_narrative, []
        normalized_language = "en" if str(language).lower().startswith("en") else "ar"
        result = self._request(normalized_language, self._canonical_context(action, turn, proposal))
        if not result:
            return fallback_narrative, []
        # لا نقبل ردًا قصيرًا جدًا بعد انتظار لاعب طويل. يظل حد الملخص أقل في مساره الخاص.
        min_scene_chars = 900 if self._context_mode() == "full" else 650
        narrative = self._valid_narrative(
            result.get("narrative"), normalized_language, min_chars=min_scene_chars
        )
        if not narrative:
            self.last_status = "language-or-format-fallback"
            return fallback_narrative, []
        suggestions = [
            re.sub(r"\s+", " ", str(item)).strip()[:160]
            for item in (result.get("suggested_actions") or [])[:3]
            if re.sub(r"\s+", " ", str(item)).strip()
        ]
        return narrative, suggestions

    def recap(self, *, language: str, fallback_recap: str) -> str:
        """يحسن ملخص الحملة فقط عند توافر الخدمة، وإلا يبقي الملخص المحلي."""
        if not self.enabled:
            return fallback_recap
        normalized_language = "en" if str(language).lower().startswith("en") else "ar"
        scenes = get_recent_scenes(limit=8)
        scene_text = "\n".join(
            f"- Turn {turn}: {self._compact(action, 150)} | {self._compact(response, 300)}"
            for turn, action, response in scenes
        ) or "No scenes have been played."
        context = f"""Write a concise campaign recap strictly from the scenes below. Do not add facts.\n\n{scene_text}"""
        prompt = self._system_prompt(normalized_language, self._context_mode(), recap=True)
        if not self.config:
            return fallback_recap
        payload = {
            "model": self.config.model,
            "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": context}],
            "temperature": 0.45,
            "top_p": self.config.top_p,
            "max_tokens": min(self.config.max_tokens, 800),
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": self.config.thinking_enabled},
        }
        try:
            request = Request(
                self.config.endpoint,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
            content = self._message_content(raw)
            # يسمح مسار الملخص بنص عادي أيضًا، ولا يقبل إخراجًا بلغة غير مختارة.
            candidate = self._extract_json(content)
            text = candidate.get("narrative") if candidate else content
            valid = self._valid_narrative(text, normalized_language, min_chars=160)
            if valid:
                self.last_status = "ready"
                return valid
        except Exception:
            self.last_status = "unavailable"
            LOGGER.warning("NVIDIA recap unavailable; using local recap.")
        return fallback_recap
