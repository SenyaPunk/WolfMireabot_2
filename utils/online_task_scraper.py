"""
Настоящий живой веб-парсер задач с LeetCode API.
- Категория влияет на выбор задач (Frontend — строки/структуры, Backend — алгоритмы/графы, и т.д.)
- Полный перевод текста (не обрезается по 450 символам)
- Корректное HTML-форматирование для Telegram parse_mode=HTML
"""
import os
import json
import re
import html
import random
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join("data", "scraped_tasks_cache.json")
HISTORY_FILE = os.path.join("data", "user_task_history.json")


# Задачи привязаны к категориям — чтобы Frontend давал задачи на строки/массивы/структуры,
# Backend — на графы/DP/алгоритмы, DevOps — на числа/массивы, Mobile — на рекурсию/деревья
CATEGORY_SLUGS: Dict[str, List[str]] = {
    "Backend": [
        "two-sum", "3sum", "group-anagrams", "coin-change", "word-search",
        "number-of-islands", "course-schedule", "lru-cache", "search-in-rotated-sorted-array",
        "longest-increasing-subsequence", "combination-sum",
    ],
    "Frontend": [
        "valid-parentheses", "valid-palindrome", "valid-anagram", "remove-nth-node-from-end-of-list",
        "reverse-linked-list", "linked-list-cycle", "implement-trie-prefix-tree",
        "maximum-subarray", "container-with-most-water",
    ],
    "Mobile": [
        "invert-binary-tree", "binary-search", "climbing-stairs", "permutations",
        "rotate-image", "merge-two-sorted-lists", "remove-nth-node-from-end-of-list",
    ],
    "DevOps": [
        "two-sum", "binary-search", "climbing-stairs", "coin-change",
        "maximum-subarray", "valid-anagram", "reverse-linked-list",
    ],
    "Алгосы": [
        "two-sum", "valid-parentheses", "merge-two-sorted-lists",
        "maximum-subarray", "climbing-stairs", "binary-search", "3sum",
        "group-anagrams", "coin-change", "longest-increasing-subsequence",
        "lru-cache", "number-of-islands", "reverse-linked-list",
        "course-schedule", "implement-trie-prefix-tree",
        "container-with-most-water", "search-in-rotated-sorted-array",
        "combination-sum", "permutations", "rotate-image",
        "word-search", "best-time-to-buy-and-sell-stock",
        "valid-palindrome", "valid-anagram", "linked-list-cycle",
    ],
}

RUSSIAN_TITLE_MAP = {
    "Two Sum": "Два числа с заданной суммой",
    "Valid Parentheses": "Проверка правильности скобочной последовательности",
    "Merge Two Sorted Lists": "Слияние двух отсортированных списков",
    "Best Time to Buy and Sell Stock": "Максимальная прибыль от покупки акций",
    "Valid Palindrome": "Проверка строки на палиндром",
    "Invert Binary Tree": "Инвертирование бинарного дерева",
    "Valid Anagram": "Проверка анаграммы в строках",
    "Binary Search": "Бинарный поиск в отсортированном массиве",
    "Linked List Cycle": "Обнаружение цикла в связном списке",
    "Maximum Subarray": "Максимальная сумма подмассива (алгоритм Кадане)",
    "Climbing Stairs": "Количество способов подняться по ступеням",
    "Coin Change": "Минимальное количество монет для сдачи",
    "Longest Increasing Subsequence": "Наибольшая возрастающая подпоследовательность",
    "LRU Cache": "Проектирование LRU-кэша",
    "Number of Islands": "Подсчет связных островов на сетке",
    "Reverse Linked List": "Разворот односвязного списка",
    "Course Schedule": "Планирование порядка прохождения курсов",
    "Implement Trie (Prefix Tree)": "Реализация префиксного дерева (Trie)",
    "Container With Most Water": "Максимальный объем воды между контейнерами",
    "3Sum": "Три числа с нулевой суммой",
    "Remove Nth Node From End of List": "Удаление N-го узла с конца списка",
    "Search in Rotated Sorted Array": "Поиск в повернутом отсортированном массиве",
    "Combination Sum": "Поиск комбинаций с заданной суммой",
    "Permutations": "Генерация всех перестановок массива",
    "Rotate Image": "Поворот матрицы на 90 градусов",
    "Group Anagrams": "Группировка анаграмм в списке строк",
    "Word Search": "Поиск слова в двухмерной сетке символов",
}

COMPANY_BRANDING = {
    "Backend": [
        ("Яндекс Поиск Backend", "Микросервисная архитектура поиска Яндекс"),
        ("Avito Backend", "Платформа объявлений Авито Core"),
        ("Т-Банк Эквайринг", "Сервис процессинга безналичных платежей"),
        ("VK Cloud", "Облачная платформа ВКонтакте Infrastructure"),
        ("Ozon Logistics", "Система автоматизации логистических хабов Ozon"),
        ("СберМаркет Core", "Ядро процессинга заказов СберМаркет"),
    ],
    "Frontend": [
        ("VKontakte Web", "Фронтенд-платформа соцсети ВКонтакте"),
        ("Яндекс Маркет Frontend", "Интерфейс витрины товаров Яндекс Маркета"),
        ("Ozon Web Platform", "Кабинет продавца Ozon Seller UI"),
        ("Т-Банк Инвестиции Web", "Торговый терминал Т-Инвестиции"),
        ("Avito Frontend Engine", "Движок подачи объявлений Авито"),
    ],
    "Mobile": [
        ("Яндекс Еда Mobile", "Мобильное приложение курьеров Яндекс Еда"),
        ("Т-Банк Android Team", "Мобильный клиент Т-Банк Android"),
        ("Avito iOS Team", "Клиент Авито для iOS"),
        ("VK Video Mobile", "Мобильный видеоплеер VK Видео"),
        ("Ozon Express App", "Приложение экспресс-доставки Ozon"),
    ],
    "DevOps": [
        ("Yandex Cloud Infrastructure", "Облачная инфраструктура Yandex Cloud"),
        ("SberTech DevOps", "CI/CD пайплайны СберТех"),
        ("VK Cloud Platform", "Кластер Kubernetes VK"),
        ("Kaspersky Security Cloud", "Центр защиты Kaspersky"),
        ("Ozon Infra Team", "Сервис мониторинга Prometheus & Grafana"),
    ],
    "Алгосы": [
        ("LeetCode Global Engine", "Академическое алгоритмическое соревнование"),
        ("Codeforces Battle", "Олимпиадное соревнование по алгоритмам"),
        ("Алгоритмическая Арена", "Баттл по алгоритмам и структурам данных"),
    ],
}


def _mymemory_translate(chunk: str) -> str:
    """Переводит блок текста через MyMemory API. Возвращает оригинал при сбое."""
    try:
        url = "https://api.mymemory.translated.net/get?q=" + urllib.parse.quote(chunk) + "&langpair=en|ru"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result = data.get("responseData", {}).get("translatedText", "")
            if result and "MYMEMORY WARNING" not in result and len(result) > 5:
                return result
    except Exception as e:
        logger.debug(f"MyMemory API error: {e}")
    return chunk


def translate_text_to_russian(raw_text: str) -> str:
    """
    Полный перевод текста задачи на русский язык:
    - Сначала экранируем HTML-символы
    - Переводим текст по абзацам (не обрезая)
    - Применяем структурные подстановки
    - Возвращаем чистый Telegram HTML
    """
    if not raw_text:
        return ""

    # --- Шаг 1: Очистка текста ---
    text = raw_text.strip()

    # --- Шаг 2: Структурные маркеры — сначала найти позиции, перевести части ---
    # Разбиваем на смысловые блоки по маркерам LeetCode
    BLOCK_MARKERS = re.compile(
        r"(Example\s+\d+:|Input:|Output:|Explanation:|Constraints:|Note:)",
        re.IGNORECASE
    )

    # Переводим весь текст по абзацам (чанками до 400 символов)
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    translated_paragraphs = []
    buffer = ""
    buffer_pars = []

    for par in paragraphs:
        if len(buffer) + len(par) < 380:
            buffer += (" " if buffer else "") + par
            buffer_pars.append(par)
        else:
            if buffer:
                translated_paragraphs.append(_mymemory_translate(buffer))
            buffer = par
            buffer_pars = [par]

    if buffer:
        translated_paragraphs.append(_mymemory_translate(buffer))

    translated = "\n".join(translated_paragraphs)

    # --- Шаг 3: Исправление машинных ошибок перевода ---
    fixups = [
        (r"\bкронштейны\b", "скобки"), (r"\bкронштейн\b", "скобка"),
        (r"\bкронштейнов\b", "скобок"), (r"\bкронштейнами\b", "скобками"),
        (r"\bдостаточно\s+скобки\b", "правильная скобочная последовательность"),
        (r"s consists of parentheses only ['\"]?\(\)\[\]\{\}['\"]?", "строка s содержит только символы '()[]{}'"),
        (r"parentheses only", "только скобки"),
        (r"Note that buying on day \d+ and selling on day \d+ is not allowed because you must buy before you sell\.",
         "Покупка в более поздний день, чем продажа, не допускается."),
        (r"In this case, no transactions are done and the max profit = 0\.",
         "В данном случае сделки совершить невозможно, поэтому максимальная прибыль равна 0."),
    ]
    for pat, repl in fixups:
        translated = re.sub(pat, repl, translated, flags=re.IGNORECASE)

    # --- Шаг 4: Экранируем HTML-символы для Telegram ---
    safe = html.escape(translated)

    # --- Шаг 5: Применяем красивые Telegram HTML-теги ---
    fmt_replacements = [
        (r"Example (\d+):", r"\n🔹 <b>Пример \1:</b>"),
        (r"Input:", r"\n• <b>Входные данные:</b>"),
        (r"Output:", r"\n• <b>Выходные данные:</b>"),
        (r"Explanation:", r"\n💡 <b>Пояснение:</b>"),
        (r"Constraints:", r"\n\n⚙️ <b>Ограничения:</b>"),
        (r"Note:", r"\n📌 <b>Примечание:</b>"),
        # Русские варианты после перевода
        (r"Пример (\d+):", r"\n🔹 <b>Пример \1:</b>"),
        (r"Входные данные:", r"\n• <b>Входные данные:</b>"),
        (r"Выходные данные:", r"\n• <b>Выходные данные:</b>"),
        (r"Пояснение:", r"\n💡 <b>Пояснение:</b>"),
        (r"Ограничения:", r"\n\n⚙️ <b>Ограничения:</b>"),
        (r"Примечание:", r"\n📌 <b>Примечание:</b>"),
    ]
    for pat, repl in fmt_replacements:
        safe = re.sub(pat, repl, safe, flags=re.IGNORECASE)

    # --- Шаг 6: Убираем дублирующиеся пустые строки ---
    safe = re.sub(r"\n{3,}", "\n\n", safe).strip()

    return safe


def extract_leetcode_function(py_snippet: str) -> Tuple[Optional[str], Optional[str]]:
    """Извлекает точку входа и чистый шаблон функции из Python3-сниппета LeetCode."""
    if not py_snippet:
        return None, None
    m = re.search(
        r"def\s+([a-zA-Z0-9_]+)\s*\(\s*self\s*,?\s*(.*?)\)\s*(?:->\s*([^:]+))?:",
        py_snippet, re.DOTALL
    )
    if m:
        fn = m.group(1)
        args = m.group(2).strip()
        ret = (m.group(3) or "").strip()
        ret_str = f" -> {ret}" if ret else ""
        code = f"def {fn}({args}){ret_str}:\n    # Напишите решение здесь\n    pass"
        return fn, code
    return None, None


class RealOnlineTaskParser:
    """Живой парсер задач с LeetCode GraphQL API с кэшированием."""

    def __init__(self):
        self.leetcode_cache: Dict[str, Dict[str, Any]] = {}
        self._load_cache()

    def _load_cache(self):
        if not os.path.exists(CACHE_FILE):
            return
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                lc = data.get("leetcode", {})
                self.leetcode_cache = lc if isinstance(lc, dict) else {}
        except Exception as e:
            logger.error(f"Cache load error: {e}")

    def _save_cache(self):
        try:
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"leetcode": self.leetcode_cache}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Cache save error: {e}")

    def fetch(self, slug: str) -> Optional[Dict[str, Any]]:
        if slug in self.leetcode_cache:
            return self.leetcode_cache[slug]

        url = "https://leetcode.com/graphql"
        gql = {
            "query": """
            query questionData($titleSlug: String!) {
              question(titleSlug: $titleSlug) {
                questionId title titleSlug content difficulty
                topicTags { name }
                codeSnippets { langSlug code }
              }
            }""",
            "variables": {"titleSlug": slug},
        }
        req = urllib.request.Request(
            url, data=json.dumps(gql).encode("utf-8"),
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                q = json.loads(resp.read().decode("utf-8")).get("data", {}).get("question", {})
                if not q or not q.get("title"):
                    return None
                raw_desc = re.sub(r"<[^>]+>", "", q.get("content", "")).strip()
                raw_desc = html.unescape(raw_desc)
                raw_desc = re.sub(r"\n{3,}", "\n\n", raw_desc)

                py_code = next(
                    (s["code"] for s in (q.get("codeSnippets") or [])
                     if isinstance(s, dict) and s.get("langSlug") == "python3"), ""
                )
                result = {
                    "id": f"lc_{q['questionId']}",
                    "title": q["title"],
                    "slug": slug,
                    "difficulty": q.get("difficulty", "MEDIUM"),
                    "tags": [t["name"] for t in (q.get("topicTags") or []) if isinstance(t, dict)],
                    "raw_description": raw_desc[:1200],
                    "raw_py_code": py_code,
                }
                self.leetcode_cache[slug] = result
                self._save_cache()
                return result
        except Exception as e:
            logger.warning(f"LeetCode fetch error [{slug}]: {e}")
            return None


real_parser_instance = RealOnlineTaskParser()


def get_user_history(user_id: int) -> List[str]:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get(str(user_id), [])
    except Exception:
        return []


def mark_user_task(user_id: int, task_id: str):
    data = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    key = str(user_id)
    data.setdefault(key, [])
    if task_id not in data[key]:
        data[key].append(task_id)
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"History save error: {e}")


def parse_and_adapt_online_task(category: str, user_id: int) -> Dict[str, Any]:
    """
    Живой парсинг задач с LeetCode с учётом категории, переводом на русский язык
    и корректным Telegram HTML-форматированием.
    """
    used = set(get_user_history(user_id))
    slug_pool = CATEGORY_SLUGS.get(category, CATEGORY_SLUGS["Алгосы"])
    available = [s for s in slug_pool if f"lc_{s}" not in used]
    if not available:
        available = slug_pool

    parsed_problem = None
    slugs_shuffled = list(available)
    random.shuffle(slugs_shuffled)
    for slug in slugs_shuffled[:3]:  # Попробуем до 3 слагов
        parsed_problem = real_parser_instance.fetch(slug)
        if parsed_problem:
            break

    # Фоллбэк из кэша
    if not parsed_problem and real_parser_instance.leetcode_cache:
        parsed_problem = random.choice(list(real_parser_instance.leetcode_cache.values()))

    from utils.it_tasks_db import IT_TASKS_DB, generate_task_test_cases
    fallback = random.choice(
        [t for t in IT_TASKS_DB if t.get("category") == category] or IT_TASKS_DB
    )

    # Извлекаем функцию
    extracted_fn, extracted_code = extract_leetcode_function(
        parsed_problem.get("raw_py_code", "") if parsed_problem else ""
    )
    if extracted_fn and extracted_code:
        entry_point = extracted_fn
        starter_code = extracted_code
        base_id = entry_point
    else:
        entry_point = fallback["entry_point"]
        starter_code = fallback["starter_code"]
        base_id = fallback["id"]

    dynamic_tests = generate_task_test_cases(entry_point, base_id)

    if parsed_problem:
        task_id = f"parsed_{parsed_problem['id']}"
        ru_title = RUSSIAN_TITLE_MAP.get(parsed_problem["title"], parsed_problem["title"])
        tags_str = ", ".join(parsed_problem["tags"]) if parsed_problem["tags"] else "Алгоритмы"
        ru_desc = translate_text_to_russian(parsed_problem["raw_description"])
        mark_user_task(user_id, parsed_problem["id"])
    else:
        task_id = f"parsed_{base_id}_{random.randint(1000, 9999)}"
        ru_title = fallback["title"]
        tags_str = category
        ru_desc = translate_text_to_russian(fallback["description"])
        starter_code = fallback["starter_code"]
        entry_point = fallback["entry_point"]
        mark_user_task(user_id, task_id)

    branding_list = COMPANY_BRANDING.get(category, COMPANY_BRANDING["Backend"])
    company_info = random.choice(branding_list)
    company_name = company_info[0]
    reward = 120 if category == "Алгосы" else random.randint(210, 340)

    description = (
        f"🏢 <b>Компания:</b> {html.escape(company_name)}\n"
        f"<i>{html.escape(company_info[1])}</i>\n\n"
        f"📝 <b>Условие задачи:</b>\n"
        f"{ru_desc}\n\n"
        f"💡 <b>Требование:</b> Реализуйте функцию <code>{entry_point}</code> согласно условию выше."
    )

    return {
        "id": task_id,
        "base_task_id": base_id,
        "company": company_name,
        "title": f"{ru_title} [{tags_str}]",
        "category": category,
        "difficulty": parsed_problem.get("difficulty", "MEDIUM") if parsed_problem else "MEDIUM",
        "language": "Python 3.11",
        "reward": reward,
        "description": description,
        "starter_code": starter_code,
        "entry_point": entry_point,
        "test_cases": dynamic_tests,
        "dynamic_tests": dynamic_tests,
    }
