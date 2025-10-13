"""Модуль для генерации текста через g4f."""
import logging
from typing import Literal, Optional, Any

logger = logging.getLogger(__name__)


class TextGenerator:

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _extract_text_from_response(self, resp: Any) -> str:
        try:
            if isinstance(resp, str):
                return resp.strip()

            if isinstance(resp, dict):
                choices = resp.get("choices")
                if choices and isinstance(choices, list) and len(choices) > 0:
                    first = choices[0]
                    if isinstance(first, dict):
                        msg = first.get("message")
                        if isinstance(msg, dict) and "content" in msg:
                            return str(msg.get("content") or "").strip()
                        if "text" in first:
                            return str(first.get("text") or "").strip()
                        if "content" in first:
                            return str(first.get("content") or "").strip()

                if "message" in resp and isinstance(resp["message"], dict):
                    content = resp["message"].get("content")
                    if content:
                        return str(content).strip()

                if "text" in resp:
                    return str(resp.get("text") or "").strip()

                return str(resp)

            if isinstance(resp, list):
                parts = []
                for item in resp:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        text = (
                            (item.get("message") or {}).get("content")
                            if isinstance(item.get("message"), dict)
                            else item.get("text") or item.get("content")
                        )
                        if text:
                            parts.append(str(text))
                return " ".join(p.strip() for p in parts if p)

            return str(resp).strip()
        except Exception as e:
            logger.debug("Не удалось извлечь текст из ответа: %s", e, exc_info=True)
            return ""

    def generate_greeting(self, kind: Literal["morning", "evening"]) -> str:
        if kind == "morning":
            user_prompt = (
                "Сгенерируй очень короткое, тёплое пожелание доброго утра "
                "на русском языке для чата Волки вуза МИРЭА (1–2 предложения). "
                "Избегай хэштегов. Разрешено 1 уместный эмодзи. "
                "Стиль — дружелюбный, заботливый, вдохновляющий."
            )
        else:
            user_prompt = (
                "Сгенерируй очень короткое, тёплое пожелание спокойной ночи "
                "на русском языке для чата Волки вуза МИРЭА (1–2 предложения). "
                "Избегай хэштегов. Разрешено 1 уместный эмодзи. "
                "Стиль — уютный, нежный, успокаивающий."
            )

        try:
            logger.info("Начинаем генерацию текста для %s", kind)

            import g4f

            model_to_use = self.model or getattr(g4f.models, "default", None) or "gpt-4o-mini"

            messages = [
                {
                    "role": "system",
                    "content": "Ты — дружелюбный и веселый автор коротких тёплых пожеланий."
                },
                {
                    "role": "user",
                    "content": user_prompt
                },
            ]

            response = g4f.ChatCompletion.create(
                model=model_to_use,
                messages=messages,
                stream=False,
            )

            generated_text = self._extract_text_from_response(response)

            if not generated_text:
                logger.warning("g4f вернул пустой ответ, используем запасной текст.")
                raise ValueError("Пустой ответ от g4f")

            generated_text = " ".join(generated_text.split())
            logger.info("Текст успешно сгенерирован (%d символов): %s",
                        len(generated_text), generated_text[:120])
            return generated_text

        except Exception as e:
            logger.exception("Ошибка генерации текста: %s", e)
            fallback_text = (
                "Доброе утро, Волки МИРЭА! Пусть день будет продуктивным! 🌅"
                if kind == "morning"
                else "Спокойной ночи, Волки МИРЭА! Сладких снов! 🌙"
            )
            logger.warning("Используется запасной текст: %s", fallback_text)
            return fallback_text
