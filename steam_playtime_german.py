import sys
import requests

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
# PAYLOAD-PROFILE (BASE64 STRINGS EINTRAGEN)
# ==========================================
PAYLOADS = {
    "normal": "HIER_DEN_PAYLOAD_FUER_GESPERRT_EINTRAGEN",
    "offen": "HIER_DEN_PAYLOAD_FUER_UNLIMITIERT_EINTRAGEN"
    "gesperrt": "HIER_DEN_PAYLOAD_FUER_GESPERRT_EINTRAGEN",
    "werktags": "HIER_DEN_PAYLOAD_FUER_WERKTAGS_EINTRAGEN",
    "wochenende": "HIER_DEN_PAYLOAD_FUER_WOCHENENDE_EINTRAGEN",
}

# ==========================================
# BENACHRICHTIGUNGS-FUNKTION
# ==========================================
def send_notification(message, is_error=False):
    """Sendet Fehlermeldungen (und auf Wunsch Erfolgsmeldungen) an HA."""
    # Wenn es kein Fehler ist und SUCCESS_MESSAGES auf False steht, brechen wir hier leise ab.
    if not is_error and not SUCCESS_MESSAGES:
        return

    url = f"{HA_URL.rstrip('/')}/api/services/{HA_NOTIFY_SERVICE}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    if is_error:
        formatted_message = f"⚠️ **Steam Family Skript Fehler:**\n{message}"
    else:
        formatted_message = f"✅ **Steam Family Skript:**\n{message}"
        
    payload = {"message": formatted_message}
    
    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except Exception as e:
        print(f"Kritischer Fehler: Konnte {HA_NOTIFY_SERVICE} nicht erreichen. Grund: {e}")

# ==========================================
# SKRIPT-START
# ==========================================
if __name__ == "__main__":
    # 1. Gewünschtes Profil aus den Argumenten auslesen
    if len(sys.argv) < 2:
        send_notification("Es wurde kein Profil-Name (z.B. 'werktags') übergeben.", is_error=True)
        sys.exit(1)

    profil_name = sys.argv[1].lower()

    if profil_name not in PAYLOADS:
        send_notification(f"Das Profil '{profil_name}' existiert nicht im Skript.", is_error=True)
        sys.exit(1)

    aktiver_payload = PAYLOADS[profil_name]

    if aktiver_payload.startswith("HIER_DEN_PAYLOAD"):
        send_notification(f"Der Payload für das Profil '{profil_name}' wurde noch nicht eingetragen.", is_error=True)
        sys.exit(1)

    # 2. HTTP-Session für Steam vorbereiten (Tarnung als echter Browser)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "de,en-US;q=0.7,en;q=0.3",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty"
    })

    # Cookies setzen
    session.cookies.set("steamLoginSecure", STEAM_LOGIN_SECURE, domain="store.steampowered.com")
    session.cookies.set("sessionid", SESSION_ID, domain="store.steampowered.com")
    session.cookies.set("steamparental", STEAM_PARENTAL, domain="store.steampowered.com")

    # 3. Token von Steam abrufen
    access_token = None
    try:
        token_resp = session.get("https://store.steampowered.com/pointssummary/ajaxgetasyncconfig", timeout=10)
        
        try:
            data = token_resp.json()
            if "data" in data and "webapi_token" in data["data"]:
                access_token = data["data"]["webapi_token"]
            else:
                access_token = data.get("webapi_token")
        except Exception:
            send_notification(f"Kein JSON erhalten (Status {token_resp.status_code}). Ist ein Cookie abgelaufen?\nAntwort: {token_resp.text[:300]}", is_error=True)
            sys.exit(1)
        
        if not access_token:
            send_notification("Steam hat geantwortet, aber der WebAPI-Token fehlte.", is_error=True)
            sys.exit(1)
            
    except Exception as e:
        send_notification(f"Verbindungsfehler beim Token-Abruf von Steam: {e}", is_error=True)
        sys.exit(1)

    # 4. Den Protobuf-Payload als Multipart/Form-Data an Steam senden
    STEAM_URL = f"https://api.steampowered.com/IParentalService/SetParentalSettings/v1/?access_token={access_token}"

    multipart_data = {
        "input_protobuf_encoded": (None, aktiver_payload)
    }

    try:
        response = requests.post(STEAM_URL, files=multipart_data, timeout=10)
        
        if response.status_code == 200:
            send_notification(f"Das Profil '{profil_name}' wurde erfolgreich auf dem Steam Deck angewendet.", is_error=False)
        else:
            send_notification(f"Steam API lehnte die Anfrage ab.\nStatus: {response.status_code}\nAntwort: {response.text}", is_error=True)
    except Exception as e:
        send_notification(f"Verbindungsfehler beim Senden der Spielzeiten an Steam: {e}", is_error=True)
