import sys
import requests
import json

# ==========================================
# KONFIGURATION (HIER DEINE WERTE EINTRAGEN)
# ==========================================
STEAM_LOGIN_SECURE = "DEIN_STEAM_LOGIN_SECURE_COOKIE"
SESSION_ID = "DEINE_SESSION_ID"
STEAM_PARENTAL = "DEIN_STEAM_PARENTAL_COOKIE"

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
    payload = {"message": f"⚠️ **Steam Fehler:**\n{message}" if is_error else f"✅ **Steam Wochenplan:**\n{message}"}
    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except Exception:
        pass

def parse_days(day_str):
    """Übersetzt Strings wie 'So-Do' oder 'Mo,Mi' in Steam-Indexe (0=So, 1=Mo... 6=Sa)."""
    days_order = ["mo", "di", "mi", "do", "fr", "sa", "so"]
    steam_map = {"mo": 1, "di": 2, "mi": 3, "do": 4, "fr": 5, "sa": 6, "so": 0}
    result = set()
    
    parts = day_str.split(',')
    for part in parts:
        if '-' in part:
            start_s, end_s = part.split('-')
            try:
                idx_start = days_order.index(start_s.lower()[:2])
                idx_end = days_order.index(end_s.lower()[:2])
            except ValueError:
                raise ValueError(f"Unbekannter Wochentag in: {part}")
            
            # Normaler Bereich (z.B. Mo-Fr)
            if idx_start <= idx_end:
                for i in range(idx_start, idx_end + 1):
                    result.add(steam_map[days_order[i]])
            # Bereich übers Wochenende (z.B. Fr-So)
            else:
                for i in range(idx_start, 7):
                    result.add(steam_map[days_order[i]])
                for i in range(0, idx_end + 1):
                    result.add(steam_map[days_order[i]])
        else:
            try:
                result.add(steam_map[part.lower()[:2]])
            except KeyError:
                raise ValueError(f"Unbekannter Wochentag: {part}")
                
    return result

def calculate_mask(start_time, end_time):
    """Berechnet den Steam-Bitmask-String für Start- und Endzeit."""
    if start_time == "24:00": start_time = "23:59"
    if end_time == "24:00": end_time = "23:59"

    def time_to_bit(time_str):
        hours, minutes = map(int, time_str.split(':'))
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

# ==========================================
# SKRIPT-START
# ==========================================
if __name__ == "__main__":
    
    args = sys.argv[1:]
    # Säubere eventuelle Semikolons, falls sie aus Versehen mitgegeben wurden
    args = [a.replace(';', '') for a in args if a.replace(';', '') != '']

    # Es müssen immer 3er-Blöcke sein
    if len(args) % 3 != 0 or len(args) == 0:
        send_notification("Ungültige Anzahl an Argumenten. Erwartet wird immer ein Dreierpack: Tage Start Ende.\nBeispiel: `So-Do 09:00 20:30 Fr-Sa 09:00 22:30`", is_error=True)
        sys.exit(1)

    # Regeln auslesen
    rules = []
    for i in range(0, len(args), 3):
        rules.append((args[i], args[i+1], args[i+2]))

    # Grund-Array für die ganze Woche vorbereiten (alles gesperrt)
    week_plan = [{"allowed_time_windows": "0", "allowed_daily_minutes": 1440} for _ in range(7)]

    # Regeln anwenden
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

    # HTTP-Session vorbereiten
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    })
    session.cookies.set("steamLoginSecure", STEAM_LOGIN_SECURE, domain="store.steampowered.com")
    session.cookies.set("sessionid", SESSION_ID, domain="store.steampowered.com")
    session.cookies.set("steamparental", STEAM_PARENTAL, domain="store.steampowered.com")

    # Token abrufen
    try:
        token_resp = session.get("https://store.steampowered.com/pointssummary/ajaxgetasyncconfig", timeout=10)
        raw_json = token_resp.json()
        access_token = None
        if isinstance(raw_json, dict):
            if "data" in raw_json and isinstance(raw_json["data"], dict):
                access_token = raw_json["data"].get("webapi_token")
            if not access_token:
                access_token = raw_json.get("webapi_token")
        if not access_token:
            send_notification("Konnte keinen WebAPI-Token generieren.", is_error=True)
            sys.exit(1)
    except Exception as e:
        send_notification(f"Fehler beim Token-Abruf: {e}", is_error=True)
        sys.exit(1)

    # Aktuelle Einstellungen abrufen
    get_url = f"https://api.steampowered.com/IParentalService/GetParentalSettings/v1/?access_token={access_token}&steamid={STEAM_ID_KIND}"
    try:
        get_resp = session.get(get_url, timeout=10)
        current_settings = get_resp.json().get("response", {}).get("settings")
        if not current_settings:
            send_notification("Konnte aktuelle Einstellungen nicht lesen.", is_error=True)
            sys.exit(1)
    except Exception as e:
        send_notification(f"Netzwerkfehler beim Abrufen der Einstellungen: {e}", is_error=True)
        sys.exit(1)

    # Wochenplan überschreiben
    if "playtime_restrictions" not in current_settings:
        current_settings["playtime_restrictions"] = {}
    
    current_settings["playtime_restrictions"]["apply_playtime_restrictions"] = True
    current_settings["playtime_restrictions"]["playtime_days"] = week_plan

    # Hochladen
    set_url = f"https://api.steampowered.com/IParentalService/SetParentalSettings/v1/?access_token={access_token}"
    set_payload = {
        "steamid": STEAM_ID_KIND,
        "settings": current_settings
    }

    try:
        set_resp = requests.post(set_url, data={"input_json": json.dumps(set_payload)}, timeout=10)
        if set_resp.status_code == 200:
            msg = "Folgender Wochenplan wurde gesetzt:\n"
            for day_str, start_time, end_time in rules:
                msg += f"• **{day_str}**: {start_time} - {end_time} Uhr\n"
            msg += "*(Nicht angegebene Tage sind komplett gesperrt)*"
            
            send_notification(msg)
            print("Erfolg: Wochenplan gespeichert.")
        else:
            send_notification(f"SetParentalSettings abgelehnt (Status {set_resp.status_code}): {set_resp.text}", is_error=True)
    except Exception as e:
        send_notification(f"Netzwerkfehler beim Speichern: {e}", is_error=True)
