import sys
import requests
import json
from pathlib import Path

# ==========================================
# KONFIGURATION (HIER DEINE WERTE EINTRAGEN)
# ==========================================
COOKIE_FILE = "/config/steam-auth/steam-state.json"
STEAM_ID_KIND = "DEINE_STEAMID64_DES_KINDES"

# Home Assistant Anbindung
HA_URL = "http://127.0.0.1:58123"            # Deine HA-IP inklusive Port
HA_TOKEN = "DEIN_LANGLEBIGER_ZUGANGS_TOKEN"   # Dein Langlebiger Zugangs-Token
HA_NOTIFY_SERVICE = "notify/matrix_xxx"  # Der genutzte Notify-Dienst

# Steuerung der Benachrichtigungen
SUCCESS_MESSAGES = True   # True = Erfolge an HA senden / False = Nur Fehler senden

# ==========================================
# HILFSFUNKTIONEN
# ==========================================
def send_notification(message, is_error=False):
    if not is_error and not SUCCESS_MESSAGES:
        return

    url = f"{HA_URL.rstrip('/')}/api/services/{HA_NOTIFY_SERVICE}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": (
            f"⚠️ Steam Fehler:\n{message}"
            if is_error else
            f"✅ Steam Wochenplan:\n{message}"
        )
    }

    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except Exception:
        pass


def parse_days(day_str):
    """Übersetzt Strings wie 'So-Do' oder 'Mo,Mi' in Steam-Indexe (0=So, 1=Mo ... 6=Sa)."""
    days_order = ["mo", "di", "mi", "do", "fr", "sa", "so"]
    steam_map = {"mo": 1, "di": 2, "mi": 3, "do": 4, "fr": 5, "sa": 6, "so": 0}
    result = set()

    parts = day_str.split(",")
    for part in parts:
        part = part.strip().lower()

        if "-" in part:
            start_s, end_s = [p.strip()[:2] for p in part.split("-", 1)]
            try:
                idx_start = days_order.index(start_s)
                idx_end = days_order.index(end_s)
            except ValueError:
                raise ValueError(f"Unbekannter Wochentag in: {part}")

            if idx_start <= idx_end:
                for i in range(idx_start, idx_end + 1):
                    result.add(steam_map[days_order[i]])
            else:
                for i in range(idx_start, 7):
                    result.add(steam_map[days_order[i]])
                for i in range(0, idx_end + 1):
                    result.add(steam_map[days_order[i]])
        else:
            key = part[:2]
            if key not in steam_map:
                raise ValueError(f"Unbekannter Wochentag: {part}")
            result.add(steam_map[key])

    return result


def calculate_mask(start_time, end_time):
    """Berechnet den Steam-Bitmask-String für Start- und Endzeit."""
    if start_time == "24:00":
        start_time = "23:59"
    if end_time == "24:00":
        end_time = "23:59"

    def time_to_bit(time_str):
        hours, minutes = map(int, time_str.split(":"))
        return hours * 2 + (1 if minutes >= 30 else 0)

    start_bit = time_to_bit(start_time)
    end_bit = time_to_bit(end_time)

    mask = 0
    if start_bit < end_bit:
        for i in range(start_bit, end_bit):
            mask |= (1 << i)
    elif start_bit > end_bit:
        for i in range(start_bit, 48):
            mask |= (1 << i)
        for i in range(0, end_bit):
            mask |= (1 << i)

    return str(int(mask))


def load_cookie_state(path):
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Cookie-Datei nicht gefunden: {path}")

    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_cookie(cookies, name, domain_contains=None):
    for cookie in cookies:
        if cookie.get("name") != name:
            continue
        if domain_contains and domain_contains not in cookie.get("domain", ""):
            continue
        return cookie.get("value")
    return None


def build_session_from_file(cookie_file):
    state = load_cookie_state(cookie_file)
    cookies = state.get("cookies", [])

    steam_login_secure = get_cookie(cookies, "steamLoginSecure", "store.steampowered.com")
    session_id = get_cookie(cookies, "sessionid", "store.steampowered.com")
    steam_parental = get_cookie(cookies, "steamparental", "store.steampowered.com")

    if not steam_login_secure:
        raise RuntimeError("steamLoginSecure fehlt in steam-state.json")
    if not session_id:
        raise RuntimeError("sessionid fehlt in steam-state.json")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://store.steampowered.com/",
        "Origin": "https://store.steampowered.com",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty"
    })

    session.cookies.set("steamLoginSecure", steam_login_secure, domain="store.steampowered.com")
    session.cookies.set("sessionid", session_id, domain="store.steampowered.com")

    if steam_parental:
        session.cookies.set("steamparental", steam_parental, domain="store.steampowered.com")

    return session, bool(steam_parental)


def get_access_token(session):
    token_resp = session.get(
        "https://store.steampowered.com/pointssummary/ajaxgetasyncconfig",
        timeout=10
    )
    token_resp.raise_for_status()

    raw_json = token_resp.json()
    access_token = None

    if isinstance(raw_json, dict):
        if "data" in raw_json and isinstance(raw_json["data"], dict):
            access_token = raw_json["data"].get("webapi_token")
        if not access_token:
            access_token = raw_json.get("webapi_token")

    if not access_token:
        raise RuntimeError("Konnte keinen WebAPI-Token generieren.")

    return access_token


# ==========================================
# SKRIPT-START
# ==========================================
if __name__ == "__main__":
    args = sys.argv[1:]
    args = [a.replace(";", "") for a in args if a.replace(";", "") != ""]

    if len(args) % 3 != 0 or len(args) == 0:
        send_notification(
            "Ungültige Anzahl an Argumenten. Erwartet werden immer 3er-Gruppen: Tage Start Ende.\n"
            "Beispiel: `So-Do 09:00 20:30 Fr-Sa 09:00 22:30`",
            is_error=True
        )
        sys.exit(1)

    rules = []
    for i in range(0, len(args), 3):
        rules.append((args[i], args[i + 1], args[i + 2]))

    week_plan = [{"allowed_time_windows": "0", "allowed_daily_minutes": 1440} for _ in range(7)]

    try:
        for day_str, start_time, end_time in rules:
            target_days = parse_days(day_str)
            mask = calculate_mask(start_time, end_time)
            for d in target_days:
                week_plan[d] = {
                    "allowed_time_windows": mask,
                    "allowed_daily_minutes": 1440
                }
    except Exception as e:
        send_notification(f"Fehler beim Verarbeiten der Tage/Zeiten: {e}", is_error=True)
        sys.exit(1)

    try:
        session, has_parental_cookie = build_session_from_file(COOKIE_FILE)
    except Exception as e:
        send_notification(f"Fehler beim Laden der Cookie-Datei: {e}", is_error=True)
        sys.exit(1)

    try:
        access_token = get_access_token(session)
    except Exception as e:
        send_notification(f"Fehler beim Token-Abruf: {e}", is_error=True)
        sys.exit(1)

    get_url = (
        "https://api.steampowered.com/IParentalService/GetParentalSettings/v1/"
        f"?access_token={access_token}&steamid={STEAM_ID_KIND}"
    )

    try:
        get_resp = session.get(get_url, timeout=10)
        get_resp.raise_for_status()

        current_settings = get_resp.json().get("response", {}).get("settings")
        if not current_settings:
            send_notification("Konnte aktuelle Einstellungen nicht lesen.", is_error=True)
            sys.exit(1)
    except Exception as e:
        send_notification(f"Netzwerkfehler beim Abrufen der Einstellungen: {e}", is_error=True)
        sys.exit(1)

    if "playtime_restrictions" not in current_settings:
        current_settings["playtime_restrictions"] = {}

    current_settings["playtime_restrictions"]["apply_playtime_restrictions"] = True
    current_settings["playtime_restrictions"]["playtime_days"] = week_plan

    set_url = (
        "https://api.steampowered.com/IParentalService/SetParentalSettings/v1/"
        f"?access_token={access_token}"
    )
    set_payload = {
        "steamid": STEAM_ID_KIND,
        "settings": current_settings
    }

    try:
        set_resp = session.post(
            set_url,
            data={"input_json": json.dumps(set_payload)},
            timeout=10
        )

        if set_resp.status_code == 200:
            message_lines = ["Folgender Wochenplan wurde gesetzt:"]
            for day_str, start_time, end_time in rules:
                message_lines.append(f"• {day_str}: {start_time} - {end_time}")
            message_lines.append("Nicht angegebene Tage bleiben komplett gesperrt.")
            message_lines.append(
                f"Cookie-Modus: {'mit steamparental' if has_parental_cookie else 'ohne steamparental'}"
            )

            send_notification("\n".join(message_lines))
            print("Erfolg: Wochenplan gespeichert.")
        else:
            send_notification(
                f"SetParentalSettings abgelehnt (Status {set_resp.status_code}): {set_resp.text}",
                is_error=True
            )
            sys.exit(1)
    except Exception as e:
        send_notification(f"Netzwerkfehler beim Speichern: {e}", is_error=True)
        sys.exit(1)
