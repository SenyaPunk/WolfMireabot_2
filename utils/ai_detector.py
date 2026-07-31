"""
Продвинутый модуль детекции ИИ-сгенерированного кода (ChatGPT, Claude, Gemini, DeepSeek).
Использует AST-анализ стиля, PEP8-перфекционизм, наименования переменных, время сдачи и проверку каноничности.
НЕ штрафует за type hints в заголовке функции, так как их выдает сам стартовый шаблон бота.
"""
import ast
import re
from typing import Tuple, Set

# Комментарии и фразы нейросетей
AI_COMMENT_PATTERNS = [
    r"#\s*step\s*\d+",
    r"#\s*шаг\s*\d+",
    r"#\s*initialize",
    r"#\s*инициализаци",
    r"#\s*base\s*case",
    r"#\s*edge\s*case",
    r"#\s*check\s*if",
    r"#\s*loop\s*through",
    r"#\s*time\s*complexity",
    r"#\s*space\s*complexity",
    r"#\s*сложность\s*по\s*времени",
    r"#\s*сложность\s*по\s*памяти",
    r"#\s*returns?:",
    r"#\s*возвращает:",
    r"#\s*helper\s*function",
    r"#\s*вспомогательная\s*функция",
    r"time\s*complexity:\s*o\(",
    r"space\s*complexity:\s*o\(",
    r"#\s*учитываем",
    r"#\s*проверяем",
    r"#\s*создаем"
]

# Формальные академические слова, которые ИИ использует для внутренних переменных
AI_FORMAL_VAR_WORDS = {
    "capacity", "operations", "operation", "result", "results", "current",
    "oldest", "seen_map", "seen_dict", "seen_set", "current_sum", "current_val",
    "current_index", "left_pointer", "right_pointer", "char_count", "char_counts",
    "char_map", "result_list", "result_arr", "accumulated_val", "target_sum",
    "dummy_head", "current_node", "prev_node", "next_node", "freq_map",
    "frequency_dict", "is_valid_flag", "intervals", "interval", "merged",
    "compressed", "transposed", "sub_array", "timestamps", "timestamp"
}

# Короткие человеческие переменные, которые обычно пишет человек в Telegram
HUMAN_SHORT_VARS = {"i", "j", "k", "v", "x", "y", "c", "d", "res", "ans", "lst", "arr", "s", "p", "n", "m", "t", "q"}


def analyze_ai_generated_code(code: str, elapsed_time_sec: float = 999.0) -> Tuple[bool, int, str]:
    """
    Возвращает (is_ai_detected: bool, score: int, reason: str).
    Если score >= 40, код считается сгенерированным ИИ.
    """
    if not code:
        return False, 0, ""

    score = 0
    reasons = []

    lines = [l for l in code.splitlines() if l.strip()]
    line_count = len(lines)

    # 1. Проверка времени отправки (Слишком быстрая сдача)
    if elapsed_time_sec < 45.0 and line_count >= 6:
        score += 35
        reasons.append(f"сверхбыстрая сдача ({int(elapsed_time_sec)} сек от получения задачи)")
    elif elapsed_time_sec < 25.0:
        score += 30
        reasons.append(f"аномальная скорость сдачи ({int(elapsed_time_sec)} сек)")

    # 2. Анализ комментариев и docstrings (AI Fingerprints)
    code_lower = code.lower()
    found_ai_comments = 0
    for pattern in AI_COMMENT_PATTERNS:
        if re.search(pattern, code_lower):
            found_ai_comments += 1

    if found_ai_comments >= 2:
        score += 35
        reasons.append("характерные ИИ-комментарии")
    elif found_ai_comments == 1:
        score += 20
        reasons.append("шаблонный комментарий нейросети")

    # 3. Анализ AST
    try:
        tree = ast.parse(code)
    except Exception:
        return False, 0, ""

    all_vars: Set[str] = set()
    has_docstring = False
    has_internal_type_hints = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Param)):
            all_vars.add(node.id)

        if isinstance(node, ast.FunctionDef):
            docstring = ast.get_docstring(node)
            if docstring and len(docstring) > 15:
                has_docstring = True

        # Проверяем ВСПОМОГАТЕЛЬНЫЕ локальные аннотации внутри тела (AnnAssign e.g. x: int = 5)
        # Игнорируем заголовки функций, так как type hints там даёт сам стартовый шаблон бота
        if isinstance(node, ast.AnnAssign):
            has_internal_type_hints = True

    if has_docstring:
        score += 25
        reasons.append("формальный ИИ-docstring")

    if has_internal_type_hints:
        score += 20
        reasons.append("внутренние аннотации типов переменным")

    # 4. Анализ стиля наименования переменных (ИИ vs Человек)
    if all_vars:
        ai_var_matches = all_vars.intersection(AI_FORMAL_VAR_WORDS)
        human_short_matches = all_vars.intersection(HUMAN_SHORT_VARS)

        if len(ai_var_matches) >= 2 and len(human_short_matches) <= 1:
            score += 30
            reasons.append("академический стиль переменных ИИ (" + ", ".join(list(ai_var_matches)[:3]) + ")")
        elif len(ai_var_matches) >= 1:
            score += 15

    # 5. Оценка PEP8 Перфекционизма
    pep8_perfect_spaces = len(re.findall(r"\b\w+\s+=\s+\w+\b", code)) + len(re.findall(r"\b\w+\s+==\s+\w+\b", code))
    if pep8_perfect_spaces >= 4 and line_count >= 8:
        score += 15
        reasons.append("идеальное ИИ-форматирование PEP8")

    is_ai = (score >= 40)
    reason_str = ", ".join(reasons) if reasons else "высокая вероятность списывания из ChatGPT/Gemini"

    return is_ai, score, reason_str
