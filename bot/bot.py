#!/usr/bin/env python3
# Телеграм-бот kussatayev.kz
# Сторож сайта и сервера плюс напоминания по срокам и задачам из базы админ-панели.
# Только стандартная библиотека Python 3.12. Отвечает одному человеку: владельцу.

import glob
import html
import json
import os
import re
import shutil
import socket
import sqlite3
import ssl
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Almaty")

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
PAIR_CODE = os.environ.get("BOT_PAIR_CODE", "").strip().lower()
STATE_DIR = os.environ.get("BOT_STATE_DIR", "/var/lib/kussatayev-bot")
PANEL_DB = os.environ.get("PANEL_DB", "").strip()
NAMES_MODE = os.environ.get("BOT_NAMES", "full").strip().lower()
MODELS_DIR = os.environ.get("VOSK_MODELS", "/opt/kussatayev-bot/models")
VOICE_MAX_SEC = int(os.environ.get("VOICE_MAX_SEC", "180"))
MIN_FREE_MB = int(os.environ.get("MIN_FREE_MB", "260"))

SITE_URL = os.environ.get("SITE_URL", "https://kussatayev.kz/")
PANEL_URL = os.environ.get("PANEL_URL", "https://admin.kussatayev.kz/admin/login")
DISK_URL = os.environ.get("DISK_URL", "")  # адрес сводки сторожа, задается в env
SITE_MARKER = os.environ.get("SITE_MARKER", "Кусатаева")

CHECK_EVERY = int(os.environ.get("CHECK_EVERY", "180"))
RENOTIFY = int(os.environ.get("RENOTIFY", "1800"))
DIGEST_AT = (8, 30)
EVENING_AT = (18, 30)
DEADLINE_SOON = 3
HORIZON = 14

STATE_PATH = os.path.join(STATE_DIR, "state.json")
MAP_PATH = os.path.join(STATE_DIR, "dbmap.json")
LOG_PATH = os.path.join(STATE_DIR, "bot.log")

_lock = threading.Lock()


def log(msg):
    line = "%s %s\n" % (datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"), msg)
    sys.stdout.write(line)
    sys.stdout.flush()
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
        if os.path.getsize(LOG_PATH) > 2_000_000:
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                tail = f.readlines()[-2000:]
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                f.writelines(tail)
    except Exception:
        pass


def load_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(st):
    tmp = STATE_PATH + ".tmp"
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
        os.replace(tmp, STATE_PATH)
    except Exception as e:
        log("state save failed: %r" % e)


STATE = load_state()


def st_get(key, default=None):
    with _lock:
        return STATE.get(key, default)


def st_set(**kw):
    with _lock:
        STATE.update(kw)
        save_state(STATE)


# ----------------------------------------------------------------- Телеграм

API = "https://api.telegram.org/bot%s/" % TOKEN


def tg(method, **params):
    data = urllib.parse.urlencode(
        {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
         for k, v in params.items() if v is not None}
    ).encode()
    req = urllib.request.Request(API + method, data=data)
    timeout = params.get("timeout", 20) + 20
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read().decode("utf-8"))
    if not out.get("ok"):
        raise RuntimeError("telegram: %s" % out.get("description"))
    return out.get("result")


KEYBOARD = {
    "keyboard": [
        [{"text": "Сегодня"}, {"text": "Сроки"}],
        [{"text": "Задачи"}, {"text": "Статус"}],
    ],
    "resize_keyboard": True,
}


def say(text, chat_id=None, keyboard=True):
    chat_id = chat_id or st_get("owner_id")
    if not chat_id:
        log("нет владельца, сообщение не отправлено: %s" % text[:60])
        return
    for part in split_msg(text):
        try:
            tg("sendMessage", chat_id=chat_id, text=part, parse_mode="HTML",
               disable_web_page_preview="true",
               reply_markup=KEYBOARD if keyboard else None)
        except Exception as e:
            log("send failed: %r" % e)


def split_msg(text, limit=3800):
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit:
            parts.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        parts.append(cur)
    return parts


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=False)


# ----------------------------------------------------------------- проверки

def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "kussatayev-bot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read(400_000).decode("utf-8", "replace")
        return r.status, body


def check_site():
    try:
        code, body = http_get(SITE_URL)
    except Exception as e:
        return False, "сайт не отвечает (%s)" % type(e).__name__
    if code != 200:
        return False, "сайт отдает код %s" % code
    if SITE_MARKER and SITE_MARKER not in body:
        return False, "сайт отвечает, но страница пустая или чужая"
    return True, "сайт отвечает"


def check_panel():
    try:
        code, _ = http_get(PANEL_URL)
    except Exception as e:
        return False, "панель не отвечает (%s)" % type(e).__name__
    if code != 200:
        return False, "панель отдает код %s" % code
    return True, "панель отвечает"


def read_disk_file():
    if not DISK_URL:
        return None
    try:
        code, body = http_get(DISK_URL, timeout=12)
        if code != 200:
            return None
        got = {}
        for chunk in body.split():
            if "=" in chunk:
                k, v = chunk.split("=", 1)
                got[k.strip()] = v.strip()
        return got
    except Exception:
        return None


def disk_percent():
    try:
        u = shutil.disk_usage("/")
        return int(round(u.used * 100.0 / u.total)), u
    except Exception:
        return None, None


def check_disk():
    pct, _ = disk_percent()
    if pct is None:
        return True, "диск: не удалось прочитать"
    if pct >= 85:
        return False, "диск занят на %d процентов" % pct
    return True, "диск занят на %d процентов" % pct


def run(cmd, timeout=10):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except Exception as e:
        return 1, "", repr(e)


def ipv4_addresses():
    rc, out, _ = run(["ip", "-4", "-o", "addr", "show", "scope", "global"])
    if rc != 0:
        return []
    found = re.findall(r"inet\s+(\d+\.\d+\.\d+\.\d+)/", out)
    return found


def check_ipv4():
    addrs = ipv4_addresses()
    if not addrs:
        return False, "у сервера нет адреса IPv4, снаружи сайт недоступен"
    rc, _, _ = run(["ip", "-4", "route", "show", "default"])
    return True, "адрес IPv4: %s" % ", ".join(addrs)


def check_services():
    bad = []
    names = ["nginx", "kussatayev-admin"]
    for n in names:
        rc, out, _ = run(["systemctl", "is-active", n])
        if out != "active":
            bad.append("%s: %s" % (n, out or "неизвестно"))
    if bad:
        return False, "службы не работают: " + "; ".join(bad)
    return True, "nginx и панель запущены"


def cert_days(host):
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ss:
                cert = ss.getpeercert()
        exp = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
        return (exp - datetime.utcnow()).days
    except Exception:
        return None


def check_cert():
    bad = []
    info = []
    for host in ("kussatayev.kz", "admin.kussatayev.kz"):
        d = cert_days(host)
        if d is None:
            info.append("%s: сертификат не прочитан" % host)
            continue
        info.append("%s: %d дн." % (host, d))
        if d <= 10:
            bad.append("%s истекает через %d дн." % (host, d))
    if bad:
        return False, "сертификат: " + "; ".join(bad)
    return True, "сертификаты: " + ", ".join(info)


def uptime_seconds():
    try:
        with open("/proc/uptime", "r") as f:
            return float(f.read().split()[0])
    except Exception:
        return None


def backups_info():
    out = []
    for label, pattern in (("база панели", "/var/backups/kussatayev-admin/*"),
                           ("сайт", "/var/www/backup/*")):
        try:
            items = sorted(glob.glob(pattern))
            if not items:
                out.append("%s: копий нет" % label)
                continue
            last = max(items, key=lambda p: os.path.getmtime(p))
            when = datetime.fromtimestamp(os.path.getmtime(last), TZ).strftime("%d.%m %H:%M")
            out.append("%s: %d, последняя %s" % (label, len(items), when))
        except Exception:
            out.append("%s: не прочитано" % label)
    return out


CHECKS = [
    ("ipv4", check_ipv4),
    ("site", check_site),
    ("panel", check_panel),
    ("services", check_services),
    ("disk", check_disk),
    ("cert", check_cert),
]


# ------------------------------------------------- база панели: разбор схемы

DB_CANDIDATES = [
    "/var/lib/kussatayev-admin/app.db",
    "/var/lib/kussatayev-admin/data.db",
    "/var/lib/kussatayev-admin/kussatayev.db",
]

DATE_KEYS = ("date", "due", "deadline", "srok", "when", "start", "dt", "day",
             "time", "slot", "data")
TITLE_KEYS = ("title", "name", "text", "subject", "tema", "label", "descr",
              "description", "comment", "note", "zametka")
DONE_KEYS = ("done", "is_done", "completed", "closed", "finished", "status")
KIND_KEYS = ("kind", "type", "vid", "category")


def find_db():
    if PANEL_DB and os.path.exists(PANEL_DB):
        return PANEL_DB
    for p in DB_CANDIDATES:
        if os.path.exists(p):
            return p
    found = []
    for pat in ("/var/lib/kussatayev-admin/*.db", "/var/lib/kussatayev-admin/*.sqlite*",
                "/opt/kussatayev-admin/*.db"):
        found += glob.glob(pat)
    found = [f for f in found if not f.endswith(("-wal", "-shm"))]
    return found[0] if found else None


def db_connect(write=False):
    path = find_db()
    if not path:
        return None
    if write:
        con = sqlite3.connect(path, timeout=10)
    else:
        con = sqlite3.connect("file:%s?mode=ro" % urllib.parse.quote(path), uri=True, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def schema():
    con = db_connect()
    if not con:
        return {}
    out = {}
    try:
        for r in con.execute("select name from sqlite_master where type='table'"):
            t = r["name"]
            if t.startswith("sqlite_"):
                continue
            cols = [c["name"] for c in con.execute('pragma table_info("%s")' % t)]
            out[t] = cols
    except Exception as e:
        log("schema failed: %r" % e)
    finally:
        con.close()
    return out


def pick(cols, keys):
    low = {c.lower(): c for c in cols}
    for k in keys:
        if k in low:
            return low[k]
    for c in cols:
        cl = c.lower()
        for k in keys:
            if k in cl:
                return c
    return None


def auto_map():
    sch = schema()
    m = {"db": find_db(), "tables": sch, "built": datetime.now(TZ).isoformat(timespec="seconds")}

    def entry(table):
        cols = sch[table]
        return {
            "table": table,
            "id": pick(cols, ("id",)),
            "date": pick(cols, DATE_KEYS),
            "title": pick(cols, TITLE_KEYS),
            "done": pick(cols, DONE_KEYS),
            "kind": pick(cols, KIND_KEYS),
            "case": pick(cols, ("case_id", "delo_id", "matter_id", "case")),
            "client": pick(cols, ("client_id", "client", "klient_id", "fio", "family")),
            "columns": cols,
        }

    def by_name(*words):
        for t in sch:
            tl = t.lower()
            for w in words:
                if w in tl:
                    return t
        return None

    for role, words in (
        ("deadlines", ("deadline", "srok", "term")),
        ("tasks", ("task", "zadach", "todo")),
        ("events", ("event", "hearing", "zasedan", "calendar", "kalendar", "meeting")),
        ("cases", ("case", "delo", "matter")),
        ("clients", ("client", "klient", "customer")),
        ("bookings", ("booking", "zapis", "appointment")),
    ):
        t = by_name(*words)
        m[role] = entry(t) if t else None
    return m


def get_map(refresh=False):
    if not refresh:
        try:
            with open(MAP_PATH, encoding="utf-8") as f:
                m = json.load(f)
            if m.get("db") and os.path.exists(m["db"]):
                return m
        except Exception:
            pass
    m = auto_map()
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(MAP_PATH, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
    return m


def parse_dt(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            if v > 10_000_000_000:
                v = v / 1000.0
            return datetime.fromtimestamp(v, TZ)
        except Exception:
            return None
    s = str(v).strip()
    if not s:
        return None
    s = s.replace("T", " ").replace("/", ".")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%d.%m.%Y %H:%M", "%d.%m.%Y", "%d.%m.%y"):
        try:
            d = datetime.strptime(s[:len(fmt) + 4].strip(), fmt)
            return d.replace(tzinfo=TZ)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s).replace(tzinfo=TZ)
    except Exception:
        return None


def is_done(val):
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ("1", "true", "yes", "done", "closed", "completed", "gotovo", "выполнено",
                 "закрыто", "исполнено")


def shorten(name):
    """В сокращенном режиме прячем только фамилию, остальное оставляем читаемым."""
    if st_get("names", NAMES_MODE) != "short" or not name:
        return name
    parts = str(name).split()
    for i, part in enumerate(parts):
        core = part.strip(",.;:")
        if len(core) > 4:
            parts[i] = core[:3] + "…" + part[len(core):]
            break
    return " ".join(parts)


def case_titles():
    m = get_map()
    cm = m.get("cases")
    if not cm or not cm.get("id"):
        return {}
    con = db_connect()
    if not con:
        return {}
    out = {}
    try:
        title = cm.get("title") or cm["id"]
        for r in con.execute('select "%s" as k, "%s" as v from "%s" limit 5000'
                             % (cm["id"], title, cm["table"])):
            out[r["k"]] = r["v"]
    except Exception as e:
        log("case_titles: %r" % e)
    finally:
        con.close()
    return out


def rows_of(role, limit=5000):
    m = get_map()
    cfg = m.get(role)
    if not cfg or not cfg.get("table"):
        return None, None
    con = db_connect()
    if not con:
        return None, cfg
    try:
        rows = [dict(r) for r in con.execute('select * from "%s" limit %d' % (cfg["table"], limit))]
        return rows, cfg
    except Exception as e:
        log("rows_of %s: %r" % (role, e))
        return None, cfg
    finally:
        con.close()


# ------------------------------------------------- тексты: сроки и задачи

WD = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")


def plural_days(n):
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return "%d день" % n
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "%d дня" % n
    return "%d дней" % n


def day_label(d):
    return "%02d.%02d (%s)" % (d.day, d.month, WD[d.weekday()])


def collect(role, days_ahead=HORIZON, days_back=0, only_open=True):
    rows, cfg = rows_of(role)
    if rows is None:
        return None
    out = []
    today = datetime.now(TZ).date()
    titles = case_titles() if cfg.get("case") else {}
    for r in rows:
        if only_open and cfg.get("done") and is_done(r.get(cfg["done"])):
            continue
        dt = parse_dt(r.get(cfg["date"])) if cfg.get("date") else None
        if not dt:
            continue
        delta = (dt.date() - today).days
        if delta > days_ahead or delta < -days_back:
            continue
        title = r.get(cfg["title"]) if cfg.get("title") else None
        kind = r.get(cfg["kind"]) if cfg.get("kind") else None
        who = None
        if cfg.get("case") and r.get(cfg["case"]) in titles:
            who = titles[r[cfg["case"]]]
        elif cfg.get("client") and isinstance(r.get(cfg["client"]), str):
            who = r[cfg["client"]]
        out.append({"dt": dt, "delta": delta, "title": title or "без названия",
                    "kind": kind, "who": who, "id": r.get(cfg.get("id") or "id"),
                    "raw": r})
    out.sort(key=lambda x: x["dt"])
    return out


def line_of(item, with_time=False):
    bits = []
    if with_time and (item["dt"].hour or item["dt"].minute):
        bits.append("%02d:%02d" % (item["dt"].hour, item["dt"].minute))
    else:
        bits.append(day_label(item["dt"]))
    head = " ".join(bits)
    tail = esc(item["title"])
    if item.get("kind"):
        tail = "%s: %s" % (esc(item["kind"]), tail)
    if item.get("who"):
        tail += " · %s" % esc(shorten(item["who"]))
    d = item["delta"]
    if d < 0:
        mark = " <b>просрочено на %s</b>" % plural_days(d)
    elif d == 0:
        mark = " <b>сегодня</b>"
    elif d <= DEADLINE_SOON:
        mark = " <b>осталось %s</b>" % plural_days(d)
    else:
        mark = " (через %s)" % plural_days(d)
    return "%s  %s%s" % (head, tail, mark)


def section(title, items, with_time=False, empty="пусто"):
    if items is None:
        return "<b>%s</b>\nв базе панели такой раздел не найден" % title
    if not items:
        return "<b>%s</b>\n%s" % (title, empty)
    lines = ["<b>%s</b>" % title]
    for i, it in enumerate(items[:30], 1):
        lines.append("%d. %s" % (i, line_of(it, with_time)))
    if len(items) > 30:
        lines.append("и еще %d" % (len(items) - 30))
    return "\n".join(lines)


def fmt_sroki(days=HORIZON):
    items = collect("deadlines", days_ahead=days, days_back=30)
    return section("Сроки на %d дней" % days, items, empty="сроков нет")


def fmt_zadachi():
    items = collect("tasks", days_ahead=60, days_back=30)
    return section("Задачи", items, empty="задач нет")


def fmt_segodnya():
    now = datetime.now(TZ)
    parts = ["<b>%s</b>" % day_label(now.date())]

    ev = collect("events", days_ahead=1, days_back=0, only_open=False)
    if ev is not None:
        today = [e for e in ev if e["delta"] == 0]
        tomorrow = [e for e in ev if e["delta"] == 1]
        parts.append(section("Сегодня в календаре", today, with_time=True, empty="ничего нет"))
        parts.append(section("Завтра", tomorrow, with_time=True, empty="ничего нет"))

    sr = collect("deadlines", days_ahead=DEADLINE_SOON, days_back=30)
    parts.append(section("Горящие сроки", sr, empty="нет"))

    tz = collect("tasks", days_ahead=0, days_back=30)
    parts.append(section("Задачи на сегодня и просроченные", tz, empty="нет"))

    bk = collect("bookings", days_ahead=0, days_back=1, only_open=False)
    if bk:
        parts.append(section("Записи", bk, with_time=True, empty="нет"))
    return "\n\n".join(parts)


def fmt_status():
    lines = ["<b>Сервер и сайт</b>"]
    for name, fn in CHECKS:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, "%s: ошибка проверки (%r)" % (name, e)
        lines.append(("✅ " if ok else "⚠️ ") + esc(msg))
    up = uptime_seconds()
    if up:
        lines.append("включен %s" % plural_days(up // 86400) if up >= 86400
                     else "включен %d ч." % (up // 3600))
    lines += [esc(x) for x in backups_info()]
    far = read_disk_file()
    if far:
        lines.append("сводка сторожа: диск %s%%, обновлена %s" %
                     (esc(far.get("disk", "?")), esc(far.get("updated", "?"))))
    m = get_map()
    lines.append("база панели: %s" % ("найдена" if m.get("db") else "не найдена"))
    return "\n".join(lines)


def fmt_schema():
    m = get_map(refresh=True)
    lines = ["<b>Что бот нашел в базе панели</b>", esc(m.get("db") or "база не найдена")]
    for role in ("deadlines", "tasks", "events", "cases", "clients", "bookings"):
        cfg = m.get(role)
        if not cfg:
            lines.append("%s: не найдено" % role)
            continue
        lines.append("%s → таблица %s (дата: %s, название: %s, признак готовности: %s)" %
                     (role, esc(cfg["table"]), esc(cfg.get("date")),
                      esc(cfg.get("title")), esc(cfg.get("done"))))
    lines.append("")
    lines.append("<b>Все таблицы</b>")
    for t, cols in sorted((m.get("tables") or {}).items()):
        lines.append("%s: %s" % (esc(t), esc(", ".join(cols))))
    return "\n".join(lines)


# ------------------------------------------------- запись в базу: задачи

def parse_due(text):
    t = text.lower()
    now = datetime.now(TZ)
    if "сегодня" in t:
        return now.date()
    if "послезавтра" in t:
        return (now + timedelta(days=2)).date()
    if "завтра" in t:
        return (now + timedelta(days=1)).date()
    m = re.search(r"\b(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?", t)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else now.year
        if y < 100:
            y += 2000
        try:
            got = date(y, mo, d)
            if not m.group(3) and got < now.date():
                got = date(y + 1, mo, d)
            return got
        except Exception:
            return None
    return None


def strip_due(text):
    out = re.sub(r"\bдо\s+\d{1,2}[.\-/]\d{1,2}(?:[.\-/]\d{2,4})?", "", text, flags=re.I)
    out = re.sub(r"\b(до\s+)?(сегодня|завтра|послезавтра)\b", "", out, flags=re.I)
    return " ".join(out.split()).strip(" ,.;")


def add_task(text):
    m = get_map()
    cfg = m.get("tasks")
    if not cfg or not cfg.get("table") or not cfg.get("title"):
        return "Не нашел в базе панели таблицу задач. Добавь задачу в панели, а я покажу ее здесь."
    due = parse_due(text)
    title = strip_due(text) or text.strip()
    con = db_connect(write=True)
    if not con:
        return "База панели недоступна для записи."
    try:
        info = list(con.execute('pragma table_info("%s")' % cfg["table"]))
        values = {cfg["title"]: title}
        if cfg.get("date") and due:
            values[cfg["date"]] = due.isoformat()
        for c in info:
            nm, typ, notnull, dflt, pk = c[1], (c[2] or "").upper(), c[3], c[4], c[5]
            if pk or nm in values or not notnull or dflt is not None:
                continue
            nl = nm.lower()
            if any(k in nl for k in ("created", "updated", "added")):
                values[nm] = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
            elif any(k in nl for k in DATE_KEYS):
                values[nm] = (due or datetime.now(TZ).date()).isoformat()
            elif "INT" in typ or "REAL" in typ or "NUM" in typ:
                values[nm] = 0
            else:
                values[nm] = ""
        cols = ", ".join('"%s"' % k for k in values)
        marks = ", ".join("?" for _ in values)
        con.execute('insert into "%s" (%s) values (%s)' % (cfg["table"], cols, marks),
                    list(values.values()))
        con.commit()
    except Exception as e:
        return "Не удалось записать задачу: %s" % esc(e)
    finally:
        con.close()
    when = (" до %s" % day_label(due)) if due else " без срока"
    return "Записал: %s%s" % (esc(title), when)


def close_task(num):
    ids = st_get("last_tasks") or []
    if not (1 <= num <= len(ids)):
        return "Нет задачи с таким номером. Открой список задач и назови номер из него."
    m = get_map()
    cfg = m.get("tasks")
    if not cfg or not cfg.get("done") or not cfg.get("id"):
        return "В таблице задач нет признака выполнения, закрыть из бота не получится."
    con = db_connect(write=True)
    if not con:
        return "База панели недоступна для записи."
    try:
        con.execute('update "%s" set "%s" = 1 where "%s" = ?'
                    % (cfg["table"], cfg["done"], cfg["id"]), (ids[num - 1],))
        con.commit()
    except Exception as e:
        return "Не удалось закрыть задачу: %s" % esc(e)
    finally:
        con.close()
    return "Задача %d закрыта." % num


# ------------------------------------------------- команды

HELP = """<b>Что я умею</b>
Сегодня — календарь на сегодня и завтра, горящие сроки, задачи
Сроки — все сроки на две недели: обжалование, исполнение, отправка
Задачи — открытые задачи
Статус — сайт, панель, адрес IPv4, диск, сертификаты, копии\n\nНовые заявки с сайта приходят сюда сами, в первые минуты.

/zadacha текст до 25.11 — записать задачу в панель
/gotovo 2 — закрыть задачу номер 2 из последнего списка
/sroki 30 — сроки на 30 дней
/tihо 3 — молчать 3 часа, /govori — снова говорить
/imena — переключить полные фамилии и сокращенные\n/golos рус | каз | авто — язык голосовых сообщений
/shema — что бот нашел в базе панели
/proverka — прогнать проверки прямо сейчас"""


def handle(text, chat_id):
    t = (text or "").strip()
    low = t.lower()

    if low.startswith("/start"):
        return "Я на связи. Снизу кнопки, остальное в /help.\n\n" + HELP
    if low.startswith("/help") or low in ("помощь", "/menu"):
        return HELP
    if low in ("сегодня", "/segodnya", "/today"):
        return fmt_segodnya()
    if low in ("сроки", "/sroki"):
        return fmt_sroki()
    if low.startswith("/sroki"):
        m = re.search(r"(\d+)", low)
        return fmt_sroki(int(m.group(1)) if m else HORIZON)
    if low in ("задачи", "/zadachi"):
        items = collect("tasks", days_ahead=60, days_back=30)
        st_set(last_tasks=[i["id"] for i in (items or [])])
        return fmt_zadachi()
    if low in ("статус", "/status"):
        return fmt_status()
    if low.startswith("/zadacha"):
        body = t[len("/zadacha"):].strip()
        return add_task(body) if body else "Напиши так: /zadacha подготовить апелляцию до 25.11"
    if low.startswith("/gotovo"):
        m = re.search(r"(\d+)", low)
        return close_task(int(m.group(1))) if m else "Назови номер: /gotovo 2"
    if low.startswith(("/tiho", "/tihо", "/mute")):
        m = re.search(r"(\d+)", low)
        hours = int(m.group(1)) if m else 3
        st_set(muted_until=time.time() + hours * 3600)
        return "Молчу %d ч. Проверки продолжаю." % hours
    if low.startswith(("/govori", "/unmute")):
        st_set(muted_until=0)
        return "Снова говорю."
    if low.startswith(("/golos", "/yazyk")):
        want = "auto"
        if " ru" in low or "рус" in low:
            want = "ru"
        elif " kk" in low or "каз" in low:
            want = "kk"
        st_set(voice_lang=want)
        names = {"ru": "русский", "kk": "казахский", "auto": "определяю сам"}
        return "Язык голосовых: %s." % names[want]
    if low.startswith("/imena"):
        cur = st_get("names", NAMES_MODE)
        new = "short" if cur != "short" else "full"
        st_set(names=new)
        return "Фамилии теперь %s." % ("сокращенные" if new == "short" else "полные")
    if low.startswith(("/shema", "/schema")):
        return fmt_schema()
    if low.startswith(("/proverka", "/check")):
        run_checks(force_report=True)
        return "Проверил, отчет выше."
    угадал = llm_intent(t)
    if угадал is not None:
        if isinstance(угадал, tuple):
            _, title, due = угадал
            line = title + (" до %02d.%02d" % (due.day, due.month) if due else "")
            return add_task(line)
        return handle(угадал, chat_id)
    return "Не понял. Нажми кнопку снизу или посмотри /help."


# ------------------------------------------------- голос: русский и казахский

def panel_settings():
    """Настройки из админ-панели: сервис распознавания, ключ, модель, язык."""
    con = db_connect()
    if not con:
        return {}
    try:
        out = {}
        for r in con.execute("select key, value from settings"):
            v = r["value"]
            try:
                v = json.loads(v)          # панель хранит значения в виде JSON
            except Exception:
                pass
            out[r["key"]] = v if isinstance(v, str) else v
        return out
    except Exception:
        return {}
    finally:
        con.close()


def openai_transcribe(path, key, model, lang):
    """Распознавание через OpenAI. Возвращает (текст, None) или (None, причина)."""
    import mimetypes
    import uuid
    boundary = "----kussbot" + uuid.uuid4().hex
    fields = [("model", model or "whisper-1")]
    if lang in ("ru", "kk"):
        fields.append(("language", lang))
    fields.append(("response_format", "json"))
    body = bytearray()
    for name, val in fields:
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (boundary, name, val)).encode("utf-8")
    fname = os.path.basename(path)
    if fname.lower().endswith(".oga"):      # OpenAI не принимает расширение oga
        fname = fname[:-4] + ".ogg"
    ctype = {"ogg": "audio/ogg", "wav": "audio/wav", "mp3": "audio/mpeg",
             "m4a": "audio/mp4"}.get(fname.rsplit(".", 1)[-1].lower()) \
            or mimetypes.guess_type(fname)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        data = f.read()
    body += ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
             "Content-Type: %s\r\n\r\n" % (boundary, fname, ctype)).encode("utf-8")
    body += data + ("\r\n--%s--\r\n" % boundary).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions", data=bytes(body),
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "multipart/form-data; boundary=" + boundary})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            out = json.loads(r.read().decode("utf-8"))
        text = (out.get("text") or "").strip()
        return (text or None), None
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        if e.code == 401:
            return None, "ключ OpenAI не принят"
        if e.code == 429:
            return None, "OpenAI ограничил запросы или кончились средства"
        return None, "OpenAI ответил ошибкой %s%s" % (e.code, (": " + msg[:120]) if msg else "")
    except Exception as e:
        return None, "до OpenAI не достучался (%s)" % type(e).__name__


_model_cache = {"lang": None, "model": None, "used_at": 0}

RU_UNITS = {"первое":1,"первого":1,"второе":2,"второго":2,"третье":3,"третьего":3,
            "четвертое":4,"четвертого":4,"пятое":5,"пятого":5,"шестое":6,"шестого":6,
            "седьмое":7,"седьмого":7,"восьмое":8,"восьмого":8,"девятое":9,"девятого":9,
            "десятое":10,"десятого":10,"одиннадцатое":11,"одиннадцатого":11,
            "двенадцатое":12,"двенадцатого":12,"тринадцатое":13,"тринадцатого":13,
            "четырнадцатое":14,"четырнадцатого":14,"пятнадцатое":15,"пятнадцатого":15,
            "шестнадцатое":16,"шестнадцатого":16,"семнадцатое":17,"семнадцатого":17,
            "восемнадцатое":18,"восемнадцатого":18,"девятнадцатое":19,"девятнадцатого":19,
            "двадцатое":20,"двадцатого":20,"тридцатое":30,"тридцатого":30}
RU_TENS = {"двадцать":20,"тридцать":30}
RU_SMALL = {"первое":1,"первого":1,"второе":2,"второго":2,"третье":3,"третьего":3,
            "четвертое":4,"четвертого":4,"пятое":5,"пятого":5,"шестое":6,"шестого":6,
            "седьмое":7,"седьмого":7,"восьмое":8,"восьмого":8,"девятое":9,"девятого":9}
MONTHS_RU = {"января":1,"февраля":2,"марта":3,"апреля":4,"мая":5,"июня":6,"июля":7,
             "августа":8,"сентября":9,"октября":10,"ноября":11,"декабря":12}


def words_to_day(tokens):
    """Переводит «двадцать пятого» или «пятое» в число дня."""
    for i, w in enumerate(tokens):
        if w in RU_TENS and i + 1 < len(tokens) and tokens[i + 1] in RU_SMALL:
            return RU_TENS[w] + RU_SMALL[tokens[i + 1]]
        if w in RU_TENS and (i + 1 >= len(tokens) or tokens[i + 1] in MONTHS_RU):
            return RU_TENS[w]
        if w in RU_UNITS:
            return RU_UNITS[w]
    return None


def parse_due_voice(text):
    """Срок из произнесенной фразы: «до 25 ноября», «до двадцать пятого ноября», «завтра»."""
    t = text.lower()
    plain = parse_due(t)
    if plain:
        return plain
    toks = re.findall(r"[а-яёa-z]+|\d+", t)
    month = None
    for w in toks:
        if w in MONTHS_RU:
            month = MONTHS_RU[w]
            break
    if not month:
        return None
    day = None
    m = re.search(r"(\d{1,2})\s+[а-я]*" + [k for k, v in MONTHS_RU.items() if v == month][0], t)
    if m:
        day = int(m.group(1))
    if day is None:
        day = words_to_day(toks)
    if not day:
        return None
    now = datetime.now(TZ)
    try:
        got = date(now.year, month, day)
        if got < now.date():
            got = date(now.year + 1, month, day)
        return got
    except Exception:
        return None


def free_mb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 9999


def drop_model_if_idle(minutes=15):
    """Через простой выгружаем модель: на сервере 961 МБ всего."""
    import gc
    last = _model_cache.get("used_at") or 0
    if _model_cache["model"] is not None and time.time() - last > minutes * 60:
        _model_cache["model"] = None
        _model_cache["lang"] = None
        gc.collect()
        log("модель выгружена из памяти после простоя")


def get_model(lang):
    """Держим в памяти только одну модель: сервер маленький."""
    import gc
    if _model_cache["lang"] == lang and _model_cache["model"] is not None:
        _model_cache["used_at"] = time.time()
        return _model_cache["model"]
    path = os.path.join(MODELS_DIR, lang)
    if not os.path.isdir(path):
        return None
    _model_cache["model"] = None
    _model_cache["lang"] = None
    gc.collect()
    try:
        from vosk import Model
        m = Model(path)
    except Exception as e:
        log("модель %s не загрузилась: %r" % (lang, e))
        return None
    _model_cache["lang"] = lang
    _model_cache["model"] = m
    _model_cache["used_at"] = time.time()
    return m


def recognize(wav_path, lang):
    """Возвращает (текст, уверенность 0..1) или (None, 0)."""
    import json as _json
    import wave
    model = get_model(lang)
    if model is None:
        return None, 0.0
    try:
        from vosk import KaldiRecognizer
        wf = wave.open(wav_path, "rb")
        rec = KaldiRecognizer(model, wf.getframerate())
        rec.SetWords(True)
        parts, confs = [], []
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if rec.AcceptWaveform(data):
                r = _json.loads(rec.Result())
                if r.get("text"):
                    parts.append(r["text"])
                confs += [w.get("conf", 0) for w in r.get("result", [])]
        r = _json.loads(rec.FinalResult())
        if r.get("text"):
            parts.append(r["text"])
        confs += [w.get("conf", 0) for w in r.get("result", [])]
        wf.close()
        text = " ".join(p for p in parts if p).strip()
        conf = (sum(confs) / len(confs)) if confs else 0.0
        return (text or None), conf
    except Exception as e:
        log("распознавание не удалось: %r" % e)
        return None, 0.0


def voice_to_text(file_id, chat_id):
    """Скачиваем голосовое, переводим в нужный формат, распознаем."""
    import subprocess as sp
    import tempfile
    try:
        info = tg("getFile", file_id=file_id)
        path = info["file_path"]
    except Exception as e:
        log("getFile: %r" % e)
        return None, None
    url = "https://api.telegram.org/file/bot%s/%s" % (TOKEN, path)
    tmp = tempfile.mkdtemp(prefix="golos-")
    src = os.path.join(tmp, "in.oga")
    wav = os.path.join(tmp, "out.wav")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as r, open(src, "wb") as f:
            shutil.copyfileobj(r, f)
        sp.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", src,
                "-ac", "1", "-ar", "16000", "-f", "wav", wav], check=True, timeout=120)
        ps = panel_settings()
        want = ps.get("stt_lang") or st_get("voice_lang", "auto")
        if want not in ("ru", "kk"):
            want = "auto"

        if (ps.get("stt_engine") or "local") == "openai" and ps.get("openai_key"):
            text, beda = openai_transcribe(src, ps["openai_key"], ps.get("stt_model"), want)
            if not text and beda and "format" in beda.lower():
                text, beda = openai_transcribe(wav, ps["openai_key"], ps.get("stt_model"), want)
            if text:
                return text, "openai:" + (want if want != "auto" else "")
            log("OpenAI не справился: %s" % beda)
            st_set(last_stt_error=beda or "")
            # дальше молча падаем на распознавание у себя

        if want in ("ru", "kk"):
            text, conf = recognize(wav, want)
            return text, want
        text, conf = recognize(wav, "ru")
        if text and conf >= 0.80:
            return text, "ru"
        text2, conf2 = recognize(wav, "kk")
        if (text2 or "") and conf2 > conf:
            return text2, "kk"
        return text, "ru"
    except Exception as e:
        log("голос: %r" % e)
        return None, None
    finally:
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


VOICE_WORDS = {
    "сегодня": "Сегодня", "бугин": "Сегодня", "бүгін": "Сегодня",
    "сроки": "Сроки", "срок": "Сроки", "мерзимдер": "Сроки", "мерзімдер": "Сроки",
    "задачи": "Задачи", "тапсырмалар": "Задачи",
    "статус": "Статус", "сервер": "Статус", "жагдай": "Статус", "жағдай": "Статус",
}


def voice_command(text):
    """Переводит произнесенную фразу в команду бота. Терпима к оговоркам."""
    t = (text or "").strip().lower().replace("ё", "е")
    if not t:
        return None
    toks = re.findall(r"[а-яa-zәғқңөұүһі]+|\d+", t)

    def есть(*корни):
        return any(w.startswith(k) for w in toks for k in корни)

    # сначала добавление задачи: нужен глагол плюс слово «задача»
    хочет_записать = есть("запиш", "запис", "добав", "созда", "постав", "напомн")
    про_задачу = есть("задач", "тапсырма")
    if хочет_записать and про_задачу:
        body = re.sub(r"^.*?(задач\w*|тапсырма\w*)\s*", "", t).strip()
        due = parse_due_voice(t)
        months = "|".join(MONTHS_RU)
        body = re.sub(r"\s*\bдо\s+[^,]*?\b(%s)\b\.?\s*$" % months, "", body, flags=re.I)
        title = strip_due(body) or body
        return ("task", title.strip(" ,.;:"), due)

    if есть("срок", "мерзим", "мерзім"):
        return "Сроки"
    if про_задачу:
        return "Задачи"
    if есть("сегодн", "бугин", "бүгін", "день"):
        return "Сегодня"
    if есть("статус", "сервер", "жагдай", "жағдай", "сайт"):
        return "Статус"
    return None



def handle_voice(voice, chat_id):
    """Голосовое сообщение: распознаем и выполняем как команду."""
    dur = int(voice.get("duration") or 0)
    if dur > VOICE_MAX_SEC:
        return "Голосовое длиннее %d секунд я не разбираю. Скажи короче или напиши текстом." % VOICE_MAX_SEC
    ps = panel_settings()
    через_openai = (ps.get("stt_engine") or "local") == "openai" and bool(ps.get("openai_key"))
    if not через_openai and _model_cache["model"] is None and free_mb() < MIN_FREE_MB:
        return "Сейчас на сервере мало свободной памяти, распознавание пропускаю. Напиши текстом."
    say("Слушаю, расшифровываю…", chat_id, keyboard=False)
    text, lang = voice_to_text(voice.get("file_id"), chat_id)
    if not text:
        return "Не разобрал. Скажи короче и ближе к микрофону, или напиши текстом."
    if (lang or "").startswith("openai"):
        хвост = (lang.split(":", 1)[1] or "").strip()
        metka = "OpenAI" + (", " + {"ru": "рус", "kk": "каз"}[хвост] if хвост in ("ru", "kk") else "")
        st_set(last_stt_error="")
    else:
        metka = {"ru": "рус", "kk": "каз"}.get(lang, lang or "")
        беда = st_get("last_stt_error") or ""
        if беда:
            metka = "на сервере, " + metka
            st_set(last_stt_error="")
            say("OpenAI не сработал: %s. Распознал у себя." % esc(беда), chat_id, keyboard=False)
    head = "🎤 Расслышал (%s): «%s»" % (metka, esc(text))
    cmd = voice_command(text) or llm_intent(text)
    if cmd is None:
        ответ = head + "\n\nНе понял, что с этим делать. Скажи: сегодня, сроки, задачи, статус, или «запиши задачу …»."
        maybe_speak("Не понял, что сделать. Скажи: сегодня, сроки, задачи, статус или запиши задачу.", chat_id, True)
        return ответ
    if isinstance(cmd, tuple):
        _, title, due = cmd
        if not title:
            return head + "\n\nНе расслышал саму задачу. Скажи: «запиши задачу» и дальше текст."
        line = title + (" до %02d.%02d" % (due.day, due.month) if due else "")
        итог = add_task(line)
        maybe_speak(итог, chat_id, True)
        return head + "\n\n" + итог
    итог = handle(cmd, chat_id)
    maybe_speak(итог, chat_id, True)
    return head + "\n\n" + итог


# ------------------------------------------------- ответ голосом и понимание речи

def openai_speak(text, key, model, voice):
    """Озвучка ответа. Возвращает путь к ogg/opus или None."""
    import tempfile
    чисто = re.sub(r"<[^>]+>", "", text or "")
    чисто = чисто.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    чисто = re.sub(r"https?://\S+", "ссылка в сообщении", чисто)
    чисто = re.sub(r"[🎤🔔✅⚠️]", "", чисто).strip()
    if not чисто:
        return None
    if len(чисто) > 900:
        чисто = чисто[:900] + "… остальное в сообщении"
    body = json.dumps({"model": model or "gpt-4o-mini-tts", "voice": voice or "alloy",
                       "input": чисто, "response_format": "opus"}).encode("utf-8")
    req = urllib.request.Request("https://api.openai.com/v1/audio/speech", data=body,
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
    except Exception as e:
        log("озвучка не вышла: %r" % e)
        return None
    path = os.path.join(tempfile.mkdtemp(prefix="otvet-"), "otvet.ogg")
    with open(path, "wb") as f:
        f.write(data)
    return path


def send_voice(path, chat_id, caption=None):
    """Отправляет голосовое сообщение в Телеграм."""
    import uuid
    b = "----kussbot" + uuid.uuid4().hex
    body = bytearray()
    поля = [("chat_id", str(chat_id))]
    if caption:
        поля.append(("caption", caption[:1000]))
    for n, v in поля:
        body += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (b, n, v)).encode("utf-8")
    with open(path, "rb") as f:
        data = f.read()
    body += ('--%s\r\nContent-Disposition: form-data; name="voice"; filename="otvet.ogg"\r\n'
             'Content-Type: audio/ogg\r\n\r\n' % b).encode("utf-8")
    body += data + ("\r\n--%s--\r\n" % b).encode("utf-8")
    req = urllib.request.Request(API + "sendVoice", data=bytes(body),
                                 headers={"Content-Type": "multipart/form-data; boundary=" + b})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            json.loads(r.read().decode("utf-8"))
        return True
    except Exception as e:
        log("голосовой ответ не ушел: %r" % e)
        return False


def maybe_speak(text, chat_id, было_голосовое):
    """Озвучивает ответ, если так настроено в панели."""
    ps = panel_settings()
    режим = ps.get("tts_on") or "voice"
    if режим == "off":
        return
    if режим == "voice" and not было_голосовое:
        return
    key = ps.get("openai_key")
    if not key:
        return
    path = openai_speak(text, key, ps.get("tts_model"), ps.get("tts_voice"))
    if not path:
        return
    try:
        send_voice(path, chat_id)
    finally:
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


ДЕЙСТВИЯ = {
    "today": "Сегодня", "deadlines": "Сроки", "tasks": "Задачи", "status": "Статус",
}


def llm_intent(text):
    """Свободная фраза через ChatGPT: что человек хочет. Возвращает команду или None."""
    ps = panel_settings()
    key = ps.get("openai_key")
    if not key or (ps.get("llm_on") or "on") == "off":
        return None
    сегодня = datetime.now(TZ).strftime("%Y-%m-%d")
    правила = (
        "Ты разбираешь короткие распоряжения юриста на русском или казахском языке. "
        "Сегодня %s, часовой пояс Астана. Верни только JSON с полями: "
        "action (today, deadlines, tasks, status, add_task, unknown), "
        "title (текст задачи, если action=add_task, иначе пустая строка), "
        "due (дата задачи в виде ГГГГ-ММ-ДД или null). "
        "today это планы на сегодня и завтра, deadlines это процессуальные сроки, "
        "tasks это список задач, status это состояние сайта и сервера, "
        "add_task это просьба записать или поставить задачу." % сегодня
    )
    body = json.dumps({
        "model": ps.get("llm_model") or "gpt-4o-mini",
        "messages": [{"role": "system", "content": правила},
                     {"role": "user", "content": text[:500]}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=body,
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read().decode("utf-8"))
        ответ = json.loads(out["choices"][0]["message"]["content"])
    except Exception as e:
        log("ChatGPT не понял: %r" % e)
        return None
    act = (ответ.get("action") or "").strip()
    if act in ДЕЙСТВИЯ:
        return ДЕЙСТВИЯ[act]
    if act == "add_task":
        title = (ответ.get("title") or "").strip()
        due = None
        d = (ответ.get("due") or "")
        if re.fullmatch(r"\d{4}-\d\d-\d\d", d or ""):
            try:
                due = date(int(d[:4]), int(d[5:7]), int(d[8:10]))
            except Exception:
                due = None
        if title:
            return ("task", title, due)
    return None


# ------------------------------------------------- сторож

def muted():
    return float(st_get("muted_until", 0) or 0) > time.time()


def run_checks(force_report=False):
    states = dict(st_get("checks", {}) or {})
    now = time.time()
    report = []
    changed = []
    for name, fn in CHECKS:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, "проверка %s не выполнилась (%r)" % (name, e)
        prev = states.get(name) or {}
        was_ok = prev.get("ok", True)
        rec = {"ok": ok, "msg": msg, "since": prev.get("since", now) if ok == was_ok else now,
               "last_notify": prev.get("last_notify", 0)}
        report.append(("✅ " if ok else "⚠️ ") + msg)
        if not ok and (was_ok or now - rec["last_notify"] >= RENOTIFY):
            changed.append("⚠️ <b>%s</b>" % esc(msg))
            rec["last_notify"] = now
        if ok and not was_ok:
            down_for = int(now - prev.get("since", now))
            changed.append("✅ %s (не работало %d мин.)" % (esc(msg), max(1, down_for // 60)))
            rec["last_notify"] = 0
        states[name] = rec

    up = uptime_seconds()
    if up is not None and up < 900:
        last = st_get("boot_alert", 0)
        if now - float(last or 0) > 3600:
            changed.append("⚠️ <b>Сервер перезагрузился.</b> Адрес IPv4 прописан вручную "
                           "и после перезагрузки слетает. Проверь, открывается ли сайт.")
            st_set(boot_alert=now)

    st_set(checks=states)
    if changed and not muted():
        say("\n".join(changed))
    if force_report:
        say("\n".join(report))
    return report


def check_new_bookings():
    """Новые заявки с сайта: сообщаем о каждой один раз."""
    rows, cfg = rows_of("bookings")
    if rows is None or not cfg:
        return
    idc = cfg.get("id") or "id"
    cols = cfg.get("columns") or []
    phone_c = pick(cols, ("phone", "tel", "telefon", "nomer"))
    topic_c = pick(cols, ("topic", "tema", "subject", "vopros"))
    msg_c = pick(cols, ("message", "text", "comment", "note"))
    name_c = cfg.get("title")
    date_c = cfg.get("date")

    ids = []
    for r in rows:
        try:
            ids.append(int(r.get(idc)))
        except Exception:
            continue
    if not ids:
        return
    last = st_get("last_booking")
    if last is None:
        st_set(last_booking=max(ids))
        return

    fresh = [r for r in rows if str(r.get(idc)).isdigit() and int(r.get(idc)) > int(last)]
    if not fresh:
        return
    fresh.sort(key=lambda r: int(r.get(idc)))
    for r in fresh:
        lines = ["🔔 <b>Новая заявка с сайта</b>"]
        when = parse_dt(r.get(date_c)) if date_c else None
        if when:
            lines.append("время: %s %02d:%02d" % (day_label(when.date()), when.hour, when.minute))
        if name_c and r.get(name_c):
            lines.append("имя: %s" % esc(r.get(name_c)))
        if phone_c and r.get(phone_c):
            lines.append("телефон: %s" % esc(r.get(phone_c)))
        if topic_c and r.get(topic_c):
            lines.append("тема: %s" % esc(r.get(topic_c)))
        if msg_c and r.get(msg_c):
            lines.append("текст: %s" % esc(str(r.get(msg_c))[:400]))
        lines.append("")
        lines.append("Панель: https://admin.kussatayev.kz/admin/bookings")
        say("\n".join(lines))
    st_set(last_booking=max(int(r.get(idc)) for r in fresh))


def digest_text():
    parts = [fmt_segodnya(), "", fmt_sroki(HORIZON)]
    bad = [c["msg"] for c in (st_get("checks", {}) or {}).values() if not c.get("ok")]
    parts.append("")
    parts.append("<b>Сервер</b>\n" + ("⚠️ " + "; ".join(esc(b) for b in bad) if bad
                                      else "✅ сайт, панель и диск в порядке"))
    return "\n".join(parts)


def evening_text():
    now = datetime.now(TZ)
    ev = collect("events", days_ahead=1, days_back=0, only_open=False)
    tomorrow = [e for e in (ev or []) if e["delta"] == 1]
    parts = ["<b>На завтра, %s</b>" % day_label((now + timedelta(days=1)).date())]
    parts.append(section("Календарь", tomorrow, with_time=True, empty="ничего не стоит"))
    sr = collect("deadlines", days_ahead=DEADLINE_SOON, days_back=30)
    parts.append(section("Сроки в ближайшие дни", sr, empty="нет"))
    return "\n\n".join(parts)


def due_now(hhmm, key):
    now = datetime.now(TZ)
    target = now.replace(hour=hhmm[0], minute=hhmm[1], second=0, microsecond=0)
    today = now.date().isoformat()
    if now >= target and st_get(key) != today:
        st_set(**{key: today})
        return True
    return False


def monitor():
    while True:
        try:
            run_checks()
            drop_model_if_idle()
            if st_get("owner_id"):
                check_new_bookings()
                if due_now(DIGEST_AT, "last_digest"):
                    say(digest_text())
                if due_now(EVENING_AT, "last_evening"):
                    say(evening_text())
        except Exception:
            log("monitor: " + traceback.format_exc())
        time.sleep(CHECK_EVERY)


# ------------------------------------------------- основной цикл

def main():
    if not TOKEN:
        print("Не задан BOT_TOKEN в /etc/kussatayev-bot.env", file=sys.stderr)
        sys.exit(2)
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        me = tg("getMe")
        log("бот запущен: @%s" % me.get("username"))
    except Exception as e:
        print("Телеграм не принял токен: %r" % e, file=sys.stderr)
        sys.exit(3)

    try:
        tg("setMyCommands", commands=[
            {"command": "segodnya", "description": "Сегодня: календарь, сроки, задачи"},
            {"command": "sroki", "description": "Сроки на две недели"},
            {"command": "zadachi", "description": "Открытые задачи"},
            {"command": "status", "description": "Сайт, сервер, копии"},
            {"command": "zadacha", "description": "Записать задачу"},
            {"command": "gotovo", "description": "Закрыть задачу по номеру"},
            {"command": "help", "description": "Все команды"},
        ])
    except Exception as e:
        log("setMyCommands: %r" % e)

    threading.Thread(target=monitor, daemon=True).start()

    if st_get("owner_id"):
        say("Бот перезапущен и снова следит за сайтом.")

    offset = int(st_get("offset", 0) or 0)
    while True:
        try:
            updates = tg("getUpdates", offset=offset, timeout=50,
                         allowed_updates=["message"]) or []
        except Exception as e:
            log("getUpdates: %r" % e)
            time.sleep(5)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            st_set(offset=offset)
            msg = u.get("message") or {}
            chat_id = (msg.get("chat") or {}).get("id")
            text = msg.get("text") or ""
            voice = msg.get("voice") or msg.get("audio") or {}
            if not chat_id:
                continue
            owner = st_get("owner_id")
            if not owner:
                code = text.strip().split()[-1].lower() if text.strip() else ""
                if PAIR_CODE and code == PAIR_CODE:
                    st_set(owner_id=chat_id)
                    log("владелец привязан: %s" % chat_id)
                    say("Готово, я теперь отвечаю только тебе.\n\n" + HELP, chat_id)
                else:
                    log("чужой или без кода: chat=%s text=%r" % (chat_id, text[:40]))
                continue
            if chat_id != owner:
                log("чужое сообщение от %s: %r" % (chat_id, text[:40]))
                continue
            if voice and not text:
                try:
                    answer = handle_voice(voice, chat_id)
                except Exception:
                    log("handle_voice: " + traceback.format_exc())
                    answer = "Не смог разобрать голосовое, попробуй еще раз или напиши текстом."
                if answer:
                    say(answer, chat_id)
                continue
            try:
                answer = handle(text, chat_id)
            except Exception:
                log("handle: " + traceback.format_exc())
                answer = "Внутренняя ошибка, посмотри журнал: journalctl -u kussatayev-bot"
            if answer:
                say(answer, chat_id)


if __name__ == "__main__":
    main()
