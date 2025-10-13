"""Модуль для генерации текста"""
import logging
import os
from typing import Literal, Optional, Any

logger = logging.getLogger(__name__)


class TextGenerator:
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or "gemini-2.5-pro"
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self._genai = None
        self._configured = False

        if self.api_key:
            try:
                import google.generativeai as genai  # type: ignore
                genai.configure(api_key=self.api_key)
                self._genai = genai
                self._configured = True
                logger.info("google.generativeai настроен для модели %s", self.model)
            except Exception as e:
                logger.exception("Не удалось подключить google.generativeai: %s", e)
                self._genai = None
        else:
            logger.warning(
                "API-ключ для google.generativeai не указан. Установка через GOOGLE_API_KEY или передачей в конструктор обязательна."
            )

    def _extract_text_from_response(self, resp: Any) -> str:
        try:
            if resp is None:
                return ""

            if isinstance(resp, str):
                return resp.strip()

            if hasattr(resp, "text") and isinstance(getattr(resp, "text"), str):
                return getattr(resp, "text").strip()

            if hasattr(resp, "content") and isinstance(getattr(resp, "content"), str):
                return getattr(resp, "content").strip()

            if hasattr(resp, "candidates"):
                candidates = getattr(resp, "candidates")
                if isinstance(candidates, (list, tuple)) and len(candidates) > 0:
                    first = candidates[0]
                    if isinstance(first, dict):
                        for k in ("content", "output", "text"):
                            if k in first and first[k]:
                                return str(first[k]).strip()
                    else:
                        for k in ("content", "output", "text"):
                            if hasattr(first, k):
                                val = getattr(first, k)
                                if isinstance(val, str):
                                    return val.strip()

            if isinstance(resp, dict):
                # g4f-style: choices -> message -> content
                choices = resp.get("choices")
                if choices and isinstance(choices, list) and len(choices) > 0:
                    first = choices[0]
                    if isinstance(first, dict):
                        # try message.content
                        msg = first.get("message")
                        if isinstance(msg, dict) and "content" in msg and msg.get("content"):
                            return str(msg.get("content")).strip()
                        # try text/content in choice
                        for k in ("text", "content"):
                            if k in first and first.get(k):
                                return str(first.get(k)).strip()

                candidates = resp.get("candidates")
                if candidates and isinstance(candidates, list) and len(candidates) > 0:
                    first = candidates[0]
                    if isinstance(first, dict):
                        for k in ("content", "output", "text"):
                            if k in first and first.get(k):
                                return str(first.get(k)).strip()

                if "message" in resp and isinstance(resp["message"], dict):
                    content = resp["message"].get("content")
                    if content:
                        return str(content).strip()

                if "text" in resp and resp.get("text"):
                    return str(resp.get("text")).strip()

                if "content" in resp and resp.get("content"):
                    return str(resp.get("content")).strip()

                return str(resp)

            if isinstance(resp, (list, tuple)):
                parts = []
                for item in resp:
                    txt = self._extract_text_from_response(item)
                    if txt:
                        parts.append(txt)
                return " ".join(parts).strip()

            return str(resp).strip()
        except Exception as e:
            logger.debug("Не удалось извлечь текст из ответа: %s", e, exc_info=True)
            return ""

    def generate_greeting(self, kind: Literal["morning", "evening"]) -> str:
        if kind == "morning":
            user_prompt = (
                "Сгенерируй очень короткое и смешное пожелание доброго утра "
                "на русском языке для чата Волки МИРЭА (1–2 предложения). "
                "Используй маты, черный юмор и смешной зумерский стиль. "
                "Важно: оставь только одно сообщение с пожеланием, не добавляй комментариев и тд. Лишь один текст сообщения! "
                "Стиль — дружелюбный, смешной, вдохновляющий, энергичный."
            )
        else:
            user_prompt = (
                "Сгенерируй очень короткое и смешное пожелание спокойной ночи "
                "на русском языке для чата Волки вуза МИРЭА (1–2 предложения). "
                "Используй маты, черный юмор и смешной зумерский стиль. "
                "Важно: оставь только одно сообщение с пожеланием, не добавляй комментариев и тд. Лишь один текст сообщения! "
                "Стиль — уютный, нежный, смешной, расслабляющий."
            )

        try:
            logger.info("Начинаем генерацию текста для %s", kind)

            if not self._configured or not self._genai:
                raise RuntimeError("google.generativeai не настроен (ключ отсутствует или импорт не удался)")

            genai = self._genai

            response = None
            try:
                if hasattr(genai, "GenerativeModel"):
                    model_obj = genai.GenerativeModel(self.model)
                    response = model_obj.generate_content(user_prompt)
                else:
                    if hasattr(genai, "models") and hasattr(genai.models, "generate"):
                        response = genai.models.generate(model=self.model, prompt=user_prompt)
                    else:
                        raise RuntimeError("Неподдерживаемая версия google.generativeai: отсутствуют ожидаемые методы")
            except Exception as e:
                logger.debug("Первый метод вызова Gemini не сработал: %s", e, exc_info=True)
                try:
                    response = genai.models.generate(model=self.model, prompt=user_prompt)
                except Exception as e2:
                    logger.exception("Ошибка при попытке вызвать genai.models.generate: %s", e2)
                    raise

            generated_text = self._extract_text_from_response(response)

            if not generated_text:
                logger.warning("Gemini вернул пустой ответ, используем запасной текст.")
                raise ValueError("Пустой ответ от Gemini")

            generated_text = " ".join(generated_text.split())
            logger.info("Текст успешно сгенерирован (%d символов): %s",
                        len(generated_text), generated_text[:120])
            return generated_text

        except Exception as e:
            logger.exception("Ошибка генерации текста через Gemini: %s", e)
            fallback_text = (
                "Доброе утро, Волки МИРЭА! Пусть день будет продуктивным! 🌅"
                if kind == "morning"
                else "Спокойной ночи, Волки МИРЭА! Сладких снов! 🌙"
            )
            logger.warning("Используется запасной текст: %s", fallback_text)
            return fallback_text
