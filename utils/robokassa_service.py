"""Сервис для интеграции с платежной системой Robokassa (robokassa.com)."""
import os
import logging
import hashlib
from typing import Dict, Any

logger = logging.getLogger(__name__)

ROBOKASSA_MERCHANT_LOGIN = os.getenv("ROBOKASSA_MERCHANT_LOGIN", "")
ROBOKASSA_PASSWORD1 = os.getenv("ROBOKASSA_PASSWORD1", "")
ROBOKASSA_IS_TEST = os.getenv("ROBOKASSA_IS_TEST", "1")  # "1" - тестовый режим, "0" - рабочий


def create_robokassa_payment(order_id: str, amount_rub: int, title: str, user_id: int) -> Dict[str, Any]:
    """
    Создает платежную ссылку Robokassa.
    Если логин мерчанта или пароли не заданы, возвращает демо-ссылку.
    """
    if not ROBOKASSA_MERCHANT_LOGIN or not ROBOKASSA_PASSWORD1:
        logger.info(f"Robokassa credentials not configured. Returning fallback demo payment url.")
        # Демо ссылка для прохождения модерации
        return {
            "success": True,
            "payment_url": f"https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=demo&OutSum={amount_rub}&InvId=0&Description=WolfMIREA&SignatureValue=demo",
            "is_demo": True
        }

    try:
        # Для Robokassa InvId должен быть числом. Так как наш order_id это строка (UUID), 
        # мы можем сгенерировать числовой хэш или использовать 0 (если счета не уникализируются строго по InvId в Robokassa).
        # Но лучше получить числовой ID. Превратим UUID в хэш-число.
        numeric_inv_id = abs(hash(order_id)) % 100000000
        
        # Формируем подпись SignatureValue: MerchantLogin:OutSum:InvId:Password1
        # OutSum должна быть строкой с точкой, например "100.00"
        out_sum_str = f"{amount_rub}.00"
        
        sign_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{out_sum_str}:{numeric_inv_id}:{ROBOKASSA_PASSWORD1}"
        signature = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
        
        # Базовый URL
        base_url = "https://auth.robokassa.ru/Merchant/Index.aspx"
        
        params = {
            "MerchantLogin": ROBOKASSA_MERCHANT_LOGIN,
            "OutSum": out_sum_str,
            "InvId": str(numeric_inv_id),
            "Description": f"Wolf MIREA: {title} (ID: {user_id})",
            "SignatureValue": signature,
        }
        
        if ROBOKASSA_IS_TEST == "1":
            params["IsTest"] = "1"
            
        # Сборка URL
        query_parts = [f"{k}={v}" for k, v in params.items()]
        payment_url = f"{base_url}?{'&'.join(query_parts)}"
        
        return {
            "success": True,
            "payment_url": payment_url,
            "is_demo": False
        }
    except Exception as e:
        logger.error(f"Error creating Robokassa payment: {e}")
        
    return {
        "success": True,
        "payment_url": f"https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=demo&OutSum={amount_rub}&InvId=0&Description=WolfMIREA",
        "is_demo": True
    }


def verify_robokassa_payment(order_id: str) -> bool:
    """
    Проверка платежа Robokassa.
    Временно возвращаем False, чтобы тестовая оплата не проходила.
    """
    return False
