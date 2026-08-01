"""
Парсер и генератор неповторяющихся IT-задач для компаний и категории "Алгосы".
Обеспечивает отслеживание истории выданных тасок для каждого пользователя (без повторов).
"""
import os
import json
import random
import logging
from typing import Dict, Any, List, Optional

from utils.it_tasks_db import IT_TASKS_DB, generate_task_test_cases, get_tasks_by_category

logger = logging.getLogger(__name__)

HISTORY_FILE = os.path.join("data", "user_task_history.json")


class TaskHistoryManager:
    """Менеджер для отслеживания истории выданных задач пользователю (защита от повторов)."""

    def __init__(self, filepath: str = HISTORY_FILE):
        self.filepath = filepath
        self.history: Dict[str, List[str]] = self._load_history()

    def _load_history(self) -> Dict[str, List[str]]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading task history: {e}")
                return {}
        return {}

    def _save_history(self):
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving task history: {e}")

    def get_used_tasks(self, user_id: int) -> List[str]:
        return self.history.get(str(user_id), [])

    def mark_task_used(self, user_id: int, task_id: str):
        key = str(user_id)
        if key not in self.history:
            self.history[key] = []
        if task_id not in self.history[key]:
            self.history[key].append(task_id)
            self._save_history()

    def clear_history_for_user(self, user_id: int):
        key = str(user_id)
        if key in self.history:
            self.history[key] = []
            self._save_history()


history_manager = TaskHistoryManager()


class CompanyTaskParser:
    """Парсер и генератор уникальных задач для компаний (Яндекс, Т-Банк, Avito, VK, Ozon, Сбер)."""

    COMPANIES = {
        "Backend": [
            "Яндекс Поиск Backend", "Avito Backend", "Т-Банк Эквайринг",
            "VK Cloud", "Ozon Logistics", "СберМаркет Core"
        ],
        "Frontend": [
            "VKontakte Web", "Яндекс Маркет Frontend", "Ozon Web Platform",
            "Т-Банк Инвестиции Web", "Avito Frontend Engine"
        ],
        "Mobile": [
            "Яндекс Еда Mobile", "Т-Банк Android Team", "Avito iOS Team",
            "VK Video Mobile", "Ozon Express App"
        ],
        "DevOps": [
            "Yandex Cloud Infrastructure", "SberTech DevOps", "VK Cloud Platform",
            "Kaspersky Security Cloud", "Ozon Infra Team"
        ]
    }

    @classmethod
    def parse_company_task(cls, category: str, user_id: int) -> Dict[str, Any]:
        """Парсит/генерирует задачу компании, избегая повторений для этого пользователя."""
        available_tasks = get_tasks_by_category(category)
        if not available_tasks:
            available_tasks = IT_TASKS_DB

        used_task_ids = history_manager.get_used_tasks(user_id)
        unused_tasks = [t for t in available_tasks if t["id"] not in used_task_ids]

        # Если пользователь решил все задачи в категории, сбрасываем историю этой категории
        if not unused_tasks:
            history_manager.clear_history_for_user(user_id)
            unused_tasks = available_tasks

        selected_template = random.choice(unused_tasks)
        history_manager.mark_task_used(user_id, selected_template["id"])

        # Модифицируем задачу (динамическое наименование компании и уникальный ID сессии)
        company_name = selected_template.get("company")
        if category in cls.COMPANIES:
            company_name = random.choice(cls.COMPANIES[category])

        task_instance = dict(selected_template)
        task_instance["company"] = company_name
        return task_instance


class AlgoTaskParser:
    """Парсер и генератор задач для категории 'Алгосы' (Алгоритмы и структуры данных)."""

    ALGO_TOPICS = [
        "algo_two_sum",
        "algo_valid_parentheses",
        "algo_sliding_window_max",
        "algo_merge_intervals",
        "algo_compress_string",
        "algo_matrix_transpose"
    ]

    @classmethod
    def parse_algo_task(cls, user_id: int) -> Dict[str, Any]:
        """Парсит задачу алгоритма из пула 'Алгосов', исключая недавние повторы."""
        algo_tasks = get_tasks_by_category("Алгосы")
        if not algo_tasks:
            algo_tasks = [t for t in IT_TASKS_DB if t.get("category") == "Алгосы"]

        used_task_ids = history_manager.get_used_tasks(user_id)
        unused_tasks = [t for t in algo_tasks if t["id"] not in used_task_ids]

        if not unused_tasks:
            history_manager.clear_history_for_user(user_id)
            unused_tasks = algo_tasks

        selected_task = random.choice(unused_tasks)
        history_manager.mark_task_used(user_id, selected_task["id"])

        return dict(selected_task)
