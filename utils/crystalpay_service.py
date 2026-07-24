"""Модуль для интеграции с платежной системой CrystalPay (crystalpay.io)."""
import os
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

CRYSTALPAY_CASHOUT_NAME = os.getenv("CRYSTALPAY_CASHOUT_NAME", "")
CRYSTALPAY_SECRET_1 = os.getenv("CRYSTALPAY_SECRET_1", "")
CRYSTALPAY_SALT = os.getenv("CRYSTALPAY_SALT", "")
CRYSTALPAY_API_URL = "https://api.crystalpay.io/v2"


def create_crystalpay_payment(order_id: str, amount_rub: int, title: str, user_id: int) -> Dict[str, Any]:
    """
    Создает счет на оплату через CrystalPay API v2.
    """
    if not CRYSTALPAY_CASHOUT_NAME or not CRYSTALPAY_SECRET_1:
        logger.warning(f"CrystalPay API keys not configured for order {order_id}.")
        return {
            "success": False,
            "payment_url": None,
            "order_id": order_id,
            "error": "Ключи CrystalPay не настроены"
        }

    try:
        payload = {
            "auth_login": CRYSTALPAY_CASHOUT_NAME,
            "auth_secret": CRYSTALPAY_SECRET_1,
            "amount": amount_rub,
            "type": "purchase",
            "lifetime": 60,
            "extra": order_id,
            "redirect_url": "https://t.me/WolfMIREA_bot"
        }

        response = requests.post(f"{CRYSTALPAY_API_URL}/invoice/create/", json=payload, timeout=10)
        if response.status_code == 200:
            res_data = response.json()
            if not res_data.get("error") and "url" in res_data:
                return {
                    "success": True,
                    "payment_url": res_data.get("url"),
                    "invoice_id": res_data.get("id"),
                    "order_id": order_id
                }
            else:
                logger.error(f"CrystalPay create invoice response error: {res_data}")
        else:
            logger.error(f"CrystalPay HTTP error {response.status_code}: {response.text}")

    except Exception as e:
        logger.error(f"Error calling CrystalPay API create: {e}")

    return {
        "success": False,
        "payment_url": None,
        "order_id": order_id,
        "error": "Ошибка при генерации ссылки на оплату"
    }


def verify_crystalpay_payment(invoice_id: str) -> bool:
    """
    Проверяет статус оплаты счета по его id через CrystalPay API.
    Состояния: payed / notpayed / processing / wrongamount / expired
    """
    if not CRYSTALPAY_CASHOUT_NAME or not CRYSTALPAY_SECRET_1 or not invoice_id:
        return False

    try:
        payload = {
            "auth_login": CRYSTALPAY_CASHOUT_NAME,
            "auth_secret": CRYSTALPAY_SECRET_1,
            "id": invoice_id
        }

        response = requests.post(f"{CRYSTALPAY_API_URL}/invoice/info/", json=payload, timeout=10)
        if response.status_code == 200:
            res_data = response.json()
            if not res_data.get("error"):
                state = res_data.get("state")
                logger.info(f"CrystalPay invoice {invoice_id} state: {state}")
                return state == "payed"
            else:
                logger.error(f"CrystalPay info error response: {res_data}")
        else:
            logger.error(f"CrystalPay info HTTP error {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Error checking CrystalPay payment status: {e}")

    return False
