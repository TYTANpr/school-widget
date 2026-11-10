import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta

URL = "https://419.spb.ru/novosti/news_post/izmeneniya-raspisaniya"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

DAYS_RU = ["ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ", "ПЯТНИЦА", "СУББОТА", "ВОСКРЕСЕНЬЕ"]
MONTHS_RU = ["", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]

DAY_MAP = {
    "понедельник": 0, "вторник": 1, "среда": 2, 
    "четверг": 3, "пятница": 4, "суббота": 5
}

# Базовое расписание 7Б из таблицы лицея № 419
BASE_SCHEDULE_7B = {
    0: { # Понедельник
        1: ("Раз-ры о важном", ""), 
        2: ("Алгебра", "105"), 
        3: ("Физкультура", "спортзал"), 
        4: ("Литература", "307"), 
        5: ("Алгебра", "105"), 
        6: ("Вер. и стат.", "105"), 
        7: ("ВГо", "316")
    },
    1: { # Вторник
        1: ("Русский язык", "307"), 
        2: ("Англ. язык", "217/222"), 
        3: ("Русский язык", "307"), 
        4: ("География", "316"), 
        5: ("История", "225"), 
        6: ("Физика", "201"), 
        7: ("Биология", "321")
    },
    2: { # Среда
        1: ("Алгебра", "323"), 
        2: ("История", "225"), 
        3: ("Англ. язык", "217/222"), 
        4: ("Информатика", "101/323"), 
        5: ("Технология", "317"), 
        6: ("Технология", "317"), 
        7: ("Физкультура", "спортзал")
    },
    3: { # Четверг
        2: ("Русский язык", "307"), 
        3: ("Геометрия", "105"), 
        4: ("Геометрия", "105"), 
        5: ("Алгебра", "105"), 
        6: ("Англ. язык", "217/222"), 
        7: ("География", "316"), 
        8: ("ВГЕ", "")
    },
    4: { # Пятница
        2: ("Русский язык", "307"), 
        3: ("Физика", "201"), 
        4: ("История", "225"), 
        5: ("Литература", "307"), 
        6: ("Информатика", "230/227"), 
        7: ("ИЗО", "101"), 
        8: ("ВСе", "")
    },
    5: { # Суббота
        2: ("ВРЕ", "201"), 
        3: ("ВЗн", "207"), 
        4: ("ВЗн", "207"), 
        5: ("ВСО", "307")
    }
}

def parse_header_date(txt):
    t = txt.lower()
    w_day = None
    for name, idx in DAY_MAP.items():
        if name in t:
            w_day = idx
            break

    day_num = None
    m = re.search(r'\b(\d{1,2})\s+(янв|фев|мар|апр|ма|июн|июл|авг|сен|окт|ноя|дек)', t)
    if m:
        day_num = int(m.group(1))
    else:
        m2 = re.search(r'\b(\d{1,2})\.\d{2}\b', t)
        if m2:
            day_num = int(m2.group(1))

    return w_day, day_num

def is_7b_row(cell_text):
    t = cell_text.lower().strip()
    m = re.match(r'^7\s*[-–—/]?\s*([а-яa-z,\s/]+)', t)
    if m:
        letters = m.group(1).split()[0]
        return 'б' in letters or 'b' in letters
    return bool(re.search(r'\b7\s*[-–—/]?\s*[бb]', t))

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

    changes_by_day = {}
    current_key = None

    try:
        res = requests.get(URL, headers=HEADERS, timeout=20)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, "html.parser")
        is_students = False

        for el in soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'div', 'b', 'strong', 'tr']):
            txt = el.get_text(" ", strip=True)
            txt_upper = txt.upper()

            if "ОБУЧАЮЩИЕСЯ" in txt_upper or "УЧАЩИЕСЯ" in txt_upper:
                is_students = True
                continue
            elif "ПЕДАГОГИ" in txt_upper and len(txt) < 30 and is_students:
                is_students = False
                continue

            if not is_students:
                continue

            w, d = parse_header_date(txt)
            if (w is not None or d is not None) and len(txt) < 80:
                current_key = (w, d)
                if current_key not in changes_by_day:
                    changes_by_day[current_key] = {}

            if el.name == 'tr' and current_key is not None:
                cells = [re.sub(r'\s+', ' ', td.get_text(strip=True)) for td in el.find_all(['td', 'th'])]
                if len(cells) < 2:
                    continue

                first_cell = cells[0].strip()
                if re.search(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.', first_cell):
                    continue

                # Проверка на 7Б
                if is_7b_row(first_cell):
                    row_full = " ".join(cells).upper()
                    is_canc = "НЕТ" in row_full or "СНЯТ" in row_full or "ОТМЕН" in row_full

                    if len(cells) >= 3 and cells[1].isdigit():
                        num = int(cells[1])
                        sub = cells[2]
                        room = cells[3] if len(cells) > 3 else ""
                        changes_by_day[current_key][num] = (sub, room, is_canc)
                    elif is_canc:
                        for digit in re.findall(r'\d+', row_full):
                            changes_by_day[current_key][int(digit)] = ("УРОК СНЯТ", "", True)
    except Exception as e:
        print("Ошибка загрузки:", e)

    chosen_key = None
    target_wday = None
    target_title = ""

    # 1. Проверяем завтра
    for key in changes_by_day.keys():
        w, d = key
        if (d is not None and d == next_num) or (d is None and w == next_wday):
            chosen_key = key
            target_wday = next_wday
            target_title = f"{DAYS_RU[next_wday]} ({next_num} {MONTHS_RU[next_dt.month]})"
            break

    # 2. Проверяем сегодня
    if not chosen_key:
        for key in changes_by_day.keys():
            w, d = key
            if (d is not None and d == today_num) or (d is None and w == today_wday):
                chosen_key = key
                target_wday = today_wday
                target_title = f"{DAYS_RU[today_wday]} ({today_num} {MONTHS_RU[now_msk.month]})"
                break

    # 3. Базовый выбор по времени дня
    if not chosen_key:
        if now_msk.hour >= 14 or today_wday in (5, 6):
            target_wday = next_wday
            target_title = f"{DAYS_RU[next_wday]} ({next_num} {MONTHS_RU[next_dt.month]})"
        else:
            target_wday = today_wday
            target_title = f"{DAYS_RU[today_wday]} ({today_num} {MONTHS_RU[now_msk.month]})"

    base = BASE_SCHEDULE_7B.get(target_wday, {}).copy()
    day_changes = changes_by_day.get(chosen_key, {})

    lines = [f"7Б • {target_title}"]
    all_nums = sorted(set(list(base.keys()) + list(day_changes.keys())))

    for num in all_nums:
        if num in day_changes:
            sub, room, cancelled = day_changes[num]
            r = f" ({room})" if room else ""
            if cancelled:
                lines.append(f"{num} ур: ❌ {sub}")
            else:
                lines.append(f"{num} ур: ⚡ {sub}{r} [ИЗМ]")
        elif num in base:
            sub, room = base[num]
            r = f" ({room})" if room else ""
            lines.append(f"{num} ур: {sub}{r}")

    with open("today_7b.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
