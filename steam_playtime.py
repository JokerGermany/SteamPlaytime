import sys
import requests

# ==========================================
# CONFIGURATION (ENTER YOUR VALUES HERE)
# ==========================================
STEAM_LOGIN_SECURE = "YOUR_STEAM_LOGIN_SECURE_COOKIE"
SESSION_ID = "YOUR_SESSION_ID"
STEAM_PARENTAL = "YOUR_STEAM_PARENTAL_COOKIE"

# Home Assistant Connection
HA_URL = "http://127.0.0.1:58123"            # Your HA IP including port
HA_TOKEN = "YOUR_LONG_LIVED_ACCESS_TOKEN"     # Your HA Long-Lived Access Token
HA_NOTIFY_SERVICE = "notify/matrix_xxx"  # The HA notify service to use

# Notification Control
SUCCESS_MESSAGES = True   # True = send success messages to HA / False = send errors only

# ==========================================
# PAYLOAD PROFILES (ENTER BASE64 STRINGS)
# ==========================================
PAYLOADS = {
    "normal": "ENTER_YOUR_PAYLOAD_FOR_LOCKED_HERE",
    "unrestricted": "ENTER_YOUR_PAYLOAD_FOR_LOCKED_HERE",
    "locked": "ENTER_YOUR_PAYLOAD_FOR_LOCKED_HERE",
    "weekdays": "ENTER_YOUR_PAYLOAD_FOR_WEEKDAYS_HERE",
    "weekend": "ENTER_YOUR_PAYLOAD_FOR_WEEKENDS_HERE",
}

# ==========================================
# NOTIFICATION FUNCTION
# ==========================================
def send_notification(message, is_error=False):
    """Sends error (and optionally success) messages to HA."""
    # If it's a success message but SUCCESS_MESSAGES is False, exit quietly.
    if not is_error and not SUCCESS_MESSAGES:
        return

    url = f"{HA_URL.rstrip('/')}/api/services/{HA_NOTIFY_SERVICE}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    if is_error:
        formatted_message = f"⚠️ **Steam Family Script Error:**\n{message}"
    else:
        formatted_message = f"✅ **Steam Family Script:**\n{message}"
        
    payload = {"message": formatted_message}
    
    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except Exception as e:
        print(f"Critical Error: Could not reach {HA_NOTIFY_SERVICE}. Reason: {e}")

# ==========================================
# SCRIPT START
# ==========================================
if __name__ == "__main__":
    # 1. Read desired profile from arguments
    if len(sys.argv) < 2:
        send_notification("No profile name (e.g., 'weekdays') was provided as an argument.", is_error=True)
        sys.exit(1)

    profile_name = sys.argv[1].lower()

    if profile_name not in PAYLOADS:
        send_notification(f"The profile '{profile_name}' does not exist in the script.", is_error=True)
        sys.exit(1)

    active_payload = PAYLOADS[profile_name]

    if active_payload.startswith("ENTER_YOUR_PAYLOAD"):
        send_notification(f"The payload for profile '{profile_name}' has not been configured yet.", is_error=True)
        sys.exit(1)

    # 2. Prepare HTTP Session for Steam (Browser spoofing)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty"
    })

    # Set cookies
    session.cookies.set("steamLoginSecure", STEAM_LOGIN_SECURE, domain="store.steampowered.com")
    session.cookies.set("sessionid", SESSION_ID, domain="store.steampowered.com")
    session.cookies.set("steamparental", STEAM_PARENTAL, domain="store.steampowered.com")

    # 3. Retrieve Steam WebAPI Token
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
            send_notification(f"Did not receive JSON (Status {token_resp.status_code}). Is a cookie expired?\nResponse: {token_resp.text[:300]}", is_error=True)
            sys.exit(1)
        
        if not access_token:
            send_notification("Steam responded, but the WebAPI token was missing.", is_error=True)
            sys.exit(1)
            
    except Exception as e:
        send_notification(f"Connection error while retrieving Steam token: {e}", is_error=True)
        sys.exit(1)

    # 4. Send the protobuf payload to Steam as multipart/form-data
    STEAM_URL = f"https://api.steampowered.com/IParentalService/SetParentalSettings/v1/?access_token={access_token}"

    multipart_data = {
        "input_protobuf_encoded": (None, active_payload)
    }

    try:
        response = requests.post(STEAM_URL, files=multipart_data, timeout=10)
        
        if response.status_code == 200:
            send_notification(f"The profile '{profile_name}' was successfully applied to the Steam account.", is_error=False)
        else:
            send_notification(f"Steam API rejected the request.\nStatus: {response.status_code}\nResponse: {response.text}", is_error=True)
    except Exception as e:
        send_notification(f"Connection error while sending playtime restrictions to Steam: {e}", is_error=True)
