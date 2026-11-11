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
    "понедельник": 0, "пн": 0,
    "вторник": 1, "вт": 1,
    "среда": 2, "ср": 2,
    "четверг": 3, "чт": 3,
    "пятница": 4, "пт": 4,
    "суббота": 5, "сб": 5
}

SHORT_NAMES = {
    "обществознание": "Общ-ние",
    "английский язык": "Ин. яз",
    "англ. язык": "Ин. яз",
    "анг/анг": "Ин. яз",
    "английский": "Ин. яз",
    "раз-ры о важном": "Разг. о важном",
    "разговоры о важном": "Разг. о важном",
    "вероятность и статистика": "Вер. и стат.",
    "вер. и статистика": "Вер. и стат.",
    "информатика": "Информ.",
    "инф/инф": "Информ.",
    "физкультура": "Физ-ра",
    "ф.культура": "Физ-ра",
    "ф.к/ф.к": "Физ-ра",
    "литература": "Лит-ра",
    "русский язык": "Рус. яз",
}


def clean_subj(name):
  """Сокращает длинные названия предметов, чтобы они не переносились на 2 строки"""
  if not name:
    return ""
  low = name.strip().lower()
  for k, v in SHORT_NAMES.items():
    if k in low:
      return v
  return name.strip()

BASE_SCHEDULE_10A = {
    0: {
        1: ("Разг. о важном", ""),
        2: ("Геометрия", "306"),
        3: ("Физика", "301"),
        4: ("Физика", "301"),
        5: ("Геометрия", "323"),
        6: ("Алгебра", "323"),
        7: ("Общ-ние", "319"),
        8: ("ВИН", ""),
    },
    1: {
        1: ("ВФи", "301"),
        2: ("Геометрия", "201"),
        3: ("ИП", "102"),
        4: ("Лит-ра", "218"),
        5: ("Физика", "301"),
        6: ("История", "101"),
        7: ("Ин. яз", "206/217"),
        8: ("Ин. яз", "206/217"),
    },
    2: {
        1: ("Алгебра", "102"),
        2: ("Лит-ра", "301"),
        3: ("Биология", "317"),
        4: ("Рус. яз", "307"),
        5: ("История", "307"),
        6: ("Алгебра", "102"),
        7: ("ВЗн", "102"),
    },
    3: {
        1: ("Физика", "301"),
        2: ("Физика", "301"),
        3: ("Общ-ние", "301"),
        4: ("Геометрия", "306"),
        5: ("Ин. яз", "206/217"),
        6: ("Вер. и стат.", "306"),
        7: ("Лит-ра", "303"),
        8: ("ВГо", "217"),
    },
    4: {
        1: ("Информ.", "230/227"),
        2: ("Рус. яз", "321"),
        3: ("География", "316"),
        4: ("Химия", "323"),
        5: ("Информ.", "230/227"),
        6: ("Физика", "301"),
        7: ("ВИН", "230"),
    },
    5: {
        1: ("Физ-ра", "сп.зал"),
        2: ("Физ-ра", "сп.зал"),
        3: ("Алгебра", "225"),
        4: ("Алгебра", "225"),
        5: ("ОБЗР", "102"),
        7: ("ВРЕ", "301"),
    },
}

def parse_header_date(txt):
    t = txt.lower()
    w_day = None
    for name, idx in DAY_MAP.items():
        if re.search(r'\b' + name, t):
            w_day = idx
            break

    day_num = None
    m = re.search(r'\b(\d{1,2})\s+(янв|фев|мар|апр|ма|июн|июл|авг|сен|окт|ноя|дек)', t)
    if m:
        day_num = int(m.group(1))
    else:
        m2 = re.search(r'\b(\d{1,2})\.\d{2}', t)
        if m2:
            day_num = int(m2.group(1))

    return w_day, day_num

def send_telegram_alert(message):
    token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID") or "-1002391481594"
    topic_id = int(os.getenv("TOPIC_ID", "21"))

    if not token:
        print("⚠️ Ошибка: BOT_TOKEN не задан")
        return False

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "message_thread_id": topic_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        res = requests.post(url, json=payload, timeout=12)
        print("Ответ Telegram:", res.status_code, res.text)
        return res.status_code == 200
    except Exception as e:
        print("Ошибка отправки в Telegram:", e)
        return False

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

    # ЕСЛИ ВРЕМЯ ПОСЛЕ 14:00 — ЦЕЛЕВОЙ ДЕНЬ ВСЕГДА ЗАВТРА!
    if now_msk.hour >= 14 or today_wday in (5, 6):
        target_wday = next_wday
        target_num = next_num
        target_dt = next_dt
        target_title = f"{DAYS_RU[next_wday]} ({next_num} {MONTHS_RU[next_dt.month]})"
    else:
        target_wday = today_wday
        target_num = today_num
        target_dt = now_msk
        target_title = f"{DAYS_RU[today_wday]} ({today_num} {MONTHS_RU[now_msk.month]})"

    print(f"🔍 Запуск парсера... Время (МСК): {now_msk.strftime('%d.%m %H:%M')}")
    print(f"🎯 Ищем расписание на: {target_title}")

    changes_by_day = {}
    current_key = (None, None)
    is_students = False

    try:
        res = requests.get(URL, headers=HEADERS, timeout=20)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, "html.parser")

        for el in soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'div', 'b', 'strong', 'tr']):
            txt = el.get_text(" ", strip=True)
            txt_upper = txt.upper()

            # Дата может быть в любом месте (до или после слова обучающиеся)
            w, d = parse_header_date(txt)
            if (w is not None or d is not None) and len(txt) < 250:
                current_key = (w, d)
                if current_key not in changes_by_day:
                    changes_by_day[current_key] = {}

            if "ОБУЧАЮЩИЕСЯ" in txt_upper or "УЧАЩИЕСЯ" in txt_upper:
                is_students = True
                continue
            elif "ПЕДАГОГИ" in txt_upper and len(txt) < 30 and is_students:
                is_students = False
                continue

            if not is_students or el.name != 'tr':
                continue

            cells = [re.sub(r'\s+', ' ', td.get_text(strip=True)) for td in el.find_all(['td', 'th'])]
            if len(cells) < 2:
                continue

            # Исключаем учителей
            if re.search(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.', cells[0]):
                continue

            # Ищем 10А в первой или второй ячейке
            is_10a = False
            class_cell = ""
            for c in cells[:2]:
                if re.search(r'\b10\s*[-–—/]?\s*[аa]', c, re.IGNORECASE):
                    is_10a = True
                    class_cell = c
                    break

            if is_10a:
                row_full = " ".join(cells).upper()
                is_canc = "НЕТ" in row_full or "СНЯТ" in row_full or "ОТМЕН" in row_full

                lesson_num = None
                for c in cells:
                    if c != class_cell and c.isdigit():
                        lesson_num = int(c)
                        break

                if lesson_num:
                    sub = cells[2] if len(cells) > 2 and cells[1].isdigit() else (cells[1] if len(cells) > 1 else "")
                    room = cells[3] if len(cells) > 3 else ""
                    if current_key not in changes_by_day:
                        changes_by_day[current_key] = {}
                    changes_by_day[current_key][lesson_num] = (sub, room, is_canc)
                elif is_canc:
                    for digit in re.findall(r'\d+', row_full):
                        if current_key not in changes_by_day:
                            changes_by_day[current_key] = {}
                        changes_by_day[current_key][int(digit)] = ("УРОК СНЯТ", "", True)
    except Exception as e:
        print(f"Ошибка загрузки сайта: {e}")

    # Собираем замены для целевого дня (ЧЕТВЕРГ)
    day_changes = {}
    for (w, d), ch in changes_by_day.items():
        if (d is not None and d == target_num) or (d is None and w is not None and w == target_wday):
            day_changes.update(ch)

    # Если точной даты не было, но на сайте найдены замены для этого дня недели
    if not day_changes:
        for (w, d), ch in changes_by_day.items():
            if w == target_wday and ch:
                day_changes.update(ch)
                break

    base = BASE_SCHEDULE_10A.get(target_wday, {}).copy()

    print(f"📊 Выбран целевой день: {target_title}")
    print(f"⚡ Найдено замен для 10А на этот день: {len(day_changes)}")

    # 1. Запись для виджета на телефон / ПК
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

    # 2. Формирование сообщения для Telegram
    if day_changes:
        tg_header = f"🔔 <b>ИЗМЕНЕНИЯ В РАСПИСАНИИ (10А)</b>\n📅 <b>{target_title}</b>\n"
    else:
        tg_header = f"🟢 <b>РАСПИСАНИЕ (10А)</b>\n📅 <b>{target_title}</b>\n\n✅ <i>Изменений нет, уроки по обычному графику:</i>\n"

    tg_lines = [tg_header]

    for num in all_nums:
        if num in day_changes:
            sub, room, cancelled = day_changes[num]
            r = f" (каб. {room})" if room else ""
            old_subj = base.get(num, ("", ""))[0]

            if cancelled:
                old_info = f" <s>{old_subj}</s>" if old_subj else ""
                tg_lines.append(f"<blockquote>❌ <b>{num} урок: УРОК СНЯТ</b>{old_info}</blockquote>")
            else:
                old_info = f"\n   ↳ <i>Вместо: <s>{old_subj}</s></i>" if old_subj else ""
                tg_lines.append(f"<blockquote>⚡ <b>{num} урок: {sub}{r}</b>{old_info}</blockquote>")
        elif num in base:
            sub, room = base[num]
            r = f" (каб. {room})" if room else ""
            tg_lines.append(f"🔹 {num} ур: {sub}{r}")

    tg_lines.append("\n🌐 <a href=\"https://419.spb.ru/novosti/news_post/izmeneniya-raspisaniya\">Сайт лицея</a> • 📱 <a href=\"https://raw.githubusercontent.com/TYTANpr/school-widget/main/today_10a.txt\">Виджет</a>")

    # 3. Умная отправка: присылает сообщение РОВНО 1 РАЗ на каждый новый день
    # Если замен нет — напишет "Изменений нет". Если позже завуч добавит замену — пришлёт обновление!
    current_sig = f"{target_title}_{sorted(day_changes.items())}"
    last_sig = ""
    if os.path.exists("last_changes_10a.txt"):
        with open("last_changes_10a.txt", "r", encoding="utf-8") as f:
            last_sig = f.read().strip()

    if current_sig != last_sig:
        print(f"📨 Отправка в Telegram для {target_title}...")
        send_telegram_alert("\n".join(tg_lines))
    else:
        print(f"ℹ️ Для {target_title} расписание уже отправлено. Пропуск дубликата.")

    with open("last_changes_10a.txt", "w", encoding="utf-8") as f:
        f.write(current_sig)

if __name__ == "__main__":
    main()
