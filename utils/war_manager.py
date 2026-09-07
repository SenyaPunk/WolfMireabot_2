"""Модуль для управления Специальными Военными Операциями (СВО) между армиями."""
import html
import json
import logging
import queue
import random
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from utils.army_manager import (
    ArmyManager,
    RANK_CREATOR,
    RANK_MOBILIZED,
    RANK_DEFAULT
)
from utils.economy_manager import EconomyManager
from utils.user_link import get_user_link

logger = logging.getLogger(__name__)

WAR_DURATION_SECONDS = 900  # 15 минут СВО
COOLDOWN_ASSAULT = 30       # Штурм каждые 30 сек
COOLDOWN_DEFENSE = 45       # Оборона каждые 45 сек
COOLDOWN_HEAL = 25          # Медпомощь каждые 25 сек
COOLDOWN_RESUPPLY = 45      # Снабжение БК каждые 45 сек
COOLDOWN_COMMANDER = 90     # Приказ главкома каждые 90 сек


class WarManager:
    _instance = None
    _initialized = False

    def __new__(cls, wars_file: str = "wars.json"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, wars_file: str = "wars.json"):
        if self._initialized:
            return

        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        wars_path = Path(wars_file)
        if not wars_path.is_absolute():
            wars_path = data_dir / wars_path

        self.wars_file: Path = wars_path
        self.wars: Dict[str, Dict[str, Any]] = {}
        self.active_wars_by_army: Dict[str, str] = {}  # army_key -> war_id
        self.user_cooldowns: Dict[str, float] = {}      # "{user_id}_{action}" -> timestamp

        self.army_manager = ArmyManager()
        self.economy_manager = EconomyManager()

        # Фоновый поток для неблокирующей записи
        self._write_queue = queue.Queue()
        self._write_thread = threading.Thread(target=self._bg_writer, daemon=True)
        self._write_thread.start()

        self.load_wars()
        WarManager._initialized = True

    def _bg_writer(self):
        while True:
            data = self._write_queue.get()
            if data is None:
                break
            try:
                temp_file = self.wars_file.with_suffix(".tmp")
                with temp_file.open("w", encoding="utf-8") as f:
                    json.dump({"wars": data}, f, ensure_ascii=False, indent=2)

                for attempt in range(5):
                    try:
                        temp_file.replace(self.wars_file)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.05)
            except Exception as e:
                logger.error(f"Ошибка сохранения СВО в фоновом потоке: {e}")
            finally:
                self._write_queue.task_done()

    def load_wars(self):
        try:
            if self.wars_file.exists():
                with self.wars_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.wars = data.get("wars", {})
                    # Восстанавливаем активные войны
                    now = time.time()
                    for wid, wdata in self.wars.items():
                        if wdata.get("status") == "active" and wdata.get("expires_at", 0) > now:
                            self.active_wars_by_army[wdata["attacker_key"]] = wid
                            self.active_wars_by_army[wdata["defender_key"]] = wid
                        elif wdata.get("status") == "active":
                            wdata["status"] = "expired"
                    logger.info(f"Загружено {len(self.wars)} СВО из {self.wars_file}")
            else:
                self.save_wars()
        except Exception as e:
            logger.error(f"Ошибка загрузки СВО: {e}")
            self.wars = {}

    def save_wars(self):
        snapshot = self.wars.copy()
        self._write_queue.put(snapshot)

    def get_war_by_army(self, army_key: str) -> Optional[dict]:
        war_id = self.active_wars_by_army.get(army_key)
        if not war_id:
            return None
        return self.wars.get(war_id)

    def get_user_war(self, user_id: int) -> Tuple[Optional[dict], Optional[str], Optional[dict]]:
        """
        Возвращает (war_data, side, soldier_data), где side - 'attacker' или 'defender'.
        """
        army_key = self.army_manager.get_user_army_key(user_id)
        if not army_key:
            return None, None, None

        war = self.get_war_by_army(army_key)
        if not war or war.get("status") != "active":
            return None, None, None

        side = "attacker" if war["attacker_key"] == army_key else "defender"
        soldiers = war[f"{side}_soldiers"]
        soldier_info = soldiers.get(str(user_id))
        return war, side, soldier_info

    def _check_cooldown(self, user_id: int, action: str, cooldown_seconds: float) -> Tuple[bool, float]:
        key = f"{user_id}_{action}"
        last_time = self.user_cooldowns.get(key, 0.0)
        remaining = cooldown_seconds - (time.time() - last_time)
        if remaining > 0:
            return False, remaining
        return True, 0.0

    def _set_cooldown(self, user_id: int, action: str):
        self.user_cooldowns[f"{user_id}_{action}"] = time.time()

    def start_war(self, commander_id: int, target_army_name: str, chat_id: int, thread_id: Optional[int] = None) -> Tuple[bool, str, Optional[dict]]:
        """
        Объявление СВО против другой армии.
        """
        user_army, commander_info = self.army_manager.get_user_army(commander_id)
        if not user_army or not commander_info:
            return False, "❌ Вы не состоите ни в одной армии!", None

        if commander_info.get("rank") != RANK_CREATOR:
            return False, f"❌ Объявлять СВО может только <b>{html.escape(RANK_CREATOR)}</b> армии!", None

        attacker_key = self.army_manager.get_user_army_key(commander_id)
        if not attacker_key:
            return False, "❌ Ошибка идентификации вашей армии.", None

        if attacker_key in self.active_wars_by_army:
            return False, "⚔️ Ваша армия уже ведёт активные боевые действия на СВО! Дождитесь окончания текущей операции.", None

        defender_army = self.army_manager.get_army_by_name(target_army_name)
        if not defender_army:
            return False, f"❌ Армия с названием «<b>{html.escape(target_army_name)}</b>» не найдена!", None

        defender_key = target_army_name.strip().lower()
        if attacker_key == defender_key:
            return False, "❌ Нельзя объявить СВО собственной армии!", None

        if defender_key in self.active_wars_by_army:
            return False, f"⚠️ Армия «<b>{html.escape(defender_army['name'])}</b>» уже находится в состоянии войны с другим противником!", None

        # Проверяем штурмовиков у атакующего
        attacker_members = user_army.get("members", {})
        attacker_mobilized = [m for m in attacker_members.values() if m.get("rank") == RANK_MOBILIZED]
        if not attacker_mobilized:
            return False, (
                f"❌ В вашей армии нет мобилизованных штурмовиков на передке!\n"
                f"💡 Перед началом СВО Главком должен объявить мобилизацию: <code>/мобилизация [число]</code>."
            ), None

        # Проверяем штурмовиков у защитника
        defender_members = defender_army.get("members", {})
        defender_mobilized = [m for m in defender_members.values() if m.get("rank") == RANK_MOBILIZED]
        if not defender_mobilized:
            return False, (
                f"❌ Армия противника «<b>{html.escape(defender_army['name'])}</b>» ещё не выставила штурмовые отряды на передок (0 мобилизованных)!\n"
                f"💡 Подождите, пока их Главнокомандующий проведет мобилизацию."
            ), None

        now = time.time()
        war_id = f"svo_{int(now)}_{uuid.uuid4().hex[:6]}"

        # Формируем передовой состав обеих армий
        def build_soldiers(mobilized_list, army_name):
            res = {}
            for m in mobilized_list:
                uid = str(m["user_id"])
                res[uid] = {
                    "user_id": m["user_id"],
                    "name": m.get("name", "Боец"),
                    "army_name": army_name,
                    "hp": 100,
                    "max_hp": 100,
                    "is_defending_until": 0.0,
                    "status": "active",  # active, wounded, captured, kia
                    "damage_dealt": 0,
                    "kills": 0,
                    "assaults": 0
                }
            return res

        attacker_soldiers = build_soldiers(attacker_mobilized, user_army["name"])
        defender_soldiers = build_soldiers(defender_mobilized, defender_army["name"])

        war_data = {
            "war_id": war_id,
            "chat_id": chat_id,
            "message_thread_id": thread_id,
            "attacker_key": attacker_key,
            "defender_key": defender_key,
            "attacker_name": user_army["name"],
            "defender_name": defender_army["name"],
            "commander_attacker_id": commander_id,
            "commander_defender_id": defender_army.get("creator_id"),
            "started_at": now,
            "duration": WAR_DURATION_SECONDS,
            "expires_at": now + WAR_DURATION_SECONDS,
            "status": "active",
            "attacker_soldiers": attacker_soldiers,
            "defender_soldiers": defender_soldiers,
            "support_buffs": {
                "attacker": {"resupply_until": 0.0, "commander_order": None, "order_until": 0.0},
                "defender": {"resupply_until": 0.0, "commander_order": None, "order_until": 0.0}
            },
            "weather": {
                "name": "☀️ Ясная погода",
                "effect": "none",
                "desc": "Прекрасная видимость. Стандартный урон артиллерии и штурмовых групп."
            },
            "reb_active_until": 0.0,
            "last_event_time": now,
            "battle_log": [
                f"🚨 <b>Главнокомандующий</b> армии «{html.escape(user_army['name'])}» объявил Специальную Военную Операцию против «{html.escape(defender_army['name'])}»!",
                f"⚔️ Линия соприкосновения развёрнута. На передке: {len(attacker_soldiers)} против {len(defender_soldiers)} штурмовиков."
            ],
            "captured_soldiers": []  # список захваченных во время СВО
        }

        self.wars[war_id] = war_data
        self.active_wars_by_army[attacker_key] = war_id
        self.active_wars_by_army[defender_key] = war_id

        self.army_manager.set_active_war(attacker_key, war_id)
        self.army_manager.set_active_war(defender_key, war_id)
        self.save_wars()

        return True, "СВО успешно начата", war_data

    def register_reinforcement(self, army_key: str, new_members: List[dict]):
        """
        Оперативный ввод подкрепления на фронт прямо во время боя.
        """
        war = self.get_war_by_army(army_key)
        if not war or war.get("status") != "active":
            return

        side = "attacker" if war["attacker_key"] == army_key else "defender"
        soldiers = war[f"{side}_soldiers"]
        army_name = war[f"{side}_name"]

        added_names = []
        for m in new_members:
            uid = str(m["user_id"])
            if uid not in soldiers:
                soldiers[uid] = {
                    "user_id": m["user_id"],
                    "name": m.get("name", "Боец"),
                    "army_name": army_name,
                    "hp": 100,
                    "max_hp": 100,
                    "is_defending_until": 0.0,
                    "status": "active",
                    "damage_dealt": 0,
                    "kills": 0,
                    "assaults": 0
                }
                added_names.append(m.get("name", "Боец"))

        if added_names:
            war["battle_log"].insert(
                0,
                f"🪖 <b>Подкрепление на фронте!</b> В строй армии «{html.escape(army_name)}» встали: {', '.join(added_names)}."
            )
            war["battle_log"] = war["battle_log"][:10]
            self.save_wars()

    def execute_assault(self, user_id: int) -> Tuple[bool, str, Optional[dict]]:
        """
        Действие штурмовика: штурмовой накат на вражеские позиции.
        """
        war, side, soldier = self.get_user_war(user_id)
        if not war:
            return False, "❌ Ваша армия сейчас не ведёт боевых действий на СВО.", None

        if not soldier:
            # Проверяем, может пользователь вообще рядовой?
            army_key = self.army_manager.get_user_army_key(user_id)
            army, m_info = self.army_manager.get_user_army(user_id)
            if m_info and m_info.get("rank") == RANK_DEFAULT:
                return False, (
                    "🛡️ <b>Вы находитесь в тыловом резерве (Рядовой)!</b>\n"
                    "Штурмовать позиции врага могут только мобилизованные <b>Штурмовики</b> на передке.\n"
                    "💡 Ваша задача — помогать раненым (<code>/медпомощь</code>) и подвозить боеприпасы (<code>/снабжение</code>)!"
                ), None
            return False, "❌ Вы не состоите в штурмовом отряде этой операции.", None

        if soldier.get("status") == "wounded":
            return False, (
                "🩸 <b>Вы тяжело ранены!</b> У вас критический уровень здоровья.\n"
                "Вы не можете идти в атаку, пока бойцы тылового резерва не окажут вам медицинскую помощь (<code>/медпомощь</code>)!"
            ), None

        if soldier.get("status") in ("captured", "kia"):
            return False, "❌ Вы выведены из строя или находитесь в плену!", None

        # Проверка кулдауна
        can_act, rem_time = self._check_cooldown(user_id, "assault", COOLDOWN_ASSAULT)
        if not can_act:
            return False, f"⏳ <b>Перезарядка и смена позиции!</b> Следующий штурм возможен через <b>{int(rem_time)} сек</b>.", None

        enemy_side = "defender" if side == "attacker" else "attacker"
        enemy_soldiers = war[f"{enemy_side}_soldiers"]

        # Ищем доступные живые цели противника (active или wounded)
        targets = [t for t in enemy_soldiers.values() if t.get("status") in ("active", "wounded")]
        if not targets:
            return False, "🏁 Все штурмовики противника уже выведены из строя или пленены!", war

        target = random.choice(targets)
        now = time.time()

        # Расчет урона
        base_damage = random.randint(22, 38)
        buffs = war["support_buffs"].get(side, {})

        # Бафф снабжения БК (+30%)
        if buffs.get("resupply_until", 0) > now:
            base_damage = int(base_damage * 1.30)

        # Приказ Главкома на атаку (+40%)
        if buffs.get("commander_order") == "attack" and buffs.get("order_until", 0) > now:
            base_damage = int(base_damage * 1.40)

        # Защита цели (глухая оборона -50%)
        is_defending = target.get("is_defending_until", 0) > now
        if is_defending:
            base_damage = max(8, int(base_damage * 0.50))

        # Погода
        weather = war.get("weather", {})
        if weather.get("effect") == "fog":
            base_damage = max(10, int(base_damage * 0.75))

        target["hp"] = max(0, target["hp"] - base_damage)
        soldier["damage_dealt"] = soldier.get("damage_dealt", 0) + base_damage
        soldier["assaults"] = soldier.get("assaults", 0) + 1

        self._set_cooldown(user_id, "assault")

        shooter_link = get_user_link(user_id, soldier["name"])
        target_link = get_user_link(target["user_id"], target["name"])

        # Обработка исхода удара
        outcome_event = ""

        if target["hp"] <= 0:
            soldier["kills"] = soldier.get("kills", 0) + 1
            # Шанс взять в плен vs выбить из строя
            capture_chance = 0.50 if not is_defending else 0.20
            if random.random() < capture_chance:
                target["status"] = "captured"
                war["captured_soldiers"].append({
                    "user_id": target["user_id"],
                    "name": target["name"],
                    "from_army": war[f"{enemy_side}_name"],
                    "captured_by": soldier["name"],
                    "captured_at": now
                })
                outcome_event = (
                    f"⛓️ <b>ВРАГ ВЗЯТ В ПЛЕН!</b> Штурмовик {shooter_link} сломил сопротивление {target_link} "
                    f"и <b>захватил его в плен прямо в окопах</b>! 🏆"
                )
            else:
                target["status"] = "kia"
                outcome_event = (
                    f"💥 <b>ПОЗИЦИЯ СМЯТА!</b> Штурмовик {shooter_link} нанёс сокрушительный удар "
                    f"и вывел бойца {target_link} из строя до конца операции!"
                )
        elif target["hp"] <= 25 and target["status"] != "wounded":
            target["status"] = "wounded"
            outcome_event = (
                f"🩸 Штурмовик {shooter_link} тяжело ранил {target_link} (осталось {target['hp']} HP)! "
                f"Боец не может вести бой без полевого медика!"
            )
        else:
            def_text = " (защищён окопом)" if is_defending else ""
            outcome_event = (
                f"⚔️ {shooter_link} совершил дерзкий штурм позиций противника, нанеся {base_damage} урона бойцу {target_link}{def_text}! "
                f"У врага осталось {target['hp']} HP."
            )

        war["battle_log"].insert(0, outcome_event)
        war["battle_log"] = war["battle_log"][:10]
        self.save_wars()

        # Проверяем не закончилась ли война полным разгромом
        finished, win_side, reason = self.check_war_outcome(war["war_id"])
        if finished:
            finish_msg = self.finish_war(war["war_id"], win_side, reason)
            return True, f"{outcome_event}\n\n{finish_msg}", war

        return True, outcome_event, war

    def execute_defense(self, user_id: int) -> Tuple[bool, str, Optional[dict]]:
        """
        Действие штурмовика: встать в глухую оборону / окопаться.
        """
        war, side, soldier = self.get_user_war(user_id)
        if not war:
            return False, "❌ Ваша армия сейчас не ведёт боевых действий на СВО.", None

        if not soldier:
            return False, "❌ Окапываться на передовой могут только штурмовики на передке!", None

        if soldier.get("status") != "active":
            return False, "❌ Вы не можете занять оборону в текущем состоянии!", None

        can_act, rem_time = self._check_cooldown(user_id, "defense", COOLDOWN_DEFENSE)
        if not can_act:
            return False, f"⏳ Сменить позицию обороны можно через <b>{int(rem_time)} сек</b>.", None

        now = time.time()
        soldier["is_defending_until"] = now + 90  # 90 секунд повышенной защиты
        self._set_cooldown(user_id, "defense")

        user_link = get_user_link(user_id, soldier["name"])
        event_str = f"🛡️ Штурмовик {user_link} закрепился на высоте и <b>окопался в глухую оборону</b> на 1.5 минуты! (-50% входящего урона)."
        war["battle_log"].insert(0, event_str)
        war["battle_log"] = war["battle_log"][:10]
        self.save_wars()

        return True, event_str, war

    def execute_heal(self, user_id: int, target_user_id: Optional[int] = None) -> Tuple[bool, str, Optional[dict]]:
        """
        Действие тылового резерва (рядовые): оказание медицинской помощи штурмовику.
        """
        army_key = self.army_manager.get_user_army_key(user_id)
        if not army_key:
            return False, "❌ Вы не состоите в армии.", None

        war = self.get_war_by_army(army_key)
        if not war or war.get("status") != "active":
            return False, "❌ Ваша армия сейчас не ведёт боевых действий на СВО.", None

        side = "attacker" if war["attacker_key"] == army_key else "defender"
        my_soldiers = war[f"{side}_soldiers"]

        can_act, rem_time = self._check_cooldown(user_id, "heal", COOLDOWN_HEAL)
        if not can_act:
            return False, f"⏳ Медикаменты распаковываются! Помощь будет готова через <b>{int(rem_time)} сек</b>.", None

        now = time.time()
        # Проверяем РЭБ
        if war.get("reb_active_until", 0) > now:
            return False, "📡 <b>Вражеский РЭБ глушит радиосвязь!</b> Координаты полевых раненых недоступны ещё некоторое время.", None

        # Находим раненого бойца
        target_soldier = None
        if target_user_id:
            target_soldier = my_soldiers.get(str(target_user_id))

        if not target_soldier:
            candidates = [s for s in my_soldiers.values() if s.get("status") in ("active", "wounded") and s.get("hp", 100) < 100]
            if candidates:
                candidates.sort(key=lambda x: (x.get("status") != "wounded", x.get("hp", 100)))
                target_soldier = candidates[0]

        if not target_soldier:
            return False, "💚 Все штурмовики вашей армии на передке в полном здравии (100% HP)!", None

        heal_amount = random.randint(35, 55)
        target_soldier["hp"] = min(100, target_soldier["hp"] + heal_amount)

        if target_soldier.get("status") == "wounded":
            target_soldier["status"] = "active"

        self._set_cooldown(user_id, "heal")

        army, m_info = self.army_manager.get_user_army(user_id)
        medic_name = m_info.get("name", "Полевой медик") if m_info else "Боец тыла"
        medic_link = get_user_link(user_id, medic_name)
        target_link = get_user_link(target_soldier["user_id"], target_soldier["name"])

        event_str = (
            f"💉 <b>ПОЛЕВАЯ МЕДИЦИНА!</b> {medic_link} оказал экстренную медпомощь штурмовику {target_link} "
            f"(+{heal_amount} HP, теперь {target_soldier['hp']}/100) и вернул бойца в строй!"
        )
        war["battle_log"].insert(0, event_str)
        war["battle_log"] = war["battle_log"][:10]
        self.save_wars()

        return True, event_str, war

    def execute_resupply(self, user_id: int) -> Tuple[bool, str, Optional[dict]]:
        """
        Действие тылового резерва: доставка боеприпасов и дронов на передовую (+30% урона).
        """
        army_key = self.army_manager.get_user_army_key(user_id)
        if not army_key:
            return False, "❌ Вы не состоите в армии.", None

        war = self.get_war_by_army(army_key)
        if not war or war.get("status") != "active":
            return False, "❌ Ваша армия сейчас не ведёт боевых действий на СВО.", None

        can_act, rem_time = self._check_cooldown(user_id, "resupply", COOLDOWN_RESUPPLY)
        if not can_act:
            return False, f"⏳ Колонна снабжения в пути! Повторный подвоз БК через <b>{int(rem_time)} сек</b>.", None

        now = time.time()
        if war.get("reb_active_until", 0) > now:
            return False, "📡 <b>Вражеский РЭБ подавил навигацию дронов и конвоев!</b> Подождите восстановления связи.", None

        side = "attacker" if war["attacker_key"] == army_key else "defender"
        war["support_buffs"][side]["resupply_until"] = now + 90
        self._set_cooldown(user_id, "resupply")

        army, m_info = self.army_manager.get_user_army(user_id)
        supplier_name = m_info.get("name", "Снабженец") if m_info else "Боец"
        user_link = get_user_link(user_id, supplier_name)

        event_str = (
            f"📦 <b>ПОДВОЗ БК И ДРОНОВ!</b> {user_link} успешно доставил партию боеприпасов "
            f"и FPV-дронов штурмовикам армии «{html.escape(war[f'{side}_name'])}»! (+30% к урону на 1.5 мин)."
        )
        war["battle_log"].insert(0, event_str)
        war["battle_log"] = war["battle_log"][:10]
        self.save_wars()

        return True, event_str, war

    def execute_commander_order(self, commander_id: int, order_type: str) -> Tuple[bool, str, Optional[dict]]:
        """
        Тактический приказ Главкома ('атака' или 'оборона').
        """
        army_key = self.army_manager.get_user_army_key(commander_id)
        if not army_key:
            return False, "❌ Вы не состоите в армии.", None

        war = self.get_war_by_army(army_key)
        if not war or war.get("status") != "active":
            return False, "❌ Ваша армия сейчас не ведёт боевых действий на СВО.", None

        army, m_info = self.army_manager.get_user_army(commander_id)
        if not m_info or m_info.get("rank") != RANK_CREATOR:
            return False, f"❌ Отдавать боевые приказы может только <b>{html.escape(RANK_CREATOR)}</b>!", None

        clean_order = order_type.strip().lower()
        if clean_order not in ("атака", "оборона", "штурм"):
            return False, "❌ Неизвестный тип приказа! Доступно: <code>/приказ атака</code> или <code>/приказ оборона</code>.", None

        can_act, rem_time = self._check_cooldown(commander_id, "order", COOLDOWN_COMMANDER)
        if not can_act:
            return False, f"⏳ Главком уже отдавал распоряжение! Перегруппировка возможна через <b>{int(rem_time)} сек</b>.", None

        now = time.time()
        side = "attacker" if war["attacker_key"] == army_key else "defender"
        mapped_order = "attack" if clean_order in ("атака", "штурм") else "defense"

        war["support_buffs"][side]["commander_order"] = mapped_order
        war["support_buffs"][side]["order_until"] = now + 60

        if mapped_order == "defense":
            for s in war[f"{side}_soldiers"].values():
                if s.get("status") == "active":
                    s["is_defending_until"] = max(s.get("is_defending_until", 0), now + 60)

        self._set_cooldown(commander_id, "order")

        commander_link = get_user_link(commander_id, m_info.get("name", "Главком"))
        order_desc = "ОБЩИЙ ШТУРМ (+40% урона штурмовикам)!" if mapped_order == "attack" else "ГЛУХАЯ КРУГОВАЯ ОБОРОНА (все окопались)!"

        event_str = f"📢 <b>БОЕВОЙ ПРИКАЗ ГЛАВКОМА!</b> {commander_link} объявил: <b>{order_desc}</b>"
        war["battle_log"].insert(0, event_str)
        war["battle_log"] = war["battle_log"][:10]
        self.save_wars()

        return True, event_str, war

    def execute_surrender(self, commander_id: int) -> Tuple[bool, str, Optional[dict]]:
        """
        Капитуляция армии: командующий признает поражение.
        """
        army_key = self.army_manager.get_user_army_key(commander_id)
        if not army_key:
            return False, "❌ Вы не состоите в армии.", None

        war = self.get_war_by_army(army_key)
        if not war or war.get("status") != "active":
            return False, "❌ Ваша армия сейчас не ведёт боевых действий на СВО.", None

        army, m_info = self.army_manager.get_user_army(commander_id)
        if not m_info or m_info.get("rank") != RANK_CREATOR:
            return False, f"❌ Объявить капитуляцию может только <b>{html.escape(RANK_CREATOR)}</b>!", None

        surrendering_side = "attacker" if war["attacker_key"] == army_key else "defender"
        winner_side = "defender" if surrendering_side == "attacker" else "attacker"

        my_soldiers = war[f"{surrendering_side}_soldiers"]
        active_soldiers = [s for s in my_soldiers.values() if s.get("status") in ("active", "wounded")]

        surrendered_pow_count = 0
        now = time.time()
        if active_soldiers:
            count_to_capture = max(1, int(len(active_soldiers) * 0.35))
            chosen = random.sample(active_soldiers, min(count_to_capture, len(active_soldiers)))
            for s in chosen:
                s["status"] = "captured"
                surrendered_pow_count += 1
                war["captured_soldiers"].append({
                    "user_id": s["user_id"],
                    "name": s["name"],
                    "from_army": war[f"{surrendering_side}_name"],
                    "captured_by": f"Капитуляция ({war[f'{winner_side}_name']})",
                    "captured_at": now
                })

        reason = (
            f"🏳️ <b>КАПИТУЛЯЦИЯ!</b> Главнокомандующий армии «{html.escape(war[f'{surrendering_side}_name'])}» "
            f"официально признал поражение и поднял белый флаг!\n"
            f"🎖️ {surrendered_pow_count} штурмовиков сдались в плен победителю."
        )

        finish_text = self.finish_war(war["war_id"], winner_side, reason, is_surrender=True)
        return True, finish_text, war

    def check_war_outcome(self, war_id: str) -> Tuple[bool, Optional[str], str]:
        """
        Проверка завершения СВО.
        """
        war = self.wars.get(war_id)
        if not war or war.get("status") != "active":
            return False, None, ""

        now = time.time()

        attacker_alive = any(s.get("status") in ("active", "wounded") for s in war["attacker_soldiers"].values())
        defender_alive = any(s.get("status") in ("active", "wounded") for s in war["defender_soldiers"].values())

        if not attacker_alive and not defender_alive:
            return True, "draw", "Обе армии полностью исчерпали свои штурмовые группы на передке. Боевая ничья!"

        if not attacker_alive:
            return True, "defender", f"Все штурмовики армии «{war['attacker_name']}» были разбиты или пленены!"

        if not defender_alive:
            return True, "attacker", f"Все штурмовики армии «{war['defender_name']}» были разбиты или пленены!"

        if now >= war["expires_at"]:
            att_dmg = sum(s.get("damage_dealt", 0) for s in war["attacker_soldiers"].values())
            def_dmg = sum(s.get("damage_dealt", 0) for s in war["defender_soldiers"].values())
            att_surv = sum(1 for s in war["attacker_soldiers"].values() if s.get("status") == "active")
            def_surv = sum(1 for s in war["defender_soldiers"].values() if s.get("status") == "active")

            att_score = att_dmg + (att_surv * 100)
            def_score = def_dmg + (def_surv * 100)

            if att_score > def_score:
                return True, "attacker", f"Время операции истекло! Армия «{war['attacker_name']}» победила по очкам фронтового превосходства ({att_score} vs {def_score})!"
            elif def_score > att_score:
                return True, "defender", f"Время операции истекло! Армия «{war['defender_name']}» победила по очкам фронтового превосходства ({def_score} vs {att_score})!"
            else:
                return True, "draw", "Время операции истекло! Полное равенство сил. Боевая ничья!"

        return False, None, ""

    def tick_war_events(self, war_id: str) -> Optional[str]:
        """
        Периодический тик для внешней балансировки и погодных явлений.
        """
        war = self.wars.get(war_id)
        if not war or war.get("status") != "active":
            return None

        now = time.time()
        event_text = None

        if now - war.get("last_weather_change", 0) > 180:
            war["last_weather_change"] = now
            weathers = [
                {"name": "☀️ Ясная погода", "effect": "none", "desc": "Прекрасная видимость. Обычный урон."},
                {"name": "🌫️ Густой туман", "effect": "fog", "desc": "Видимость нулевая! Точность снижена, урон штурмов -25%."},
                {"name": "🌧️ Проливной дождь и грязь", "effect": "mud", "desc": "Тяжелые условия. Техника завязла, укрытия промокли."},
                {"name": "💨 Шквальный ветер", "effect": "wind", "desc": "Дроны сбиваются с курса, артиллерия бьет с разбросом."}
            ]
            chosen_w = random.choice(weathers)
            war["weather"] = chosen_w
            event_text = f"🌦️ <b>ФРОНТОВАЯ ПОГОДА:</b> {chosen_w['name']}!\n<i>{chosen_w['desc']}</i>"
            war["battle_log"].insert(0, event_text)
            war["battle_log"] = war["battle_log"][:10]

        att_alive = [s for s in war["attacker_soldiers"].values() if s.get("status") in ("active", "wounded")]
        def_alive = [s for s in war["defender_soldiers"].values() if s.get("status") in ("active", "wounded")]

        if len(att_alive) > 0 and len(def_alive) > 0:
            ratio = max(len(att_alive), len(def_alive)) / min(len(att_alive), len(def_alive))
            if ratio >= 1.5 and (now - war.get("last_balance_event", 0) > 120):
                war["last_balance_event"] = now
                weaker_side = "attacker" if len(att_alive) < len(def_alive) else "defender"
                stronger_side = "defender" if weaker_side == "attacker" else "attacker"
                weaker_name = war[f"{weaker_side}_name"]
                stronger_name = war[f"{stronger_side}_name"]

                balance_type = random.choice(["lend_lease", "partisans", "reb"])
                if balance_type == "lend_lease":
                    for s in war[f"{weaker_side}_soldiers"].values():
                        if s.get("status") in ("active", "wounded"):
                            s["hp"] = min(100, s["hp"] + 30)
                            s["status"] = "active"
                    event_text = (
                        f"📦 <b>ВНЕШНЯЯ ПОДДЕРЖКА (ЛЕНД-ЛИЗ)!</b> Уступающая по численности армия «{html.escape(weaker_name)}» "
                        f"получила срочный гуманитарный конвой с медикаментами и бронежилетами! Все штурмовики подлечились (+30 HP)!"
                    )
                elif balance_type == "partisans":
                    targets = [s for s in war[f"{stronger_side}_soldiers"].values() if s.get("status") in ("active", "wounded")]
                    if targets:
                        victim = random.choice(targets)
                        victim["hp"] = max(1, victim["hp"] - 25)
                        event_text = (
                            f"💣 <b>ПАРТИЗАНСКАЯ ВЫЛАЗКА!</b> В тылу армии «{html.escape(stronger_name)}» сработала мина-ловушка! "
                            f"Штурмовик {html.escape(victim['name'])} контужен (-25 HP)!"
                        )
                else:
                    war["reb_active_until"] = now + 60
                    event_text = (
                        f"📡 <b>СИСТЕМА РЭБ ВКЛЮЧЕНА!</b> В зону боевых действий вошёл комплекс РЭБ «Красуха»! "
                        f"Радиосвязь тыла и наведение дронов заглушены на 60 секунд."
                    )

                if event_text:
                    war["battle_log"].insert(0, event_text)
                    war["battle_log"] = war["battle_log"][:10]

        self.save_wars()
        return event_text

    def finish_war(self, war_id: str, winner_side: str, reason: str, is_surrender: bool = False) -> str:
        """
        Завершение операции, распределение трофеев, зачисление военнопленных.
        """
        war = self.wars.get(war_id)
        if not war:
            return ""

        war["status"] = "finished"
        war["finished_at"] = time.time()
        war["finish_reason"] = reason

        att_key = war["attacker_key"]
        def_key = war["defender_key"]

        self.active_wars_by_army.pop(att_key, None)
        self.active_wars_by_army.pop(def_key, None)

        if winner_side == "draw":
            self.army_manager.record_war_result(att_key, def_key, 0.0, 0)
            self.army_manager.set_active_war(att_key, None)
            self.army_manager.set_active_war(def_key, None)
            self.save_wars()
            return f"🏳️ <b>СПЕЦИАЛЬНАЯ ВОЕННАЯ ОПЕРАЦИЯ ЗАВЕРШЕНА ВНИЧЬЮ!</b>\n\n{reason}"

        winner_key = war[f"{winner_side}_key"]
        loser_side = "defender" if winner_side == "attacker" else "attacker"
        loser_key = war[f"{loser_side}_key"]

        winner_name = war[f"{winner_side}_name"]
        loser_name = war[f"{loser_side}_name"]

        # 1. Расчет контрибуции
        loser_army = self.army_manager.get_army_by_name(loser_name) or {}
        loser_bank = loser_army.get("bank", 0.0)

        tribute_percent = 0.30 if is_surrender else 0.45
        looted_from_bank = round(loser_bank * tribute_percent, 2)
        base_war_bounty = 250.0
        total_loot = looted_from_bank + base_war_bounty

        # 2. Пленные: зачисляем захваченных штурмовиков в армию победителя
        captured_list = war.get("captured_soldiers", [])
        for cap in captured_list:
            self.army_manager.add_prisoner(winner_key, {
                "user_id": cap["user_id"],
                "name": cap["name"],
                "from_army": cap["from_army"],
                "captured_at": cap.get("captured_at", time.time()),
                "status": "prisoner"
            })

        self.army_manager.record_war_result(winner_key, loser_key, total_loot, len(captured_list))

        # 3. Награждаем лучшего штурмовика
        top_assault = None
        max_dmg = 0
        for s in war[f"{winner_side}_soldiers"].values():
            if s.get("damage_dealt", 0) > max_dmg:
                max_dmg = s.get("damage_dealt", 0)
                top_assault = s

        mvp_msg = ""
        if top_assault and max_dmg > 0:
            bonus = 100.0
            self.economy_manager.add_money(top_assault["user_id"], bonus)
            top_link = get_user_link(top_assault["user_id"], top_assault["name"])
            mvp_msg = f"\n🎖️ <b>Лучший штурмовик операции:</b> {top_link} ({max_dmg} урона) — награждён премией <b>{int(bonus)} монет</b>!"

        pow_summary = ""
        if captured_list:
            pow_names = [html.escape(c["name"]) for c in captured_list]
            pow_summary = f"\n⛓️ <b>Захвачено в плен бойцов противника ({len(captured_list)} чел.):</b> {', '.join(pow_names)}"

        report = (
            f"🏆 <b>ПОБЕДА В СПЕЦИАЛЬНОЙ ВОЕННОЙ ОПЕРАЦИИ!</b> 🏆\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Вооруженные Силы «<b>{html.escape(winner_name)}</b>» одержали триумфальную победу над «<b>{html.escape(loser_name)}</b>»!\n\n"
            f"📝 <b>Причина победы:</b> {reason}\n"
            f"💰 <b>Трофеи и контрибуция:</b> <b>{total_loot:.2f} монет</b> зачислено в казну победителя!\n"
            f"{pow_summary}"
            f"{mvp_msg}\n\n"
            f"🫡 Слава бойцам и командирам! СВО объявляется официально завершённой."
        )

        self.save_wars()
        return report

    def get_war_summary(self, user_id: int) -> Tuple[bool, str]:
        """
        Возвращает детальную фронтовую сводку СВО.
        """
        army_key = self.army_manager.get_user_army_key(user_id)
        if not army_key:
            return False, "❌ Вы не состоите ни в одной армии."

        war = self.get_war_by_army(army_key)
        if not war or war.get("status") != "active":
            return False, "❌ Ваша армия в данный момент не ведёт боевых действий на СВО."

        now = time.time()
        rem_sec = max(0, int(war["expires_at"] - now))
        rem_min = rem_sec // 60
        rem_s = rem_sec % 60

        att_name = war["attacker_name"]
        def_name = war["defender_name"]

        def format_soldiers(soldiers_dict):
            lines = []
            for s in soldiers_dict.values():
                st = s.get("status", "active")
                hp = s.get("hp", 0)
                link = get_user_link(s["user_id"], s["name"])
                is_def = " 🛡️(в окопе)" if s.get("is_defending_until", 0) > now else ""

                if st == "captured":
                    icon = "⛓️ [В ПЛЕНУ]"
                elif st == "kia":
                    icon = "💀 [ВЫБИТ]"
                elif st == "wounded":
                    icon = f"🩸 [РАНЕН {hp} HP]"
                else:
                    bar_cnt = max(1, hp // 10)
                    hp_bar = "🟩" * bar_cnt + "⬜" * (10 - bar_cnt)
                    icon = f"[{hp_bar} {hp} HP]"

                lines.append(f"• {link}: {icon}{is_def}")
            return "\n".join(lines) if lines else "<i>Нет бойцов</i>"

        att_list = format_soldiers(war["attacker_soldiers"])
        def_list = format_soldiers(war["defender_soldiers"])

        reb_line = ""
        if war.get("reb_active_until", 0) > now:
            reb_line = f"\n📡 <b>РЭБ:</b> активен (связь тыла заглушена ещё {int(war['reb_active_until'] - now)} с)!"

        logs = "\n".join(war.get("battle_log", [])[:6])

        summary_text = (
            f"⚔️ <b>ОПЕРАТИВНАЯ СВОДКА С ФРОНТА СВО</b> ⚔️\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🚩 <b>Стороны конфликта:</b>\n"
            f"🔴 Наступающие: «<b>{html.escape(att_name)}</b>»\n"
            f"🔵 Обороняющиеся: «<b>{html.escape(def_name)}</b>»\n\n"
            f"⏳ <b>До окончания операции:</b> <b>{rem_min:02d}:{rem_s:02d}</b>\n"
            f"🌦️ <b>Условия фронта:</b> {war['weather']['name']}{reb_line}\n\n"
            f"🎖️ <b>Линия соприкосновения «{html.escape(att_name)}»:</b>\n{att_list}\n\n"
            f"🎖️ <b>Линия соприкосновения «{html.escape(def_name)}»:</b>\n{def_list}\n\n"
            f"📜 <b>Хроника последних столкновений:</b>\n{logs}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Штурмовикам:</i> /штурм, /оборона\n"
            f"💡 <i>Тылу (рядовым):</i> /медпомощь, /снабжение\n"
            f"💡 <i>Главкому:</i> /приказ, /мобилизация, /капитуляция"
        )
        return True, summary_text
