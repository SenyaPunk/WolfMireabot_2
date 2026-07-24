import io
import math
import os
import urllib.request
import logging
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

logger = logging.getLogger(__name__)

# Список символов слотов под стиль «Волки МИРЭА»: (Смайлик, Название, Коэффициент)
SYMBOLS = [
    ("7️⃣", "Семерка", 100.0),
    ("🐺", "Волк", 50.0),
    ("💰", "Мешок денег", 25.0),
    ("🏆", "Золотой кубок", 15.0),
    ("🪙", "Золотая монета", 10.0),
    ("🎲", "Игральные кости", 8.0),
    ("🔥", "Огонь азарта", 5.0),
    ("🐾", "Волчьи лапы", 3.0)
]

ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "assets"))

# Соответствие индексов символов именам файлов кастомных ассетов
CUSTOM_ASSETS = {
    1: "wolf.png",
    2: "bag.png",
    3: "cup.png",
    4: "coin.png",
    5: "dice.png",
    6: "fire.png",
    7: "paw.png"
}

# Соответствие кодам Twemoji (в качестве автоматического красивого fallback)
EMOJI_CODES = {
    1: "1f43a",  # Волк 🐺
    2: "1f4b0",  # Мешок денег 💰
    3: "1f3c6",  # Золотой кубок 🏆
    4: "1fa99",  # Золотая монета 🪙
    5: "1f3b2",  # Игральные кости 🎲
    6: "1f525",  # Огонь 🔥
    7: "1f43e"   # Волчьи лапы 🐾
}

def draw_seven(draw_obj, x_offset: int, y_offset: int):
    """Рисует красивую объемную красную семерку 70x70 с золотой тенью."""
    points = [
        (18, 12), (52, 12), (30, 58), (20, 58), 
        (40, 23), (18, 23)
    ]
    shifted_points = [(x + x_offset, y + y_offset) for x, y in points]
    gold_points = [(x + 2, y + 2) for x, y in shifted_points]
    draw_obj.polygon(gold_points, fill=(218, 165, 32, 255))
    draw_obj.polygon(shifted_points, fill=(230, 20, 20, 255))

def draw_fallback_symbol(draw_obj, idx: int, x_offset: int, y_offset: int):
    """Векторная отрисовка новых fallback-фигур 70x70, если нет картинок."""
    cx = x_offset + 35
    cy = y_offset + 35
    
    if idx == 1:  # Волк 🐺 (серый силуэт головы волка)
        points = [
            (cx, y_offset + 18),
            (x_offset + 52, y_offset + 36),
            (x_offset + 46, y_offset + 52),
            (x_offset + 24, y_offset + 52),
            (x_offset + 18, y_offset + 36)
        ]
        draw_obj.polygon(points, fill=(120, 125, 130, 255), outline=(80, 85, 90, 255), width=1)
        # Ушки волка
        draw_obj.polygon([(x_offset + 18, y_offset + 36), (x_offset + 16, y_offset + 18), (cx - 8, y_offset + 28)], fill=(100, 105, 110, 255))
        draw_obj.polygon([(x_offset + 52, y_offset + 36), (x_offset + 54, y_offset + 18), (cx + 8, y_offset + 28)], fill=(100, 105, 110, 255))
    elif idx == 2:  # Мешок денег 💰
        draw_obj.ellipse([x_offset + 20, y_offset + 26, x_offset + 50, y_offset + 54], fill=(218, 165, 32, 255), outline=(150, 100, 10, 255), width=1)
        draw_obj.polygon([(cx - 8, y_offset + 26), (cx + 8, y_offset + 26), (cx, y_offset + 18)], fill=(184, 134, 11, 255))
    elif idx == 3:  # Золотой кубок 🏆
        points = [
            (x_offset + 18, y_offset + 18),
            (x_offset + 52, y_offset + 18),
            (x_offset + 46, y_offset + 42),
            (x_offset + 26, y_offset + 42)
        ]
        draw_obj.polygon(points, fill=(255, 215, 0, 255), outline=(184, 134, 11, 255), width=1)
        draw_obj.line([(cx, y_offset + 42), (cx, y_offset + 50)], fill=(184, 134, 11, 255), width=2)
        draw_obj.ellipse([cx - 12, y_offset + 48, cx + 12, y_offset + 54], fill=(184, 134, 11, 255))
    elif idx == 4:  # Золотая монета 🪙
        draw_obj.ellipse([x_offset + 18, y_offset + 18, x_offset + 52, y_offset + 52], fill=(240, 190, 20, 255), outline=(180, 130, 10, 255), width=2)
        draw_obj.ellipse([x_offset + 25, y_offset + 25, x_offset + 45, y_offset + 45], fill=(250, 210, 40, 255))
    elif idx == 5:  # Игральные кости 🎲
        draw_obj.rounded_rectangle([x_offset + 18, y_offset + 18, x_offset + 52, y_offset + 52], radius=6, fill=(245, 245, 245, 255), outline=(150, 150, 150, 255), width=1)
        # Точки на кубике (5 точек)
        draw_obj.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(20, 20, 20, 255))
        draw_obj.ellipse([x_offset + 24, y_offset + 24, x_offset + 28, y_offset + 28], fill=(20, 20, 20, 255))
        draw_obj.ellipse([x_offset + 42, y_offset + 24, x_offset + 46, y_offset + 28], fill=(20, 20, 20, 255))
        draw_obj.ellipse([x_offset + 24, y_offset + 42, x_offset + 28, y_offset + 46], fill=(20, 20, 20, 255))
        draw_obj.ellipse([x_offset + 42, y_offset + 42, x_offset + 46, y_offset + 46], fill=(20, 20, 20, 255))
    elif idx == 6:  # Огонь 🔥
        points = [
            (cx, y_offset + 16),
            (x_offset + 46, y_offset + 32),
            (x_offset + 52, y_offset + 48),
            (cx, y_offset + 56),
            (x_offset + 18, y_offset + 48),
            (x_offset + 24, y_offset + 32)
        ]
        draw_obj.polygon(points, fill=(255, 69, 0, 255))
        # Внутреннее пламя
        draw_obj.polygon([(cx, y_offset + 28), (cx + 8, y_offset + 42), (cx, y_offset + 48), (cx - 8, y_offset + 42)], fill=(255, 215, 0, 255))
    elif idx == 7:  # Волчьи лапы 🐾
        # Центральная подушечка
        draw_obj.ellipse([cx - 10, cy - 4, cx + 10, cy + 12], fill=(50, 50, 50, 255))
        # Четыре пальчика
        draw_obj.ellipse([cx - 12, cy - 14, cx - 4, cy - 6], fill=(50, 50, 50, 255))
        draw_obj.ellipse([cx - 4, cy - 18, cx + 4, cy - 10], fill=(50, 50, 50, 255))
        draw_obj.ellipse([cx + 4, cy - 14, cx + 12, cy - 6], fill=(50, 50, 50, 255))

def create_strip() -> Image.Image:
    """Создает вертикальную ленту символов 70x560 из кастомных PNG или Twemoji."""
    strip = Image.new("RGBA", (70, 560), (0, 0, 0, 0))
    draw = ImageDraw.Draw(strip)
    
    try:
        os.makedirs(ASSETS_DIR, exist_ok=True)
    except Exception as e:
        logger.warning(f"Не удалось создать директорию ассетов: {e}")
        
    for i in range(8):
        y_offset = i * 70
        if i == 0:  # Семерка вектором
            draw_seven(draw, 0, y_offset)
        else:
            custom_name = CUSTOM_ASSETS[i]
            custom_path = os.path.join(ASSETS_DIR, custom_name)
            
            # 1. Проверяем, есть ли пользовательский кастомный ассет
            if os.path.exists(custom_path):
                try:
                    img = Image.open(custom_path).convert("RGBA")
                    # Сжимаем кастомный ассет до 54x54 и центрируем
                    img_resized = img.resize((54, 54), Image.Resampling.LANCZOS)
                    strip.paste(img_resized, (8, y_offset + 8), img_resized)
                    logger.info(f"Используется кастомный ассет: {custom_path}")
                    continue
                except Exception as e:
                    logger.error(f"Ошибка загрузки кастомного ассета {custom_path}: {e}")
                    
            # 2. Если кастомного файла нет, используем Twemoji
            code = EMOJI_CODES[i]
            file_path = os.path.join(ASSETS_DIR, f"{code}.png")
            
            # Пробуем скачать с jsDelivr/cdnjs при необходимости
            if not os.path.exists(file_path):
                url = f"https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{code}.png"
                try:
                    logger.info(f"Скачивание ассета эмодзи (jsDelivr): {url} -> {file_path}")
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        with open(file_path, "wb") as f:
                            f.write(response.read())
                except Exception as e_js:
                    logger.warning(f"Не удалось скачать с jsDelivr: {e_js}. Пробуем cdnjs...")
                    url_cdnjs = f"https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/{code}.png"
                    try:
                        logger.info(f"Скачивание ассета эмодзи (cdnjs): {url_cdnjs} -> {file_path}")
                        req = urllib.request.Request(url_cdnjs, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=5) as response:
                            with open(file_path, "wb") as f:
                                f.write(response.read())
                    except Exception as e_cdn:
                        logger.error(f"Не удалось скачать с cdnjs: {e_cdn}")
            
            if os.path.exists(file_path):
                try:
                    img = Image.open(file_path).convert("RGBA")
                    img_resized = img.resize((54, 54), Image.Resampling.LANCZOS)
                    strip.paste(img_resized, (8, y_offset + 8), img_resized)
                    continue
                except Exception as e:
                    logger.error(f"Ошибка чтения ассета {file_path}: {e}")
            
            # 3. Векторный fallback, если ничего не сработало
            draw_fallback_symbol(draw, i, 0, y_offset)
            
    return strip

def draw_drum_column(strip: Image.Image, y_offset: float) -> Image.Image:
    """Рендерит прозрачную колонку барабана 81x144 с плавными 3D-тенями цилиндра."""
    column = Image.new("RGBA", (81, 144), (0, 0, 0, 0))
    col_draw = ImageDraw.Draw(column)
    
    y_mod = y_offset % 560
    
    for i in range(8):
        for shift in [-560, 0, 560]:
            cy = (i * 70 + 35 - y_mod) + shift
            # Если символ виден в пределах высоты 144 (с запасом 35 пикселей)
            if -35 <= cy <= 179:
                symbol_box = strip.crop((0, i * 70, 70, (i + 1) * 70))
                column.paste(symbol_box, (5, int(cy - 35)), symbol_box)
                
    # Накладываем мягкие черные 3D-тени затемнения цилиндра сверху и снизу
    shadow_height = 25
    for shadow_y in range(shadow_height):
        alpha = int((shadow_height - shadow_y) / shadow_height * 180)
        col_draw.line([(0, shadow_y), (81, shadow_y)], fill=(0, 0, 0, alpha))
        col_draw.line([(0, 144 - shadow_y), (81, 144 - shadow_y)], fill=(0, 0, 0, alpha))
        
    return column

def generate_slots_gif(s1: int, s2: int, s3: int) -> bytes:
    """
    Генерирует высококачественную GIF-анимацию слотов «Волки МИРЭА» с повышенной резкостью.
    Добавлена экстремальная задержка финала (65 кадров статичных в конце).
    """
    bg_path = os.path.join(ASSETS_DIR, "slots_bg.jpg")
    try:
        bg_base = Image.open(bg_path).convert("RGBA")
        bg_resized = bg_base.resize((512, 341), Image.Resampling.LANCZOS)
    except Exception as e:
        logger.error(f"Не удалось загрузить фоновое изображение {bg_path}: {e}")
        bg_resized = Image.new("RGBA", (512, 341), (40, 25, 15, 255))
        
    strip = create_strip()
    
    frames = []
    spin_frames = 65
    
    # Смещение барабана: S * 70 - 37 (для точного центра при высоте 144 и Y=124)
    y_end_0 = 3 * 560 + (s1 * 70 - 37)
    y_end_1 = 4 * 560 + (s2 * 70 - 37)
    y_end_2 = 5 * 560 + (s3 * 70 - 37)
    
    for i in range(spin_frames):
        if i <= 25:
            t0 = i / 25
            f_t0 = 1.0 - (1.0 - t0) ** 3
            current_y0 = y_end_0 * f_t0
        else:
            current_y0 = y_end_0
            
        if i <= 43:
            t1 = i / 43
            f_t1 = 1.0 - (1.0 - t1) ** 3
            current_y1 = y_end_1 * f_t1
        else:
            current_y1 = y_end_1
            
        if i <= 61:
            t2 = i / 61
            f_t2 = 1.0 - (1.0 - t2) ** 3
            current_y2 = y_end_2 * f_t2
        else:
            current_y2 = y_end_2
            
        frame = bg_resized.copy()
        
        drum0 = draw_drum_column(strip, current_y0)
        drum1 = draw_drum_column(strip, current_y1)
        drum2 = draw_drum_column(strip, current_y2)
        
        frame.paste(drum0, (116, 124), drum0)
        frame.paste(drum1, (215, 124), drum1)
        frame.paste(drum2, (314, 124), drum2)
        
        frame_rgb = frame.convert("RGB")
        
        # Повышаем резкость кадра
        enhancer = ImageEnhance.Sharpness(frame_rgb)
        frame_sharp = enhancer.enhance(1.4)
        frames.append(frame_sharp)
        
    # Добавляем 65 статичных кадров в конце (около 5.2 сек застывания для азарта)
    final_frame = frames[-1]
    for _ in range(65):
        frames.append(final_frame)
        
    # Максимальное качество: квантование палитры до 256 цветов
    frame0_p = frames[0].convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
    frames_p = [f.quantize(palette=frame0_p, colors=256) for f in frames]
        
    output_buf = io.BytesIO()
    frames_p[0].save(
        output_buf,
        format="GIF",
        save_all=True,
        append_images=frames_p[1:],
        duration=80,
        loop=0,
        optimize=True
    )
    
    return output_buf.getvalue()
