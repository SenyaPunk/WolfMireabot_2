"""Модуль для работы с Fusion Brain API для генерации изображений."""
import json
import time
import base64
import requests
import logging
import os 
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

class FusionBrainAPI:
    
    def __init__(self, url: str, api_key: str, secret_key: str):
        self.URL = url
        self.AUTH_HEADERS = {
            'X-Key': f'Key {api_key}',
            'X-Secret': f'Secret {secret_key}',
        }
        
        if not api_key or api_key == os.getenv("FUSION_API_KEY"):
            logger.warning("API ключ Fusion Brain не настроен!")
        if not secret_key or secret_key == os.getenv("FUSION_SECRET_KEY"):
            logger.warning("Секретный ключ Fusion Brain не настроен!")

    def get_pipeline(self) -> str | None:
        try:
            url = self.URL + 'key/api/v1/pipelines'
            logger.info(f"Запрос pipeline: {url}")
            
            response = requests.get(url, headers=self.AUTH_HEADERS, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Ошибка получения pipeline: {response.status_code}")
                logger.error(f"Ответ сервера: {response.text}")
                logger.error(f"URL запроса: {url}")
                return None
                
            data = response.json()
            if not data or len(data) == 0:
                logger.error("Получен пустой список pipelines")
                return None
                
            pipeline_id = data[0]['id']
            logger.info(f"Получен pipeline ID: {pipeline_id}")
            return pipeline_id
            
        except requests.exceptions.Timeout:
            logger.error("Превышено время ожидания запроса к API")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сетевого запроса: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении pipeline: {e}")
            return None

    def generate(
        self,
        prompt: str,
        pipeline_id: str,
        images: int = 1,
        width: int = 1024,
        height: int = 1024
    ) -> str | None:
        params = {
            "type": "GENERATE",
            "numImages": images,
            "width": width,
            "height": height,
            "generateParams": {
                "query": prompt
            }
        }

        data = {
            'pipeline_id': (None, pipeline_id),
            'params': (None, json.dumps(params), 'application/json')
        }

        try:
            url = self.URL + 'key/api/v1/pipeline/run'
            logger.info(f"Запуск генерации: {prompt[:50]}...")
            
            response = requests.post(
                url,
                headers=self.AUTH_HEADERS,
                files=data,
                timeout=30
            )

            if response.status_code not in (200, 201):
                logger.error(f"Ошибка генерации: {response.status_code}")
                logger.error(f"Ответ сервера: {response.text}")
                return None

            result = response.json()
            uuid = result.get('uuid')
            if uuid:
                logger.info(f"Генерация запущена, UUID: {uuid}")
            return uuid
            
        except requests.exceptions.Timeout:
            logger.error("Превышено время ожидания запроса генерации")
            return None
        except Exception as e:
            logger.error(f"Ошибка при запуске генерации: {e}")
            return None

    def check_generation(
        self,
        request_id: str,
        attempts: int = 15,
        delay: int = 8
    ) -> list | None:
        logger.info(f"Ожидание завершения генерации (макс. {attempts * delay} сек)...")
        
        while attempts > 0:
            try:
                response = requests.get(
                    self.URL + 'key/api/v1/pipeline/status/' + request_id,
                    headers=self.AUTH_HEADERS,
                    timeout=30
                )
                
                if response.status_code != 200:
                    logger.error(f"Ошибка проверки статуса: {response.status_code}")
                    logger.error(f"Ответ сервера: {response.text}")
                    return None

                data = response.json()
                status = data.get('status')
                
                if status == 'DONE':
                    logger.info("Генерация завершена успешно!")
                    return data['result']['files']
                elif status == 'FAIL':
                    logger.error(f"Генерация завершилась с ошибкой: {data.get('error', 'Неизвестная ошибка')}")
                    return None
                else:
                    logger.info(f"Статус: {status}, осталось попыток: {attempts}")

                attempts -= 1
                time.sleep(delay)
                
            except requests.exceptions.Timeout:
                logger.error("Превышено время ожидания проверки статуса")
                return None
            except Exception as e:
                logger.error(f"Ошибка при проверке генерации: {e}")
                return None

        logger.error("Превышено время ожидания генерации")
        return None

    def generate_image_bytes(self, prompt: str) -> bytes | None:
        logger.info(f"Начало генерации изображения: {prompt}")
        
        pipeline_id = self.get_pipeline()
        if not pipeline_id:
            logger.error("Не удалось получить pipeline ID")
            return None

        uuid = self.generate(prompt, pipeline_id)
        if not uuid:
            logger.error("Не удалось запустить генерацию")
            return None

        files = self.check_generation(uuid)
        if not files:
            logger.error("Не удалось получить результат генерации")
            return None

        try:
            image_base64 = files[0]
            image_bytes = base64.b64decode(image_base64)
            logger.info(f"Изображение успешно сгенерировано ({len(image_bytes)} байт)")
            return image_bytes
        except Exception as e:
            logger.error(f"Ошибка декодирования изображения: {e}")
            return None
