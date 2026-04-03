import sys
import requests
import json

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
    
    formatted_message = f"⚠️ **Steam Script Error:**\n{message}" if is_error else f"✅ **Steam Weekly Schedule:**\n{message}"
    payload = {"message": formatted_message}
    
    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except Exception:
        pass

def parse_days(day_str):
    """
    Parses strings like 'Su-Th', 'Mo-Fr', 'We,Fr' into Steam index numbers (0=Su, 1=Mo... 6=Sa).
    Supports both English (Mo,Tu,We,Th,Fr,Sa,Su) and German (Mo,Di,Mi,Do,Fr,Sa,So) abbreviations.
    """
    days_order = ["mo", "tu", "we", "th", "fr", "sa", "su"]
    steam_map = {"mo": 1, "tu": 2, "we": 3, "th": 4, "fr": 5, "sa": 6, "su": 0}
    
    # Dictionary to map both EN and DE input strings to the internal standard
    alias_map = {
        "mo": "mo", "tu": "tu", "di": "tu", "we": "we", "mi": "we",
        "th": "th", "do": "th", "fr": "fr", "sa": "sa", "su": "su", "so": "su"
    }
    
    result = set()
    parts = day_str.split(',')
    
    for part in parts:
        if '-' in part:
            start_s, end_s = part.split('-')
            start_clean = start_s.lower()[:2]
            end_clean = end_s.lower()[:2]
            
            if start_clean not in alias_map or end_clean not in alias_map:
                raise ValueError(f"Unknown day abbreviation in: {part}")
                
            idx_start = days_order.index(alias_map[start_clean])
            idx_end = days_order.index(alias_map[end_clean])
            
            # Regular range (e.g., Mo-Fr)
            if idx_start <= idx_end:
                for i in range(idx_start, idx_end + 1):
                    result.add(steam_map[days_order[i]])
            # Range over the weekend (e.g., Fr-Su)
            else:
                for i in range(idx_start, 7):
                    result.add(steam_map[days_order[i]])
                for i in range(0, idx_end + 1):
                    result.add(steam_map[days_order[i]])
        else:
            part_clean = part.lower()[:2]
            if part_clean not in alias_map:
                raise ValueError(f"Unknown day abbreviation: {part}")
            result.add(steam_map[alias_map[part_clean]])
                
    return result

def calculate_mask(start_time, end_time):
    """Calculates the Steam bitmask string for a given start and end time."""
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
# SCRIPT EXECUTION
# ==========================================
if __name__ == "__main__":
    
    args = sys.argv[1:]
    # Clean up any accidental semicolons passed from bash commands
    args = [a.replace(';', '') for a in args if a.replace(';', '') != '']

    # Arguments must be provided in blocks of 3 (Days StartTime EndTime)
    if len(args) % 3 != 0 or len(args) == 0:
        send_notification("Invalid number of arguments. Expected in groups of three: Days Start End.\nExample: `Su-Th 09:00 20:30 Fr-Sa 09:00 22:30`", is_error=True)
        sys.exit(1)

    # Read the rules into a list
    rules = []
    for i in range(0, len(args), 3):
        rules.append((args[i], args[i+1], args[i+2]))

    # Prepare a default weekly plan with everything restricted/blocked
    week_plan = [{"allowed_time_windows": "0", "allowed_daily_minutes": 1440} for _ in range(7)]

    # Apply rules to the weekly plan
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
        send_notification(f"Error parsing days or times: {e}", is_error=True)
        sys.exit(1)

    # Prepare HTTP session (Browser Spoofing)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    })
    session.cookies.set("steamLoginSecure", STEAM_LOGIN_SECURE, domain="store.steampowered.com")
    session.cookies.set("sessionid", SESSION_ID, domain="store.steampowered.com")
    session.cookies.set("steamparental", STEAM_PARENTAL, domain="store.steampowered.com")

    # 1. Retrieve WebAPI Token
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

    # 2. Retrieve the child's current parental settings
    get_url = f"https://api.steampowered.com/IParentalService/GetParentalSettings/v1/?access_token={access_token}&steamid={STEAM_ID_CHILD}"
    try:
        get_resp = session.get(get_url, timeout=10)
        current_settings = get_resp.json().get("response", {}).get("settings")
        if not current_settings:
            send_notification("Could not read current Steam settings.", is_error=True)
            sys.exit(1)
    except Exception as e:
        send_notification(f"Network error retrieving settings: {e}", is_error=True)
        sys.exit(1)

    # 3. Overwrite the playtime restrictions block
    if "playtime_restrictions" not in current_settings:
        current_settings["playtime_restrictions"] = {}
    
    current_settings["playtime_restrictions"]["apply_playtime_restrictions"] = True
    current_settings["playtime_restrictions"]["playtime_days"] = week_plan

    # 4. Upload and save the modified settings to Steam
    set_url = f"https://api.steampowered.com/IParentalService/SetParentalSettings/v1/?access_token={access_token}"
    set_payload = {
        "steamid": STEAM_ID_CHILD,
        "settings": current_settings
    }

    try:
        set_resp = requests.post(set_url, data={"input_json": json.dumps(set_payload)}, timeout=10)
        if set_resp.status_code == 200:
            msg = "The following weekly schedule has been set:\n"
            for day_str, start_time, end_time in rules:
                msg += f"• **{day_str}**: {start_time} - {end_time}\n"
            msg += "\n*(Days not specified are restricted)*"
            
            send_notification(msg)
            print("Success: Weekly schedule saved.")
        else:
            send_notification(f"SetParentalSettings rejected (Status {set_resp.status_code}): {set_resp.text}", is_error=True)
    except Exception as e:
        send_notification(f"Network error saving settings: {e}", is_error=True)
