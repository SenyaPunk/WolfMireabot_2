"""
Продвинутый модуль детекции ИИ-сгенерированного кода (ChatGPT, Claude, Gemini, DeepSeek).
Анализирует комментарии-пояснения, академический стиль наименования переменных, PEP8-перфекционизм и сигнатуры.
"""
import ast
import re
from typing import Tuple, Set

# Паттерны любых пояснительных комментариев ИИ (русские и английские фразы)
AI_EXPLANATORY_COMMENT_PATTERNS = [
    r"#\s*(подсчет|расчет|проверка|защита|аналог|округление|возврат|обработка|находим|получаем|преобразуем|преобразование|фильтрация|создаем|инициализация|сортировка|поиск|проверяем|учитываем|добавляем|формируем|вычисляем|считываем|извлекаем)",
    r"#\s*(без|вместо)\s+(импорта|библиотеки|использования|math|sys|os|модуля)",
    r"#\s*(step|step\s*\d+|initialize|base\s*case|edge\s*case|check\s*if|loop\s*through|time\s*complexity|space\s*complexity|helper\s*function|returns?:)",
    r"#\s*[а-яёa-z0-9_]+\s+(для|через|без|из|по|согласно|чтобы|если|встроенн)",
    r"time\s*complexity:\s*o\(",
    r"space\s*complexity:\s*o\("
]

# Короткие человеческие переменные (сокращения), которые обычно использует разработчик при наборе вручную
HUMAN_SHORT_VARS = {"i", "j", "k", "v", "x", "y", "c", "d", "res", "ans", "lst", "arr", "s", "p", "st", "cnt", "lat", "lats", "n", "m", "t", "q", "elem"}


def analyze_ai_generated_code(code: str, elapsed_time_sec: float = 999.0) -> Tuple[bool, int, str]:
    """
    Возвращает (is_ai_detected: bool, score: int, reason: str).
    Если score >= 40, код считается сгенерированным ИИ.
    """
    if not code:
        return False, 0, ""

    score = 0
    reasons = []

    lines = [l.strip() for l in code.splitlines() if l.strip()]
    line_count = len(lines)

    # 1. Анализ комментариев (Пояснительные комментарии ИИ)
    comment_lines = [l for l in lines if l.startswith("#")]
    comment_count = len(comment_lines)
    
    code_lower = code.lower()
    found_explanatory_comments = 0
    for pattern in AI_EXPLANATORY_COMMENT_PATTERNS:
        if re.search(pattern, code_lower):
            found_explanatory_comments += 1

    if found_explanatory_comments >= 1:
        score += 45
        reasons.append("пояснительные комментарии ИИ к строкам кода")
    elif comment_count >= 2:
        score += 35
        reasons.append("наличие нескольких строк комментариев")

    # 2. Проверка времени отправки
    if elapsed_time_sec < 45.0 and line_count >= 6:
        score += 35
        reasons.append(f"сверхбыстрая сдача ({int(elapsed_time_sec)} сек от получения задачи)")
    elif elapsed_time_sec < 25.0:
        score += 30
        reasons.append(f"аномальная скорость сдачи ({int(elapsed_time_sec)} сек)")

    # 3. Анализ AST-дерева и переменных
    try:
        tree = ast.parse(code)
    except Exception:
        return False, 0, ""

    all_vars: Set[str] = set()
    has_docstring = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Param)):
            # Игнорируем стандартные имена функций
            if node.id not in {"parse_nginx_logs", "two_sum", "is_valid_parentheses", "max_subarray_sum", "merge_intervals", "compress_string", "transpose_matrix", "simulate_lru_cache", "check_rate_limit", "filter_gps_track", "clsx"}:
                all_vars.add(node.id)

        if isinstance(node, ast.FunctionDef):
            docstring = ast.get_docstring(node)
            if docstring and len(docstring) > 15:
                has_docstring = True

    if has_docstring:
        score += 25
        reasons.append("формальный ИИ-docstring")

    # 4. Анализ длин и академичности имен переменных
    if all_vars:
        avg_var_len = sum(len(v) for v in all_vars) / len(all_vars)
        human_short_matches = all_vars.intersection(HUMAN_SHORT_VARS)
        snake_case_vars = [v for v in all_vars if "_" in v]

        # Если средняя длина переменных > 7.5 символов и нет коротких человеческих сокращений
        if (avg_var_len >= 7.5 or len(snake_case_vars) >= 2) and len(human_short_matches) == 0:
            score += 35
            reasons.append("академический стиль полного наименования переменных нейросети")
        elif avg_var_len >= 6.5 and len(human_short_matches) == 0:
            score += 20
            reasons.append("отсутствие индивидуальных сокращений в переменных")

    # 5. Оценка PEP8 Перфекционизма
    pep8_perfect_spaces = len(re.findall(r"\b\w+\s+=\s+\w+\b", code)) + len(re.findall(r"\b\w+\s+==\s+\w+\b", code))
    if pep8_perfect_spaces >= 3 and line_count >= 6:
        score += 15
        reasons.append("идеальное ИИ-форматирование PEP8")

    is_ai = (score >= 40)
    reason_str = ", ".join(reasons) if reasons else "высокая вероятность списывания из ChatGPT/Gemini"

    return is_ai, score, reason_str
