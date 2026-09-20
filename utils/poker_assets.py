"""Генератор инфографики комбинаций для покера."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def generate_poker_chart(output_path: str = "data/assets/poker_combinations.png") -> str:
    """Генерирует красивую инфографику 10 комбинаций Техасского Холдема."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    
    width = 960
    height = 1400
    img = Image.new("RGB", (width, height), color=(18, 22, 34))
    draw = ImageDraw.Draw(img)
    
    # Пытаемся загрузить шрифты Windows и Linux
    def get_font(size: int, bold: bool = False):
        font_candidates = [
            f"C:/Windows/Fonts/{'segoeuib.ttf' if bold else 'segoeui.ttf'}",
            f"C:/Windows/Fonts/{'arialbd.ttf' if bold else 'arial.ttf'}",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "segoeuib.ttf" if bold else "segoeui.ttf",
            "arialbd.ttf" if bold else "arial.ttf",
            "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        ]
        for path in font_candidates:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    font_title = get_font(34, bold=True)
    font_sub = get_font(18, bold=False)
    font_combo_title = get_font(21, bold=True)
    font_desc = get_font(15, bold=False)
    font_card_rank = get_font(17, bold=True)
    font_card_suit = get_font(16, bold=True)
    
    # Внешняя рамка
    draw.rounded_rectangle([15, 15, width - 15, height - 15], radius=24, outline=(212, 175, 55), width=3)
    
    # Шапка
    draw.rounded_rectangle([30, 30, width - 30, 115], radius=16, fill=(28, 35, 54), outline=(70, 85, 125), width=2)
    draw.text((width // 2, 52), "ПОКЕРНЫЕ КОМБИНАЦИИ", fill=(255, 215, 0), font=font_title, anchor="mm")
    draw.text((width // 2, 92), "Техасский Холдем • Иерархия от сильнейшей к слабейшей", fill=(180, 200, 225), font=font_sub, anchor="mm")
    
    combos = [
        {
            "rank": 1,
            "name": "Роял-флеш (Royal Flush)",
            "desc": "Туз, Король, Дама, Валет и Десятка одной масти. Непобедима!",
            "cards": [("A", "♠", "black"), ("K", "♠", "black"), ("Q", "♠", "black"), ("J", "♠", "black"), ("10", "♠", "black")],
            "highlight": (255, 215, 0)
        },
        {
            "rank": 2,
            "name": "Стрит-флеш (Straight Flush)",
            "desc": "Пять карт по порядку одной масти.",
            "cards": [("9", "♥", "red"), ("8", "♥", "red"), ("7", "♥", "red"), ("6", "♥", "red"), ("5", "♥", "red")],
            "highlight": (255, 180, 50)
        },
        {
            "rank": 3,
            "name": "Каре (Four of a Kind)",
            "desc": "Четыре карты одного достоинства.",
            "cards": [("K", "♦", "red"), ("K", "♠", "black"), ("K", "♥", "red"), ("K", "♣", "black"), ("4", "♠", "black")],
            "highlight": (255, 120, 120)
        },
        {
            "rank": 4,
            "name": "Фулл-хаус (Full House)",
            "desc": "Тройка одного достоинства + Пара другого.",
            "cards": [("Q", "♠", "black"), ("Q", "♥", "red"), ("Q", "♦", "red"), ("8", "♣", "black"), ("8", "♦", "red")],
            "highlight": (180, 150, 255)
        },
        {
            "rank": 5,
            "name": "Флеш (Flush)",
            "desc": "Пять карт одинаковой масти в любом порядке.",
            "cards": [("A", "♦", "red"), ("J", "♦", "red"), ("8", "♦", "red"), ("6", "♦", "red"), ("3", "♦", "red")],
            "highlight": (120, 200, 255)
        },
        {
            "rank": 6,
            "name": "Стрит (Straight)",
            "desc": "Пять карт по порядку любых мастей (Туз может быть A-2-3-4-5).",
            "cards": [("9", "♣", "black"), ("8", "♠", "black"), ("7", "♦", "red"), ("6", "♥", "red"), ("5", "♠", "black")],
            "highlight": (120, 255, 160)
        },
        {
            "rank": 7,
            "name": "Тройка / Сет (Three of a Kind)",
            "desc": "Три карты одного достоинства.",
            "cards": [("7", "♠", "black"), ("7", "♥", "red"), ("7", "♦", "red"), ("K", "♣", "black"), ("2", "♠", "black")],
            "highlight": (240, 230, 140)
        },
        {
            "rank": 8,
            "name": "Две пары (Two Pair)",
            "desc": "Две карты одного достоинства и две другого.",
            "cards": [("J", "♠", "black"), ("J", "♦", "red"), ("4", "♥", "red"), ("4", "♣", "black"), ("A", "♠", "black")],
            "highlight": (200, 200, 200)
        },
        {
            "rank": 9,
            "name": "Пара (One Pair)",
            "desc": "Две карты одного достоинства.",
            "cards": [("10", "♥", "red"), ("10", "♦", "red"), ("A", "♣", "black"), ("K", "♠", "black"), ("6", "♦", "red")],
            "highlight": (170, 170, 180)
        },
        {
            "rank": 10,
            "name": "Старшая карта (High Card)",
            "desc": "Если нет ни одной комбинации, побеждает старшая карта.",
            "cards": [("A", "♠", "black"), ("K", "♦", "red"), ("9", "♥", "red"), ("7", "♣", "black"), ("3", "♦", "red")],
            "highlight": (140, 140, 150)
        }
    ]
    
    start_y = 135
    row_height = 118
    
    suit_char_map = {
        "♠": "\u2660",
        "♥": "\u2665",
        "♦": "\u2666",
        "♣": "\u2663"
    }

    for i, item in enumerate(combos):
        y = start_y + i * row_height
        
        # Плашка комбинации
        draw.rounded_rectangle([30, y, width - 30, y + row_height - 12], radius=12, fill=(24, 30, 46), outline=(48, 58, 84), width=1)
        
        # Номер ранга в кружочке/плашке
        draw.rounded_rectangle([42, y + 14, 76, y + 48], radius=8, fill=item["highlight"])
        draw.text((59, y + 31), str(item["rank"]), fill=(20, 20, 20), font=font_combo_title, anchor="mm")
        
        # Название комбинации
        draw.text((90, y + 29), item["name"], fill=(245, 245, 245), font=font_combo_title, anchor="lm")
        # Описание
        draw.text((90, y + 54), item["desc"], fill=(160, 175, 200), font=font_desc, anchor="lm")
        
        # Отрисовка 5 карт справа
        cards_start_x = width - 290
        card_w = 46
        card_h = 64
        card_y = y + 20
        
        for ci, (rank_val, suit_val, color_type) in enumerate(item["cards"]):
            cx = cards_start_x + ci * (card_w + 6)
            # Белая подложка карты с легкой тенью
            draw.rounded_rectangle([cx, card_y, cx + card_w, card_y + card_h], radius=6, fill=(245, 248, 252), outline=(180, 190, 210), width=1)
            
            c_fill = (220, 30, 30) if color_type == "red" else (25, 25, 30)
            s_icon = suit_char_map.get(suit_val, suit_val)
            
            # Ранг карты
            draw.text((cx + 7, card_y + 16), rank_val, fill=c_fill, font=font_card_rank, anchor="mm")
            # Масть карты
            draw.text((cx + card_w - 12, card_y + card_h - 18), s_icon, fill=c_fill, font=font_card_suit, anchor="mm")

    # Футер
    draw.text((width // 2, height - 32), "WolfMireaBot Casino • Покерные правила", fill=(120, 140, 170), font=font_sub, anchor="mm")
    
    img.save(target, format="PNG")
    return str(target)


if __name__ == "__main__":
    generate_poker_chart()
