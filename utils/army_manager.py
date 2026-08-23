"""Модуль для управления армиями и войсками."""
import html
import json
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from utils.economy_manager import EconomyManager

logger = logging.getLogger(__name__)

CREATE_ARMY_COST = 700.0
RANK_CREATOR = "Главнокомандующий"
RANK_DEFAULT = "Рядовой"


class ArmyManager:
    _instance = None
    _initialized = False

    def __new__(cls, armies_file: str = "armies.json"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, armies_file: str = "armies.json"):
        if self._initialized:
            return

        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        armies_path = Path(armies_file)
        if not armies_path.is_absolute():
            armies_path = data_dir / armies_path

        self.armies_file: Path = armies_path
        self.armies: Dict[str, Dict[str, Any]] = {}
        self.user_army_map: Dict[int, str] = {}  # user_id -> army_key (lowercase)
        
        self.economy_manager = EconomyManager()

        # Очередь и фоновый поток для неблокирующей записи на диск
        self._write_queue = queue.Queue()
        self._write_thread = threading.Thread(target=self._bg_writer, daemon=True)
        self._write_thread.start()

        self.load_armies()

        ArmyManager._initialized = True

    def _bg_writer(self):
        while True:
            data = self._write_queue.get()
            if data is None:
                break
            try:
                temp_file = self.armies_file.with_suffix(".tmp")
                serializable_armies = data.get("armies", {})
                serializable_map = {str(k): v for k, v in data.get("user_army_map", {}).items()}
                
                with temp_file.open("w", encoding="utf-8") as f:
                    json.dump(
                        {"armies": serializable_armies, "user_army_map": serializable_map},
                        f,
                        ensure_ascii=False,
                        indent=2
                    )

                for attempt in range(5):
                    try:
                        temp_file.replace(self.armies_file)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.05)
            except Exception as e:
                logger.error(f"Ошибка сохранения армий в фоновом потоке: {e}")
            finally:
                self._write_queue.task_done()

    def load_armies(self):
        try:
            if self.armies_file.exists():
                with self.armies_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.armies = data.get("armies", {})
                    raw_map = data.get("user_army_map", {})
                    self.user_army_map = {int(k): v for k, v in raw_map.items()}
                    logger.info(f"Загружено {len(self.armies)} армий из {self.armies_file}")
            else:
                logger.info(f"Файл армий {self.armies_file} не найден, создаем новый")
                self.save_armies()
        except Exception as e:
            logger.error(f"Ошибка загрузки армий: {e}")
            self.armies = {}
            self.user_army_map = {}

    def save_armies(self):
        snapshot = {
            "armies": self.armies.copy(),
            "user_army_map": self.user_army_map.copy()
        }
        self._write_queue.put(snapshot)

    def get_user_army_key(self, user_id: int) -> Optional[str]:
        return self.user_army_map.get(user_id)

    def get_user_army(self, user_id: int) -> Tuple[Optional[dict], Optional[dict]]:
        army_key = self.get_user_army_key(user_id)
        if not army_key or army_key not in self.armies:
            return None, None
        army = self.armies[army_key]
        member_info = army.get("members", {}).get(str(user_id))
        return army, member_info

    def get_army_by_name(self, army_name: str) -> Optional[dict]:
        clean_name = army_name.strip().lower()
        return self.armies.get(clean_name)

    def create_army(self, creator_id: int, creator_name: str, army_name: str, max_members: int) -> Tuple[bool, str]:
        army_name = army_name.strip()
        if not army_name:
            return False, "❌ Название армии не может быть пустым!"

        if len(army_name) < 2 or len(army_name) > 32:
            return False, "❌ Название армии должно быть от 2 до 32 символов!"

        if max_members < 2 or max_members > 1000:
            return False, "❌ Численность армии должна быть от 2 до 1000 человек!"

        # Проверка, не состоит ли пользователь уже в армии
        if self.get_user_army_key(creator_id):
            existing_army, _ = self.get_user_army(creator_id)
            army_title = existing_army['name'] if existing_army else "армии"
            return False, f"❌ Вы уже состоите в армии «<b>{html.escape(army_title)}</b>»! Сначала покиньте её."

        clean_name = army_name.lower()
        if clean_name in self.armies:
            return False, f"❌ Армия с названием «<b>{html.escape(army_name)}</b>» уже существует!"

        # Проверка баланса монет (700 монет)
        balance = self.economy_manager.get_balance(creator_id)
        if balance < CREATE_ARMY_COST:
            return False, f"❌ Недостаточно монет! Создание армии стоит <b>{int(CREATE_ARMY_COST)} монет</b> (ваш баланс: <b>{balance:.2f} монет</b>)."

        # Списываем монеты
        self.economy_manager.remove_money(creator_id, CREATE_ARMY_COST)

        now = time.time()
        new_army = {
            "name": army_name,
            "creator_id": creator_id,
            "max_members": max_members,
            "created_at": now,
            "members": {
                str(creator_id): {
                    "user_id": creator_id,
                    "name": creator_name,
                    "rank": RANK_CREATOR,
                    "joined_at": now
                }
            },
            "drones": 0,
            "bank": 0,
            "battles_won": 0,
            "battles_lost": 0
        }

        self.armies[clean_name] = new_army
        self.user_army_map[creator_id] = clean_name
        self.save_armies()

        return True, (
            f"🪖 <b>Армия «{html.escape(army_name)}» успешно создана!</b>\n"
            f"👑 Ваш статус: <b>{html.escape(RANK_CREATOR)}</b>\n"
            f"👥 Лимит численности: <b>1/{max_members} чел.</b>\n"
            f"💰 Списано: <b>{int(CREATE_ARMY_COST)} монет</b>."
        )

    def join_army(self, user_id: int, user_name: str, army_name: str) -> Tuple[bool, str]:
        army_name = army_name.strip()
        if not army_name:
            return False, "❌ Укажите название армии, в которую хотите вступить."

        if self.get_user_army_key(user_id):
            existing_army, _ = self.get_user_army(user_id)
            army_title = existing_army['name'] if existing_army else "армии"
            return False, f"❌ Вы уже состоите в армии «<b>{html.escape(army_title)}</b>»! Сначала покиньте её."

        clean_name = army_name.lower()
        army = self.armies.get(clean_name)
        if not army:
            return False, f"❌ Армия с названием «<b>{html.escape(army_name)}</b>» не найдена!"

        members = army.get("members", {})
        if len(members) >= army.get("max_members", 10):
            return False, f"❌ В армии «<b>{html.escape(army['name'])}</b>» нет свободных мест! Достигнут лимит численности ({len(members)}/{army['max_members']} чел.)."

        now = time.time()
        members[str(user_id)] = {
            "user_id": user_id,
            "name": user_name,
            "rank": RANK_DEFAULT,
            "joined_at": now
        }

        self.user_army_map[user_id] = clean_name
        self.save_armies()

        return True, (
            f"🎖️ Вы успешно вступили в армию «<b>{html.escape(army['name'])}</b>»!\n"
            f"Ваше звание: <b>{html.escape(RANK_DEFAULT)}</b>.\n"
            f"Состав: <b>{len(members)}/{army['max_members']} чел.</b>"
        )

    def leave_army(self, user_id: int) -> Tuple[bool, str]:
        army_key = self.get_user_army_key(user_id)
        if not army_key or army_key not in self.armies:
            return False, "❌ Вы не состоите ни в одной армии."

        army = self.armies[army_key]
        members = army.get("members", {})
        member_info = members.get(str(user_id))

        if not member_info:
            self.user_army_map.pop(user_id, None)
            self.save_armies()
            return False, "❌ Вы не являетесь участником этой армии."

        is_creator = (member_info.get("rank") == RANK_CREATOR or army.get("creator_id") == user_id)

        del members[str(user_id)]
        del self.user_army_map[user_id]

        army_name = army["name"]

        if not members:
            # Если участников не осталось — расформировываем армию
            del self.armies[army_key]
            self.save_armies()
            return True, f"🚪 Вы покинули армию «<b>{html.escape(army_name)}</b>». Так как в ней больше никого не осталось, армия расформирована."

        if is_creator:
            # Передаем звание Главнокомандующего старожилу
            sorted_members = sorted(members.values(), key=lambda x: x.get("joined_at", 0))
            new_leader = sorted_members[0]
            new_leader["rank"] = RANK_CREATOR
            army["creator_id"] = new_leader["user_id"]
            self.save_armies()
            return True, (
                f"🚪 Вы покинули армию «<b>{html.escape(army_name)}</b>».\n"
                f"👑 Полномочия <b>{html.escape(RANK_CREATOR)}</b> переданы бойцу <b>{html.escape(new_leader['name'])}</b>."
            )

        self.save_armies()
        return True, f"🚪 Вы успешно покинули армию «<b>{html.escape(army_name)}</b>»."

    def disband_army(self, user_id: int) -> Tuple[bool, str]:
        army_key = self.get_user_army_key(user_id)
        if not army_key or army_key not in self.armies:
            return False, "❌ Вы не состоите ни в одной армии."

        army = self.armies[army_key]
        member_info = army.get("members", {}).get(str(user_id))

        if not member_info or member_info.get("rank") != RANK_CREATOR:
            return False, f"❌ Расформировать армию может только <b>{html.escape(RANK_CREATOR)}</b>!"

        army_name = army["name"]
        members = army.get("members", {})

        # Удаляем маппинг для всех участников
        for mid in list(members.keys()):
            self.user_army_map.pop(int(mid), None)

        del self.armies[army_key]
        self.save_armies()

        return True, f"💥 Армия «<b>{html.escape(army_name)}</b>» была расформирована Главнокомандующим."

    def get_all_armies(self) -> List[dict]:
        return list(self.armies.values())
