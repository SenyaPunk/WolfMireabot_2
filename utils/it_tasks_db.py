"""
Расширенная база данных IT-задач из ведущих IT-компаний (27+ уникальных тасок)
Поддержка языков Kotlin, C++, Go, TypeScript, Python, Swift, Rust.
Нативные HTML pre/code блоки для Telegram с экранированием HTML сущностей.
"""
from typing import Dict, Any, List, Optional

IT_TASKS_DB: List[Dict[str, Any]] = [
    # =========================================================================
    # 📱 MOBILE (Kotlin / Swift / Python)
    # =========================================================================
    {
        "id": "yandex_eda_kotlin_location",
        "company": "Яндекс Еда Mobile",
        "title": "Фильтрация GPS-шумов курьера",
        "category": "Mobile",
        "difficulty": "MEDIUM",
        "language": "Kotlin / Python 3.11",
        "reward": 260,
        "description": (
            "При движении курьера среди высотных зданий GPS-модуль смартфона передает скачки координат (GPS noise).\n"
            "Напишите функцию <code>filter_gps_track(points, max_speed_mps)</code>, где <code>points</code> — список точек:\n"
            "<pre>[{'lat': float, 'lon': float, 'timestamp': int}]</pre>\n"
            "а <code>max_speed_mps</code> — предельно возможная скорость курьера (в м/с).\n\n"
            "Дистанция между точками вычисляется по Евклиду на плоскости (1 градус ~ 111 000 м).\n"
            "Если скорость от предыдущей валидной точки превышает <code>max_speed_mps</code>, точка отбраковывается.\n"
            "Верните список валидных точек."
        ),
        "starter_code": (
            "def filter_gps_track(points: list, max_speed_mps: float) -> list:\n"
            "    # Напишите решение на Kotlin/Python здесь\n"
            "    pass"
        ),
        "entry_point": "filter_gps_track",
        "test_cases": [
            {
                "input": [[
                    {"lat": 55.75, "lon": 37.61, "timestamp": 1000},
                    {"lat": 55.85, "lon": 37.81, "timestamp": 1001},
                    {"lat": 55.7501, "lon": 37.6101, "timestamp": 1010}
                ], 15.0],
                "expected": [
                    {"lat": 55.75, "lon": 37.61, "timestamp": 1000},
                    {"lat": 55.7501, "lon": 37.6101, "timestamp": 1010}
                ],
                "description": "Фильтрация GPS выброса"
            },
            {"input": [[], 10.0], "expected": [], "description": "Пустой трек"}
        ]
    },
    {
        "id": "tbank_kotlin_stateflow",
        "company": "Т-Банк Mobile",
        "title": "Редюсер UiState для платежного экрана",
        "category": "Mobile",
        "difficulty": "MEDIUM",
        "language": "Kotlin / Python 3.11",
        "reward": 240,
        "description": (
            "На платежном экране Android-приложения состояние UI управляется чистой редукцией <code>reduce_ui_state(current_state, event)</code>.\n"
            "<code>current_state</code> имеет вид:\n"
            "<pre>{'status': str, 'balance': float, 'error': str | None}</pre>\n"
            "Возможные события <code>event</code>:\n"
            "• <code>{'type': 'PAY_START'}</code> ➔ статус <code>'LOADING'</code>, <code>error = None</code>.\n"
            "• <code>{'type': 'PAY_SUCCESS', 'amount': float}</code> ➔ списание <code>balance</code> на <code>amount</code>, статус <code>'SUCCESS'</code>.\n"
            "• <code>{'type': 'PAY_ERROR', 'message': str}</code> ➔ статус <code>'ERROR'</code>, <code>error = message</code>.\n\n"
            "Верните новое состояние словарем."
        ),
        "starter_code": (
            "def reduce_ui_state(current_state: dict, event: dict) -> dict:\n"
            "    # Напишите редюсер состояния здесь\n"
            "    pass"
        ),
        "entry_point": "reduce_ui_state",
        "test_cases": [
            {
                "input": [{"status": "IDLE", "balance": 1000.0, "error": None}, {"type": "PAY_START"}],
                "expected": {"status": "LOADING", "balance": 1000.0, "error": None},
                "description": "Переход в LOADING"
            },
            {
                "input": [{"status": "LOADING", "balance": 1000.0, "error": None}, {"type": "PAY_SUCCESS", "amount": 300.0}],
                "expected": {"status": "SUCCESS", "balance": 700.0, "error": None},
                "description": "Успешная оплата"
            }
        ]
    },
    {
        "id": "avito_mobile_dynamic_form",
        "company": "Avito Mobile",
        "title": "Валидатор динамических полей формы объявления",
        "category": "Mobile",
        "difficulty": "MEDIUM",
        "language": "Kotlin / Python 3.11",
        "reward": 220,
        "description": (
            "В мобильном клиенте Авито форма подачи объявления динамически проверяет правила валидации.\n"
            "Напишите функцию <code>validate_form_fields(fields, rules)</code>.\n"
            "• <code>fields</code>: <code>{'field_name': value}</code>\n"
            "• <code>rules</code>: <code>[{'field': str, 'required': bool, 'min_val': int|None}]</code>\n\n"
            "Если обязательное поле отсутствует или равно <code>None</code>/пустой строке, добавить в список ошибок <code>'field_name_required'</code>.\n"
            "Если числовое значение меньше <code>min_val</code>, добавить <code>'field_name_too_low'</code>.\n"
            "Верните отсортированный список строк с ошибками."
        ),
        "starter_code": (
            "def validate_form_fields(fields: dict, rules: list[dict]) -> list[str]:\n"
            "    # Напишите валидатор формы здесь\n"
            "    pass"
        ),
        "entry_point": "validate_form_fields",
        "test_cases": [
            {
                "input": [
                    {"title": "", "price": 50},
                    [
                        {"field": "title", "required": True, "min_val": None},
                        {"field": "price", "required": True, "min_val": 100}
                    ]
                ],
                "expected": ["price_too_low", "title_required"],
                "description": "Пустой заголовок и низкая цена"
            }
        ]
    },
    {
        "id": "vk_mobile_chat_unreads",
        "company": "VK Android Team",
        "title": "Счетчик непрочитанных диалогов по папкам",
        "category": "Mobile",
        "difficulty": "MEDIUM",
        "language": "Kotlin / Python 3.11",
        "reward": 210,
        "description": (
            "В мессенджере VK Android нужно вычислять бейджик непрочитанных сообщений по вкладкам.\n"
            "Напишите функцию <code>count_unread_by_folders(dialogs)</code>, где <code>dialogs</code> — список:\n"
            "<pre>[{'folder': str, 'unread_count': int, 'is_muted': bool}]</pre>\n"
            "Заглушенные диалоги (<code>is_muted == True</code>) НЕ учитываются в сумме.\n"
            "Верните словарь <code>{'folder_name': total_unreads}</code>."
        ),
        "starter_code": (
            "def count_unread_by_folders(dialogs: list[dict]) -> dict:\n"
            "    # Напишите подсчет бейджей здесь\n"
            "    pass"
        ),
        "entry_point": "count_unread_by_folders",
        "test_cases": [
            {
                "input": [[
                    {"folder": "Work", "unread_count": 5, "is_muted": False},
                    {"folder": "Work", "unread_count": 10, "is_muted": True},
                    {"folder": "Personal", "unread_count": 2, "is_muted": False}
                ]],
                "expected": {"Work": 5, "Personal": 2},
                "description": "Игнорирование muted диалогов"
            }
        ]
    },
    {
        "id": "tbank_mobile_retry",
        "company": "Т-Банк Mobile",
        "title": "Очередь офлайн-платежей с Exponential Backoff",
        "category": "Mobile",
        "difficulty": "MEDIUM",
        "language": "Kotlin / Python 3.11",
        "reward": 230,
        "description": (
            "Мобильное приложение Т-Банк отправляет накопившиеся офлайн-платежи.\n"
            "Напишите функцию <code>schedule_retries(failed_requests, max_retries, base_delay)</code>, где <code>failed_requests</code> — список id <code>[str]</code>.\n"
            "Для каждого запроса рассчитывается список задержек повтора в секундах по формуле <code>base_delay * (2 ** attempt)</code>.\n"
            "Верните словарь <code>{'req_id': [delay_1, delay_2, ...]}</code>."
        ),
        "starter_code": (
            "def schedule_retries(failed_requests: list, max_retries: int, base_delay: int) -> dict:\n"
            "    # Напишите решение здесь\n"
            "    pass"
        ),
        "entry_point": "schedule_retries",
        "test_cases": [
            {
                "input": [["req_101", "req_102"], 3, 2],
                "expected": {"req_101": [2, 4, 8], "req_102": [2, 4, 8]},
                "description": "3 попытки задержки"
            }
        ]
    },
    {
        "id": "tg_media_cache_manager",
        "company": "Telegram Mobile",
        "title": "Управление медиа-кэшем мобильного клиента",
        "category": "Mobile",
        "difficulty": "SENIOR HARD",
        "is_hard": True,
        "language": "Kotlin / Swift / Python 3.11",
        "reward": 360,
        "description": (
            "В Telegram iOS/Android необходимо автоматически очищать медиафайлы при превышении лимита хранилища.\n"
            "Напишите функцию <code>evict_media_cache(files, max_storage_bytes)</code>, где <code>files</code> — список словарей:\n"
            "<pre>[{'path': str, 'size_bytes': int, 'last_accessed': int, 'is_pinned': bool}]</pre>\n"
            "Запрещено удалять закрепленные файлы (<code>is_pinned == True</code>).\n"
            "Остальные файлы вытесняются по LRU (самые старые по <code>last_accessed</code>), пока суммарный размер не станет <code>&lt;= max_storage_bytes</code>.\n"
            "Верните список путей <code>[str]</code> удаленных файлов."
        ),
        "starter_code": (
            "def evict_media_cache(files: list[dict], max_storage_bytes: int) -> list[str]:\n"
            "    # Напишите решение LRU очистки здесь\n"
            "    pass"
        ),
        "entry_point": "evict_media_cache",
        "test_cases": [
            {
                "input": [[
                    {"path": "video1.mp4", "size_bytes": 500, "last_accessed": 100, "is_pinned": False},
                    {"path": "photo1.jpg", "size_bytes": 300, "last_accessed": 200, "is_pinned": False},
                    {"path": "important.doc", "size_bytes": 400, "last_accessed": 50, "is_pinned": True}
                ], 600],
                "expected": ["video1.mp4"],
                "description": "Удаление открепленного video1"
            }
        ]
    },

    # =========================================================================
    # ⚙️ BACKEND (C++20 / Go / Python / Rust)
    # =========================================================================
    {
        "id": "vk_cpp_order_book",
        "company": "VK Tech / High-Load",
        "title": "Движок матчинга биржевых ордеров",
        "category": "Backend",
        "difficulty": "SENIOR HARD",
        "is_hard": True,
        "language": "C++20 / Python 3.11",
        "reward": 380,
        "description": (
            "В высоконагруженном ядре биржевых торгов требуется исполнять встречи заявок BUY и SELL.\n"
            "Напишите функцию <code>match_orders(buy_orders, sell_orders)</code>, где ордер имеет вид:\n"
            "<pre>{'id': str, 'price': float, 'qty': int}</pre>\n"
            "• BUY отсортированы по убыванию цены (ранние в приоритете).\n"
            "• SELL отсортированы по возрастанию цены.\n"
            "Сделка происходит, когда <code>buy_price &gt;= sell_price</code> по цене SELL ордера.\n"
            "Верните список сделок:\n"
            "<pre>[{'buy_id': str, 'sell_id': str, 'matched_qty': int, 'exec_price': float}]</pre>"
        ),
        "starter_code": (
            "def match_orders(buy_orders: list[dict], sell_orders: list[dict]) -> list[dict]:\n"
            "    # Напишите решение матчинга здесь\n"
            "    pass"
        ),
        "entry_point": "match_orders",
        "test_cases": [
            {
                "input": [
                    [{"id": "b1", "price": 100.0, "qty": 10}],
                    [{"id": "s1", "price": 95.0, "qty": 5}]
                ],
                "expected": [{"buy_id": "b1", "sell_id": "s1", "matched_qty": 5, "exec_price": 95.0}],
                "description": "Частичное исполнение"
            }
        ]
    },
    {
        "id": "yandex_search_tf_idf",
        "company": "Яндекс Поиск",
        "title": "Ранжирование документов по алгоритму TF-IDF",
        "category": "Backend",
        "difficulty": "SENIOR HARD",
        "is_hard": True,
        "language": "C++20 / Python 3.11",
        "reward": 370,
        "description": (
            "В поисковом движке Яндекса требуется отранжировать список текстовых документов по запросу.\n"
            "Напишите функцию <code>rank_documents(docs, query_words)</code>, где <code>docs</code> — список <code>[{'id': str, 'text': str}]</code>.\n"
            "Для каждого документа считается TF (частота слов запроса в данном документе = суммарное число вхождений / всего слов в документе).\n"
            "Верните список id документов, отсортированный по убыванию релевантности (документы с TF == 0 отбрасываются)."
        ),
        "starter_code": (
            "def rank_documents(docs: list[dict], query_words: list[str]) -> list[str]:\n"
            "    # Напишите ранжирование TF-IDF здесь\n"
            "    pass"
        ),
        "entry_point": "rank_documents",
        "test_cases": [
            {
                "input": [[
                    {"id": "doc1", "text": "yandex search engine query"},
                    {"id": "doc2", "text": "cat dog animal"},
                    {"id": "doc3", "text": "yandex yandex fast search"}
                ], ["yandex", "search"]],
                "expected": ["doc3", "doc1"],
                "description": "Ранжирование doc3 выше doc1 по TF"
            }
        ]
    },
    {
        "id": "tg_go_worker_pool",
        "company": "Telegram Core",
        "title": "Диспетчер пула воркеров доставки сообщений",
        "category": "Backend",
        "difficulty": "MEDIUM",
        "language": "Go 1.22 / Python 3.11",
        "reward": 250,
        "description": (
            "Для параллельной рассылки push-уведомлений используется ограниченный пул воркеров.\n"
            "Напишите функцию <code>distribute_jobs(jobs, num_workers)</code>, где <code>jobs</code> — список трудоемкостей задач <code>[int]</code> (в мс).\n"
            "Воркеры берут задачи из общей очереди по мере высвобождения.\n"
            "Верните список суммарного времени работы каждого воркера <code>[total_w1, total_w2, ...]</code>."
        ),
        "starter_code": (
            "def distribute_jobs(jobs: list[int], num_workers: int) -> list[int]:\n"
            "    # Напишите алгоритм распределения задач здесь\n"
            "    pass"
        ),
        "entry_point": "distribute_jobs",
        "test_cases": [
            {
                "input": [[10, 20, 30, 40, 50], 2],
                "expected": [70, 80],
                "description": "Балансировка 5 задач на 2 воркера"
            }
        ]
    },
    {
        "id": "ozon_rate_limiter",
        "company": "Ozon Backend Team",
        "title": "Rate Limiter для API шлюза распродаж",
        "category": "Backend",
        "difficulty": "MEDIUM",
        "language": "Python 3.11 / Go",
        "reward": 200,
        "description": (
            "В период Мега-Распродажи нагрузка на API шлюз возрастает в десятки раз.\n"
            "Напишите функцию <code>is_rate_limited(user_requests, max_requests, time_window)</code>, "
            "которая принимает список временных меток запросов <code>user_requests</code> (в секундах), "
            "лимит запросов <code>max_requests</code> и ширину скользящего окна <code>time_window</code>.\n\n"
            "Верните <code>True</code>, если количество запросов за последние <code>time_window</code> секунд превышает <code>max_requests</code>."
        ),
        "starter_code": (
            "def is_rate_limited(user_requests: list, max_requests: int, time_window: float) -> bool:\n"
            "    # Напишите решение здесь\n"
            "    pass"
        ),
        "entry_point": "is_rate_limited",
        "test_cases": [
            {"input": [[10.0, 11.0, 12.0, 13.0, 14.0], 3, 5.0], "expected": True, "description": "5 запросов при лимите 3"}
        ]
    },
    {
        "id": "tbank_idempotency",
        "company": "Т-Банк Fintech",
        "title": "Детектор дубликатов транзакций",
        "category": "Backend",
        "difficulty": "MEDIUM",
        "language": "Python 3.11",
        "reward": 220,
        "description": (
            "Напишите функцию <code>process_transactions(transactions)</code>, принимающую список словарей транзакций:\n"
            "<pre>[{'id': str, 'amount': int, 'idempotency_key': str}]</pre>\n"
            "Верните список только уникальных транзакций (по <code>idempotency_key</code>), сохраняя порядок первого появления.\n"
            "Если сумма транзакции <code>amount &lt;= 0</code>, она отбрасывается."
        ),
        "starter_code": (
            "def process_transactions(transactions: list) -> list:\n"
            "    # Напишите решение здесь\n"
            "    pass"
        ),
        "entry_point": "process_transactions",
        "test_cases": [
            {
                "input": [[
                    {"id": "t1", "amount": 500, "idempotency_key": "k1"},
                    {"id": "t2", "amount": 500, "idempotency_key": "k1"},
                    {"id": "t3", "amount": 1000, "idempotency_key": "k2"}
                ]],
                "expected": [
                    {"id": "t1", "amount": 500, "idempotency_key": "k1"},
                    {"id": "t3", "amount": 1000, "idempotency_key": "k2"}
                ],
                "description": "Фильтрация повторов"
            }
        ]
    },

    # =========================================================================
    # 🎨 FRONTEND (TypeScript / JavaScript)
    # =========================================================================
    {
        "id": "vk_video_hls_buffer",
        "company": "VK Video Frontend",
        "title": "Управление HLS-буфером чанков видеоплеера",
        "category": "Frontend",
        "difficulty": "MEDIUM",
        "language": "TypeScript / Python 3.11",
        "reward": 220,
        "description": (
            "Плеер VK Video загружает сегменты видео (.ts чанки).\n"
            "Напишите функцию <code>manage_hls_buffer(buffer_chunks, max_buffer_duration)</code>, где <code>buffer_chunks</code> — список:\n"
            "<pre>[{'id': int, 'duration_sec': float, 'quality': str}]</pre>\n"
            "Если суммарная длительность чанков превышает <code>max_buffer_duration</code>, вытесняются наиболее старые чанки с начала списка.\n"
            "Верните новый список оставшихся чанков."
        ),
        "starter_code": (
            "def manage_hls_buffer(buffer_chunks: list[dict], max_buffer_duration: float) -> list[dict]:\n"
            "    # Напишите решение здесь\n"
            "    pass"
        ),
        "entry_point": "manage_hls_buffer",
        "test_cases": [
            {
                "input": [[
                    {"id": 1, "duration_sec": 4.0, "quality": "1080p"},
                    {"id": 2, "duration_sec": 4.0, "quality": "1080p"},
                    {"id": 3, "duration_sec": 4.0, "quality": "1080p"}
                ], 10.0],
                "expected": [
                    {"id": 2, "duration_sec": 4.0, "quality": "1080p"},
                    {"id": 3, "duration_sec": 4.0, "quality": "1080p"}
                ],
                "description": "Вытеснение чанка #1 при лимите 10с"
            }
        ]
    },
    {
        "id": "avito_draft_deep_diff",
        "company": "Avito Frontend",
        "title": "Вычисление изменений формы автосохранения (Deep Diff)",
        "category": "Frontend",
        "difficulty": "MEDIUM",
        "language": "TypeScript / Python 3.11",
        "reward": 230,
        "description": (
            "Для автосохранения черновика объявления Avito нужно вычислять измененные поля между предыдущей и текущей версией.\n"
            "Напишите функцию <code>compute_draft_diff(old_draft, new_draft)</code>, где <code>old_draft</code> и <code>new_draft</code> — словари <code>{'key': val}</code>.\n"
            "Верните словарь только с теми ключами из <code>new_draft</code>, значение которых изменилось или добавилось."
        ),
        "starter_code": (
            "def compute_draft_diff(old_draft: dict, new_draft: dict) -> dict:\n"
            "    # Напишите вычисление diff здесь\n"
            "    pass"
        ),
        "entry_point": "compute_draft_diff",
        "test_cases": [
            {
                "input": [
                    {"title": "iPhone 13", "price": 50000, "city": "Moscow"},
                    {"title": "iPhone 13 Pro", "price": 50000, "city": "Moscow", "desc": "New"}
                ],
                "expected": {"title": "iPhone 13 Pro", "desc": "New"},
                "description": "Детекция изменений title и desc"
            }
        ]
    },
    {
        "id": "tg_hashtag_extractor",
        "company": "Telegram Web",
        "title": "Парсер и группировщик хештегов",
        "category": "Frontend",
        "difficulty": "MEDIUM",
        "language": "TypeScript / Python 3.11",
        "reward": 180,
        "description": (
            "В Telegram Web необходимо парсить текст и собирать статистику хештегов.\n"
            "Напишите функцию <code>extract_hashtags(text)</code>, которая находит все хештеги в тексте.\n"
            "Приведите хештеги к нижнему регистру и верните словарь <code>{'#tag': count}</code>, отсортированный по убыванию частоты."
        ),
        "starter_code": (
            "def extract_hashtags(text: str) -> dict:\n"
            "    # Напишите решение здесь\n"
            "    pass"
        ),
        "entry_point": "extract_hashtags",
        "test_cases": [
            {"input": ["Привет #python и #Telegram! #PYTHON это здорово. #telegram #bot"], "expected": {"#python": 2, "#telegram": 2, "#bot": 1}, "description": "Подсчет тегов"}
        ]
    },

    # =========================================================================
    # 🛠️ DEVOPS (Python / YAML / Shell / SQL)
    # =========================================================================
    {
        "id": "yandex_terraform_drift",
        "company": "Яндекс Облако DevOps",
        "title": "Детектор дрифта конфигураций Terraform",
        "category": "DevOps",
        "difficulty": "SENIOR HARD",
        "is_hard": True,
        "language": "Python 3.11 / Shell",
        "reward": 370,
        "description": (
            "В DevOps инфраструктуре необходимо обнаруживать дрифт (несоответствие) созданных виртуальных машин их конфигурации в `.tfstate`.\n"
            "Напишите функцию <code>detect_tf_drift(state_resources, actual_resources)</code>, где машины представлены словарями:\n"
            "<pre>{'id': str, 'cpu': int, 'ram_mb': int, 'zone': str}</pre>\n"
            "Верните словарь изменений:\n"
            "<pre>{'created': list[str], 'deleted': list[str], 'modified': list[str]}</pre>"
        ),
        "starter_code": (
            "def detect_tf_drift(state_resources: list[dict], actual_resources: list[dict]) -> dict:\n"
            "    # Напишите решение здесь\n"
            "    pass"
        ),
        "entry_point": "detect_tf_drift",
        "test_cases": [
            {
                "input": [
                    [{"id": "vm-1", "cpu": 2, "ram_mb": 4096, "zone": "ru-central1-a"}],
                    [
                        {"id": "vm-1", "cpu": 4, "ram_mb": 4096, "zone": "ru-central1-a"},
                        {"id": "vm-2", "cpu": 1, "ram_mb": 1024, "zone": "ru-central1-b"}
                    ]
                ],
                "expected": {
                    "created": ["vm-2"],
                    "deleted": [],
                    "modified": ["vm-1"]
                },
                "description": "Дрифт vm-1 и созданная vm-2"
            }
        ]
    },
    {
        "id": "tbank_db_pool_health",
        "company": "Т-Банк Infrastructure",
        "title": "Детектор утечки подключений СУБД (Connection Pool Leak)",
        "category": "DevOps",
        "difficulty": "MEDIUM",
        "language": "Python 3.11 / SQL",
        "reward": 240,
        "description": (
            "В системе мониторинга Т-Банк требуется определять микросервисы, утекающие пулы соединений к PostgreSQL.\n"
            "Напишите функцию <code>detect_leaking_services(connections, max_idle_sec)</code>, где <code>connections</code> — список:\n"
            "<pre>[{'service': str, 'state': str, 'idle_duration_sec': int}]</pre>\n"
            "Если соединение находится в статусе <code>'IDLE'</code> дольше <code>max_idle_sec</code>, оно считается 'зависшим'.\n"
            "Верните словарь <code>{'service_name': leaked_count}</code> с сервисами, у которых есть хотя бы 1 зависшее соединение."
        ),
        "starter_code": (
            "def detect_leaking_services(connections: list[dict], max_idle_sec: int) -> dict:\n"
            "    # Напишите мониторинг пула БД здесь\n"
            "    pass"
        ),
        "entry_point": "detect_leaking_services",
        "test_cases": [
            {
                "input": [[
                    {"service": "auth-service", "state": "IDLE", "idle_duration_sec": 300},
                    {"service": "auth-service", "state": "ACTIVE", "idle_duration_sec": 10},
                    {"service": "payment-service", "state": "IDLE", "idle_duration_sec": 50}
                ], 120],
                "expected": {"auth-service": 1},
                "description": "Обнаружение утечки у auth-service"
            }
        ]
    },
    {
        "id": "sber_log_parser",
        "company": "Сбер AI / Cloud",
        "title": "Анализатор логов Nginx и детектор 5xx ошибок",
        "category": "DevOps",
        "difficulty": "MEDIUM",
        "language": "Python 3.11",
        "reward": 220,
        "description": (
            "Система мониторинга СберCloud анализирует логи веб-серверов.\n"
            "Напишите функцию <code>analyze_nginx_logs(logs)</code>, принимающую список строк формата:\n"
            "<pre>'IP - [TIMESTAMP] \"METHOD PATH\" STATUS RESPONSE_TIME'</pre>\n"
            "Верните словарь <code>{'total_requests': int, 'error_rate_pct': float, 'top_failing_path': str}</code>."
        ),
        "starter_code": (
            "def analyze_nginx_logs(logs: list) -> dict:\n"
            "    # Напишите решение здесь\n"
            "    pass"
        ),
        "entry_point": "analyze_nginx_logs",
        "test_cases": [
            {
                "input": [[
                    '10.0.0.1 - [24/Jul] "GET /pay" 500 0.1',
                    '10.0.0.2 - [24/Jul] "POST /login" 200 0.05',
                    '10.0.0.3 - [24/Jul] "GET /pay" 502 0.3'
                ]],
                "expected": {"total_requests": 3, "error_rate_pct": 66.67, "top_failing_path": "/pay"},
                "description": "66.67% ошибок 5xx"
            }
        ]
    }
]

def get_tasks_by_category(category: Optional[str] = None) -> List[Dict[str, Any]]:
    if not category or category.lower() in ["all", "случайный", "any", "все"]:
        return IT_TASKS_DB
    return [t for t in IT_TASKS_DB if t["category"].lower() == category.lower()]

def get_task_by_id(task_id: str) -> Optional[Dict[str, Any]]:
    for t in IT_TASKS_DB:
        if t["id"] == task_id:
            return t
    return None
