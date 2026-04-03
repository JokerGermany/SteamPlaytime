import sys
import requests
import json
from datetime import datetime, timedelta

# ==========================================
# CONFIGURATION (ENTER YOUR VALUES HERE)
# ==========================================
STEAM_LOGIN_SECURE = "YOUR_STEAM_LOGIN_SECURE_COOKIE"
SESSION_ID = "YOUR_SESSION_ID"
STEAM_PARENTAL = "YOUR_STEAM_PARENTAL_COOKIE"
STEAM_ID_CHILD = "YOUR_CHILD_STEAM_ID"

# Home Assistant Connection
HA_URL = "http://127.0.0.1:58123"            # Your HA IP including port
HA_TOKEN = "YOUR_LONG_LIVED_ACCESS_TOKEN"    # Your Long-Lived Access Token
HA_NOTIFY_SERVICE = "notify/matrix_xxx"      # The notify service used

# Notification Settings
SUCCESS_MESSAGES = True   # True = Send success to HA / False = Send errors only

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def send_notification(message, is_error=False):
    """Sends error (and optionally success) messages to Home Assistant."""
    if not is_error and not SUCCESS_MESSAGES:
        return
    url = f"{HA_URL.rstrip('/')}/api/services/{HA_NOTIFY_SERVICE}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    formatted_message = f"⚠️ **Steam Error:**\n{message}" if is_error else f"✅ **Steam Update:**\n{message}"
    payload = {"message": formatted_message}
    
    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except Exception:
        pass

def time_to_bit(time_str):
    """Converts a time string like '11:30' into a Steam bit index."""
    hours, minutes = map(int, time_str.split(':'))
    return hours * 2 + (1 if minutes >= 30 else 0)

# ==========================================
# SCRIPT EXECUTION
# ==========================================
if __name__ == "__main__":
    # Check if start and end times were provided
    if len(sys.argv) < 3:
        send_notification("Start and end time are missing (e.g., '11:30' '23:00').", is_error=True)
        sys.exit(1)

    start_time = sys.argv[1]
    end_time = sys.argv[2]

    try:
        start_bit = time_to_bit(start_time)
        end_bit = time_to_bit(end_time)
    except Exception:
        send_notification(f"Invalid time format: {start_time} - {end_time}", is_error=True)
        sys.exit(1)

    # 1. Calculate the bitmask (Steam requires this as a string, not a float!)
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

    # Calculate expiration time (tomorrow at midnight)
    now = datetime.now()
    tomorrow_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    rtime_expires = int(tomorrow_midnight.timestamp())

    # 2. HTTP Session (Browser Spoofing)
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

    # 3. Retrieve WebAPI Token
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
            send_notification("Could not generate a WebAPI token. Is the cookie expired?", is_error=True)
            sys.exit(1)
    except Exception as e:
        send_notification(f"Error fetching token: {e}", is_error=True)
        sys.exit(1)

    # 4. Read the child's current parental settings
    get_url = f"https://api.steampowered.com/IParentalService/GetParentalSettings/v1/?access_token={access_token}&steamid={STEAM_ID_CHILD}"
    try:
        get_resp = session.get(get_url, timeout=10)
        if get_resp.status_code != 200:
            send_notification(f"Could not retrieve settings (Status {get_resp.status_code}).", is_error=True)
            sys.exit(1)
        
        current_settings = get_resp.json().get("response", {}).get("settings")
        if not current_settings:
            send_notification("JSON did not contain a 'settings' field.", is_error=True)
            sys.exit(1)
    except Exception as e:
        send_notification(f"Network error retrieving settings: {e}", is_error=True)
        sys.exit(1)

    # 5. Modify settings (Inject temporary playtime)
    current_settings["temporary_playtime_restrictions"] = {
        "restrictions": {
            "allowed_time_windows": mask_str,
            "allowed_daily_minutes": 1440
        },
        "rtime_expires": rtime_expires
    }

    # 6. Upload and save settings as parent (Overwrite)
    set_url = f"https://api.steampowered.com/IParentalService/SetParentalSettings/v1/?access_token={access_token}"
    set_payload = {
        "steamid": STEAM_ID_CHILD,
        "settings": current_settings
    }

    try:
        set_resp = requests.post(set_url, data={"input_json": json.dumps(set_payload)}, timeout=10)
        if set_resp.status_code == 200:
            send_notification(f"Temporary time window for today ({start_time} - {end_time}) successfully set!")
            print(f"Success: {start_time}-{end_time} has been set.")
        else:
            send_notification(f"SetParentalSettings rejected (Status {set_resp.status_code}): {set_resp.text}", is_error=True)
    except Exception as e:
        send_notification(f"Network error saving settings: {e}", is_error=True)
