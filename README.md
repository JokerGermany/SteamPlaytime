# Steam Parental Controls with Home Assistant, Podman, and Browser Cookie Login

This guide explains how to set up a beginner-friendly Steam cookie login flow with:

- **Podman**
- **systemd**
- **a browser inside a container**
- **Home Assistant shell commands**
- **local Python scripts**

The goal is simple:

1. Start a container with a browser.
2. Log in to Steam in that browser.
3. Export the Steam cookies to a JSON file.
4. Let Home Assistant scripts read that file.
5. Use those cookies to call Steam parental control endpoints.

This setup also works when `steamparental` is not present.  
If Family View is enabled, the scripts will use `steamparental` automatically when available.

# KI-Warning
This was Vibe-coded because no capable human wrote it^^  
I used perplexity KI.  
The modell was  
Gemini 3.1 Pro  
ChatGPT 5.4 Pro.
# Dependencies
- git
- podman
- systemd
This was written for [Home Assistant](https://www.home-assistant.io), but HA is only used for the Notifications.

# 1. What this setup does

You will run a container that opens a browser in the background.

You connect to that browser using your web browser through noVNC.

After logging in to Steam once, the container writes a file called:

```text
/config/steam-auth/steam-state.json
```

Your Home Assistant Python scripts then read that cookie file and use it for Steam API calls.

---
# 2. Folder layout

This guide assumes the following host paths:

```text
/mnt/smarthome/HAFamilyLink
/mnt/smarthome/homeassistant/config
```
# 3. Requirements

Install these first on your Linux host:

- `git`
- `podman`
- `systemd`
- a text editor like `nano`

Example on Debian/Ubuntu:

```bash
sudo apt update
sudo apt install -y git podman
```

If `systemctl` works on your system, systemd is already available.

Check Podman:

```bash
podman --version
```

---

# 4. Clone the repository

Clone my modified HAFamilyLink repository:

```bash
cd /mnt/smarthome
git clone https://github.com/JokerGermany/HAFamilyLink
```

# 5. Create the systemd service

Create a systemd service file for the Podman container.

**Path:**
```text
/etc/systemd/system/container-familylink-auth.service
```

Open it:

```bash
sudo nano /etc/systemd/system/container-familylink-auth.service
```

Paste this example:

```ini
[Unit]
Description=Podman container-familylink-auth.service
Documentation=man:podman-generate-systemd(1)
Wants=network-online.target
After=network-online.target
RequiresMountsFor=%t/containers

[Service]
Environment=PODMAN_SYSTEMD_UNIT=%n
Restart=always
TimeoutStopSec=70
ExecStart=/usr/bin/podman run \
	--cidfile=%t/%n.ctr-id \
	--cgroups=no-conmon \
	--rm \
	--sdnotify=conmon \
	--replace \
	-d \
	--name familylink-auth \
	-p 8099:8099 \
	-p 6080:6080 \
	-v /mnt/smarthome/familylink-auth:/share/familylink:rw \
	-v /mnt/smarthome/homeassistant/config/steam-auth:/share/steam-auth:rw \
	-v /mnt/smarthome/HAFamilyLink/familylink-playwright/app:/app/app:rw \
	-e LOG_LEVEL=info \
	-e AUTH_TIMEOUT=300 \
	-e SESSION_DURATION=86400 \
	-e VNC_PASSWORD=familylink \
	-e STEAM_ENABLED=true \
	-e STEAM_PROFILE_DIR=/share/steam-auth/profile \
	-e STEAM_STATE_FILE=/share/steam-auth/steam-state.json \
	-e STEAM_LOGIN_TIMEOUT=300 \
	-e STEAM_REQUIRE_PARENTAL=false \
	--health-cmd CMD,curl,-f,http://localhost:8099/api/health \
	--health-interval 30s \
	--health-retries 3 \
	--health-start-period 30s \
	--health-timeout 10s \
	ghcr.io/noiwid/familylink-auth:standalone
ExecStop=/usr/bin/podman stop \
	--ignore -t 10 \
	--cidfile=%t/%n.ctr-id
ExecStopPost=/usr/bin/podman rm \
	-f \
	--ignore -t 10 \
	--cidfile=%t/%n.ctr-id
Type=notify
NotifyAccess=all

[Install]
WantedBy=default.target

## Important

If you use Family View PIN unlock, change:

```ini
-e STEAM_REQUIRE_PARENTAL=false \
```

to:

```ini
-e STEAM_REQUIRE_PARENTAL=true \
```

---

# 6. Reload and start the service

Run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable container-familylink-auth.service
sudo systemctl restart container-familylink-auth.service
sudo systemctl status container-familylink-auth.service
```

If the service fails, check logs:

```bash
journalctl -u container-familylink-auth.service -n 100 --no-pager
podman logs familylink-auth --tail 100
```

---

# 7. Test the container

Check the API:

```bash
curl http://127.0.0.1:8099/api/health
curl http://127.0.0.1:8099/api/steam/health
```

Open the browser session in noVNC:

```text
http://YOUR-SERVER-IP:6080/vnc.html
```

Trigger Steam login:

```bash
curl -X POST http://127.0.0.1:8099/api/steam/login
```

Now log in to Steam in the browser.

If Family View is enabled and you require it, also enter the Family View PIN.

After a successful login, the browser should close and the cookie file should exist:

```bash
ls -lah /mnt/smarthome/homeassistant/config/steam-auth
cat /mnt/smarthome/homeassistant/config/steam-auth/steam-state.json | head
```
# How to Fill the variables.
This is how to do it with Firefox, but you can ask the KI for other ways ;)
## CHILD_STEAM_ID
Go to https://store.steampowered.com/account/familymanagement => click on your childs account => parental controls
Now look at the adressbar it should look like this
https://store.steampowered.com/account/familymanagement/parentalcontrols/<CHILD_STEAM_ID>

## HA_TOKEN
Click in HA on your Name, then on the Tab Security, then on create Token.
# Home Assistant
## Where to save the script when using with HA
Somewhere in the HomeAssistant config folder.  
**DON'T SAVE THE SCRIPT TO python_scripts. SCRIPTS IN THIS FOLDER ARE RESTRICTED!**  
e.g. create a folder scripts. I will use scripts in this README!
## How to use in HA
https://www.home-assistant.io/integrations/shell_command#examples
# steam_playtime_week.py
## What paramenters do the script Accept:
MILITARY TIME!  
Example:  
`python3 steam_playtime_week.py Su-Th 09:00 - 20:30 Fri-Sat 09:00 - 22:30`  
(Additional blocks can be added, e.g., `Su-Th 09:00 - 20:30 Fri 09:00 - 22:30 Sat 10:00 - 23:00`, as long as they are always in sets of three).  
[If you want to confuse people, you can also use German abbreviations for the days of the week.]  
## Home Assistant
### How to add the script to HA
you need to insert the following in the configuration.yaml:
```
shell_command:
  <chooseAUniqueName1>:
    python3 /config/scripts/steam_playtime_week.py Su-Th 09:00 20:30 Fr-Sa 09:00 22:30
```
With variables:
```
shell_command:
  steam_set_locked: Mo-Su 00:00 00:00
  steam_set_weekly_plan: >
    python3 /config/scripts/steam_playtime_week.py {{ states('input_text.kid_good_night_alarm_day_workingDays') }} {{ states('input_datetime.kid_good_night_alarm_heute_morgen')[:5] }} {{ states('input_datetime.kid_good_night_alarm_workingDays')[:5] }} {{ states('input_text.kid_good_night_alarm_day_notWorkingDays') }} {{ states('input_datetime.kid_good_night_alarm_morning')[:5] }} {{ states('input_datetime.kid_good_night_alarm_notWorkingDays')[:5] }}
```
### Example Automation in HA
If one of the variables is changed it will trigger and set the schedule in Steam
```
alias: kid Weekly Game schedule
description: ""
triggers:
  - trigger: state
    entity_id:
      - input_text.kid_good_night_alarm_day_notWorkingDays
      - input_text.kid_good_night_alarm_day_workingDays
      - input_datetime.kid_good_night_alarm_morning
      - input_datetime.kid_good_night_alarm_notWorkingDays
      - input_datetime.kid_good_night_alarm_workingDays
    for:
      hours: 0
      minutes: 5
      seconds: 0
conditions: []
actions:
  - action: shell_command.steam_set_weekly_plan
    data: {}
mode: single
```
# steam_playtime_today.py 
Only overwrites the time for today.
(This cannot be verified in the web interface or the Steam app!)
## What paramenters do the script Accept:
MILITARY TIME!  
Example:  
`python3 steam_playtime_today.py HH:MM HH:MM 
## Home Assistant
### How to add the script to HA
you need to insert the following in the configuration.yaml:
```
shell_command:
  <chooseAUniqueName1>: 
    python3 /config/scripts/steam_playtime_today.py HH:MM HH:MM
```
With variables:
```
shell_command:
  steam_set_today: >
    python3 /config/scripts/steam_playtime_today.py {{ states('input_datetime.kid_good_night_alarm_today_morning')[:5] }} {{ states('input_datetime.kid_good_night_alarm_today_evening')[:5] }}
```
### Example Automation in HA
If one of the variables is changed it will trigger and set the schedule in Steam
```
alias: Kid - Good Night Alarm Today has changed
description: ""
triggers:
  - trigger: state
    entity_id:
      - input_datetime.kid_good_night_alarm_today_evening
      - input_datetime.kid_good_night_alarm_today_morning
    for:
      hours: 0
      minutes: 5
      seconds: 0
conditions: []
actions:
  - variables:
      target_time: >
        {% set days = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'] %}
        {% set today_idx = now().weekday() %}

        {% set w_text = states('input_text.kid_good_night_alarm_day_WorkingDays') %}
        {% set parts = w_text.split('-') %}
        {% set p0 = parts[0] | trim %}
        {% set p1 = (parts[1] | trim) if parts | length > 1 else p0 %}

        {% set start_idx = days.index(p0) if p0 in days else -1 %}
        {% set end_idx = days.index(p1) if p1 in days else start_idx %}

        {% set is_w = (start_idx <= today_idx <= end_idx) if (start_idx <= end_idx) else (today_idx >= start_idx or today_idx <= end_idx) %}
        {% set is_werktags = is_w if start_idx != -1 else false %}

        {{ states('input_datetime.kid_good_night_alarm_WorkingDays') if is_werktags else states('input_datetime.kid_good_night_alarm_WorkingDays') }}

      current_time: "{{ states('input_datetime.kid_good_night_alarm_today_evening') }}"

  - condition: template
    value_template: "{{ target_time[:5] != current_time[:5] }}"
  - service: shell_command.steam_set_today
mode: single
```
## Credits
Thanks to [@xPaw](https://xpaw.me/) for [publishing the undocumented API](https://steamapi.xpaw.me/IParentalService)!
