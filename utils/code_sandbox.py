"""
Безопасная песочница для AST-проверки и выполнения кода решений задач в /freelance
"""
import ast
import math
import logging
import asyncio
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

FORBIDDEN_AST_NODES = (
    ast.Import,
    ast.ImportFrom,
)

FORBIDDEN_NAMES = {
    "__import__", "eval", "exec", "open", "compile", "globals", "locals",
    "vars", "breakpoint", "input", "getattr", "setattr", "delattr",
    "os", "sys", "subprocess", "shutil", "importlib", "pathlib",
    "socket", "urllib", "requests", "aiohttp", "threading", "multiprocessing"
}

SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "hasattr": hasattr,
    "hash": hash,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "pow": pow,
    "print": lambda *args, **kwargs: None,  # Безопасный заглушечный print
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    "math": math,
    "False": False,
    "True": True,
    "None": None,
}


def validate_code_safety(code: str) -> Tuple[bool, str]:
    """Проверяет исходный код на отсутствие опасных вызовов и импортов через AST."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Синтаксическая ошибка в коде: {e.msg} (строка {e.lineno})"

    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_AST_NODES):
            return False, f"Использование импортов (`import`) запрещено!"

        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            return False, f"Использование запрещенного имени/функции `{node.id}`!"

        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
            return False, f"Использование запрещенного атрибута `{node.attr}`!"

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAMES:
                return False, f"Вызов запрещенной функции `{node.func.id}()`!"

    return True, ""


async def run_code_tests(code: str, entry_point: str, test_cases: list[dict], timeout_sec: float = 2.0) -> Dict[str, Any]:
    """Выполняет решение в изолированной среде и сравнивает результаты с тест-кейсами."""
    is_safe, error_msg = validate_code_safety(code)
    if not is_safe:
        return {
            "success": False,
            "passed": 0,
            "total": len(test_cases),
            "error": f"🛡️ <b>Ошибка безопасности:</b> {error_msg}",
            "details": f"❌ {error_msg}"
        }

    # Изолированное окружение
    safe_globals = {
        "__builtins__": SAFE_BUILTINS,
        "math": math
    }

    try:
        exec(code, safe_globals)
    except Exception as e:
        return {
            "success": False,
            "passed": 0,
            "total": len(test_cases),
            "error": f"❌ <b>Ошибка компиляции/выполнения:</b> {type(e).__name__}: {e}",
            "details": f"Не удалось скомпилировать код: {type(e).__name__}: {e}"
        }

    target_func = safe_globals.get(entry_point)
    if not target_func or not callable(target_func):
        return {
            "success": False,
            "passed": 0,
            "total": len(test_cases),
            "error": f"❌ Функция <code>{entry_point}</code> не найдена в отправленном коде!",
            "details": f"Убедитесь, что название функции точно совпадает с <code>{entry_point}</code>."
        }

    passed_count = 0
    test_details = []

    for idx, test in enumerate(test_cases, 1):
        args = test.get("input", [])
        expected = test.get("expected")
        description = test.get("description", f"Тест #{idx}")

        try:
            # Запускаем функцию с тайм-аутом
            result = await asyncio.wait_for(
                asyncio.to_thread(target_func, *args),
                timeout=timeout_sec
            )

            if result == expected:
                passed_count += 1
                test_details.append(f"✅ <b>Тест #{idx}:</b> PASSED ({description})")
            else:
                test_details.append(
                    f"❌ <b>Тест #{idx}:</b> FAILED ({description})\n"
                    f"   <i>Получено:</i> <code>{repr(result)}</code>\n"
                    f"   <i>Ожидалось:</i> <code>{repr(expected)}</code>"
                )
        except asyncio.TimeoutError:
            test_details.append(f"⏰ <b>Тест #{idx}:</b> TIMEOUT (превышен лимит {timeout_sec} сек)")
        except Exception as e:
            test_details.append(f"💥 <b>Тест #{idx}:</b> ERROR ({type(e).__name__}: {e})")

    success = (passed_count == len(test_cases))
    details_str = "\n".join(test_details)

    return {
        "success": success,
        "passed": passed_count,
        "total": len(test_cases),
        "details": details_str,
        "error": None
    }
