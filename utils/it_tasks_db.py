"""
Расширенная база данных IT-задач с поддержкой динамической генерации 6-10 уникальных тестов для защиты от хардкода.
Включает новую категорию "Алгосы" (алгоритмы и структуры данных) с наградной от 80 до 160 монет.
"""
import random
from typing import Dict, Any, List, Optional

IT_TASKS_DB: List[Dict[str, Any]] = [
    # =========================================================================
    # ⚡ АЛГОСЫ (Алгоритмы и структуры данных) - Награда: 80 - 160 монет
    # =========================================================================
    {
        "id": "algo_two_sum",
        "company": "Алгоритмический баттл",
        "title": "Два числа с заданной суммой (Two Sum)",
        "category": "Алгосы",
        "difficulty": "EASY",
        "language": "Python 3.11",
        "reward": 110,
        "description": (
            "Напишите функцию <code>two_sum(nums, target)</code>, которая принимает список целых чисел <code>nums</code> "
            "и целое число <code>target</code>.\n"
            "Функция должна вернуть **список индексов** двух чисел из <code>nums</code>, сумма которых равна <code>target</code>.\n\n"
            "Если пары нет, верните пустой список <code>[]</code>.\n"
            "Пример: <code>two_sum([2, 7, 11, 15], 9) ➔ [0, 1]</code>"
        ),
        "starter_code": (
            "def two_sum(nums: list[int], target: int) -> list[int]:\n"
            "    # Напишите решение здесь\n"
            "    pass"
        ),
        "entry_point": "two_sum",
        "test_cases": [
            {"input": [[2, 7, 11, 15], 9], "expected": [0, 1], "description": "Базовый тест 2+7=9"},
            {"input": [[3, 2, 4], 6], "expected": [1, 2], "description": "Тест 2+4=6"}
        ]
    },
    {
        "id": "algo_valid_parentheses",
        "company": "Алгоритмический баттл",
        "title": "Проверка правильности скобочной последовательности",
        "category": "Алгосы",
        "difficulty": "EASY",
        "language": "Python 3.11",
        "reward": 100,
        "description": (
            "Напишите функцию <code>is_valid_parentheses(s)</code>, проверяющую, является ли скобочная строка <code>s</code> "
            "валидной. Строка состоит из символов <code>'('</code>, <code>')'</code>, <code>'{'</code>, <code>'}'</code>, <code>'['</code>, <code>']'</code>.\n\n"
            "Правила:\n"
            "1. Открытые скобки закрываются скобками того же типа.\n"
            "2. Скобки закрываются в правильном порядке.\n"
            "3. Каждая закрывающая скобка имеет парную открывающую.\n"
            "Верните <code>True</code> или <code>False</code>."
        ),
        "starter_code": (
            "def is_valid_parentheses(s: str) -> bool:\n"
            "    # Напишите решение со стеком здесь\n"
            "    pass"
        ),
        "entry_point": "is_valid_parentheses",
        "test_cases": [
            {"input": ["()[]{}"], "expected": True, "description": "Валидные скобки"},
            {"input": ["(]"], "expected": False, "description": "Неверный тип"}
        ]
    },
    {
        "id": "algo_sliding_window_max",
        "company": "Алгоритмический баттл",
        "title": "Максимальная сумма подмассива длины K",
        "category": "Алгосы",
        "difficulty": "EASY-MEDIUM",
        "language": "Python 3.11",
        "reward": 130,
        "description": (
            "Напишите функцию <code>max_subarray_sum(nums, k)</code>, использующую метод скользящего окна (Sliding Window).\n"
            "Функция принимает список чисел <code>nums</code> и размер окна <code>k</code>.\n"
            "Нужно вернуть **максимальную сумму** непрерывного подмассива длины <code>k</code>.\n"
            "Если <code>nums</code> пуст или <code>k &gt; len(nums)</code> или <code>k &lt;= 0</code>, верните <code>0</code>."
        ),
        "starter_code": (
            "def max_subarray_sum(nums: list[int], k: int) -> int:\n"
            "    # Напишите решение методом скользящего окна здесь\n"
            "    pass"
        ),
        "entry_point": "max_subarray_sum",
        "test_cases": [
            {"input": [[2, 1, 5, 1, 3, 2], 3], "expected": 9, "description": "Подмассив [5,1,3] дает сумму 9"},
            {"input": [[2, 3, 4, 1, 5], 2], "expected": 7, "description": "Подмассив [3,4] дает сумму 7"}
        ]
    },
    {
        "id": "algo_merge_intervals",
        "company": "Алгоритмический баттл",
        "title": "Объединение пересекающихся интервалов",
        "category": "Алгосы",
        "difficulty": "MEDIUM",
        "language": "Python 3.11",
        "reward": 150,
        "description": (
            "Напишите функцию <code>merge_intervals(intervals)</code>, где <code>intervals</code> — список интервалов "
            "<code>[[start, end], ...]</code>.\n"
            "Объедините все пересекающиеся или соприкасающиеся интервалы и верните список отсортированных объединенных интервалов.\n\n"
            "Пример: <code>[[1, 3], [2, 6], [8, 10], [15, 18]] ➔ [[1, 6], [8, 10], [15, 18]]</code>"
        ),
        "starter_code": (
            "def merge_intervals(intervals: list[list[int]]) -> list[list[int]]:\n"
            "    # Напишите сортировку и объединение здесь\n"
            "    pass"
        ),
        "entry_point": "merge_intervals",
        "test_cases": [
            {"input": [[[1, 3], [2, 6], [8, 10], [15, 18]]], "expected": [[1, 6], [8, 10], [15, 18]], "description": "Пересекающиеся интервалы"},
            {"input": [[[1, 4], [4, 5]]], "expected": [[1, 5]], "description": "Соприкасающиеся интервалы"}
        ]
    },
    {
        "id": "algo_compress_string",
        "company": "Алгоритмический баттл",
        "title": "Сжатие строки (Run-Length Encoding)",
        "category": "Алгосы",
        "difficulty": "EASY",
        "language": "Python 3.11",
        "reward": 95,
        "description": (
            "Напишите функцию <code>compress_string(s)</code>, выполняющую простую архивацию RLE.\n"
            "Заменяет повторяющиеся подряд символы на символ и количество их повторений (например, <code>'aabcccccaaa' ➔ 'a2b1c5a3'</code>).\n"
            "Если сжатая строка **не короче** исходной, верните исходную строку."
        ),
        "starter_code": (
            "def compress_string(s: str) -> str:\n"
            "    # Напишите алгоритм сжатия RLE здесь\n"
            "    pass"
        ),
        "entry_point": "compress_string",
        "test_cases": [
            {"input": ["aabcccccaaa"], "expected": "a2b1c5a3", "description": "Сжатие строки"},
            {"input": ["abcd"], "expected": "abcd", "description": "Строка не становится короче"}
        ]
    },
    {
        "id": "algo_matrix_transpose",
        "company": "Алгоритмический баттл",
        "title": "Транспонирование матрицы",
        "category": "Алгосы",
        "difficulty": "EASY",
        "language": "Python 3.11",
        "reward": 90,
        "description": (
            "Напишите функцию <code>transpose_matrix(matrix)</code>, поворачивающую двухмерную матрицу относительно главной диагонали.\n"
            "Строки становятся столбцами, а столбцы — строками.\n"
            "Если матрица пуста, верните <code>[]</code>."
        ),
        "starter_code": (
            "def transpose_matrix(matrix: list[list[int]]) -> list[list[int]]:\n"
            "    # Напишите транспонирование здесь\n"
            "    pass"
        ),
        "entry_point": "transpose_matrix",
        "test_cases": [
            {"input": [[[1, 2, 3], [4, 5, 6]]], "expected": [[1, 4], [2, 5], [3, 6]], "description": "Матрица 2х3 в 3х2"},
            {"input": [[]], "expected": [], "description": "Пустая матрица"}
        ]
    },

    # =========================================================================
    # ⚙️ BACKEND (Reward: 220 - 360)
    # =========================================================================
    {
        "id": "backend_lru_cache",
        "company": "Яндекс Поиск",
        "title": "Симулятор LRU Кэша",
        "category": "Backend",
        "difficulty": "MEDIUM",
        "language": "Python 3.11",
        "reward": 290,
        "description": (
            "Напишите функцию <code>simulate_lru_cache(capacity, operations)</code>.\n"
            "<code>capacity</code> — максимальный размер кэша.\n"
            "<code>operations</code> — список команд: <code>[('put', key, val), ('get', key)]</code>.\n"
            "Функция должна вернуть **список результатов всех операций 'get'** (если ключа нет, выводить <code>-1</code>).\n"
            "При вытечнении удаляется элемент, к которому дольше всего не было обращений (Least Recently Used)."
        ),
        "starter_code": (
            "def simulate_lru_cache(capacity: int, operations: list) -> list:\n"
            "    # Напишите симуляцию LRU-кэша здесь\n"
            "    pass"
        ),
        "entry_point": "simulate_lru_cache",
        "test_cases": [
            {
                "input": [2, [("put", 1, 1), ("put", 2, 2), ("get", 1), ("put", 3, 3), ("get", 2), ("get", 3)]],
                "expected": [1, -1, 3],
                "description": "Элемент 2 вытеснен из кэша"
            }
        ]
    },
    {
        "id": "backend_rate_limiter",
        "company": "Avito Backend",
        "title": "Sliding Window Rate Limiter",
        "category": "Backend",
        "difficulty": "MEDIUM",
        "language": "Python 3.11",
        "reward": 270,
        "description": (
            "Напишите функцию <code>check_rate_limit(requests, window_size, max_requests)</code>.\n"
            "<code>requests</code> — список временных меток запросов (timestamp in sec).\n"
            "Запрос разрешен, если за последние <code>window_size</code> секунд было менее <code>max_requests</code> зафиксированных вызовов.\n"
            "Верните список булевых значений <code>[True/False, ...]</code> для каждого запроса."
        ),
        "starter_code": (
            "def check_rate_limit(requests: list[int], window_size: int, max_requests: int) -> list[bool]:\n"
            "    # Напишите проверку rate limiter здесь\n"
            "    pass"
        ),
        "entry_point": "check_rate_limit",
        "test_cases": [
            {
                "input": [[1, 2, 3, 10, 11], 5, 3],
                "expected": [True, True, True, True, True],
                "description": "Запросы равномерно распределены"
            },
            {
                "input": [[1, 1, 1, 1], 5, 2],
                "expected": [True, True, False, False],
                "description": "Превышение лимита в одну секунду"
            }
        ]
    },

    # =========================================================================
    # 📱 MOBILE (Reward: 210 - 300)
    # =========================================================================
    {
        "id": "mobile_gps_filter",
        "company": "Яндекс Еда Mobile",
        "title": "Фильтрация GPS выбросов курьера",
        "category": "Mobile",
        "difficulty": "MEDIUM",
        "language": "Python 3.11",
        "reward": 260,
        "description": (
            "Напишите функцию <code>filter_gps_track(points, max_speed_mps)</code>.\n"
            "<code>points</code> — список <code>[{'lat': float, 'lon': float, 'timestamp': int}]</code>.\n"
            "Если скорость от предыдущей валидной точки (расстояние по Евклиду: 1 град ~ 111 000м) превышает <code>max_speed_mps</code>, точка фильтруется.\n"
            "Верните список валидных точек."
        ),
        "starter_code": (
            "def filter_gps_track(points: list, max_speed_mps: float) -> list:\n"
            "    # Напишите фильтрацию GPS трека здесь\n"
            "    pass"
        ),
        "entry_point": "filter_gps_track",
        "test_cases": [
            {
                "input": [[
                    {"lat": 55.75, "lon": 37.61, "timestamp": 1000},
                    {"lat": 55.85, "lon": 37.81, "timestamp": 1001},
                    {"lat": 55.7501, "lon": 37.6101, "timestamp": 1010}
                ], 15.0],
                "expected": [
                    {"lat": 55.75, "lon": 37.61, "timestamp": 1000},
                    {"lat": 55.7501, "lon": 37.6101, "timestamp": 1010}
                ],
                "description": "Выброс первой скорой точки"
            }
        ]
    },

    # =========================================================================
    # 🎨 FRONTEND (Reward: 190 - 280)
    # =========================================================================
    {
        "id": "frontend_clsx_builder",
        "company": "VK Frontend",
        "title": "Условный генератор CSS-классов (clsx)",
        "category": "Frontend",
        "difficulty": "EASY-MEDIUM",
        "language": "Python 3.11",
        "reward": 210,
        "description": (
            "Напишите функцию <code>clsx(*args)</code>, аналогичную популярной утилите `classnames`.\n"
            "Аргументы могут быть строками, словарями <code>{'class_name': bool}</code> или вложенными списками.\n"
            "Игнорируйте ложные значения (`False`, `None`, `""`). Верните строку со всеми активными классами через пробел."
        ),
        "starter_code": (
            "def clsx(*args) -> str:\n"
            "    # Напишите утилиту clsx здесь\n"
            "    pass"
        ),
        "entry_point": "clsx",
        "test_cases": [
            {"input": ["btn", {"btn-active": True, "btn-disabled": False}, ["extra"]], "expected": "btn btn-active extra", "description": "Комбинация аргументов"}
        ]
    },

    # =========================================================================
    # 🛠️ DEVOPS (Reward: 230 - 320)
    # =========================================================================
    {
        "id": "devops_nginx_log_parser",
        "company": "Yandex Cloud DevOps",
        "title": "Парсер логов Nginx и 95-й процентиль",
        "category": "DevOps",
        "difficulty": "MEDIUM",
        "language": "Python 3.11",
        "reward": 270,
        "description": (
            "Напишите функцию <code>parse_nginx_logs(log_lines)</code>.\n"
            "Принимает список строк лога вида: <code>'192.168.1.1 200 0.145'</code> (IP status_code response_time_sec).\n"
            "Верните словарь с результатами:\n"
            "<pre>{\n  'total_requests': int,\n  'status_counts': {'200': int, ...},\n  'p95_latency': float  # 95-й процентиль задержки, округленный до 3 знаков\n}</pre>"
        ),
        "starter_code": (
            "def parse_nginx_logs(log_lines: list[str]) -> dict:\n"
            "    # Напишите парсер логов Nginx здесь\n"
            "    pass"
        ),
        "entry_point": "parse_nginx_logs",
        "test_cases": [
            {
                "input": [["1.1.1.1 200 0.100", "1.1.1.2 200 0.200", "1.1.1.3 500 0.500"]],
                "expected": {
                    "total_requests": 3,
                    "status_counts": {"200": 2, "500": 1},
                    "p95_latency": 0.500
                },
                "description": "Расчет процентилей и подсчет кодов"
            }
        ]
    }
]


# =============================================================================
# 🎲 ОРАКУЛЫ И ДИНАМИЧЕСКИЕ ГЕНЕРАТОРЫ ТЕСТ-КЕЙСОВ (Анти-Хардкод Движок)
# =============================================================================

def _oracle_two_sum(nums: list, target: int) -> list:
    seen = {}
    for idx, val in enumerate(nums):
        diff = target - val
        if diff in seen:
            return [seen[diff], idx]
        seen[val] = idx
    return []

def _gen_two_sum() -> list:
    tests = [
        {"input": [[2, 7, 11, 15], 9], "expected": [0, 1], "description": "Базовый пример"},
        {"input": [[1, 2, 3], 100], "expected": [], "description": "Пары не существует"},
        {"input": [[3, 3], 6], "expected": [0, 1], "description": "Одинаковые элементы"}
    ]
    for i in range(5):
        size = random.randint(10, 50)
        nums = [random.randint(-100, 100) for _ in range(size)]
        if random.random() < 0.7:
            idx1, idx2 = random.sample(range(size), 2)
            target = nums[idx1] + nums[idx2]
        else:
            target = 99999
        expected = _oracle_two_sum(nums, target)
        tests.append({
            "input": [nums, target],
            "expected": expected,
            "description": f"Динамический рандомный тест #{i+1} (размер {size})"
        })
    return tests


def _oracle_valid_parentheses(s: str) -> bool:
    stack = []
    mapping = {")": "(", "}": "{", "]": "["}
    for char in s:
        if char in mapping:
            top = stack.pop() if stack else '#'
            if mapping[char] != top:
                return False
        else:
            stack.append(char)
    return not stack

def _gen_valid_parentheses() -> list:
    tests = [
        {"input": ["()[]{}"], "expected": True, "description": "Правильные скобки"},
        {"input": ["(]"], "expected": False, "description": "Несовпадение типов скобок"},
        {"input": [""], "expected": True, "description": "Пустая строка"}
    ]
    for i in range(5):
        if random.random() < 0.5:
            # Валидная последовательность
            pairs = [("(", ")"), ("{", "}"), ("[", "]")]
            s = ""
            for _ in range(random.randint(3, 10)):
                p = random.choice(pairs)
                s = p[0] + s + p[1]
        else:
            # Невалидная последовательность
            chars = ["(", ")", "{", "}", "[", "]"]
            s = "".join(random.choices(chars, k=random.randint(5, 15)))
        expected = _oracle_valid_parentheses(s)
        tests.append({
            "input": [s],
            "expected": expected,
            "description": f"Динамический рандомный тест #{i+1}"
        })
    return tests


def _oracle_sliding_window_max(nums: list, k: int) -> int:
    if not nums or k <= 0 or k > len(nums):
        return 0
    curr = sum(nums[:k])
    m = curr
    for i in range(k, len(nums)):
        curr += nums[i] - nums[i - k]
        if curr > m:
            m = curr
    return m

def _gen_sliding_window_max() -> list:
    tests = [
        {"input": [[2, 1, 5, 1, 3, 2], 3], "expected": 9, "description": "Базовый пример"},
        {"input": [[], 2], "expected": 0, "description": "Пустой массив"},
        {"input": [[1, 2], 5], "expected": 0, "description": "Окно больше массива"}
    ]
    for i in range(5):
        size = random.randint(15, 60)
        nums = [random.randint(-50, 100) for _ in range(size)]
        k = random.randint(1, size)
        expected = _oracle_sliding_window_max(nums, k)
        tests.append({
            "input": [nums, k],
            "expected": expected,
            "description": f"Динамический рандомный тест #{i+1} (N={size}, K={k})"
        })
    return tests


def _oracle_merge_intervals(intervals: list) -> list:
    if not intervals:
        return []
    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0]]
    for current in sorted_intervals[1:]:
        prev = merged[-1]
        if current[0] <= prev[1]:
            prev[1] = max(prev[1], current[1])
        else:
            merged.append(current)
    return merged

def _gen_merge_intervals() -> list:
    tests = [
        {"input": [[[1, 3], [2, 6], [8, 10], [15, 18]]], "expected": [[1, 6], [8, 10], [15, 18]], "description": "Базовое пересечение"},
        {"input": [[]], "expected": [], "description": "Пустой список"}
    ]
    for i in range(5):
        size = random.randint(5, 20)
        intervals = []
        for _ in range(size):
            st = random.randint(1, 100)
            end = st + random.randint(1, 25)
            intervals.append([st, end])
        expected = _oracle_merge_intervals(intervals)
        tests.append({
            "input": [intervals],
            "expected": expected,
            "description": f"Динамический рандомный тест #{i+1} ({size} интервалов)"
        })
    return tests


def _oracle_compress_string(s: str) -> str:
    if not s:
        return ""
    res = []
    curr_char = s[0]
    count = 1
    for char in s[1:]:
        if char == curr_char:
            count += 1
        else:
            res.append(f"{curr_char}{count}")
            curr_char = char
            count = 1
    res.append(f"{curr_char}{count}")
    compressed = "".join(res)
    return compressed if len(compressed) < len(s) else s

def _gen_compress_string() -> list:
    tests = [
        {"input": ["aabcccccaaa"], "expected": "a2b1c5a3", "description": "Сжатие RLE"},
        {"input": ["abcd"], "expected": "abcd", "description": "Без сжатия"}
    ]
    for i in range(5):
        chars = ["a", "b", "c", "d", "e"]
        s_parts = []
        for _ in range(random.randint(3, 8)):
            ch = random.choice(chars)
            cnt = random.randint(1, 6)
            s_parts.append(ch * cnt)
        s = "".join(s_parts)
        expected = _oracle_compress_string(s)
        tests.append({
            "input": [s],
            "expected": expected,
            "description": f"Динамическая подстрока RLE #{i+1}"
        })
    return tests


def _oracle_transpose(matrix: list) -> list:
    if not matrix or not matrix[0]:
        return []
    return [[matrix[r][c] for r in range(len(matrix))] for c in range(len(matrix[0]))]

def _gen_matrix_transpose() -> list:
    tests = [
        {"input": [[[1, 2, 3], [4, 5, 6]]], "expected": [[1, 4], [2, 5], [3, 6]], "description": "Матрица 2х3"},
        {"input": [[]], "expected": [], "description": "Пустая матрица"}
    ]
    for i in range(5):
        rows = random.randint(1, 6)
        cols = random.randint(1, 6)
        mat = [[random.randint(0, 50) for _ in range(cols)] for _ in range(rows)]
        expected = _oracle_transpose(mat)
        tests.append({
            "input": [mat],
            "expected": expected,
            "description": f"Динамическая матрица #{i+1} ({rows}x{cols})"
        })
    return tests


def _oracle_lru_cache(capacity: int, operations: list) -> list:
    from collections import OrderedDict
    cache = OrderedDict()
    results = []
    for op in operations:
        cmd = op[0]
        if cmd == "put":
            k, v = op[1], op[2]
            if k in cache:
                cache.move_to_end(k)
            cache[k] = v
            if len(cache) > capacity:
                cache.popitem(last=False)
        elif cmd == "get":
            k = op[1]
            if k in cache:
                cache.move_to_end(k)
                results.append(cache[k])
            else:
                results.append(-1)
    return results

def _gen_lru_cache() -> list:
    tests = [
        {
            "input": [2, [("put", 1, 1), ("put", 2, 2), ("get", 1), ("put", 3, 3), ("get", 2), ("get", 3)]],
            "expected": [1, -1, 3],
            "description": "Базовый тест LRU"
        }
    ]
    for i in range(5):
        cap = random.randint(2, 5)
        ops = []
        for _ in range(random.randint(10, 25)):
            if random.random() < 0.6:
                ops.append(("put", random.randint(1, 8), random.randint(10, 99)))
            else:
                ops.append(("get", random.randint(1, 8)))
        expected = _oracle_lru_cache(cap, ops)
        tests.append({
            "input": [cap, ops],
            "expected": expected,
            "description": f"Динамический стресс-тест LRU #{i+1} (емкость {cap})"
        })
    return tests


def _oracle_rate_limiter(requests: list, window_size: int, max_requests: int) -> list:
    allowed = []
    timestamps = []
    for t in requests:
        timestamps = [x for x in timestamps if t - x <= window_size]
        if len(timestamps) < max_requests:
            timestamps.append(t)
            allowed.append(True)
        else:
            allowed.append(False)
    return allowed

def _gen_rate_limiter() -> list:
    tests = [
        {"input": [[1, 2, 3, 10, 11], 5, 3], "expected": [True, True, True, True, True], "description": "Равномерные запросы"},
        {"input": [[1, 1, 1, 1], 5, 2], "expected": [True, True, False, False], "description": "Превышение лимита"}
    ]
    for i in range(5):
        window = random.randint(3, 10)
        max_req = random.randint(2, 5)
        reqs = sorted([random.randint(1, 30) for _ in range(random.randint(10, 20))])
        expected = _oracle_rate_limiter(reqs, window, max_req)
        tests.append({
            "input": [reqs, window, max_req],
            "expected": expected,
            "description": f"Динамический поток запросов #{i+1}"
        })
    return tests


def _oracle_gps_filter(points: list, max_speed_mps: float) -> list:
    if not points:
        return []
    valid = [points[0]]
    for p in points[1:]:
        prev = valid[-1]
        dt = p["timestamp"] - prev["timestamp"]
        if dt <= 0:
            continue
        dlat = (p["lat"] - prev["lat"]) * 111000
        dlon = (p["lon"] - prev["lon"]) * 111000
        dist = (dlat ** 2 + dlon ** 2) ** 0.5
        speed = dist / dt
        if speed <= max_speed_mps:
            valid.append(p)
    return valid

def _gen_gps_filter() -> list:
    tests = [
        {
            "input": [[
                {"lat": 55.75, "lon": 37.61, "timestamp": 1000},
                {"lat": 55.85, "lon": 37.81, "timestamp": 1001},
                {"lat": 55.7501, "lon": 37.6101, "timestamp": 1010}
            ], 15.0],
            "expected": [
                {"lat": 55.75, "lon": 37.61, "timestamp": 1000},
                {"lat": 55.7501, "lon": 37.6101, "timestamp": 1010}
            ],
            "description": "Фильтрация прыжка координат"
        }
    ]
    for i in range(5):
        pts = [{"lat": 55.75, "lon": 37.61, "timestamp": 1000}]
        curr_time = 1000
        curr_lat, curr_lon = 55.75, 37.61
        for _ in range(random.randint(6, 15)):
            curr_time += random.randint(5, 30)
            if random.random() < 0.3:
                # GPS noise выброс
                pts.append({"lat": curr_lat + random.uniform(0.1, 0.5), "lon": curr_lon + random.uniform(0.1, 0.5), "timestamp": curr_time})
            else:
                curr_lat += random.uniform(0.0001, 0.0005)
                curr_lon += random.uniform(0.0001, 0.0005)
                pts.append({"lat": round(curr_lat, 6), "lon": round(curr_lon, 6), "timestamp": curr_time})
        expected = _oracle_gps_filter(pts, 15.0)
        tests.append({
            "input": [pts, 15.0],
            "expected": expected,
            "description": f"Динамический GPS трек #{i+1} ({len(pts)} точек)"
        })
    return tests


def _oracle_clsx(*args) -> str:
    classes = []
    for arg in args:
        if isinstance(arg, str) and arg:
            classes.append(arg)
        elif isinstance(arg, dict):
            for k, v in arg.items():
                if v:
                    classes.append(k)
        elif isinstance(arg, (list, tuple)):
            sub = _oracle_clsx(*arg)
            if sub:
                classes.append(sub)
    return " ".join(classes)

def _gen_clsx_builder() -> list:
    tests = [
        {"input": ["btn", {"btn-active": True, "btn-disabled": False}, ["extra"]], "expected": "btn btn-active extra", "description": "Базовый clsx"}
    ]
    for i in range(5):
        args = ["classA", {"classB": random.choice([True, False]), "classC": random.choice([True, False])}, [random.choice(["active", "disabled"])]]
        expected = _oracle_clsx(*args)
        tests.append({
            "input": args,
            "expected": expected,
            "description": f"Динамический набор классов #{i+1}"
        })
    return tests


def _oracle_nginx_log_parser(log_lines: list) -> dict:
    if not log_lines:
        return {'total_requests': 0, 'status_counts': {}, 'p95_latency': 0.0}
    status_counts = {}
    latencies = []
    for line in log_lines:
        parts = line.strip().split()
        if len(parts) >= 3:
            st = parts[1]
            lat = float(parts[2])
            status_counts[st] = status_counts.get(st, 0) + 1
            latencies.append(lat)
    latencies.sort()
    idx = int(0.95 * len(latencies))
    if idx >= len(latencies):
        idx = len(latencies) - 1
    p95 = round(latencies[idx], 3) if latencies else 0.0
    return {'total_requests': len(log_lines), 'status_counts': status_counts, 'p95_latency': p95}

def _gen_nginx_log_parser() -> list:
    tests = [
        {
            "input": [["1.1.1.1 200 0.100", "1.1.1.2 200 0.200", "1.1.1.3 500 0.500"]],
            "expected": {
                "total_requests": 3,
                "status_counts": {"200": 2, "500": 1},
                "p95_latency": 0.500
            },
            "description": "Базовый лог"
        }
    ]
    for i in range(5):
        logs = []
        statuses = ["200", "200", "200", "404", "500"]
        for _ in range(random.randint(10, 30)):
            ip = f"10.0.0.{random.randint(1, 50)}"
            st = random.choice(statuses)
            lat = round(random.uniform(0.01, 2.5), 3)
            logs.append(f"{ip} {st} {lat}")
        expected = _oracle_nginx_log_parser(logs)
        tests.append({
            "input": [logs],
            "expected": expected,
            "description": f"Динамический поток логов Nginx #{i+1}"
        })
    return tests


def generate_task_test_cases(task_id: str) -> list[dict]:
    """Генерирует от 6 до 10 уникальных динамических тест-кейсов для задачи."""
    generator_map = {
        "algo_two_sum": _gen_two_sum,
        "algo_valid_parentheses": _gen_valid_parentheses,
        "algo_sliding_window_max": _gen_sliding_window_max,
        "algo_merge_intervals": _gen_merge_intervals,
        "algo_compress_string": _gen_compress_string,
        "algo_matrix_transpose": _gen_matrix_transpose,
        "backend_lru_cache": _gen_lru_cache,
        "backend_rate_limiter": _gen_rate_limiter,
        "mobile_gps_filter": _gen_gps_filter,
        "frontend_clsx_builder": _gen_clsx_builder,
        "devops_nginx_log_parser": _gen_nginx_log_parser
    }
    gen_func = generator_map.get(task_id)
    if gen_func:
        return gen_func()
    
    task = get_task_by_id(task_id)
    return task.get("test_cases", []) if task else []


def get_tasks_by_category(category: str) -> List[Dict[str, Any]]:
    if category.lower() == "any":
        return IT_TASKS_DB
    return [t for t in IT_TASKS_DB if t.get("category", "").lower() == category.lower()]


def get_task_by_id(task_id: str) -> Optional[Dict[str, Any]]:
    for t in IT_TASKS_DB:
        if t.get("id") == task_id:
            return t
    return None
