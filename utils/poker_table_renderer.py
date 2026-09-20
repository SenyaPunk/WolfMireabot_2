"""Рендерер графического покерного стола с картами и игроками."""
import io
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# Символы мастей
SUIT_SYMBOLS = {
    'S': '♠', 'H': '♥', 'D': '♦', 'C': '♣',
    'spades': '♠', 'hearts': '♥', 'diamonds': '♦', 'clubs': '♣'
}
RED_SUITS = {'H', 'D', 'hearts', 'diamonds', '♥', '♦'}


def get_font(size: int, bold: bool = False):
    """Кросс-платформенная загрузка шрифтов."""
    font_candidates = [
        f"C:/Windows/Fonts/{'segoeuib.ttf' if bold else 'segoeui.ttf'}",
        f"C:/Windows/Fonts/{'arialbd.ttf' if bold else 'arial.ttf'}",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "arialbd.ttf" if bold else "arial.ttf"
    ]
    for path in font_candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_card(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, card: Optional[Dict[str, str]] = None, is_small: bool = False):
    """Отрисовывает одну карту: лицевую или рубашку."""
    if card is None:
        # Рубашка карты
        draw.rounded_rectangle([x, y, x + w, y + h], radius=5, fill=(24, 44, 88), outline=(170, 185, 215), width=1)
        inset = 3
        draw.rounded_rectangle([x + inset, y + inset, x + w - inset, y + h - inset], radius=3, fill=(32, 56, 110), outline=(65, 100, 180), width=1)
        cx, cy = x + w // 2, y + h // 2
        draw.line([x + inset + 2, y + inset + 2, x + w - inset - 2, y + h - inset - 2], fill=(50, 80, 150), width=1)
        draw.line([x + inset + 2, y + h - inset - 2, x + w - inset - 2, y + inset + 2], fill=(50, 80, 150), width=1)
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(212, 175, 55))
        return

    # Лицевая карта
    rank = str(card.get("rank", "?"))
    suit = card.get("suit", "S")
    suit_char = SUIT_SYMBOLS.get(suit, suit)
    is_red = suit in RED_SUITS

    color = (215, 20, 20) if is_red else (20, 22, 28)
    
    # Белая основа карты с закруглениями
    draw.rounded_rectangle([x, y, x + w, y + h], radius=5, fill=(252, 253, 255), outline=(150, 165, 185), width=1)
    
    if is_small:
        f_rank = get_font(12, bold=True)
        f_suit = get_font(11, bold=True)
        draw.text((x + 4, y + 8), rank, fill=color, font=f_rank, anchor="lm")
        draw.text((x + w - 4, y + h - 8), suit_char, fill=color, font=f_suit, anchor="rm")
        draw.text((x + w // 2, y + h // 2), suit_char, fill=color, font=get_font(15, bold=True), anchor="mm")
    else:
        f_rank = get_font(18, bold=True)
        f_suit = get_font(16, bold=True)
        f_center = get_font(28, bold=True)
        
        # Левый верхний угол
        draw.text((x + 7, y + 13), rank, fill=color, font=f_rank, anchor="mm")
        draw.text((x + 7, y + 29), suit_char, fill=color, font=f_suit, anchor="mm")
        
        # Центр карты
        draw.text((x + w // 2, y + h // 2 + 2), suit_char, fill=color, font=f_center, anchor="mm")
        
        # Правый нижний угол
        draw.text((x + w - 7, y + h - 29), suit_char, fill=color, font=f_suit, anchor="mm")
        draw.text((x + w - 7, y + h - 13), rank, fill=color, font=f_rank, anchor="mm")


def render_poker_table_image(game_state: Dict[str, Any], is_showdown: bool = False) -> io.BytesIO:
    """Генерирует изображение покерного стола на основе текущего состояния игры."""
    w, h = 960, 580
    img = Image.new("RGB", (w, h), color=(14, 17, 24))
    draw = ImageDraw.Draw(img)
    
    # 1. Стол (Деревянный бортик и зеленое сукно)
    draw.rounded_rectangle([30, 25, w - 30, h - 25], radius=160, fill=(42, 22, 14), outline=(212, 168, 67), width=4)
    draw.rounded_rectangle([42, 37, w - 42, h - 37], radius=150, outline=(135, 90, 30), width=2)
    draw.rounded_rectangle([48, 43, w - 48, h - 43], radius=145, fill=(15, 78, 50), outline=(8, 48, 30), width=3)
    draw.rounded_rectangle([95, 85, w - 95, h - 85], radius=120, outline=(24, 112, 72), width=2)
    
    # Небольшой едва заметный водяной знак логотипа Волки МИРЭА
    logo_path = Path("data/assets/volki_mirea_logo.png")
    if logo_path.exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo_size = 100
            logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            alpha = logo.split()[3]
            alpha = ImageEnhance.Brightness(alpha).enhance(0.10)
            logo.putalpha(alpha)
            img.paste(logo, ((w - logo_size) // 2, 200), mask=logo)
        except Exception:
            pass

    # Брендинг университета и чата на сукне (мягкий и ненавязчивый)
    f_brand = get_font(12, bold=False)
    draw.text((w // 2, 385), "РТУ МИРЭА • ВОЛКИ", fill=(24, 96, 62), font=f_brand, anchor="mm")
    
    # Едва заметная пасхалка автора (SenyaPnk) на нижнем деревянном бортике
    f_egg = get_font(11, bold=False)
    draw.text((w // 2, h - 31), "SenyaPnk", fill=(72, 40, 26), font=f_egg, anchor="mm")
    
    # 2. Банк (Pot) и название улицы в центре стола
    pot = game_state.get("pot", 0)
    street = game_state.get("street", "preflop").upper()
    street_names = {
        "PREFLOP": "ПРЕФЛОП",
        "FLOP": "ФЛОП",
        "TURN": "ТЕРН",
        "RIVER": "РИВЕР",
        "SHOWDOWN": "ИТОГИ РАЗДАЧИ"
    }
    street_display = street_names.get(street, street)
    
    # Плашка банка
    pot_w, pot_h = 240, 38
    pot_x = (w - pot_w) // 2
    pot_y = 145
    draw.rounded_rectangle([pot_x, pot_y, pot_x + pot_w, pot_y + pot_h], radius=10, fill=(20, 26, 36), outline=(212, 175, 55), width=2)
    f_pot = get_font(18, bold=True)
    draw.text((w // 2, pot_y + pot_h // 2), f"БАНК: {pot} МОНЕТ", fill=(255, 215, 60), font=f_pot, anchor="mm")
    
    # Бейдж улицы над банком
    f_street = get_font(14, bold=True)
    draw.text((w // 2, pot_y - 13), f"• {street_display} •", fill=(195, 230, 210), font=f_street, anchor="mm")
    
    # 3. 5 Общих карт стола (Community Cards)
    community = game_state.get("community_cards", [])
    card_w, card_h = 68, 96
    gap = 14
    total_cards_w = 5 * card_w + 4 * gap
    start_cards_x = (w - total_cards_w) // 2
    cards_y = 200
    
    for i in range(5):
        cx = start_cards_x + i * (card_w + gap)
        if i < len(community):
            draw_card(draw, cx, cards_y, card_w, card_h, card=community[i], is_small=False)
        else:
            # Закрытая позиция (рубашка)
            draw_card(draw, cx, cards_y, card_w, card_h, card=None, is_small=False)
            
    # 4. Игроки за столом
    players = game_state.get("players", [])
    current_actor_idx = game_state.get("current_actor_idx", 0)
    
    # Координаты мест (для 2..6 игроков)
    seat_positions = [
        {"x": 160, "y": 65},   # 0 Top Left
        {"x": 620, "y": 65},   # 1 Top Right
        {"x": 730, "y": 320},  # 2 Mid Right
        {"x": 620, "y": 475},  # 3 Bottom Right
        {"x": 160, "y": 475},  # 4 Bottom Left
        {"x": 60,  "y": 320},  # 5 Mid Left
    ]
    # Оптимизация для 2 игроков (друг напротив друга)
    if len(players) == 2:
        seat_positions = [
            {"x": 370, "y": 475}, # Игрок 1 снизу
            {"x": 370, "y": 65},  # Игрок 2 сверху
        ]
        
    for idx, p in enumerate(players):
        if idx >= len(seat_positions):
            break
            
        pos = seat_positions[idx]
        sx, sy = pos["x"], pos["y"]
        
        is_acting = (idx == current_actor_idx) and not is_showdown and not p.get("folded") and not p.get("all_in")
        is_folded = p.get("folded", False)
        is_allin = p.get("all_in", False)
        
        # Размеры плашки и 2 карт
        c_w, c_h = 32, 46
        box_w, box_h = 145, 48
        
        # Карты слева от плашки
        card1_x = sx
        card2_x = sx + c_w + 3
        card_y = sy + (box_h - c_h) // 2
        
        # Плашка справа от карт
        bx = card2_x + c_w + 8
        by = sy
        
        if is_acting:
            box_border = (50, 220, 90)
            box_bg = (24, 46, 32)
            border_w = 2
        elif is_folded:
            box_border = (80, 85, 95)
            box_bg = (25, 27, 34)
            border_w = 1
        elif is_allin:
            box_border = (255, 170, 40)
            box_bg = (44, 34, 20)
            border_w = 2
        else:
            box_border = (60, 75, 105)
            box_bg = (20, 26, 38)
            border_w = 1
            
        draw.rounded_rectangle([bx, by, bx + box_w, by + box_h], radius=8, fill=box_bg, outline=box_border, width=border_w)
        
        # Имя игрока
        name = p.get("first_name", f"Игрок {idx+1}")
        if len(name) > 13:
            name = name[:12] + "…"
        f_name = get_font(12, bold=True)
        draw.text((bx + box_w // 2, by + 12), name, fill=(240, 240, 240) if not is_folded else (130, 135, 145), font=f_name, anchor="mm")
        
        # Стек и ставка
        stack = p.get("stack", 0)
        round_bet = p.get("round_bet", 0)
        f_info = get_font(10, bold=False)
        
        if is_folded:
            draw.text((bx + box_w // 2, by + 30), "[ ПАС ]", fill=(190, 110, 110), font=get_font(11, bold=True), anchor="mm")
        elif is_acting:
            draw.text((bx + box_w // 2, by + 26), f"Стек: {stack} | {round_bet}", fill=(180, 245, 190), font=f_info, anchor="mm")
            draw.text((bx + box_w // 2, by + 38), ">> ХОДИТ <<", fill=(60, 255, 120), font=get_font(9, bold=True), anchor="mm")
        elif is_allin:
            draw.text((bx + box_w // 2, by + 30), f"ALL-IN: {p.get('total_bet', 0)}", fill=(255, 200, 70), font=get_font(11, bold=True), anchor="mm")
        else:
            draw.text((bx + box_w // 2, by + 30), f"Стек: {stack} | {round_bet}", fill=(180, 195, 215), font=f_info, anchor="mm")
            
        # Отрисовка 2 карт
        hole = p.get("hole_cards", [])
        if is_showdown and not is_folded and len(hole) == 2:
            # На шоудауне открываем карты
            draw_card(draw, card1_x, card_y, c_w, c_h, card=hole[0], is_small=True)
            draw_card(draw, card2_x, card_y, c_w, c_h, card=hole[1], is_small=True)
        elif not is_folded:
            # Рубашки карт
            draw_card(draw, card1_x, card_y, c_w, c_h, card=None, is_small=True)
            draw_card(draw, card2_x, card_y, c_w, c_h, card=None, is_small=True)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


if __name__ == "__main__":
    test_state = {
        "pot": 400,
        "street": "flop",
        "community_cards": [{"rank": "A", "suit": "S"}, {"rank": "K", "suit": "H"}, {"rank": "10", "suit": "D"}],
        "current_actor_idx": 0,
        "players": [
            {"first_name": "Сеня", "stack": 850, "round_bet": 50, "hole_cards": [{"rank": "A", "suit": "H"}, {"rank": "Q", "suit": "S"}]},
            {"first_name": "Иван", "stack": 400, "round_bet": 50, "hole_cards": [{"rank": "K", "suit": "D"}, {"rank": "J", "suit": "C"}]}
        ]
    }
    b = render_poker_table_image(test_state)
    Path("data/assets/test_table.png").write_bytes(b.getvalue())
    print("Clean horizontal layout rendered to data/assets/test_table.png")
