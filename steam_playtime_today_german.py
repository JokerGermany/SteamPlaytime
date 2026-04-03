import sys
import requests
import json
from datetime import datetime, timedelta

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
    payload = {"message": f"⚠️ **Steam Fehler:**\n{message}" if is_error else f"✅ **Steam Update:**\n{message}"}
    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except Exception:
        pass

def time_to_bit(time_str):
    hours, minutes = map(int, time_str.split(':'))
    return hours * 2 + (1 if minutes >= 30 else 0)

# ==========================================
# SKRIPT-START
# ==========================================
if __name__ == "__main__":
    if len(sys.argv) < 3:
        send_notification("Start- und Endzeit fehlen (z.B. '11:30' '23:00').", is_error=True)
        sys.exit(1)

    start_time = sys.argv[1]
    end_time = sys.argv[2]

    try:
        start_bit = time_to_bit(start_time)
        end_bit = time_to_bit(end_time)
    except Exception:
        send_notification(f"Ungültiges Zeitformat: {start_time} - {end_time}", is_error=True)
        sys.exit(1)

    # 1. Bitmaske ausrechnen (Achtung: Steam benötigt das als String, kein Float!)
    mask = 0
    if start_bit < end_bit:
        for i in range(start_bit, end_bit):
            mask |= (1 << i)
    elif start_bit > end_bit: 
        for i in range(start_bit, 48):
            mask |= (1 << i)
        for i in range(0, end_bit):
            mask |= (1 << i)

    mask_str = str(int(mask))

    jetzt = datetime.now()
    morgen_mitternacht = (jetzt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    rtime_expires = int(morgen_mitternacht.timestamp())

    # 2. HTTP-Session
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty"
    })

    session.cookies.set("steamLoginSecure", STEAM_LOGIN_SECURE, domain="store.steampowered.com")
    session.cookies.set("sessionid", SESSION_ID, domain="store.steampowered.com")
    session.cookies.set("steamparental", STEAM_PARENTAL, domain="store.steampowered.com")

    # 3. Token abrufen
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
            send_notification("Konnte keinen WebAPI-Token generieren. Cookie abgelaufen?", is_error=True)
            sys.exit(1)
    except Exception as e:
        send_notification(f"Fehler beim Token-Abruf: {e}", is_error=True)
        sys.exit(1)

    # 4. Aktuelle Einstellungen des Kindes auslesen
    get_url = f"https://api.steampowered.com/IParentalService/GetParentalSettings/v1/?access_token={access_token}&steamid={STEAM_ID_KIND}"
    try:
        get_resp = session.get(get_url, timeout=10)
        if get_resp.status_code != 200:
            send_notification(f"Konnte Einstellungen nicht abrufen (Status {get_resp.status_code}).", is_error=True)
            sys.exit(1)
        
        current_settings = get_resp.json().get("response", {}).get("settings")
        if not current_settings:
            send_notification("JSON enthielt kein 'settings' Feld.", is_error=True)
            sys.exit(1)
    except Exception as e:
        send_notification(f"Netzwerkfehler beim Abrufen der Einstellungen: {e}", is_error=True)
        sys.exit(1)

    # 5. Einstellungen anpassen (temporäre Spielzeit injizieren)
    current_settings["temporary_playtime_restrictions"] = {
        "restrictions": {
            "allowed_time_windows": mask_str,
            "allowed_daily_minutes": 1440
        },
        "rtime_expires": rtime_expires
    }

    # 6. Einstellungen als Elternteil wieder hochladen (Überschreiben)
    set_url = f"https://api.steampowered.com/IParentalService/SetParentalSettings/v1/?access_token={access_token}&steamid={STEAM_ID_KIND}"
        # 6. Einstellungen als Elternteil wieder hochladen (Überschreiben)
    set_url = f"https://api.steampowered.com/IParentalService/SetParentalSettings/v1/?access_token={access_token}"
    set_payload = {
        "steamid": STEAM_ID_KIND,
        "settings": current_settings
    }

    try:
        set_resp = requests.post(set_url, data={"input_json": json.dumps(set_payload)}, timeout=10)
        if set_resp.status_code == 200:
            send_notification(f"Temporäres Zeitfenster für heute ({start_time} - {end_time} Uhr) erfolgreich gesetzt!")
            print(f"Erfolg: {start_time}-{end_time} gesetzt.")
        else:
            send_notification(f"SetParentalSettings abgelehnt (Status {set_resp.status_code}): {set_resp.text}", is_error=True)
    except Exception as e:
        send_notification(f"Netzwerkfehler beim Speichern der Einstellungen: {e}", is_error=True)
