import pdfplumber
import re
from datetime import datetime

def parse_inbody_pdf(pdf_path: str) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text()
        if not text:
            raise ValueError("Не удалось извлечь текст из PDF")

    data = {
        "date": None,
        "segmental_muscle_kg": [],
        "segmental_muscle_pct": [],
        "segmental_fat_kg": [],
        "segmental_fat_pct": []
    }

    # Дата
    date_match = re.search(r'Дата\s+(\d{2})\.(\d{2})\.(\d{2})', text)
    if date_match:
        d, m, y = date_match.groups()
        data["date"] = datetime.strptime(f"20{y}-{m}-{d}", "%Y-%m-%d").date()

    # Основные метрики
    patterns = {
        "weight_kg":        r'Вес\s+(?:Норма|Выше нормы|Ниже нормы)?\s*([\d.]+)\s*кг',
        "muscle_kg":        r'Мышцы\s+(?:Норма|Выше нормы|Ниже нормы)?\s*([\d.]+)\s*кг',
        "fat_percent":      r'Жир\s+(?:Норма|Выше нормы|Ниже нормы)?\s*([\d.]+)\s*%',
        "visceral_fat_level": r'Висцеральный жир\s*(?:Ниже нормы|Норма|Выше нормы)?\s*(\d+)',
        "bmi":              r'Индекс массы тела\s*([\d.]+)',
        "ffm_kg":           r'Безжировая масса\s*([\d.]+)\s*кг',
        "bmr_kcal":         r'Обмен веществ\s*(\d+)',
        "daily_calories":   r'Суточная норма калорий\s*(\d+)',
        "water_l":          r'Вода\s*([\d.]+)\s*л',
        "protein_kg":       r'Белок\s*(?:Выше нормы)?\s*([\d.]+)\s*кг',
        "bone_kg":          r'Кости\s*(?:Выше нормы)?\s*([\d.]+)\s*кг',
        "optimal_weight_kg": r'Оптимальный вес\s*([\d.]+)\s*кг',
    }
    for field, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value = match.group(1)
            if field in ("visceral_fat_level", "bmr_kcal", "daily_calories"):
                data[field] = int(value)
            else:
                data[field] = float(value)

    # Сегментный анализ мышц — ищем числа после "Содержание мышц"
    # Используем более гибкий подход: находим блок между "Содержание мышц" и "Содержание Жира"
    muscle_block = re.search(r'Содержание мышц\s*[\d.]+\s*кг(.*?)(?=Содержание Жира)', text, re.DOTALL)
    if not muscle_block:
        # Иногда блоки могут быть без заголовка, пробуем найти просто подряд 5 значений кг и %
        muscle_block = re.search(r'([\d.]+\s*кг\s*){5}', text)
    if muscle_block:
        block = muscle_block.group(0)
        kgs = re.findall(r'([\d.]+)\s*кг', block)
        pcts = re.findall(r'([\d.]+)\s*%', block)
        if len(kgs) >= 5:
            data["segmental_muscle_kg"] = [float(x) for x in kgs[:5]]
        if len(pcts) >= 5:
            data["segmental_muscle_pct"] = [float(x) for x in pcts[:5]]

    # Сегментный анализ жира — после "Содержание Жира"
    fat_block = re.search(r'Содержание Жира\s*[\d.]+\s*кг(.*?)$', text, re.DOTALL)
    if fat_block:
        block = fat_block.group(0)
        kgs = re.findall(r'([\d.]+)\s*кг', block)
        pcts = re.findall(r'([\d.]+)\s*%', block)
        if len(kgs) >= 5:
            data["segmental_fat_kg"] = [float(x) for x in kgs[:5]]
        if len(pcts) >= 5:
            data["segmental_fat_pct"] = [float(x) for x in pcts[:5]]

    return data
