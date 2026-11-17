import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta

URL = "https://419.spb.ru/novosti/news_post/izmeneniya-raspisaniya"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

DAYS_RU = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
MONTHS_RU = ["", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]

SHORT_NAMES = {
    "обществознание": "Общ-ние", "английский язык": "Ин. яз", "англ. язык": "Ин. яз",
    "анг/анг": "Ин. яз", "английский": "Ин. яз", "раз-ры о важном": "Разг. о важном",
    "разговоры о важном": "Разг. о важном", "вероятность и статистика": "Вер. и стат.",
    "вер. и статистика": "Вер. и стат.", "информатика": "Информ.", "инф/инф": "Информ.",
    "физкультура": "Физ-ра", "ф.культура": "Физ-ра", "ф.к/ф.к": "Физ-ра",
    "литература": "Лит-ра", "русский язык": "Рус. яз"
}

def clean_subj(name):
    if not name: return ""
    low = name.strip().lower()
    for k, v in SHORT_NAMES.items():
        if k in low: return v
    return name.strip()

BASE_SCHEDULE_7B = {
    0: {1: ("Разг. о важном", ""), 2: ("Алгебра", "105"), 3: ("Физ-ра", "спортзал"), 4: ("Лит-ра", "307"), 5: ("Алгебра", "105"), 6: ("Вер. и стат.", "105"), 7: ("ВГо", "316")},
    1: {1: ("Рус. яз", "307"), 2: ("Ин. яз", "217/222"), 3: ("Рус. яз", "307"), 4: ("География", "316"), 5: ("История", "225"), 6: ("Физика", "201"), 7: ("Биология", "321")},
    2: {1: ("Алгебра", "323"), 2: ("История", "225"), 3: ("Ин. яз", "217/222"), 4: ("Информ.", "101/323"), 5: ("Технология", "317"), 6: ("Технология", "317"), 7: ("Физ-ра", "спортзал")},
    3: {2: ("Рус. яз", "307"), 3: ("Геометрия", "105"), 4: ("Геометрия", "105"), 5: ("Алгебра", "105"), 6: ("Ин. яз", "217/222"), 7: ("География", "316")},
    4: {2: ("Рус. яз", "307"), 3: ("Физика", "201"), 4: ("История", "225"), 5: ("Лит-ра", "307"), 6: ("Информ.", "230/227"), 7: ("ИЗО", "101"), 8: ("ВСе", "")},
    5: {2: ("ВРЕ", "201"), 3: ("ВЗн", "207"), 4: ("ВЗн", "207"), 5: ("ВСО", "307")}
}

def parse_header_date(txt):
    t = txt.lower()
    w_day = None
    day_patterns = [
        (r'\bпонедельник\w*', 0), (r'\bвторник\w*', 1), (r'\bсред[ауеы]\b', 2),
        (r'\bчетверг\w*', 3), (r'\bпятниц[ауеы]\b', 4), (r'\bсуббот[ауеы]\b', 5),
        (r'\bпн\b', 0), (r'\bвт\b', 1), (r'\bср\b', 2),
        (r'\bчт\b', 3), (r'\bпт\b', 4), (r'\bсб\b', 5)
    ]
    for pattern, idx in day_patterns:
        if re.search(pattern, t):
            w_day = idx
            break

    day_num = None
    m = re.search(r'\b(\d{1,2})\s+(янв|фев|мар|апр|ма[йя]|июн|июл|авг|сен|окт|ноя|дек)', t)
    if m:
        day_num = int(m.group(1))
    else:
        m2 = re.search(r'\b(\d{1,2})\.\d{2}', t)
        if m2:
            day_num = int(m2.group(1))
    return w_day, day_num

def extract_lesson_nums(cell_text):
    t = cell_text.strip()
    m_range = re.match(r'^(\d{1,2})\s*[-–—]\s*(\d{1,2})(?:\s*ур\.?)?$', t, re.I)
    if m_range:
        start, end = int(m_range.group(1)), int(m_range.group(2))
        if 0 <= start <= end <= 12:
            return list(range(start, end + 1))
    if re.match(r'^[\d\s,;ур\.]+$', t, re.I):
        return [int(x) for x in re.findall(r'\d+', t) if 0 <= int(x) <= 12]
    return []

def main():
    now_msk = datetime.utcnow() + timedelta(hours=3)
    today_num = now_msk.day
    today_wday = now_msk.weekday()

    if today_wday == 5:
        next_dt = now_msk + timedelta(days=2)
    elif today_wday == 6:
        next_dt = now_msk + timedelta(days=1)
    else:
        next_dt = now_msk + timedelta(days=1)

    next_num = next_dt.day
    next_wday = next_dt.weekday()

    if now_msk.hour >= 14 or today_wday in (5, 6):
        target_wday = next_wday
        target_num = next_num
        target_title = f"{DAYS_RU[next_wday]} ({next_num} {MONTHS_RU[next_dt.month]})"
    else:
        target_wday = today_wday
        target_num = today_num
        target_title = f"{DAYS_RU[today_wday]} ({today_num} {MONTHS_RU[now_msk.month]})"

    changes_by_day = {}
    current_key = (None, None)
    is_students = False

    try:
        res = requests.get(URL, headers=HEADERS, timeout=20)
        res.raise_for_status()
        res.encoding = 'utf-8'

        if "ОБУЧАЮЩ" not in res.text.upper() and "РАСПИСАНИ" not in res.text.upper():
            return

        soup = BeautifulSoup(res.text, "html.parser")

        for el in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'span', 'b', 'strong', 'em', 'font', 'caption', 'tr']):
            if el.name in ('div', 'p', 'span') and el.find('table'):
                continue

            txt = el.get_text(" ", strip=True)
            if not txt:
                continue
            txt_upper = txt.upper()

            if ("ОБУЧАЮЩ" in txt_upper or "УЧАЩ" in txt_upper or "УЧЕНИК" in txt_upper) and len(txt) < 100:
                is_students = True
            elif txt_upper.strip(" :") == "ПЕДАГОГИ":
                is_students = False
                continue

            is_inside_table = (el.name == 'tr') or (el.find_parent('table') is not None)
            if not is_inside_table or "ИЗМЕНЕНИЯ РАСПИСАНИЯ" in txt_upper:
                if not re.search(r'\bза\s+(?:пн|вт|ср|чт|пт|сб|понедельник|вторник|среду|четверг|пятницу|субботу)', txt.lower()):
                    w, d = parse_header_date(txt)
                    if w is not None and len(txt) < 250:
                        if "ОЛИМПИАД" not in txt_upper and "РЕГИСТРАЦ" not in txt_upper and "ИНСТРУКТАЖ" not in txt_upper and "ФЕДЕРАЛЬН" not in txt_upper:
                            current_key = (w, d)
                            if current_key not in changes_by_day:
                                changes_by_day[current_key] = {}

            if el.name != 'tr':
                continue

            cells = [re.sub(r'\s+', ' ', td.get_text(strip=True)) for td in el.find_all(['td', 'th'])]
            if len(cells) < 2:
                continue

            if re.search(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.', cells[0]):
                continue

            starts_with_7b = bool(re.match(r'^7\s*[-–—/]?\s*[а-яa-z,\s]*[бb](?:\b|[^а-яa-z])', cells[0].strip(), re.IGNORECASE))
            if not is_students and not starts_with_7b:
                continue

            is_7b = False
            class_cell = ""
            for c in cells[:2]:
                if re.search(r'\b7\s*[-–—/]?\s*[бb]', c, re.IGNORECASE) or re.search(r'\b7[а-яa-z,\s]*[бb]', c, re.IGNORECASE):
                    is_7b = True
                    class_cell = c
                    break

            if is_7b:
                row_full = " ".join(cells).upper()
                is_canc = "НЕТ" in row_full or "СНЯТ" in row_full or "ОТМЕН" in row_full

                lesson_nums = []
                num_cell_idx = -1
                for idx, c in enumerate(cells):
                    if c != class_cell:
                        extracted = extract_lesson_nums(c)
                        if extracted:
                            lesson_nums = extracted
                            num_cell_idx = idx
                            break

                if lesson_nums:
                    sub_idx = num_cell_idx + 1 if num_cell_idx + 1 < len(cells) else 1
                    sub = cells[sub_idx] if not is_canc else "УРОК СНЯТ"
                    room = cells[sub_idx + 1] if (not is_canc and sub_idx + 1 < len(cells)) else ""
                    comment = cells[5].strip() if (not is_canc and len(cells) > 5) else ""
                    room_info = f"{room}, {comment}" if (room and comment) else (room or comment)

                    if current_key not in changes_by_day:
                        changes_by_day[current_key] = {}
                    for l_num in lesson_nums:
                        changes_by_day[current_key][l_num] = (sub, room_info, is_canc)
                elif is_canc:
                    for digit in re.findall(r'\d+', row_full):
                        if int(digit) <= 12:
                            if current_key not in changes_by_day:
                                changes_by_day[current_key] = {}
                            changes_by_day[current_key][int(digit)] = ("УРОК СНЯТ", "", True)
    except Exception as e:
        print(f"Ошибка загрузки сайта (7Б): {e}")
        return

    day_changes = {}
    for (w, d), ch in changes_by_day.items():
        if (d is not None and d == target_num) or (d is None and w is not None and w == target_wday):
            day_changes.update(ch)

    if not day_changes:
        for (w, d), ch in changes_by_day.items():
            if w == target_wday and ch:
                day_changes.update(ch)
                break

    base = BASE_SCHEDULE_7B.get(target_wday, {}).copy()
    lines = [f"7Б • {target_title}"]
    all_nums = sorted(set(list(base.keys()) + list(day_changes.keys())))

    for num in all_nums:
        if num in day_changes:
            sub, room, cancelled = day_changes[num]
            sub = clean_subj(sub)
            r_disp = room if room else "---"
            lines.append(f"{num} | --- | ❌ {sub}" if cancelled else f"{num} | {r_disp} | ⚡ {sub} [ИЗМ]")
        elif num in base:
            sub, room = base[num]
            sub = clean_subj(sub)
            r_disp = room if room else "---"
            lines.append(f"{num} | {r_disp} | {sub}")

    with open("today_7b.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
