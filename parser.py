import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta

URL = "https://419.spb.ru/novosti/news_post/izmeneniya-raspisaniya"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

STICKER_ID = "CAACAgIAAyEFAASOixz6AAIm82r8gHSgdnbqu4oIdj9rPvquxr4fAALTqgACsntRSgFMmIStpRd-PQQ"

DAYS_RU = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
MONTHS_RU = ["", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]

LESSON_END_TIMES = {
    1: "09:45",
    2: "10:40",
    3: "11:45",
    4: "12:50",
    5: "13:45",
    6: "14:40",
    7: "15:45",
    8: "16:40",
    9: "17:35"
}

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

BASE_SCHEDULE_10A = {
    0: {
        1: ("Разг. о важном", ""), 2: ("Геометрия", "306"), 3: ("Физика", "301"),
        4: ("Физика", "301"), 5: ("Геометрия", "323"), 6: ("Алгебра", "323"),
        7: ("Общ-ние", "319"), 8: ("ВИН", ""), 9: ("ВИН", "")
    },
    1: {
        1: ("ВРЕ", "301"), 2: ("Геометрия", "201"), 3: ("ИП", "102"),
        4: ("Лит-ра", "218"), 5: ("Физика", "301"), 6: ("История", "101"),
        7: ("Ин. яз", "206/217"), 8: ("Ин. яз", "206/217"), 9: ("ВХИ", "")
    },
    2: {
        1: ("Алгебра", "102"), 2: ("Лит-ра", "301"), 3: ("Биология", "317"),
        4: ("Рус. яз", "307"), 5: ("История", "307"), 6: ("Алгебра", "102"),
        7: ("ВЗн", "102"), 9: ("ВФП", "")
    },
    3: {
        1: ("Физика", "301"), 2: ("Физика", "301"), 3: ("Общ-ние", "301"),
        4: ("Геометрия", "306"), 5: ("Ин. яз", "206/217"), 6: ("Вер. и стат.", "306"),
        7: ("Лит-ра", "303"), 8: ("ВГо", "217"), 9: ("ВГр", "")
    },
    4: {
        1: ("Информ.", "230/227"), 2: ("Рус. яз", "321"), 3: ("География", "316"),
        4: ("Химия", "323"), 5: ("Информ.", "230/227"), 6: ("Физика", "301"),
        7: ("ВИН", "230"), 8: ("Вил", ""), 9: ("ВОБ", "")
    },
    5: {
        1: ("Физ-ра", "спорт.з./сп.зал"), 2: ("Физ-ра", "спорт.з./сп.зал"),
        3: ("Алгебра", "225"), 4: ("Алгебра", "225"),
        5: ("ОБЗР", "102"), 7: ("ВРЕ", "301")
    }
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

def load_manual_changes(target_dt=None, now_msk=None):
    manual = {}
    if not os.path.exists("manual_changes.txt"):
        return manual

    if now_msk is None:
        now_msk = datetime.utcnow() + timedelta(hours=3)
    if target_dt is None:
        target_dt = now_msk

    target_day = target_dt.day
    target_month = target_dt.month
    today_day = now_msk.day
    today_month = now_msk.month

    active_for_target = False
    cleaned_lines = []
    current_block_expired = False
    file_was_changed = False

    try:
        with open("manual_changes.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            stripped = line.strip()
            header_m = re.match(r"^\[(.*?)\]", stripped)
            if header_m:
                h_txt = header_m.group(1).strip().lower()
                active_for_target = False
                current_block_expired = False

                date_m = re.search(r"(\d{1,2})\.(\d{1,2})", h_txt)
                if date_m:
                    d_num = int(date_m.group(1))
                    m_num = int(date_m.group(2))
                    if (m_num < today_month) or (m_num == today_month and d_num < today_day):
                        current_block_expired = True
                        file_was_changed = True
                        continue
                    if d_num == target_day and m_num == target_month:
                        active_for_target = True
                else:
                    w, _ = parse_header_date(h_txt)
                    if w is not None and w == target_dt.weekday():
                        active_for_target = True

                cleaned_lines.append(line)
                continue

            if current_block_expired:
                continue
            cleaned_lines.append(line)

            if active_for_target and stripped and not stripped.startswith("#"):
                m = re.match(r"^(\d+)\s*[:\-]\s*(.*)$", stripped)
                if m:
                    num = int(m.group(1))
                    val = m.group(2).strip()
                    is_canc = "СНЯТ" in val.upper() or "НЕТ" in val.upper()
                    room = ""
                    room_m = re.search(r"\((?:каб\.?\s*)?([^)]+)\)", val)
                    if room_m:
                        room = room_m.group(1).strip()
                        sub = re.sub(r"\(.*?\)", "", val).strip()
                    else:
                        sub = val
                    manual[num] = (clean_subj(sub), room, is_canc)

        if file_was_changed:
            with open("manual_changes.txt", "w", encoding="utf-8") as f:
                f.writelines(cleaned_lines)
            print("🧹 Прошедшие даты автоматически удалены из manual_changes.txt")
    except Exception as e:
        print("Ошибка чтения manual_changes.txt:", e)

    return manual

def delete_old_telegram_message(target_date_key):
    token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID") or "-1002391481594"
    if not os.path.exists("last_message_id.txt") or not token:
        return
    try:
        with open("last_message_id.txt", "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return
        if ":" in content:
            saved_date, old_ids_str = content.split(":", 1)
        else:
            saved_date, old_ids_str = "", content

        if saved_date == target_date_key:
            for old_id in old_ids_str.split(","):
                old_id = old_id.strip()
                if old_id.isdigit():
                    url = f"https://api.telegram.org/bot{token}/deleteMessage"
                    requests.post(url, json={"chat_id": chat_id, "message_id": int(old_id)}, timeout=6)
                    print(f"🗑️ Предыдущее сообщение #{old_id} за этот же день ({target_date_key}) удалено.")
        else:
            print(f"🗓️ Новый день ({target_date_key})! Предыдущие посты оставлены в истории чата.")
    except Exception as e:
        print("Не удалось удалить старое сообщение:", e)

def send_telegram_alert(message, target_date_key):
    token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID") or "-1002391481594"
    debug_mode = os.getenv("DEBUG_MODE") == "true"

    topic_env = os.getenv("TOPIC_ID", "9965").strip()
    topic_id = int(topic_env) if (topic_env.isdigit() and int(topic_env) > 0) else None

    if not token:
        print("⚠️ Ошибка: BOT_TOKEN не задан")
        return False

    if not debug_mode:
        delete_old_telegram_message(target_date_key)

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if topic_id and not debug_mode:
            payload["message_thread_id"] = topic_id

        res = requests.post(url, json=payload, timeout=12)
        print("Ответ Telegram:", res.status_code, res.text)
        if res.status_code == 200:
            if not debug_mode:
                msg_id = res.json().get("result", {}).get("message_id")
                if msg_id:
                    with open("last_message_id.txt", "w", encoding="utf-8") as f:
                        f.write(f"{target_date_key}:{msg_id}")
            return True
        return False
    except Exception as e:
        print("Ошибка отправки в Telegram:", e)
        return False

def send_telegram_sticker(sticker_id, target_date_key):
    if not sticker_id:
        return
    token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID") or "-1002391481594"
    debug_mode = os.getenv("DEBUG_MODE") == "true"

    topic_env = os.getenv("TOPIC_ID", "9965").strip()
    topic_id = int(topic_env) if (topic_env.isdigit() and int(topic_env) > 0) else None

    try:
        url = f"https://api.telegram.org/bot{token}/sendSticker"
        payload = {
            "chat_id": chat_id,
            "sticker": sticker_id
        }
        if topic_id and not debug_mode:
            payload["message_thread_id"] = topic_id

        res = requests.post(url, json=payload, timeout=10)
        print("Ответ Telegram (Стикер):", res.status_code)
        if res.status_code == 200 and not debug_mode:
            st_id = res.json().get("result", {}).get("message_id")
            if st_id and os.path.exists("last_message_id.txt"):
                with open("last_message_id.txt", "a", encoding="utf-8") as f:
                    f.write(f",{st_id}")
    except Exception as e:
        print("Ошибка отправки стикера:", e)

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
        res.raise_for_status()
        res.encoding = 'utf-8'

        if "ОБУЧАЮЩ" not in res.text.upper() and "РАСПИСАНИ" not in res.text.upper():
            print("⚠️ Сайт вернул неполную страницу или тех. работы. Отмена проверки.")
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

            starts_with_10a = bool(re.match(r'^10\s*[-–—/]?\s*[аa](?:\b|[^а-яa-z])', cells[0].strip(), re.IGNORECASE))
            if not is_students and not starts_with_10a:
                continue

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
        print(f"❌ Ошибка загрузки сайта (пропускаем проверку, ничего не меняем): {e}")
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

    manual = load_manual_changes(target_dt, now_msk)
    if manual:
        print(f"✏️ Применены ручные правки: {manual}")
        day_changes.update(manual)

    base = BASE_SCHEDULE_10A.get(target_wday, {}).copy()

    # --- УМНЫЙ РАСЧЁТ ОКОНЧАНИЯ ДНЯ (С УЧЁТОМ ОТМЕН И ОКОН) ---
    all_active_nums = []
    for num in sorted(set(list(base.keys()) + list(day_changes.keys()))):
        if num in day_changes:
            _, _, cancelled = day_changes[num]
            if not cancelled:
                all_active_nums.append(num)
        else:
            all_active_nums.append(num)

    real_last_lesson = 0
    if all_active_nums:
        all_active_nums.sort()
        real_last_lesson = all_active_nums[0]
        for i in range(1, len(all_active_nums)):
            if all_active_nums[i] == all_active_nums[i-1] + 1:
                real_last_lesson = all_active_nums[i]
            else:
                break

    end_time_str = LESSON_END_TIMES.get(real_last_lesson, "")
    time_info = f"\n⏱ <b>Окончание: ~{end_time_str}</b> (после {real_last_lesson} ур.)" if end_time_str else ""

    print(f"📊 Выбран целевой день: {target_title} | Последний урок: {real_last_lesson} ({end_time_str})")
    print(f"⚡ Итого замен для 10А: {len(day_changes)}")

    # 1. Запись для виджета
    widget_lines = [f"10А • {target_title}"]
    all_nums = sorted(set(list(base.keys()) + list(day_changes.keys())))

    for num in all_nums:
        if num in day_changes:
            sub, room, cancelled = day_changes[num]
            sub = clean_subj(sub)
            r_disp = room if room else "---"
            widget_lines.append(f"{num} | --- | ❌ {sub}" if cancelled else f"{num} | {r_disp} | ⚡ {sub} [ИЗМ]")
        elif num in base:
            sub, room = base[num]
            sub = clean_subj(sub)
            r_disp = room if room else "---"
            widget_lines.append(f"{num} | {r_disp} | {sub}")

    with open("today_10a.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(widget_lines))

    # 2. Формирование сообщения для Telegram (время окончания перенесено под дату)
    if day_changes:
        tg_header = f"🔔 <b>ИЗМЕНЕНИЯ В РАСПИСАНИИ (10А)</b>\n📅 <b>{target_title}</b>{time_info}\n"
    else:
        tg_header = f"🟢 <b>РАСПИСАНИЕ (10А)</b>\n📅 <b>{target_title}</b>{time_info}\n\n✅ <i>Изменений нет, уроки по обычному графику:</i>\n"

    tg_lines = [tg_header]

    for num in all_nums:
        if num in day_changes:
            sub, room, cancelled = day_changes[num]
            sub = clean_subj(sub)
            r_disp = room if room else "---"
            old_subj_raw = base.get(num, ("", ""))[0]
            old_subj = clean_subj(old_subj_raw)

            if cancelled:
                old_info = f" <s>{old_subj}</s>" if old_subj else ""
                tg_lines.append(f"<blockquote>❌ <b>{num} | --- | УРОК СНЯТ</b>{old_info}</blockquote>")
            else:
                if sub.lower() == old_subj.lower():
                    tg_lines.append(f"<blockquote>⚡ <b>{num} | {r_disp} | {sub}</b></blockquote>")
                else:
                    old_info = f"\n   ↳ <i>Вместо: <s>{old_subj}</s></i>" if old_subj else ""
                    tg_lines.append(f"<blockquote>⚡ <b>{num} | {r_disp} | {sub}</b>{old_info}</blockquote>")
        elif num in base:
            sub, room = base[num]
            sub = clean_subj(sub)
            r_disp = room if room else "---"
            tg_lines.append(f"🔹 {num} | {r_disp} | {sub}")

    tg_lines.append("\n🌐 <a href=\"https://419.spb.ru/novosti/news_post/izmeneniya-raspisaniya\">Сайт лицея</a>")

    # 3. Отправка
    debug_mode = os.getenv("DEBUG_MODE") == "true"
    cancelled_count = sum(1 for _, _, canc in day_changes.values() if canc)

    current_sig = f"{target_title}_{sorted(day_changes.items())}"
    last_sig = ""
    if os.path.exists("last_changes_10a.txt"):
        with open("last_changes_10a.txt", "r", encoding="utf-8") as f:
            last_sig = f.read().strip()

    if debug_mode:
        print("🧪 РЕЖИМ ОТЛАДКИ: принудительная отправка в личку...")
        target_date_key = target_dt.strftime("%Y-%m-%d")
        debug_text = "🧪 <b>[ОТЛАДКА]</b>\n\n" + "\n".join(tg_lines)
        if send_telegram_alert(debug_text, target_date_key):
            if cancelled_count >= 2:
                send_telegram_sticker(STICKER_ID, target_date_key)
    elif current_sig != last_sig:
        print(f"📨 Отправка обновленного расписания для {target_title}...")
        target_date_key = target_dt.strftime("%Y-%m-%d")
        success = send_telegram_alert("\n".join(tg_lines), target_date_key)
        if success:
            if cancelled_count >= 2:
                print(f"🎉 Отменено уроков: {cancelled_count}! Отправляем стикер!")
                send_telegram_sticker(STICKER_ID, target_date_key)
            with open("last_changes_10a.txt", "w", encoding="utf-8") as f:
                f.write(current_sig)
    else:
        print(f"ℹ️ Для {target_title} расписание уже актуально.")

if __name__ == "__main__":
    main()