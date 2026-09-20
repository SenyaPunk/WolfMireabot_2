"""Тестирование системы микрозаймов и работы коллекторов."""
import os
import sys
import time
from pathlib import Path

# Добавляем корневую папку в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.loan_manager import LoanManager, TARIFFS, COLLECTOR_RANKS, SANCTION_LEVELS
from utils.economy_manager import EconomyManager


def test_loan_lifecycle():
    print("--- 1. Тестирование жизненного цикла займа ---")
    em = EconomyManager("test_economy.json")
    lm = LoanManager("test_loans.json")

    user_id = 999001
    em.set_balance(user_id, 50.0)

    # 1. Попытка взять некорректную сумму
    ok, err, _ = lm.take_loan(user_id, "light", 500.0)
    assert not ok, "Должна быть ошибка лимита"
    print("✅ Проверка лимита тарифа: успешно")

    # 2. Успешное взятие тарифа "light" на 200 монет
    ok, msg, data = lm.take_loan(user_id, "light", 200.0)
    assert ok, f"Не удалось взять займ: {msg}"
    assert data["principal"] == 200.0
    assert data["debt"] == 230.0  # +15%
    assert em.get_balance(user_id) == 250.0  # 50 + 200
    print("✅ Взятие тарифа Лайт: баланс 250.0, долг 230.0")

    # 3. Попытка взять второй займ
    ok, err, _ = lm.take_loan(user_id, "light", 100.0)
    assert not ok, "Нельзя брать второй займ"
    print("✅ Защита от повторного займа: успешно")

    # 4. Частичное погашение (100 монет)
    ok, msg, paid = lm.repay_loan(user_id, 100.0)
    assert ok
    assert paid == 100.0
    loan = lm.get_user_loan(user_id)
    assert loan["debt"] == 130.0
    assert em.get_balance(user_id) == 150.0
    print("✅ Частичное погашение: долг 130.0, баланс 150.0")

    # 5. Полное погашение
    ok, msg, paid = lm.repay_loan(user_id, None)  # Полное погашение
    assert ok
    assert lm.get_user_loan(user_id) is None
    hist = lm.get_credit_history(user_id)
    assert hist["successful_loans"] == 1
    print("✅ Полное погашение: займ закрыт, рейтинг повышен до 1")

    # 6. Теперь доступен тариф "standard" (требует 1 закрытый займ)
    ok, msg, data = lm.take_loan(user_id, "standard", 500.0)
    assert ok, f"Стандарт должен быть доступен: {msg}"
    assert data["debt"] == 600.0  # +20%
    print("✅ Взятие тарифа Стандарт после закрытия Лайт: успешно")

    # Очищаем
    lm.repay_loan(user_id, None)
    print("--- Жизненный цикл займа проверен успешно ---\n")


def test_collector_and_sanctions():
    print("--- 2. Тестирование работы коллектора и санкций до 5 дней ---")
    em = EconomyManager("test_economy.json")
    lm = LoanManager("test_loans.json")

    collector_id = 999002
    debtor_id = 999003

    em.set_balance(collector_id, 200.0)
    em.set_balance(debtor_id, 100.0)

    # 1. Должник берет займ и просрочивает его
    ok, _, _ = lm.take_loan(debtor_id, "light", 200.0)
    assert ok
    loan = lm.get_user_loan(debtor_id)
    loan["status"] = "overdue"
    loan["due_at"] = time.time() - 1000
    lm.save_data_sync()
    assert lm.has_overdue_loan(debtor_id)
    print("✅ Должник переведен в статус overdue")

    # 2. Трудоустройство коллектора (списание 50 монет)
    ok, msg = lm.register_collector(collector_id)
    assert ok, msg
    assert em.get_balance(collector_id) == 150.0  # 200 - 50
    coll = lm.get_collector(collector_id)
    assert coll["rank"] == "trainee"
    print("✅ Коллектор успешно трудоустроен со взносом 50 монет")

    # 3. Взятие контракта на должника
    ok, msg = lm.take_debt_contract(collector_id, debtor_id)
    assert ok, msg
    assert coll["active_contract"]["debtor_id"] == debtor_id
    print("✅ Контракт на должника успешно оформлен на 3 часа")

    # 4. Успешное взыскание (process_collector_success)
    # Выбиваем 100 монет. Стажер получает 20% = 20 монет
    col_share, mfi_share, is_closed = lm.process_collector_success(collector_id, debtor_id, 100.0)
    assert col_share == 20.0
    assert mfi_share == 80.0
    assert em.get_balance(collector_id) == 170.0  # 150 + 20
    print("✅ Взыскание и выплата 20% комиссии коллектору: успешно")

    # 5. Тестирование САНКЦИЙ и БАНОВ (Страйки 1, 2, 3)
    # Страйк 1: 12 часов бана, штраф 100
    strikes, ban_sec, desc = lm.apply_sanction(collector_id, "Тестовое нарушение 1")
    assert strikes == 1
    assert ban_sec == 12 * 3600
    is_banned, rem, _ = lm.is_collector_banned(collector_id)
    assert is_banned
    assert rem > 11 * 3600
    print(f"✅ Страйк 1: бан на 12 часов ({ban_sec}с) наложен корректно")

    # Страйк 2: 48 часов бана (2 дня), штраф 250
    strikes, ban_sec, desc = lm.apply_sanction(collector_id, "Тестовое нарушение 2")
    assert strikes == 2
    assert ban_sec == 48 * 3600
    is_banned, rem, _ = lm.is_collector_banned(collector_id)
    assert is_banned
    assert rem > 47 * 3600
    print(f"✅ Страйк 2: бан на 48 часов (2 дня) наложен корректно")

    # Страйк 3: 120 часов бана (5 дней!), сброс ранга, штраф 500
    coll["rank"] = "senior"  # Искусственно повысим ранг
    strikes, ban_sec, desc = lm.apply_sanction(collector_id, "Критический беспредел")
    assert strikes == 3
    assert ban_sec == 120 * 3600  # 5 дней!
    assert ban_sec == 5 * 24 * 3600
    assert coll["rank"] == "trainee"  # Ранг аннулирован
    is_banned, rem, _ = lm.is_collector_banned(collector_id)
    assert is_banned
    assert rem > 119 * 3600
    print(f"✅ Страйк 3: МАКСИМАЛЬНЫЙ БАН НА 5 ДНЕЙ (120 часов) и сброс ранга подтвержден!")

    print("--- Работа коллектора и санкции до 5 дней проверены успешно ---\n")


def cleanup():
    data_dir = Path.cwd() / "data"
    for fname in ["test_economy.json", "test_economy.tmp", "test_loans.json", "test_loans.tmp"]:
        p = data_dir / fname
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        test_loan_lifecycle()
        test_collector_and_sanctions()
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ БЕЗУПРЕЧНО!")
    finally:
        cleanup()
