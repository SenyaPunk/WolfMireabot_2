"""Тесты системы банкротства и судебного урегулирования долгов."""
import shutil
import tempfile
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.economy_manager import EconomyManager
from utils.loan_manager import LoanManager
from utils.slave_manager import SlaveManager
from utils.treasury_manager import TreasuryManager
from utils.bankruptcy_manager import BankruptcyManager, SERVICE_SHIFTS_TOTAL, SERVICE_PAY_PER_SHIFT


def setup_test_env():
    test_dir = Path(tempfile.mkdtemp())
    # Сбрасываем синглтоны
    EconomyManager._instance = None
    EconomyManager._initialized = False
    LoanManager._instance = None
    LoanManager._initialized = False
    SlaveManager._instance = None
    SlaveManager._initialized = False
    TreasuryManager._instance = None
    TreasuryManager._initialized = False
    BankruptcyManager._instance = None
    BankruptcyManager._initialized = False

    eco = EconomyManager(str(test_dir / "economy.json"))
    treasury = TreasuryManager(str(test_dir / "treasury.json"))
    slaves = SlaveManager(str(test_dir / "slaves.json"))
    loans = LoanManager(str(test_dir / "loans.json"))
    bankruptcy = BankruptcyManager(str(test_dir / "bankruptcy.json"))

    return test_dir, eco, treasury, slaves, loans, bankruptcy


def test_bankruptcy_declaration_and_service():
    test_dir, eco, treasury, slaves, loans, bankruptcy = setup_test_env()
    try:
        user_id = 777111
        # Выдаем долг 2500
        loans.loans[user_id] = [{
            "id": 1,
            "tariff": "premium",
            "tariff_name": "Премиум",
            "principal": 2000.0,
            "debt": 2500.0,
            "rate": 0.25,
            "taken_at": time.time() - 100000,
            "due_at": time.time() - 50000,
            "status": "overdue",
            "last_penalty_at": time.time() - 10000,
            "repaid_amount": 0.0,
            "collector_contract": None
        }]
        eco.balances[user_id] = 20.0  # Мало денег на балансе

        # Проверяем допуск
        can, reason = bankruptcy.can_declare_bankruptcy(user_id)
        assert can, f"Should be eligible for bankruptcy: {reason}"

        # Запускаем банкротство
        ok, msg, case = bankruptcy.declare_bankruptcy(user_id)
        assert ok, msg
        assert case["initial_debt"] == 2500.0
        assert eco.get_balance(user_id) == 0.0  # Баланс конфискован

        # Проверяем иммунитет
        has_imm, _ = bankruptcy.has_immunity(user_id)
        assert has_imm, "Should have immunity during active case"

        # Выбираем исправительные работы
        ok, _ = bankruptcy.choose_path(user_id, "service")
        assert ok

        # Выполняем смены
        for shift in range(1, SERVICE_SHIFTS_TOTAL + 1):
            # Сбрасываем время последней смены для теста кулдауна
            case["service_data"]["last_shift_at"] = 0.0
            ok, res_text, finished = bankruptcy.perform_service_shift(user_id)
            assert ok
            if shift == SERVICE_SHIFTS_TOTAL:
                assert finished, "Should be finished after all shifts"
            else:
                assert not finished

        # После завершения всех смен:
        # Долг должен быть полностью списан!
        assert len(loans.get_user_loans(user_id)) == 0
        assert loans.get_total_debt(user_id) == 0.0

        # Пользователь должен иметь иммунитет на 7 дней
        has_imm, rem_imm = bankruptcy.has_immunity(user_id)
        assert has_imm
        assert rem_imm > 0

        # Пользователь должен быть на кредитном карантине
        in_quar, rem_quar = bankruptcy.is_in_quarantine(user_id)
        assert in_quar

        # Проверяем, что МФО отказывает в новом займе во время карантина
        can_loan, loan_reason = loans.can_take_loan(user_id, "light", 100.0)
        assert not can_loan
        assert "КАРАНТИН" in loan_reason

        print("test_bankruptcy_declaration_and_service: PASSED")
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_bankruptcy_auction():
    test_dir, eco, treasury, slaves, loans, bankruptcy = setup_test_env()
    try:
        debtor_id = 888222
        buyer_id = 999333

        loans.loans[debtor_id] = [{
            "id": 1,
            "tariff": "premium",
            "principal": 2000.0,
            "debt": 3000.0,
            "due_at": time.time() - 10000,
            "status": "overdue"
        }]
        eco.balances[debtor_id] = 0.0
        eco.balances[buyer_id] = 5000.0

        ok, _, case = bankruptcy.declare_bankruptcy(debtor_id)
        assert ok
        ok, _ = bankruptcy.choose_path(debtor_id, "auction")
        assert ok

        buyout_price = case["auction_data"]["buyout_price"]
        ok, res_text = bankruptcy.buyout_bankrupt(buyer_id, debtor_id)
        assert ok, res_text

        # Проверяем: у покупателя списано buyout_price
        assert eco.get_balance(buyer_id) == 5000.0 - buyout_price
        # Должник стал рабом покупателя
        assert slaves.get_owner(debtor_id) == buyer_id
        # Долги должника полностью аннулированы
        assert loans.get_total_debt(debtor_id) == 0.0

        print("test_bankruptcy_auction: PASSED")
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_bankruptcy_duel():
    test_dir, eco, treasury, slaves, loans, bankruptcy = setup_test_env()
    try:
        user_id = 666444
        loans.loans[user_id] = [{
            "id": 1,
            "tariff": "premium",
            "principal": 2000.0,
            "debt": 2500.0,
            "due_at": time.time() - 10000,
            "status": "overdue"
        }]
        eco.balances[user_id] = 10.0

        ok, _, case = bankruptcy.declare_bankruptcy(user_id)
        assert ok
        ok, _ = bankruptcy.choose_path(user_id, "duel")
        assert ok

        # Играем 3 раунда
        for r in range(1, 4):
            ok, res_text, payload = bankruptcy.play_duel_round(user_id)
            assert ok
            assert payload["round"] == r
            if r == 3:
                assert payload["is_finished"]

        # В случае победы долг списан на 100%, в случае поражения 60% списано и назначены смены
        if payload["final_outcome"] == "victory":
            assert loans.get_total_debt(user_id) == 0.0
        else:
            assert case["status"] == "service"
            assert case["service_data"]["shifts_needed"] == 4

        print("test_bankruptcy_duel: PASSED")
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    test_bankruptcy_declaration_and_service()
    test_bankruptcy_auction()
    test_bankruptcy_duel()
    print("ALL TESTS PASSED!")
