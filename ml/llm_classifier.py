"""
LLM-based classifier using local Ollama.
Falls back to keyword classifier if Ollama is unavailable.
"""
import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

_PROMPT = """\
Ты аналитик финансовой разведки Казахстана (АФМ РК).
Проанализируй текст объявления или сообщения и определи наличие признаков незаконной деятельности.

Категории:
- наркотики: продажа/доставка наркотических веществ, закладки
- крипто_отмывание: обнал, p2p без KYC, миксеры, крипта за нал
- финансовое_мошенничество: фишинг, кардинг, пробив баз, поддельные документы
- дропперство: прием переводов за %, работа дропом, карта для перевода
- оружие: продажа оружия без документов
- нелицензионная_торговля: оптовая продажа алкоголя/вейпов без документов, анонимная доставка
- легальный: обычная законная торговля

Отвечай СТРОГО в формате JSON, без пояснений вне JSON:
{{"category": "...", "risk": "critical|high|medium|low", "is_illegal": true|false, "confidence": 0.0-1.0, "reasoning": "кратко на русском"}}

Текст:
{text}"""


class LLMClassifier:
    _instance: "LLMClassifier | None" = None

    @classmethod
    def get(cls) -> "LLMClassifier":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_available(self) -> bool:
        try:
            r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def classify(self, text: str) -> dict:
        text_trunc = text[:1200]
        prompt = _PROMPT.format(text=text_trunc)
        try:
            with httpx.Client(timeout=45) as client:
                resp = client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.1, "num_predict": 200},
                    },
                )
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama HTTP {resp.status_code}")

            raw = resp.json().get("response", "{}")
            parsed = json.loads(raw)

            return {
                "category":       parsed.get("category", "легальный"),
                "risk":           parsed.get("risk", "low"),
                "is_illegal_sale": bool(parsed.get("is_illegal", False)),
                "confidence":     float(parsed.get("confidence", 0.0)),
                "matches":        1 if parsed.get("is_illegal") else 0,
                "reasoning":      parsed.get("reasoning", ""),
            }

        except Exception as e:
            logger.debug(f"LLM classify failed ({e}), using keyword fallback")
            return _keyword_fallback(text)


def _keyword_fallback(text: str) -> dict:
    from ml.classifier import Classifier
    return Classifier.get().classify(text)


def get_classifier() -> LLMClassifier:
    return LLMClassifier.get()
