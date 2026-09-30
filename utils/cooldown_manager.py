"""Модуль для управления кулдаунами команд."""
import json
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class CooldownManager:
    _instance = None
    _initialized = False

    def __new__(cls, cooldown_file: str = "cooldowns.json"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, cooldown_file: str = "cooldowns.json"):
        if self._initialized:
            return

        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        cooldown_path = Path(cooldown_file)
        if not cooldown_path.is_absolute():
            cooldown_path = data_dir / cooldown_path

        self.cooldown_file: Path = cooldown_path
        self.cooldowns: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self.load_cooldowns()

        # Фоновый поток для неблокирующей и безопасной записи на диск
        self._write_queue = queue.Queue()
        self._write_thread = threading.Thread(target=self._bg_writer, daemon=True)
        self._write_thread.start()

        # Очистка старых кулдаунов при запуске
        self.cleanup_expired()

        CooldownManager._initialized = True

    def _bg_writer(self):
        while True:
            data = self._write_queue.get()
            if data is None:
                break
            try:
                temp_file = self.cooldown_file.with_suffix(".tmp")
                with temp_file.open('w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                for attempt in range(5):
                    try:
                        temp_file.replace(self.cooldown_file)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.05)
            except Exception as e:
                logger.error(f"Ошибка сохранения кулдаунов в фоновом потоке: {e}")
            finally:
                self._write_queue.task_done()

    def load_cooldowns(self):
        try:
            if self.cooldown_file.exists():
                file_content = self.cooldown_file.read_text(encoding='utf-8').strip()
                if file_content:
                    with self._lock:
                        self.cooldowns = json.loads(file_content)
                    logger.info(f"Загружено {len(self.cooldowns)} кулдаунов из {self.cooldown_file}")
                else:
                    logger.info("Cooldowns file is empty, initializing with empty dict")
                    self.cooldowns = {}
            else:
                logger.info(f"Файл кулдаунов {self.cooldown_file} не найден, создаем новый")
                self.cooldowns = {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in cooldowns file: {e}. Resetting to empty.")
            self.cooldowns = {}
        except Exception as e:
            logger.error(f"Ошибка загрузки кулдаунов: {e}")
            self.cooldowns = {}

    def save_cooldowns(self):
        with self._lock:
            snapshot = {k: v.copy() if isinstance(v, dict) else v for k, v in self.cooldowns.items()}
        self._write_queue.put(snapshot)

    def check_cooldown(self, key: str, cooldown_seconds: float) -> Optional[float]:
        with self._lock:
            entry = self.cooldowns.get(key)
            if not entry:
                return None
            last_time = entry.get("last_time", 0) if isinstance(entry, dict) else 0

        current_time = time.time()
        time_passed = current_time - last_time

        if time_passed >= cooldown_seconds:
            return None

        return cooldown_seconds - time_passed

    def set_cooldown(self, key: str):
        current_time = time.time()
        with self._lock:
            if key not in self.cooldowns or not isinstance(self.cooldowns[key], dict):
                self.cooldowns[key] = {}
            self.cooldowns[key]["last_time"] = current_time
        self.save_cooldowns()

    def get_data(self, key: str) -> Dict[str, Any]:
        with self._lock:
            val = self.cooldowns.get(key, {})
            return val.copy() if isinstance(val, dict) else {}

    def set_data(self, key: str, data: Dict[str, Any]):
        with self._lock:
            self.cooldowns[key] = data
        self.save_cooldowns()

    def delete_data(self, key: str):
        with self._lock:
            if key in self.cooldowns:
                del self.cooldowns[key]
        self.save_cooldowns()

    def reset_user_cooldowns(self, user_id: int, cd_type: str = "all") -> int:
        """Сбрасывает кулдауны пользователя. Возвращает количество удаленных записей."""
        keys_to_delete = []
        user_str = str(user_id)

        with self._lock:
            for key in list(self.cooldowns.keys()):
                if f":{user_id}:" in key or key.endswith(f":{user_id}") or key.startswith(f"freelance_session:{user_id}"):
                    if cd_type == "all" or cd_type in key:
                        keys_to_delete.append(key)

            count = len(keys_to_delete)
            for k in keys_to_delete:
                del self.cooldowns[k]

        if count > 0:
            self.save_cooldowns()

        return count

    def cleanup_expired(self, max_age_seconds: float = 259200):
        """Очищает устаревшие кулдауны старше max_age_seconds (по умолчанию 3 дня)."""
        now = time.time()
        removed = 0
        with self._lock:
            for key in list(self.cooldowns.keys()):
                entry = self.cooldowns[key]
                if isinstance(entry, dict):
                    last_time = entry.get("last_time", 0)
                    # Если кулдаун старше 3 суток и нет кастомных активных блокировок
                    if now - last_time > max_age_seconds:
                        del self.cooldowns[key]
                        removed += 1

        if removed > 0:
            logger.info(f"Очищено {removed} устаревших кулдаунов из памяти")
            self.save_cooldowns()
