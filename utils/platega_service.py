"""Модуль для интеграции с платежной системой Platega (platega.io)."""
import os
import logging
import hashlib
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

PLATEGA_MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID", "")
PLATEGA_SECRET_KEY = os.getenv("PLATEGA_SECRET_KEY", "")
PLATEGA_API_URL = os.getenv("PLATEGA_API_URL", "https://api.platega.io/v1")


def create_platega_payment(order_id: str, amount_rub: int, title: str, user_id: int) -> Dict[str, Any]:
    """
    Создает платежную ссылку через Platega API.
    Если API ключи не заданы, возвращает ссылку на платежную форму / эмуляцию.
    """
    if not PLATEGA_MERCHANT_ID or not PLATEGA_SECRET_KEY:
        logger.info(f"Platega API keys not configured. Returning fallback payment structure for order {order_id}.")
        # Возвращаем fallback структуры
        return {
            "success": True,
            "payment_url": f"https://platega.io/pay?merchant={PLATEGA_MERCHANT_ID or 'demo'}&order={order_id}&amount={amount_rub}",
            "order_id": order_id,
            "is_demo": True
        }

    try:
        payload = {
            "merchant_id": PLATEGA_MERCHANT_ID,
            "order_id": order_id,
            "amount": amount_rub,
            "currency": "RUB",
            "description": f"Wolf MIREA: {title} (ID: {user_id})",
            "user_id": str(user_id)
        }
        
        # Генерация подписи под запрос
        sign_str = f"{PLATEGA_MERCHANT_ID}:{amount_rub}:{order_id}:{PLATEGA_SECRET_KEY}"
        payload["sign"] = hashlib.sha256(sign_str.encode('utf-8')).hexdigest()

        response = requests.post(f"{PLATEGA_API_URL}/payment/create", json=payload, timeout=10)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("status") == "success" or "payment_url" in res_data:
                return {
                    "success": True,
                    "payment_url": res_data.get("payment_url"),
                    "order_id": order_id,
                    "is_demo": False
                }

        logger.error(f"Platega API error: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"Error calling Platega API: {e}")

    return {
        "success": True,
        "payment_url": f"https://platega.io/pay?merchant={PLATEGA_MERCHANT_ID or 'demo'}&order={order_id}&amount={amount_rub}",
        "order_id": order_id,
        "is_demo": True
    }


def verify_platega_payment(order_id: str) -> bool:
    """
    Проверяет статус платежа через Platega API.
    """
    if not PLATEGA_MERCHANT_ID or not PLATEGA_SECRET_KEY:
        return False

    try:
        sign_str = f"{PLATEGA_MERCHANT_ID}:{order_id}:{PLATEGA_SECRET_KEY}"
        sign = hashlib.sha256(sign_str.encode('utf-8')).hexdigest()
        
        url = f"{PLATEGA_API_URL}/payment/status?merchant_id={PLATEGA_MERCHANT_ID}&order_id={order_id}&sign={sign}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            res_data = response.json()
            return res_data.get("status") == "paid"
    except Exception as e:
        logger.error(f"Error checking Platega payment status: {e}")

    return False
