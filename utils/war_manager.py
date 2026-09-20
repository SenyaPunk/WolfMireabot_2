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
COOLDOWN_DRONE = 40         # Удар дроном каждые 40 сек
COOLDOWN_REPAIR = 45        # Ремонт укрепрайона каждые 45 сек
COOLDOWN_EWAR = 120         # Постановка помех РЭБ каждые 120 сек

FORTRESS_HP_MAP = {0: 0, 1: 150, 2: 300, 3: 500, 4: 750, 5: 1100}


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

        # Загружаем улучшения обеих армий
        att_upgrades = self.army_manager.get_army_upgrades(attacker_key)
        def_upgrades = self.army_manager.get_army_upgrades(defender_key)

        # Проверяем боеспособность атакующего (штурмовики ИЛИ укрепрайон)
        attacker_members = user_army.get("members", {})
        attacker_mobilized = [m for m in attacker_members.values() if m.get("rank") == RANK_MOBILIZED]
        if not attacker_mobilized and att_upgrades.get("fortress", 0) == 0:
            return False, (
                f"❌ В вашей армии нет мобилизованных штурмовиков на передке и не возведён укрепрайон!\n"
                f"💡 Отправьте бойцов на передок (<code>/мобилизация [число]</code>) или постройте фортификации (<code>/прокачать база</code>)."
            ), None

        # Проверяем боеспособность защитника (штурмовики ИЛИ укрепрайон)
        defender_members = defender_army.get("members", {})
        defender_mobilized = [m for m in defender_members.values() if m.get("rank") == RANK_MOBILIZED]
        if not defender_mobilized and def_upgrades.get("fortress", 0) == 0:
            return False, (
                f"❌ Армия противника «<b>{html.escape(defender_army['name'])}</b>» не имеет ни штурмовиков (0 мобилизованных), ни укрепрайона!\n"
                f"💡 Подождите, пока их Главком проведёт мобилизацию или возведёт оборону."
            ), None

        now = time.time()
        war_id = f"svo_{int(now)}_{uuid.uuid4().hex[:6]}"

        att_med_lvl = att_upgrades.get("medicine", 0)
        def_med_lvl = def_upgrades.get("medicine", 0)
        att_max_hp = 100 + (att_med_lvl * 10)
        def_max_hp = 100 + (def_med_lvl * 10)

        # Формируем передовой состав обеих армий с учётом госпиталя
        def build_soldiers(mobilized_list, army_name, max_hp):
            res = {}
            for m in mobilized_list:
                uid = str(m["user_id"])
                res[uid] = {
                    "user_id": m["user_id"],
                    "name": m.get("name", "Боец"),
                    "army_name": army_name,
                    "hp": max_hp,
                    "max_hp": max_hp,
                    "is_defending_until": 0.0,
                    "status": "active",  # active, wounded, captured, kia
                    "damage_dealt": 0,
                    "kills": 0,
                    "assaults": 0
                }
            return res

        attacker_soldiers = build_soldiers(attacker_mobilized, user_army["name"], att_max_hp)
        defender_soldiers = build_soldiers(defender_mobilized, defender_army["name"], def_max_hp)

        att_fort_lvl = att_upgrades.get("fortress", 0)
        def_fort_lvl = def_upgrades.get("fortress", 0)
        att_fort_hp = FORTRESS_HP_MAP.get(att_fort_lvl, 0)
        def_fort_hp = FORTRESS_HP_MAP.get(def_fort_lvl, 0)

        att_resupply = (now + 90) if att_upgrades.get("logistics", 0) >= 4 else 0.0
        def_resupply = (now + 90) if def_upgrades.get("logistics", 0) >= 4 else 0.0

        att_desc = f"{len(attacker_soldiers)} штурмовиков" if attacker_soldiers else f"Укрепрайон ({att_fort_hp} HP)"
        def_desc = f"{len(defender_soldiers)} штурмовиков" if defender_soldiers else f"Укрепрайон ({def_fort_hp} HP)"

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
            "attacker_upgrades": att_upgrades,
            "defender_upgrades": def_upgrades,
            "attacker_fortress_hp": att_fort_hp,
            "attacker_max_fortress_hp": att_fort_hp,
            "defender_fortress_hp": def_fort_hp,
            "defender_max_fortress_hp": def_fort_hp,
            "support_buffs": {
                "attacker": {"resupply_until": att_resupply, "commander_order": None, "order_until": 0.0},
                "defender": {"resupply_until": def_resupply, "commander_order": None, "order_until": 0.0}
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
                f"⚔️ Линия фронта развёрнута: 🔴 «{html.escape(user_army['name'])}» ({att_desc}) против 🔵 «{html.escape(defender_army['name'])}» ({def_desc})."
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

        upgrades = war.get(f"{side}_upgrades", {})
        med_lvl = upgrades.get("medicine", 0)
        max_hp = 100 + (med_lvl * 10)

        added_names = []
        for m in new_members:
            uid = str(m["user_id"])
            if uid not in soldiers:
                soldiers[uid] = {
                    "user_id": m["user_id"],
                    "name": m.get("name", "Боец"),
                    "army_name": army_name,
                    "hp": max_hp,
                    "max_hp": max_hp,
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
        now = time.time()

        # Ищем доступные живые цели противника (active или wounded)
        targets = [t for t in enemy_soldiers.values() if t.get("status") in ("active", "wounded")]
        enemy_fort_hp = war.get(f"{enemy_side}_fortress_hp", 0)

        if not targets and enemy_fort_hp <= 0:
            return False, "🏁 Все силы противника разбиты, а укрепления полностью разрушены!", war

        shooter_link = get_user_link(user_id, soldier["name"])
        outcome_event = ""

        # Случай 1: Живых штурмовиков врага нет, но стоит укрепрайон!
        if not targets:
            base_damage = random.randint(28, 46)
            buffs = war["support_buffs"].get(side, {})
            if buffs.get("resupply_until", 0) > now:
                base_damage = int(base_damage * 1.30)
            if buffs.get("commander_order") == "attack" and buffs.get("order_until", 0) > now:
                base_damage = int(base_damage * 1.40)

            drone_lvl = war.get(f"{side}_upgrades", {}).get("drones", 0)
            if drone_lvl > 0:
                base_damage = int(base_damage * (1.0 + drone_lvl * 0.07))

            war[f"{enemy_side}_fortress_hp"] = max(0, enemy_fort_hp - base_damage)
            soldier["damage_dealt"] = soldier.get("damage_dealt", 0) + base_damage
            soldier["assaults"] = soldier.get("assaults", 0) + 1
            self._set_cooldown(user_id, "assault")

            rem_fort = war[f"{enemy_side}_fortress_hp"]
            max_fort = war.get(f"{enemy_side}_max_fortress_hp", 1)

            if rem_fort <= 0:
                outcome_event = (
                    f"💥 <b>УКРЕПРАЙОН ВРАГА ВЗЯТ ШТУРМОМ!</b> Штурмовик {shooter_link} прорвал оборонительный рубеж "
                    f"«{html.escape(war[f'{enemy_side}_name'])}» и уничтожил фортификации базы! Оборона пала!"
                )
            else:
                outcome_event = (
                    f"🏰 <b>ШТУРМ УКРЕПРАЙОНА!</b> Штурмовик {shooter_link} атаковал ДОТы и бункеры противника, "
                    f"нанеся {base_damage} урона укреплениям! (Прочность рубежа: {rem_fort}/{max_fort} HP)."
                )

            war["battle_log"].insert(0, outcome_event)
            war["battle_log"] = war["battle_log"][:10]
            self.save_wars()

            finished, win_side, reason = self.check_war_outcome(war["war_id"])
            if finished:
                finish_msg = self.finish_war(war["war_id"], win_side, reason)
                return True, f"{outcome_event}\n\n{finish_msg}", war
            return True, outcome_event, war

        # Случай 2: Атака по живым штурмовикам
        target = random.choice(targets)

        # Расчет урона с учетом бонусов дронов и баффов
        base_damage = random.randint(22, 38)
        drone_lvl = war.get(f"{side}_upgrades", {}).get("drones", 0)
        if drone_lvl > 0:
            base_damage = int(base_damage * (1.0 + drone_lvl * 0.07))

        buffs = war["support_buffs"].get(side, {})
        if buffs.get("resupply_until", 0) > now:
            base_damage = int(base_damage * 1.30)
        if buffs.get("commander_order") == "attack" and buffs.get("order_until", 0) > now:
            base_damage = int(base_damage * 1.40)

        # Защита цели (глухая оборона -50%)
        is_defending = target.get("is_defending_until", 0) > now
        if is_defending:
            base_damage = max(8, int(base_damage * 0.50))

        # Снижение урона от укрепрайона врага (до 30%)
        fort_lvl = war.get(f"{enemy_side}_upgrades", {}).get("fortress", 0)
        if fort_lvl > 0:
            base_damage = max(6, int(base_damage * (1.0 - min(0.30, fort_lvl * 0.05))))

        # Погода
        weather = war.get("weather", {})
        if weather.get("effect") == "fog":
            base_damage = max(10, int(base_damage * 0.75))

        target["hp"] = max(0, target["hp"] - base_damage)
        soldier["damage_dealt"] = soldier.get("damage_dealt", 0) + base_damage
        soldier["assaults"] = soldier.get("assaults", 0) + 1

        self._set_cooldown(user_id, "assault")
        target_link = get_user_link(target["user_id"], target["name"])

        # Обработка исхода удара с учётом спасения госпиталем
        med_lvl = war.get(f"{enemy_side}_upgrades", {}).get("medicine", 0)

        if target["hp"] <= 0:
            if med_lvl >= 3 and random.random() < 0.35:
                target["hp"] = 15
                target["status"] = "wounded"
                outcome_event = (
                    f"🏥 <b>ГОСПИТАЛЬ СПАС БОЙЦА!</b> Штурмовик {shooter_link} нанёс смертельный удар {target_link}, "
                    f"но военные хирурги врага экстренно эвакуировали бойца (осталось 15 HP, тяжело ранен)!"
                )
            else:
                soldier["kills"] = soldier.get("kills", 0) + 1
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
        upgrades = war.get(f"{side}_upgrades", {})
        med_lvl = upgrades.get("medicine", 0)

        heal_cd = 20 if med_lvl >= 2 else COOLDOWN_HEAL
        can_act, rem_time = self._check_cooldown(user_id, "heal", heal_cd)
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
            candidates = [
                s for s in my_soldiers.values()
                if s.get("status") in ("active", "wounded") and s.get("hp", s.get("max_hp", 100)) < s.get("max_hp", 100)
            ]
            if candidates:
                candidates.sort(key=lambda x: (x.get("status") != "wounded", x.get("hp", 100)))
                target_soldier = candidates[0]

        if not target_soldier:
            return False, "💚 Все штурмовики вашей армии на передке в полном здравии (100% HP)!", None

        max_h = target_soldier.get("max_hp", 100)
        if med_lvl >= 5:
            target_soldier["hp"] = max_h
            heal_amount = max_h
        else:
            heal_amount = random.randint(35, 55) + (med_lvl * 12)
            target_soldier["hp"] = min(max_h, target_soldier["hp"] + heal_amount)

        if target_soldier.get("status") == "wounded":
            target_soldier["status"] = "active"

        self._set_cooldown(user_id, "heal")

        army, m_info = self.army_manager.get_user_army(user_id)
        medic_name = m_info.get("name", "Полевой медик") if m_info else "Боец тыла"
        medic_link = get_user_link(user_id, medic_name)
        target_link = get_user_link(target_soldier["user_id"], target_soldier["name"])

        event_str = (
            f"💉 <b>ПОЛЕВАЯ МЕДИЦИНА!</b> {medic_link} оказал экстренную медпомощь штурмовику {target_link} "
            f"(+{heal_amount} HP, теперь {target_soldier['hp']}/{max_h}) и вернул бойца в строй!"
        )
        war["battle_log"].insert(0, event_str)
        war["battle_log"] = war["battle_log"][:10]
        self.save_wars()

        return True, event_str, war

    def execute_resupply(self, user_id: int) -> Tuple[bool, str, Optional[dict]]:
        """
        Действие тылового резерва: доставка боеприпасов и снаряжения (+30% или +40% урона).
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
            return False, "📡 <b>Вражеский РЭБ подавил навигацию конвоев!</b> Подождите восстановления связи.", None

        side = "attacker" if war["attacker_key"] == army_key else "defender"
        log_lvl = war.get(f"{side}_upgrades", {}).get("logistics", 0)

        duration = 120 if log_lvl >= 1 else 90
        dmg_text = "+40% к урону" if log_lvl >= 2 else "+30% к урону"

        war["support_buffs"][side]["resupply_until"] = now + duration
        self._set_cooldown(user_id, "resupply")

        army, m_info = self.army_manager.get_user_army(user_id)
        supplier_name = m_info.get("name", "Снабженец") if m_info else "Боец"
        user_link = get_user_link(user_id, supplier_name)

        event_str = (
            f"📦 <b>ПОДВОЗ БК И СНАРЯЖЕНИЯ!</b> {user_link} успешно доставил партию боеприпасов "
            f"штурмовикам армии «{html.escape(war[f'{side}_name'])}»! ({dmg_text} на {duration} сек)."
        )
        war["battle_log"].insert(0, event_str)
        war["battle_log"] = war["battle_log"][:10]
        self.save_wars()

        return True, event_str, war

    def execute_drone_strike(self, user_id: int) -> Tuple[bool, str, Optional[dict]]:
        """
        Запуск боевого ударного дрона / FPV-камикадзе.
        Доступно штурмовикам, рядовым и Главкому при наличии улучшения «Дронопарк».
        """
        war, side, soldier = self.get_user_war(user_id)
        if not war:
            army_key = self.army_manager.get_user_army_key(user_id)
            if not army_key:
                return False, "❌ Вы не состоите ни в одной армии.", None
            war = self.get_war_by_army(army_key)
            if not war or war.get("status") != "active":
                return False, "❌ Ваша армия сейчас не ведёт боевых действий на СВО.", None
            side = "attacker" if war["attacker_key"] == army_key else "defender"
            soldier = None

        upgrades = war.get(f"{side}_upgrades", {})
        drone_lvl = upgrades.get("drones", 0)
        if drone_lvl <= 0:
            return False, (
                "❌ <b>В вашей армии не закуплены боевые дроны!</b>\n"
                "Главнокомандующий может открыть дронопарк в меню улучшений: <code>/прокачать дрон</code>."
            ), None

        ewar_lvl = upgrades.get("ewar", 0)
        drone_cd = 32 if ewar_lvl >= 2 else COOLDOWN_DRONE
        can_act, rem_time = self._check_cooldown(user_id, "drone", drone_cd)
        if not can_act:
            return False, f"⏳ <b>Дроны на перезарядке!</b> Следующий вылет через <b>{int(rem_time)} сек</b>.", None

        now = time.time()
        # Проверка глушения РЭБ
        if war.get("reb_active_until", 0) > now:
            return False, "📡 <b>Вражеский РЭБ глушит радиочастоты наведения!</b> Удар дроном невозможен.", None

        enemy_side = "defender" if side == "attacker" else "attacker"
        enemy_upgrades = war.get(f"{enemy_side}_upgrades", {})
        enemy_ewar = enemy_upgrades.get("ewar", 0)

        army, m_info = self.army_manager.get_user_army(user_id)
        operator_name = m_info.get("name", "Оператор БПЛА") if m_info else "Боец"
        operator_link = get_user_link(user_id, operator_name)

        # Проверка перехвата вражеским РЭБ
        intercept_chances = {0: 0.0, 1: 0.25, 2: 0.30, 3: 0.45, 4: 0.60, 5: 0.75}
        intercept_p = intercept_chances.get(enemy_ewar, 0.0)

        self._set_cooldown(user_id, "drone")

        if random.random() < intercept_p:
            if enemy_ewar == 5:
                # Взлом и разворот дрона обратно!
                reflected_damage = random.randint(30, 50)
                my_targets = [s for s in war[f"{side}_soldiers"].values() if s.get("status") in ("active", "wounded")]
                if my_targets:
                    vic = random.choice(my_targets)
                    vic["hp"] = max(1, vic["hp"] - reflected_damage)
                    v_link = get_user_link(vic["user_id"], vic["name"])
                    event_str = (
                        f"📡💥 <b>ВРАЖЕСКИЙ РЭБ «КРАСУХА-4» ПЕРЕХВАТИЛ ДРОН!</b>\n"
                        f"Противник перехватил радиосигнал {operator_link}, развернул FPV-дрон "
                        f"и поразил своего же бойца {v_link} (-{reflected_damage} HP)!"
                    )
                else:
                    war[f"{side}_fortress_hp"] = max(0, war.get(f"{side}_fortress_hp", 0) - reflected_damage)
                    event_str = (
                        f"📡💥 <b>ПЕРЕХВАТ ДРОНА «КРАСУХОЙ-4»!</b>\n"
                        f"Противник перехватил управление дроном {operator_link} и взорвал его над вашим укрепрайоном (-{reflected_damage} HP базы)!"
                    )
                war["battle_log"].insert(0, event_str)
                war["battle_log"] = war["battle_log"][:10]
                self.save_wars()
                return True, event_str, war
            else:
                event_str = (
                    f"📡 <b>ВРАЖЕСКИЙ РЭБ СБИЛ ДРОН!</b> Запущенный {operator_link} беспилотник "
                    f"потерял управление под помехами РЭБ армии «{html.escape(war[f'{enemy_side}_name'])}» и рухнул в овраг."
                )
                war["battle_log"].insert(0, event_str)
                war["battle_log"] = war["battle_log"][:10]
                self.save_wars()
                return True, event_str, war

        # Базовый урон дрона по уровню
        dmg_ranges = {1: (18, 28), 2: (28, 42), 3: (38, 58), 4: (50, 72), 5: (65, 100)}
        min_d, max_d = dmg_ranges.get(drone_lvl, (20, 35))
        drone_damage = random.randint(min_d, max_d)

        # Выбираем цель (живой штурмовик или укрепрайон врага)
        enemy_soldiers = war[f"{enemy_side}_soldiers"]
        targets = [t for t in enemy_soldiers.values() if t.get("status") in ("active", "wounded")]
        enemy_fort_hp = war.get(f"{enemy_side}_fortress_hp", 0)

        if not targets and enemy_fort_hp <= 0:
            return False, "🏁 Все силы противника разбиты и укрепления уничтожены!", war

        outcome_event = ""
        if targets:
            target = random.choice(targets)
            is_defending = target.get("is_defending_until", 0) > now
            # Дроны 4-5 уровня игнорируют окоп
            if is_defending and drone_lvl < 4:
                drone_damage = max(10, int(drone_damage * 0.65))

            target["hp"] = max(0, target["hp"] - drone_damage)
            if soldier:
                soldier["damage_dealt"] = soldier.get("damage_dealt", 0) + drone_damage

            target_link = get_user_link(target["user_id"], target["name"])

            if target["hp"] <= 0:
                # Спасение госпиталем
                if enemy_upgrades.get("medicine", 0) >= 3 and random.random() < 0.35:
                    target["hp"] = 15
                    target["status"] = "wounded"
                    outcome_event = (
                        f"🛸 <b>ТОЧНЫЙ ПРИЛЁТ FPV-ДРОНА!</b> {operator_link} нанёс сокрушительный удар по {target_link} "
                        f"(-{drone_damage} HP)! 🏥 Но полевой госпиталь врага чудом эвакуировал раненого бойца!"
                    )
                else:
                    target["status"] = "kia"
                    if soldier:
                        soldier["kills"] = soldier.get("kills", 0) + 1
                    outcome_event = (
                        f"💥 <b>ДРОН УНИЧТОЖИЛ ЦЕЛЬ!</b> {operator_link} мастерски поразил {target_link} "
                        f"прямым попаданием кумулятивного дрона (-{drone_damage} HP)! Боец выведен из строя!"
                    )
            elif target["hp"] <= 25 and target["status"] != "wounded":
                target["status"] = "wounded"
                outcome_event = (
                    f"🩸 <b>ДРОНОВЫЙ НАЛЁТ!</b> {operator_link} сбросил боеприпас на позиции {target_link} "
                    f"(-{drone_damage} HP, тяжело ранен)! Бойцу требуется медик."
                )
            else:
                outcome_event = (
                    f"🛸 <b>УДАР БПЛА!</b> {operator_link} спикировал дроном на окоп {target_link}, "
                    f"нанеся {drone_damage} урона! (Осталось {target['hp']} HP)."
                )

            # Рой ИИ-дронов (ур. 5): сплит-урон по второй цели
            if drone_lvl == 5:
                other_targets = [t for t in targets if t["user_id"] != target["user_id"]]
                if other_targets:
                    sec_t = random.choice(other_targets)
                    sec_dmg = random.randint(25, 45)
                    sec_t["hp"] = max(1, sec_t["hp"] - sec_dmg)
                    sec_link = get_user_link(sec_t["user_id"], sec_t["name"])
                    outcome_event += f"\n🤖 <b>Рой дронов</b> также зацепил {sec_link} (-{sec_dmg} HP)!"
        else:
            # Атакуем укрепрайон базы
            war[f"{enemy_side}_fortress_hp"] = max(0, enemy_fort_hp - drone_damage)
            rem_f = war[f"{enemy_side}_fortress_hp"]
            max_f = war.get(f"{enemy_side}_max_fortress_hp", 1)
            if rem_f <= 0:
                outcome_event = (
                    f"💥 <b>ФОРТИФИКАЦИИ ВРАГА РАЗНЕСЕНЫ В ЩЕПКИ!</b> {operator_link} нанёс массированный удар дронами "
                    f"по главному бункеру армии «{html.escape(war[f'{enemy_side}_name'])}» (-{drone_damage} HP)! Укрепрайон пал!"
                )
            else:
                outcome_event = (
                    f"🛸 <b>БОМБАРДИРОВКА УКРЕПРАЙОНА!</b> {operator_link} сбросил тяжелые боеприпасы на ДОТы врага "
                    f"(-{drone_damage} HP укреплений)! Прочность базы: {rem_f}/{max_f} HP."
                )

        war["battle_log"].insert(0, outcome_event)
        war["battle_log"] = war["battle_log"][:10]
        self.save_wars()

        finished, win_side, reason = self.check_war_outcome(war["war_id"])
        if finished:
            finish_msg = self.finish_war(war["war_id"], win_side, reason)
            return True, f"{outcome_event}\n\n{finish_msg}", war

        return True, outcome_event, war

    def execute_repair_fortress(self, user_id: int) -> Tuple[bool, str, Optional[dict]]:
        """
        Действие тыла / главкома: инженерно-сапёрный ремонт укрепрайона базы.
        """
        army_key = self.army_manager.get_user_army_key(user_id)
        if not army_key:
            return False, "❌ Вы не состоите ни в одной армии.", None

        war = self.get_war_by_army(army_key)
        if not war or war.get("status") != "active":
            return False, "❌ Ваша армия сейчас не ведёт боевых действий на СВО.", None

        side = "attacker" if war["attacker_key"] == army_key else "defender"
        upgrades = war.get(f"{side}_upgrades", {})
        fort_lvl = upgrades.get("fortress", 0)

        if fort_lvl <= 0:
            return False, (
                "❌ <b>У вашей армии нет укрепрайона!</b>\n"
                "Главнокомандующий может возвести оборонительный рубеж: <code>/прокачать база</code>."
            ), None

        can_act, rem_time = self._check_cooldown(user_id, "repair", COOLDOWN_REPAIR)
        if not can_act:
            return False, f"⏳ <b>Сапёры укрепляют позиции!</b> Следующий ремонт через <b>{int(rem_time)} сек</b>.", None

        cur_hp = war.get(f"{side}_fortress_hp", 0)
        max_hp = war.get(f"{side}_max_fortress_hp", FORTRESS_HP_MAP.get(fort_lvl, 150))

        if cur_hp >= max_hp:
            return False, f"🏰 <b>Укрепрайон в идеальном состоянии ({cur_hp}/{max_hp} HP)!</b> Ремонт не требуется.", None

        repair_amount = random.randint(40, 65) + (fort_lvl * 15)
        new_hp = min(max_hp, cur_hp + repair_amount)
        actual_repaired = new_hp - cur_hp
        war[f"{side}_fortress_hp"] = new_hp

        self._set_cooldown(user_id, "repair")

        army, m_info = self.army_manager.get_user_army(user_id)
        user_name = m_info.get("name", "Инженер") if m_info else "Боец"
        user_link = get_user_link(user_id, user_name)

        bar_cnt = max(1, min(10, int(new_hp / max_hp * 10)))
        fort_bar = "🟩" * bar_cnt + "⬜" * (10 - bar_cnt)

        event_str = (
            f"🛠️ <b>ИНЖЕНЕРНО-САПЁРНЫЕ РАБОТЫ!</b> {user_link} заделал бреши в ДОТах "
            f"и восстановил укрепления рубежа (+{actual_repaired} HP, теперь [{fort_bar}] {new_hp}/{max_hp} HP)!"
        )

        war["battle_log"].insert(0, event_str)
        war["battle_log"] = war["battle_log"][:10]
        self.save_wars()

        return True, event_str, war

    def execute_ewar_pulse(self, user_id: int) -> Tuple[bool, str, Optional[dict]]:
        """
        Ручная активация направленного импульса РЭБ (требует 4+ уровень РЭБ).
        """
        army_key = self.army_manager.get_user_army_key(user_id)
        if not army_key:
            return False, "❌ Вы не состоите ни в одной армии.", None

        war = self.get_war_by_army(army_key)
        if not war or war.get("status") != "active":
            return False, "❌ Ваша армия сейчас не ведёт боевых действий на СВО.", None

        side = "attacker" if war["attacker_key"] == army_key else "defender"
        upgrades = war.get(f"{side}_upgrades", {})
        ewar_lvl = upgrades.get("ewar", 0)

        if ewar_lvl < 4:
            return False, (
                "❌ <b>Требуется комплекс РЭБ 4-го уровня или выше!</b>\n"
                "Главнокомандующий может прокачать системы подавления: <code>/прокачать рэб</code>."
            ), None

        can_act, rem_time = self._check_cooldown(user_id, "ewar", COOLDOWN_EWAR)
        if not can_act:
            return False, f"⏳ <b>Генераторы РЭБ остывают!</b> Следующий импульс через <b>{int(rem_time)} сек</b>.", None

        now = time.time()
        war["reb_active_until"] = now + 45
        self._set_cooldown(user_id, "ewar")

        army, m_info = self.army_manager.get_user_army(user_id)
        user_name = m_info.get("name", "Оператор РЭБ") if m_info else "Боец"
        user_link = get_user_link(user_id, user_name)

        enemy_side = "defender" if side == "attacker" else "attacker"
        event_str = (
            f"📡⚡ <b>МОЩНЫЙ ИМПУЛЬС СИСТЕМЫ РЭБ!</b> {user_link} активировал станцию радиоэлектронного подавления!\n"
            f"Радиосвязь, наведение дронов и снабжение армии «{html.escape(war[f'{enemy_side}_name'])}» заглушены на 45 секунд!"
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

        side = "attacker" if war["attacker_key"] == army_key else "defender"
        ewar_lvl = war.get(f"{side}_upgrades", {}).get("ewar", 0)
        order_cd = 75 if ewar_lvl >= 2 else COOLDOWN_COMMANDER

        can_act, rem_time = self._check_cooldown(commander_id, "order", order_cd)
        if not can_act:
            return False, f"⏳ Главком уже отдавал распоряжение! Перегруппировка возможна через <b>{int(rem_time)} сек</b>.", None

        now = time.time()
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
        Армия держится, пока живы её штурмовики ИЛИ цел её укрепрайон!
        """
        war = self.wars.get(war_id)
        if not war or war.get("status") != "active":
            return False, None, ""

        now = time.time()

        attacker_alive = any(s.get("status") in ("active", "wounded") for s in war["attacker_soldiers"].values())
        defender_alive = any(s.get("status") in ("active", "wounded") for s in war["defender_soldiers"].values())

        att_fort_hp = war.get("attacker_fortress_hp", 0)
        def_fort_hp = war.get("defender_fortress_hp", 0)

        attacker_down = (not attacker_alive) and (att_fort_hp <= 0)
        defender_down = (not defender_alive) and (def_fort_hp <= 0)

        if attacker_down and defender_down:
            return True, "draw", "Обе армии полностью исчерпали свои штурмовые группы и оборонительные рубежи. Боевая ничья!"

        if attacker_down:
            return True, "defender", f"Все штурмовики армии «{war['attacker_name']}» разбиты, а оборонительный рубеж полностью сокрушён!"

        if defender_down:
            return True, "attacker", f"Все штурмовики армии «{war['defender_name']}» разбиты, а оборонительный рубеж полностью сокрушён!"

        if now >= war["expires_at"]:
            att_dmg = sum(s.get("damage_dealt", 0) for s in war["attacker_soldiers"].values())
            def_dmg = sum(s.get("damage_dealt", 0) for s in war["defender_soldiers"].values())
            att_surv = sum(1 for s in war["attacker_soldiers"].values() if s.get("status") == "active")
            def_surv = sum(1 for s in war["defender_soldiers"].values() if s.get("status") == "active")

            att_score = att_dmg + (att_surv * 100) + int(att_fort_hp * 0.8)
            def_score = def_dmg + (def_surv * 100) + int(def_fort_hp * 0.8)

            if att_score > def_score:
                return True, "attacker", f"Время операции истекло! Армия «{war['attacker_name']}» победила по очкам фронтового превосходства ({att_score} vs {def_score})!"
            elif def_score > att_score:
                return True, "defender", f"Время операции истекло! Армия «{war['defender_name']}» победила по очкам фронтового превосходства ({def_score} vs {att_score})!"
            else:
                return True, "draw", "Время операции истекло! Полное равенство сил и укреплений. Боевая ничья!"

        return False, None, ""

    def tick_war_events(self, war_id: str) -> Optional[str]:
        """
        Периодический тик: погода, ленд-лиз, огонь турелей укрепрайона (ур. 3+) и регенерация госпиталя (ур. 4+).
        """
        war = self.wars.get(war_id)
        if not war or war.get("status") != "active":
            return None

        now = time.time()
        event_text = None

        # 1. Автоматический огонь турелей укрепрайонов (ур. 3+)
        for s_key, opp_key in (("attacker", "defender"), ("defender", "attacker")):
            f_lvl = war.get(f"{s_key}_upgrades", {}).get("fortress", 0)
            f_hp = war.get(f"{s_key}_fortress_hp", 0)
            last_t = war.get(f"last_turret_{s_key}", 0)
            if f_lvl >= 3 and f_hp > 0 and (now - last_t > 40):
                war[f"last_turret_{s_key}"] = now
                opp_targets = [s for s in war[f"{opp_key}_soldiers"].values() if s.get("status") in ("active", "wounded")]
                if opp_targets:
                    vic = random.choice(opp_targets)
                    turret_dmg = random.randint(14, 26) if f_lvl < 5 else random.randint(24, 40)
                    vic["hp"] = max(0, vic["hp"] - turret_dmg)
                    vic_link = get_user_link(vic["user_id"], vic["name"])
                    if vic["hp"] <= 0:
                        vic["status"] = "kia"
                        turret_event = (
                            f"🏰💥 <b>ТУРЕЛИ УКРЕПРАЙОНА!</b> Автоматические пулемётные гнёзда базы «{html.escape(war[f'{s_key}_name'])}» "
                            f"открыли огонь и сразили {vic_link} (-{turret_dmg} HP)! Боец выбит!"
                        )
                    else:
                        turret_event = (
                            f"🏰🎯 <b>ОГОНЬ ТУРЕЛЕЙ!</b> Оборонительный рубеж «{html.escape(war[f'{s_key}_name'])}» "
                            f"накрыл пулемётным огнём {vic_link} (-{turret_dmg} HP, осталось {vic['hp']} HP)!"
                        )
                    war["battle_log"].insert(0, turret_event)
                    war["battle_log"] = war["battle_log"][:10]
                    event_text = turret_event

        # 2. Пассивная регенерация полевого госпиталя (ур. 4+)
        for s_key in ("attacker", "defender"):
            m_lvl = war.get(f"{s_key}_upgrades", {}).get("medicine", 0)
            last_m = war.get(f"last_regen_{s_key}", 0)
            if m_lvl >= 4 and (now - last_m > 50):
                war[f"last_regen_{s_key}"] = now
                healed_any = False
                for s in war[f"{s_key}_soldiers"].values():
                    max_h = s.get("max_hp", 100)
                    if s.get("status") in ("active", "wounded") and s.get("hp", max_h) < max_h:
                        s["hp"] = min(max_h, s["hp"] + 12)
                        if s["hp"] > 25 and s.get("status") == "wounded":
                            s["status"] = "active"
                        healed_any = True
                if healed_any and not event_text:
                    regen_event = (
                        f"🏥 <b>ГОСПИТАЛЬ:</b> Полевые врачи армии «{html.escape(war[f'{s_key}_name'])}» "
                        f"стабилизировали состояние раненых бойцов (+12 HP)!"
                    )
                    war["battle_log"].insert(0, regen_event)
                    war["battle_log"] = war["battle_log"][:10]
                    event_text = regen_event

        # 3. Погода
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
            w_text = f"🌦️ <b>ФРОНТОВАЯ ПОГОДА:</b> {chosen_w['name']}!\n<i>{chosen_w['desc']}</i>"
            war["battle_log"].insert(0, w_text)
            war["battle_log"] = war["battle_log"][:10]
            if not event_text:
                event_text = w_text

        # 4. Внешний ленд-лиз аутсайдеру
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
                            max_h = s.get("max_hp", 100)
                            s["hp"] = min(max_h, s["hp"] + 30)
                            s["status"] = "active"
                    event_text = (
                        f"📦 <b>ВНЕШНЯЯ ПОДДЕРЖКА (ЛЕНД-ЛИЗ)!</b> Уступающая по силам армия «{html.escape(weaker_name)}» "
                        f"получила гуманитарный конвой с медикаментами! Все штурмовики подлечились (+30 HP)!"
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
        Завершение операции, распределение трофеев с учётом логистики, зачисление военнопленных.
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

        # 1. Расчет контрибуции с учётом прокачки логистики победителя
        winner_upgrades = war.get(f"{winner_side}_upgrades", {})
        log_lvl = winner_upgrades.get("logistics", 0)

        loot_mult = 1.0
        if log_lvl >= 5:
            loot_mult = 1.30
        elif log_lvl >= 3:
            loot_mult = 1.15

        loser_army = self.army_manager.get_army_by_name(loser_name) or {}
        loser_bank = loser_army.get("bank", 0.0)

        tribute_percent = 0.30 if is_surrender else 0.45
        looted_from_bank = round(loser_bank * tribute_percent, 2)
        base_war_bounty = 250.0
        total_loot = round((looted_from_bank + base_war_bounty) * loot_mult, 2)

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

        # 3. Награждаем лучшего бойца
        top_assault = None
        max_dmg = 0
        for s in war[f"{winner_side}_soldiers"].values():
            if s.get("damage_dealt", 0) > max_dmg:
                max_dmg = s.get("damage_dealt", 0)
                top_assault = s

        mvp_msg = ""
        if top_assault and max_dmg > 0:
            bonus = 250.0 if log_lvl >= 5 else 100.0
            self.economy_manager.add_money(top_assault["user_id"], bonus)
            top_link = get_user_link(top_assault["user_id"], top_assault["name"])
            mvp_msg = f"\n🎖️ <b>Лучший штурмовик операции:</b> {top_link} ({max_dmg} урона) — награждён премией <b>{int(bonus)} монет</b>!"

        pow_summary = ""
        if captured_list:
            pow_names = [html.escape(c["name"]) for c in captured_list]
            pow_summary = f"\n⛓️ <b>Захвачено в плен бойцов противника ({len(captured_list)} чел.):</b> {', '.join(pow_names)}"

        loot_bonus_note = f" (включая бонус логистики +{int((loot_mult - 1) * 100)}%)" if loot_mult > 1.0 else ""

        report = (
            f"🏆 <b>ПОБЕДА В СПЕЦИАЛЬНОЙ ВОЕННОЙ ОПЕРАЦИИ!</b> 🏆\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Вооруженные Силы «<b>{html.escape(winner_name)}</b>» одержали триумфальную победу над «<b>{html.escape(loser_name)}</b>»!\n\n"
            f"📝 <b>Причина победы:</b> {reason}\n"
            f"💰 <b>Трофеи и контрибуция:</b> <b>{total_loot:.2f} монет</b>{loot_bonus_note} зачислено в казну победителя!\n"
            f"{pow_summary}"
            f"{mvp_msg}\n\n"
            f"🫡 Слава бойцам и командирам! СВО объявляется официально завершённой."
        )

        self.save_wars()
        return report

    def get_war_summary(self, user_id: int) -> Tuple[bool, str]:
        """
        Возвращает детальную фронтовую сводку СВО с укреплениями и технологиями.
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
                max_h = s.get("max_hp", 100)
                link = get_user_link(s["user_id"], s["name"])
                is_def = " 🛡️(в окопе)" if s.get("is_defending_until", 0) > now else ""

                if st == "captured":
                    icon = "⛓️ [В ПЛЕНУ]"
                elif st == "kia":
                    icon = "💀 [ВЫБИТ]"
                elif st == "wounded":
                    icon = f"🩸 [РАНЕН {hp}/{max_h} HP]"
                else:
                    bar_cnt = max(1, min(10, int(hp / max_h * 10))) if max_h > 0 else 1
                    hp_bar = "🟩" * bar_cnt + "⬜" * (10 - bar_cnt)
                    icon = f"[{hp_bar} {hp}/{max_h} HP]"

                lines.append(f"• {link}: {icon}{is_def}")
            return "\n".join(lines) if lines else "<i>Штурмовиков нет на передке</i>"

        def format_fortress(side_key):
            hp = war.get(f"{side_key}_fortress_hp", 0)
            max_h = war.get(f"{side_key}_max_fortress_hp", 0)
            upgrades = war.get(f"{side_key}_upgrades", {})
            f_lvl = upgrades.get("fortress", 0)
            if f_lvl <= 0:
                return "<i>🏰 Укрепрайон не возведён</i>"
            if hp <= 0:
                return "<i>🏰 Укрепрайон: [💥 СОКРУШЁН]</i>"
            bar_cnt = max(1, min(10, int(hp / max_h * 10))) if max_h > 0 else 1
            bar = "🟩" * bar_cnt + "⬜" * (10 - bar_cnt)
            turret_note = " 🎯(Турели активны)" if f_lvl >= 3 else ""
            return f"🏰 <b>Укрепрайон:</b> [{bar}] <b>{hp}/{max_h} HP</b>{turret_note}"

        def format_tech(side_key):
            u = war.get(f"{side_key}_upgrades", {})
            return f"🛸 Дроны {u.get('drones',0)} | 🏰 Форт {u.get('fortress',0)} | 🏥 Мед {u.get('medicine',0)} | 📡 РЭБ {u.get('ewar',0)}"

        att_list = format_soldiers(war["attacker_soldiers"])
        def_list = format_soldiers(war["defender_soldiers"])
        att_fort = format_fortress("attacker")
        def_fort = format_fortress("defender")
        att_tech = format_tech("attacker")
        def_tech = format_tech("defender")

        reb_line = ""
        if war.get("reb_active_until", 0) > now:
            reb_line = f"\n📡 <b>РЭБ:</b> активен (связь тыла и дроны заглушены ещё {int(war['reb_active_until'] - now)} с)!"

        logs = "\n".join(war.get("battle_log", [])[:6])

        summary_text = (
            f"⚔️ <b>ОПЕРАТИВНАЯ СВОДКА С ФРОНТА СВО</b> ⚔️\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🚩 <b>Стороны конфликта:</b>\n"
            f"🔴 Наступающие: «<b>{html.escape(att_name)}</b>» [{att_tech}]\n"
            f"   └ {att_fort}\n"
            f"🔵 Обороняющиеся: «<b>{html.escape(def_name)}</b>» [{def_tech}]\n"
            f"   └ {def_fort}\n\n"
            f"⏳ <b>До окончания операции:</b> <b>{rem_min:02d}:{rem_s:02d}</b>\n"
            f"🌦️ <b>Условия фронта:</b> {war['weather']['name']}{reb_line}\n\n"
            f"🎖️ <b>Личный состав «{html.escape(att_name)}»:</b>\n{att_list}\n\n"
            f"🎖️ <b>Личный состав «{html.escape(def_name)}»:</b>\n{def_list}\n\n"
            f"📜 <b>Хроника последних столкновений:</b>\n{logs}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Штурмовикам:</i> /штурм, /оборона, /дрон\n"
            f"💡 <i>Тылу (рядовым):</i> /медпомощь, /снабжение, /дрон, /укрепить\n"
            f"💡 <i>Главкому:</i> /приказ, /мобилизация, /рэб, /капитуляция"
        )
        return True, summary_text
