import os
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

BASE_SCHEDULE_10A = {
    0: {1: ("Раз-ры о важном", ""), 2: ("Геометрия", "306"), 3: ("Физика", "301"), 4: ("Физика", "301"), 5: ("Геометрия", "323"), 6: ("Алгебра", "323"), 7: ("Обществознание", "319"), 8: ("ВИН", "")},
    1: {1: ("ВФи", "301"), 2: ("Геометрия", "201"), 3: ("ИП", "102"), 4: ("Литература", "218"), 5: ("Физика", "301"), 6: ("История", "101"), 7: ("Англ. язык", "206/217"), 8: ("Англ. язык", "206/217")},
    2: {1: ("Алгебра", "102"), 2: ("Литература", "301"), 3: ("Биология", "317"), 4: ("Русский язык", "307"), 5: ("История", "307"), 6: ("Алгебра", "102"), 7: ("ВЗн", "102")},
    3: {1: ("Физика", "301"), 2: ("Физика", "301"), 3: ("Обществознание", "301"), 4: ("Геометрия", "306"), 5: ("Англ. язык", "206/217"), 6: ("Вер. и стат.", "306"), 7: ("Литература", "303"), 8: ("ВГо", "217")},
    4: {1: ("Информатика", "230/227"), 2: ("Русский язык", "321"), 3: ("География", "316"), 4: ("Химия", "323"), 5: ("Информатика", "230/227"), 6: ("Физика", "301"), 7: ("ВИН", "230")},
    5: {1: ("Физкультура", "сп.зал"), 2: ("Физкультура", "сп.зал"), 3: ("Алгебра", "225"), 4: ("Алгебра", "225"), 5: ("ОБЗР", "102"), 7: ("ВРЕ", "301")}
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

def send_telegram_alert(message):
    token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID") or "-1002391481594"
    topic_id = 21

    if not token:
        print("Ошибка: BOT_TOKEN не найден в переменных окружения")
        return

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "message_thread_id": topic_id,
            "text": message,
            "parse_mode": "HTML"              # <--- ПЕРЕКЛЮЧИЛИ НА HTML
        }
        res = requests.post(url, json=payload, timeout=10)
        print("Ответ Telegram:", res.status_code, res.text)
    except Exception as e:
        print("Ошибка отправки в Telegram:", e)

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

                if re.search(r'\b10\s*[-–—/]?\s*[аa]', first_cell, re.IGNORECASE):
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

    # Проверка на завтра
    for key in changes_by_day.keys():
        w, d = key
        if (d is not None and d == next_num) or (d is None and w == next_wday):
            chosen_key = key
            target_wday = next_wday
            target_title = f"{DAYS_RU[next_wday]} ({next_num} {MONTHS_RU[next_dt.month]})"
            break

    # Проверка на сегодня
    if not chosen_key:
        for key in changes_by_day.keys():
            w, d = key
            if (d is not None and d == today_num) or (d is None and w == today_wday):
                chosen_key = key
                target_wday = today_wday
                target_title = f"{DAYS_RU[today_wday]} ({today_num} {MONTHS_RU[now_msk.month]})"
                break

    if not chosen_key:
        if now_msk.hour >= 14 or today_wday in (5, 6):
            target_wday = next_wday
            target_title = f"{DAYS_RU[next_wday]} ({next_num} {MONTHS_RU[next_dt.month]})"
        else:
            target_wday = today_wday
            target_title = f"{DAYS_RU[today_wday]} ({today_num} {MONTHS_RU[now_msk.month]})"

    base = BASE_SCHEDULE_10A.get(target_wday, {}).copy()
    day_changes = changes_by_day.get(chosen_key, {})

    # 1. ФОРМИРУЕМ ЧИСТЫЙ ТЕКСТ ДЛЯ ВИДЖЕТА НА ТЕЛЕФОНЕ (без лишних HTML тегов)
    widget_lines = [f"10А • {target_title}"]
    all_nums = sorted(set(list(base.keys()) + list(day_changes.keys())))

    for num in all_nums:
        if num in day_changes:
            sub, room, cancelled = day_changes[num]
            r = f" ({room})" if room else ""
            widget_lines.append(f"{num} ур: ❌ {sub}" if cancelled else f"{num} ур: ⚡ {sub}{r} [ИЗМ]")
        elif num in base:
            sub, room = base[num]
            r = f" ({room})" if room else ""
            widget_lines.append(f"{num} ур: {sub}{r}")

    with open("today_10a.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(widget_lines))

    # 2. ФОРМИРУЕМ КРАСИВОЕ СООБЩЕНИЕ ДЛЯ TELEGRAM С КАРТОЧКАМИ
    tg_lines = [f"🔔 <b>ИЗМЕНЕНИЯ В РАСПИСАНИИ (10А)</b>", f"📅 <b>{target_title}</b>\n"]

    for num in all_nums:
        if num in day_changes:
            sub, room, cancelled = day_changes[num]
            r = f" (каб. {room})" if room else ""
            old_subj = base.get(num, ("", ""))[0]
            
            if cancelled:
                # Отменённый урок (красный маркер + зачёркивание старого)
                old_info = f" <s>{old_subj}</s>" if old_subj else ""
                tg_lines.append(f"<blockquote>❌ <b>{num} урок: УРОК СНЯТ</b>{old_info}</blockquote>")
            else:
                # Изменённый урок (выделенная плашка с полосой слева + что заменили)
                old_info = f"\n   ↳ <i>Вместо: <s>{old_subj}</s></i>" if old_subj else ""
                tg_lines.append(f"<blockquote>⚡ <b>{num} урок: {sub}{r}</b>{old_info}</blockquote>")
        elif num in base:
            sub, room = base[num]
            r = f" (каб. {room})" if room else ""
            tg_lines.append(f"🔹 {num} ур: {sub}{r}")

    # Добавляем кликабельные ссылки внизу
    tg_lines.append("\n🌐 <a href=\"https://419.spb.ru/novosti/news_post/izmeneniya-raspisaniya\">Сайт лицея</a> • 📱 <a href=\"https://tytanpr.github.io/school-widget/\">Виджет</a>")

    # 3. ОТПРАВКА ТОЛЬКО ПРИ НОВЫХ ЗАМЕНАХ
    current_sig = f"{target_title}_{sorted(day_changes.items())}" if day_changes else "NO_CHANGES"
    last_sig = ""
    if os.path.exists("last_changes_10a.txt"):
        with open("last_changes_10a.txt", "r", encoding="utf-8") as f:
            last_sig = f.read().strip()

    if day_changes and current_sig != last_sig:
        send_telegram_alert("\n".join(tg_lines))
        print("Отправлено красивое оповещение в Telegram")

    with open("last_changes_10a.txt", "w", encoding="utf-8") as f:
        f.write(current_sig)

if __name__ == "__main__":
    main()
