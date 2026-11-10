import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta

URL = "https://419.spb.ru/novosti/news_post/izmeneniya-raspisaniya"
HEADERS = {"User-Agent": "Mozilla/5.0"}

DAYS_RU = ["ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ", "ПЯТНИЦА", "СУББОТА", "ВОСКРЕСЕНЬЕ"]

BASE_SCHEDULE_10A = {
    0: {1: ("Раз-ры о важном", ""), 2: ("Геометрия", "306"), 3: ("Физика", "301"), 4: ("Физика", "301"), 5: ("Геометрия", "323"), 6: ("Алгебра", "323"), 7: ("Обществознание", "319")},
    1: {1: ("ВФи", "301"), 2: ("Геометрия", "201"), 3: ("ИП", "102"), 4: ("Литература", "218"), 5: ("Физика", "301"), 6: ("История", "101"), 7: ("Англ. язык", "206/217"), 8: ("Англ. язык", "206/217")},
    2: {1: ("Алгебра", "102"), 2: ("Литература", "301"), 3: ("Биология", "317"), 4: ("Русский язык", "307"), 5: ("История", "307"), 6: ("Алгебра", "102"), 7: ("ВЗн", "102")},
    3: {1: ("Физика", "301"), 2: ("Физика", "301"), 3: ("Обществознание", "301"), 4: ("Геометрия", "306"), 5: ("Англ. язык", "206/217"), 6: ("Вер. и стат.", "306"), 7: ("Литература", "303")},
    4: {1: ("Информатика", "230/227"), 2: ("Русский язык", "321"), 3: ("География", "316"), 4: ("Химия", "323"), 5: ("Информатика", "230/227"), 6: ("Физика", "301"), 7: ("ВИН", "230")},
    5: {1: ("Физкультура", "сп.зал"), 2: ("Физкультура", "сп.зал"), 3: ("Алгебра", "225"), 4: ("Алгебра", "225"), 5: ("ОБЗР", "102"), 7: ("ВРЕ", "301")}
}

def get_day():
    now = datetime.utcnow() + timedelta(hours=3) # Поправка на МСК (UTC+3)
    if now.weekday() == 6 or (now.weekday() == 5 and now.hour >= 15):
        return 0, "ПОНЕДЕЛЬНИК"
    if now.hour >= 16:
        nxt = now + timedelta(days=1)
        return (0, "ПОНЕДЕЛЬНИК") if nxt.weekday() == 6 else (nxt.weekday(), DAYS_RU[nxt.weekday()])
    return now.weekday(), DAYS_RU[now.weekday()]

def main():
    target_weekday, day_title = get_day()
    base = BASE_SCHEDULE_10A.get(target_weekday, {}).copy()
    changes_by_day = {i: {} for i in range(7)}
    current_weekday = None

    try:
        res = requests.get(URL, headers=HEADERS, timeout=12)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, "html.parser")
        is_students = False

        for el in soup.find_all(['h1', 'h2', 'h3', 'p', 'div', 'tr']):
            txt = el.get_text(" ", strip=True)
            txt_lower = txt.lower()

            if "ОБУЧАЮЩИЕСЯ" in txt.upper() or "УЧАЩИЕСЯ" in txt.upper():
                is_students = True
                continue
            elif "ПЕДАГОГИ" in txt.upper() and len(txt) < 30 and is_students:
                is_students = False
                continue

            if not is_students:
                continue

            for d_name, d_idx in DAY_MAP.items():
                if d_name in txt_lower and ("изменения" in txt_lower or "расписани" in txt_lower or re.search(r'\d{1,2}\s+[а-я]+', txt_lower)):
                    if len(txt) < 80:
                        current_weekday = d_idx
                        break

            if el.name == 'tr' and current_weekday is not None:
                cells = [re.sub(r'\s+', ' ', td.get_text(strip=True)) for td in el.find_all(['td', 'th'])]
                if len(cells) < 2:
                    continue

                if re.search(r'\b10\s*[-–—/]?\s*[аa]', cells[0], re.IGNORECASE):
                    row_str = " ".join(cells)
                    is_canc = bool(re.search(r'(?i)\b(нет\s*урока|снят|отмен)', row_str))

                    if len(cells) >= 3 and cells[1].isdigit():
                        num = int(cells[1])
                        sub = cells[2]
                        room = cells[3] if len(cells) > 3 else ""
                        changes_by_day[current_weekday][num] = (sub, room, is_canc)
                    elif is_canc:
                        for digit in re.findall(r'\d+', row_str):
                            changes_by_day[current_weekday][int(digit)] = ("Нет урока", "", True)
    except Exception:
        pass

    day_changes = changes_by_day.get(target_weekday, {})
    lines = [f"10А • {day_title}"]
    all_nums = sorted(set(list(base.keys()) + list(day_changes.keys())))

    for num in all_nums:
        if num in day_changes:
            sub, room, cancelled = day_changes[num]
            r = f" ({room})" if room else ""
            lines.append(f"{num} ур: ❌ {sub} [СНЯТ]" if cancelled else f"{num} ур: ⚡ {sub}{r}")
        elif num in base:
            sub, room = base[num]
            r = f" ({room})" if room else ""
            lines.append(f"{num} ур: {sub}{r}")

    with open("today_10a.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
