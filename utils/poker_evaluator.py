"""Движок оценки покерных комбинаций для Техасского Холдема (Texas Hold'em).
Оценивает 5-карточные и 7-карточные комбинации, определяет победителей и кикеры.
"""
from itertools import combinations
from typing import List, Tuple, Dict, Any, Union

# Ранги карт: 2..14 (14 = Туз)
RANK_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
}
VALUE_TO_RANK = {v: k for k, v in RANK_VALUES.items()}

SUIT_SYMBOLS = {
    'S': '♠', 'H': '♥', 'D': '♦', 'C': '♣',
    'spades': '♠', 'hearts': '♥', 'diamonds': '♦', 'clubs': '♣'
}

# Старшинство комбинаций
HAND_ROYAL_FLUSH = 10
HAND_STRAIGHT_FLUSH = 9
HAND_FOUR_OF_A_KIND = 8
HAND_FULL_HOUSE = 7
HAND_FLUSH = 6
HAND_STRAIGHT = 5
HAND_THREE_OF_A_KIND = 4
HAND_TWO_PAIR = 3
HAND_ONE_PAIR = 2
HAND_HIGH_CARD = 1

HAND_NAMES = {
    HAND_ROYAL_FLUSH: "Роял-флеш",
    HAND_STRAIGHT_FLUSH: "Стрит-флеш",
    HAND_FOUR_OF_A_KIND: "Каре",
    HAND_FULL_HOUSE: "Фулл-хаус",
    HAND_FLUSH: "Флеш",
    HAND_STRAIGHT: "Стрит",
    HAND_THREE_OF_A_KIND: "Тройка (Сет)",
    HAND_TWO_PAIR: "Две пары",
    HAND_ONE_PAIR: "Пара",
    HAND_HIGH_CARD: "Старшая карта"
}

RANK_NAMES_RU = {
    2: "Двоек", 3: "Троек", 4: "Четверок", 5: "Пятерок", 6: "Шестерок",
    7: "Семерок", 8: "Восьмерок", 9: "Девяток", 10: "Десяток",
    11: "Валетов", 12: "Дам", 13: "Королей", 14: "Тузов"
}

RANK_SINGLE_RU = {
    2: "Двойка", 3: "Тройка", 4: "Четверка", 5: "Пятерка", 6: "Шестерка",
    7: "Семерка", 8: "Восьмерка", 9: "Девятка", 10: "Десятка",
    11: "Валет", 12: "Дама", 13: "Король", 14: "Туз"
}

RANK_GENITIVE_RU = {
    2: "Двойки", 3: "Тройки", 4: "Четверки", 5: "Пятерки", 6: "Шестерки",
    7: "Семерки", 8: "Восьмерки", 9: "Девятки", 10: "Десятки",
    11: "Валета", 12: "Дамы", 13: "Короля", 14: "Туза"
}

RANK_INSTRUMENTAL_RU = {
    2: "Двойкой", 3: "Тройкой", 4: "Четверкой", 5: "Пятеркой", 6: "Шестеркой",
    7: "Семеркой", 8: "Восьмеркой", 9: "Девяткой", 10: "Десяткой",
    11: "Валетом", 12: "Дамой", 13: "Королем", 14: "Тузом"
}


def card_str(card: Union[Dict[str, str], Tuple[str, str]]) -> str:
    """Форматирует карту в виде 'A♠' или '10♥'."""
    if isinstance(card, dict):
        rank = card['rank']
        suit = card['suit']
    else:
        rank, suit = card
    suit_icon = SUIT_SYMBOLS.get(suit, suit)
    return f"{rank}{suit_icon}"


def format_cards(cards: List[Union[Dict[str, str], Tuple[str, str]]]) -> str:
    """Форматирует список карт: '[ 10♠ ] [ A♥ ]'."""
    return " ".join(f"[{card_str(c)}]" for c in cards)


def _card_val(card: Union[Dict[str, str], Tuple[str, str]]) -> Tuple[int, str]:
    if isinstance(card, dict):
        return RANK_VALUES[str(card['rank'])], card['suit']
    return RANK_VALUES[str(card[0])], card[1]


def evaluate_5card_hand(cards: List[Any]) -> Tuple[int, List[int], str]:
    """
    Оценивает ровно 5 карт.
    Возвращает: (hand_rank, kickers, hand_description)
    Где kickers - список чисел для точного сравнения рук при равенстве hand_rank.
    """
    parsed = [_card_val(c) for c in cards]
    # Сортируем по убыванию достоинства
    ranks = sorted([p[0] for p in parsed], reverse=True)
    suits = [p[1] for p in parsed]
    
    is_flush = len(set(suits)) == 1
    
    # Проверка на стрит (включая Ace-low A-2-3-4-5)
    is_straight = False
    straight_high = 0
    if len(set(ranks)) == 5:
        if ranks[0] - ranks[4] == 4:
            is_straight = True
            straight_high = ranks[0]
        elif ranks == [14, 5, 4, 3, 2]:
            is_straight = True
            straight_high = 5  # Пятерка - старшая в колесе
    
    # Подсчет количества одинаковых рангов
    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    
    # Сортируем группы по частоте (убывание), затем по значению ранга (убывание)
    freq_sorted = sorted(rank_counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    counts = [item[1] for item in freq_sorted]
    grouped_ranks = [item[0] for item in freq_sorted]
    
    # 1. Роял-флеш и Стрит-флеш
    if is_flush and is_straight:
        if straight_high == 14:
            return HAND_ROYAL_FLUSH, [14], "Роял-флеш"
        return HAND_STRAIGHT_FLUSH, [straight_high], f"Стрит-флеш до {RANK_GENITIVE_RU[straight_high]}"
    
    # 2. Каре
    if counts == [4, 1]:
        desc = f"Каре {RANK_NAMES_RU[grouped_ranks[0]]}"
        return HAND_FOUR_OF_A_KIND, grouped_ranks, desc
    
    # 3. Фулл-хаус
    if counts == [3, 2]:
        desc = f"Фулл-хаус ({RANK_NAMES_RU[grouped_ranks[0]]} и {RANK_NAMES_RU[grouped_ranks[1]]})"
        return HAND_FULL_HOUSE, grouped_ranks, desc
    
    # 4. Флеш
    if is_flush:
        desc = f"Флеш со старшей {RANK_INSTRUMENTAL_RU[ranks[0]]}"
        return HAND_FLUSH, ranks, desc
    
    # 5. Стрит
    if is_straight:
        desc = f"Стрит до {RANK_GENITIVE_RU[straight_high]}"
        return HAND_STRAIGHT, [straight_high], desc
    
    # 6. Тройка / Сет
    if counts == [3, 1, 1]:
        desc = f"Тройка {RANK_NAMES_RU[grouped_ranks[0]]}"
        return HAND_THREE_OF_A_KIND, grouped_ranks, desc
    
    # 7. Две пары
    if counts == [2, 2, 1]:
        desc = f"Две пары ({RANK_NAMES_RU[grouped_ranks[0]]} и {RANK_NAMES_RU[grouped_ranks[1]]})"
        return HAND_TWO_PAIR, grouped_ranks, desc
    
    # 8. Одна пара
    if counts == [2, 1, 1, 1]:
        desc = f"Пара {RANK_NAMES_RU[grouped_ranks[0]]}"
        return HAND_ONE_PAIR, grouped_ranks, desc
    
    # 9. Старшая карта
    return HAND_HIGH_CARD, ranks, f"Старшая карта {RANK_SINGLE_RU[ranks[0]]}"


def evaluate_7card_hand(cards: List[Any]) -> Dict[str, Any]:
    """
    Оценивает 7 карт (2 карманные + до 5 общих на столе).
    Если на столе пока меньше 5 карт (например префлоп/флоп/терн), оценивает из имеющихся карт.
    Возвращает лучший 5-карточный расклад:
    {
        "hand_rank": int,
        "kickers": list,
        "description": str,
        "best_5_cards": list
    }
    """
    if len(cards) < 5:
        parsed = [_card_val(c) for c in cards]
        ranks = sorted([p[0] for p in parsed], reverse=True)
        if len(cards) == 2 and ranks[0] == ranks[1]:
            return {
                "hand_rank": HAND_ONE_PAIR,
                "kickers": [ranks[0]],
                "description": f"Карманная пара {RANK_NAMES_RU[ranks[0]]}",
                "best_5_cards": cards
            }
        return {
            "hand_rank": HAND_HIGH_CARD,
            "kickers": ranks,
            "description": f"Старшая карта {RANK_SINGLE_RU[ranks[0]]}" if ranks else "Карты сданы",
            "best_5_cards": cards
        }
    
    best_hand = None
    best_rank = (-1, [])
    
    for combo in combinations(cards, 5):
        hand_rank, kickers, desc = evaluate_5card_hand(list(combo))
        score = (hand_rank, kickers)
        if score > best_rank:
            best_rank = score
            best_hand = {
                "hand_rank": hand_rank,
                "kickers": kickers,
                "description": desc,
                "best_5_cards": list(combo)
            }
            
    return best_hand


def compare_hands(hand1: Dict[str, Any], hand2: Dict[str, Any]) -> int:
    """
    Сравнивает две руки.
    Возвращает 1 если hand1 > hand2, -1 если hand1 < hand2, 0 если ничья (сплит).
    """
    score1 = (hand1["hand_rank"], hand1["kickers"])
    score2 = (hand2["hand_rank"], hand2["kickers"])
    
    if score1 > score2:
        return 1
    elif score1 < score2:
        return -1
    else:
        return 0
