"""Модуль для управления армиями и войсками."""
import html
import json
import logging
import queue
import random
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from utils.economy_manager import EconomyManager
from utils.user_link import get_user_link

logger = logging.getLogger(__name__)

CREATE_ARMY_COST = 700.0
RANK_CREATOR = "Главнокомандующий"
RANK_MOBILIZED = "Штурмовик"
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
                    # Гарантируем наличие полей для СВО, казны и пленных
                    for army in self.armies.values():
                        army.setdefault("bank", 0.0)
                        army.setdefault("drones", 0)
                        army.setdefault("prisoners", [])
                        army.setdefault("active_war_id", None)
                        army.setdefault("war_stats", {"wins": 0, "losses": 0, "captures": 0, "total_looted": 0.0})
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
            "bank": 0.0,
            "prisoners": [],
            "active_war_id": None,
            "war_stats": {
                "wins": 0,
                "losses": 0,
                "captures": 0,
                "total_looted": 0.0
            },
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
        if army.get("active_war_id"):
            return False, "⚔️ <b>Ваша армия сейчас ведёт боевые действия на СВО!</b> Выход из армии во время войны строго запрещён."

        # Проверка, не находится ли боец во вражеском плену
        is_pow, captor_key, _ = self.is_user_prisoner(user_id)
        if is_pow:
            captor_army = self.armies.get(captor_key, {})
            c_name = captor_army.get("name", "вражеской армии")
            return False, f"⛓️ <b>Вы находитесь в плену у армии «{html.escape(c_name)}»!</b> Сначала вас должны освободить или выкупить."

        members = army.get("members", {})
        member_info = members.get(str(user_id))

        if not member_info:
            self.user_army_map.pop(user_id, None)
            self.save_armies()
            return False, "❌ Вы не являетесь участником этой армии."

        if member_info.get("rank") == RANK_MOBILIZED:
            return False, (
                "🚫 <b>Дезертирство карается по законам военного времени!</b>\n\n"
                "⚔️ Вы мобилизованы в штурмовой отряд и находитесь на передке. "
                "Вы не можете самовольно покинуть армию!\n"
                "💡 Только <b>Главнокомандующий</b> может объявить вашу демобилизацию (<code>/демобилизация</code>)."
            )

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
            leader_link = get_user_link(new_leader["user_id"], new_leader.get("name", "").lstrip("@"))
            return True, (
                f"🚪 Вы покинули армию «<b>{html.escape(army_name)}</b>».\n"
                f"👑 Полномочия <b>{html.escape(RANK_CREATOR)}</b> переданы бойцу {leader_link}."
            )

        self.save_armies()
        return True, f"🚪 Вы успешно покинули армию «<b>{html.escape(army_name)}</b>»."

    def disband_army(self, user_id: int) -> Tuple[bool, str]:
        army_key = self.get_user_army_key(user_id)
        if not army_key or army_key not in self.armies:
            return False, "❌ Вы не состоите ни в одной армии."

        army = self.armies[army_key]
        if army.get("active_war_id"):
            return False, "⚔️ <b>Нельзя расформировать армию во время активной СВО!</b> Завершите или капитулируйте в операции."

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

    def mobilize_members(self, commander_id: int, count: int) -> Tuple[bool, str, List[dict]]:
        """
        Объявляет мобилизацию в армии: случайным образом переводит указанное число
        рядовых в ранг Штурмовиков для будущих боевых действий.
        """
        army_key = self.get_user_army_key(commander_id)
        if not army_key or army_key not in self.armies:
            return False, "❌ Вы не состоите ни в одной армии.", []

        army = self.armies[army_key]
        commander_info = army.get("members", {}).get(str(commander_id))

        if not commander_info or commander_info.get("rank") != RANK_CREATOR:
            return False, f"❌ Объявлять мобилизацию может только <b>{html.escape(RANK_CREATOR)}</b>!", []

        if count <= 0:
            return False, "❌ Количество мобилизуемых бойцов должно быть больше 0!", []

        members = army.get("members", {})
        available_privates = [
            m for m in members.values()
            if m.get("rank") == RANK_DEFAULT
        ]

        if not available_privates:
            return False, (
                f"❌ В армии «<b>{html.escape(army['name'])}</b>» нет доступных рядовых для мобилизации!\n"
                f"💡 Все бойцы уже на передке либо армия состоит только из командования."
            ), []

        if count > len(available_privates):
            return False, (
                f"⚠️ Недостаточно рядовых для мобилизации!\n"
                f"В тыловом резерве доступно: <b>{len(available_privates)} чел.</b>\n"
                f"Укажите число от 1 до <b>{len(available_privates)}</b>."
            ), []

        # Случайный отбор бойцов
        chosen = random.sample(available_privates, count)
        now = time.time()
        for member in chosen:
            member["rank"] = RANK_MOBILIZED
            member["mobilized_at"] = now
            member["status"] = "frontline"

        self.save_armies()
        return True, "Успешно", chosen

    def demobilize_members(self, commander_id: int, count: Optional[int] = None) -> Tuple[bool, str, List[dict]]:
        """
        Демобилизация: возвращает штурмовиков с передка обратно в резерв (статус Рядовой).
        Если count is None — демобилизует всех штурмовиков.
        """
        army_key = self.get_user_army_key(commander_id)
        if not army_key or army_key not in self.armies:
            return False, "❌ Вы не состоите ни в одной армии.", []

        army = self.armies[army_key]
        commander_info = army.get("members", {}).get(str(commander_id))

        if not commander_info or commander_info.get("rank") != RANK_CREATOR:
            return False, f"❌ Демобилизацию может проводить только <b>{html.escape(RANK_CREATOR)}</b>!", []

        members = army.get("members", {})
        mobilized = [
            m for m in members.values()
            if m.get("rank") == RANK_MOBILIZED
        ]

        if not mobilized:
            return False, f"❌ В армии «<b>{html.escape(army['name'])}</b>» нет мобилизованных штурмовиков на передке.", []

        if count is None or count >= len(mobilized):
            to_demobilize = mobilized
        elif count <= 0:
            return False, "❌ Количество для демобилизации должно быть больше 0!", []
        else:
            # Демобилизуем первыми тех, кто дольше всех на передке
            sorted_mob = sorted(mobilized, key=lambda x: x.get("mobilized_at", 0))
            to_demobilize = sorted_mob[:count]

        for member in to_demobilize:
            member["rank"] = RANK_DEFAULT
            member.pop("status", None)
            member.pop("mobilized_at", None)

        self.save_armies()
        return True, "Успешно", to_demobilize

    def get_all_armies(self) -> List[dict]:
        return list(self.armies.values())

    def is_user_prisoner(self, user_id: int) -> Tuple[bool, Optional[str], Optional[dict]]:
        """
        Проверяет, находится ли боец в плену у какой-либо армии.
        Возвращает (is_prisoner, captor_army_key, prisoner_data).
        """
        for army_key, army in self.armies.items():
            for p in army.get("prisoners", []):
                if p.get("user_id") == user_id:
                    return True, army_key, p
        return False, None, None

    def get_prisoners(self, army_key: str) -> List[dict]:
        """Возвращает список военнопленных армии."""
        army = self.armies.get(army_key)
        if not army:
            return []
        return army.get("prisoners", [])

    def add_prisoner(self, captor_army_key: str, prisoner: dict) -> bool:
        """Добавляет военнопленного в армию-захватчик."""
        army = self.armies.get(captor_army_key)
        if not army:
            return False
        prisoners = army.setdefault("prisoners", [])
        # Проверяем, нет ли его уже
        if not any(p.get("user_id") == prisoner.get("user_id") for p in prisoners):
            prisoners.append(prisoner)
            self.save_armies()
            return True
        return False

    def release_prisoner(self, commander_id: int, prisoner_id: int) -> Tuple[bool, str, Optional[dict]]:
        """Главнокомандующий отпускает военнопленного на волю."""
        army_key = self.get_user_army_key(commander_id)
        if not army_key:
            return False, "❌ Вы не состоите в армии.", None

        army = self.armies.get(army_key)
        commander_info = army.get("members", {}).get(str(commander_id))
        if not commander_info or commander_info.get("rank") != RANK_CREATOR:
            return False, f"❌ Освобождать военнопленных может только <b>{html.escape(RANK_CREATOR)}</b>!", None

        prisoners = army.get("prisoners", [])
        target = None
        for p in prisoners:
            if p.get("user_id") == prisoner_id:
                target = p
                break

        if not target:
            return False, "❌ Военнопленный с таким ID не найден в застенках вашей армии.", None

        prisoners.remove(target)
        self.save_armies()
        return True, f"🕊️ Военнопленный <b>{html.escape(target.get('name', 'Боец'))}</b> был отпущен на свободу по приказу Главкома.", target

    def ransom_prisoner(self, payer_id: int, prisoner_id: int, amount: float) -> Tuple[bool, str, Optional[dict]]:
        """
        Выкуп военнопленного из плена чужой армии за монеты.
        Деньги переводятся в казну удерживающей армии.
        """
        is_pow, captor_key, prisoner_info = self.is_user_prisoner(prisoner_id)
        if not is_pow or not captor_key or not prisoner_info:
            return False, "❌ Этот боец не числится в списках военнопленных.", None

        captor_army = self.armies.get(captor_key)
        if not captor_army:
            return False, "❌ Ошибка: армия-захватчик не найдена.", None

        if amount <= 0:
            return False, "❌ Сумма выкупа должна быть положительной!", None

        payer_balance = self.economy_manager.get_balance(payer_id)
        if payer_balance < amount:
            return False, f"❌ Недостаточно средств для выкупа! Требуется <b>{amount:.2f} монет</b> (у вас: <b>{payer_balance:.2f}</b>).", None

        # Списываем у плательщика и начисляем в казну удерживающей армии
        self.economy_manager.remove_money(payer_id, amount)
        captor_army["bank"] = captor_army.get("bank", 0.0) + amount

        # Удаляем из пленных
        captor_army.get("prisoners", []).remove(prisoner_info)
        self.save_armies()

        return True, (
            f"🤝 <b>Выкуп успешно выплачен!</b>\n"
            f"Боец <b>{html.escape(prisoner_info.get('name', 'Боец'))}</b> освобождён из плена армии «<b>{html.escape(captor_army['name'])}</b>»!\n"
            f"💰 В казну захватчиков поступило: <b>{amount:.2f} монет</b>."
        ), prisoner_info

    def deposit_to_bank(self, user_id: int, amount: float) -> Tuple[bool, str]:
        """Пополнение казны армии бойцом."""
        if amount <= 0:
            return False, "❌ Сумма пополнения должна быть больше 0!"

        army_key = self.get_user_army_key(user_id)
        if not army_key:
            return False, "❌ Вы не состоите ни в одной армии."

        balance = self.economy_manager.get_balance(user_id)
        if balance < amount:
            return False, f"❌ Недостаточно монет на балансе (у вас <b>{balance:.2f} монет</b>)."

        army = self.armies.get(army_key)
        self.economy_manager.remove_money(user_id, amount)
        army["bank"] = army.get("bank", 0.0) + amount
        self.save_armies()

        return True, (
            f"🏦 <b>Казна армии «{html.escape(army['name'])}» пополнена!</b>\n"
            f"💰 Внесено: <b>{amount:.2f} монет</b>\n"
            f"💳 Общий баланс казны: <b>{army['bank']:.2f} монет</b>"
        )

    def withdraw_from_bank(self, commander_id: int, amount: float) -> Tuple[bool, str]:
        """Снятие средств из казны Главкомом."""
        if amount <= 0:
            return False, "❌ Сумма снятия должна быть больше 0!"

        army_key = self.get_user_army_key(commander_id)
        if not army_key:
            return False, "❌ Вы не состоите в армии."

        army = self.armies.get(army_key)
        member_info = army.get("members", {}).get(str(commander_id))
        if not member_info or member_info.get("rank") != RANK_CREATOR:
            return False, f"❌ Снимать средства из казны может только <b>{html.escape(RANK_CREATOR)}</b>!"

        current_bank = army.get("bank", 0.0)
        if current_bank < amount:
            return False, f"❌ В казне армии недостаточно средств! Доступно: <b>{current_bank:.2f} монет</b>."

        army["bank"] = current_bank - amount
        self.economy_manager.add_money(commander_id, amount)
        self.save_armies()

        return True, (
            f"💸 <b>Средства выведены из казны армии!</b>\n"
            f"💰 Получено: <b>{amount:.2f} монет</b>\n"
            f"💳 Остаток в казне: <b>{army['bank']:.2f} монет</b>"
        )

    def set_active_war(self, army_key: str, war_id: Optional[str]):
        """Устанавливает или сбрасывает ID активной СВО для армии."""
        army = self.armies.get(army_key)
        if army:
            army["active_war_id"] = war_id
            self.save_armies()

    def record_war_result(self, winner_key: str, loser_key: str, looted_amount: float, prisoners_count: int):
        """Записывает результаты СВО в статистику обеих армий."""
        winner = self.armies.get(winner_key)
        loser = self.armies.get(loser_key)

        if winner:
            winner["battles_won"] = winner.get("battles_won", 0) + 1
            w_stats = winner.setdefault("war_stats", {"wins": 0, "losses": 0, "captures": 0, "total_looted": 0.0})
            w_stats["wins"] = w_stats.get("wins", 0) + 1
            w_stats["captures"] = w_stats.get("captures", 0) + prisoners_count
            w_stats["total_looted"] = w_stats.get("total_looted", 0.0) + looted_amount
            winner["bank"] = winner.get("bank", 0.0) + looted_amount
            winner["active_war_id"] = None

        if loser:
            loser["battles_lost"] = loser.get("battles_lost", 0) + 1
            l_stats = loser.setdefault("war_stats", {"wins": 0, "losses": 0, "captures": 0, "total_looted": 0.0})
            l_stats["losses"] = l_stats.get("losses", 0) + 1
            loser["bank"] = max(0.0, loser.get("bank", 0.0) - looted_amount)
            loser["active_war_id"] = None

        self.save_armies()
