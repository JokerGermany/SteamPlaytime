# SteamPlaytime
## KI-Warning
This was Vibe-coded because no capable human wrote it^^  
I used perplexity KI.  
The modell was  
Most Time Gemini 3.1 Pro  
Sometimes ChatGPT Pro.
## Dependencies
This was written for [Home Assistant](https://www.home-assistant.io), but HA is only used for the Notifications.
## Limitations
1. The script uses steamLoginSecure from the cookies of your webbrowser, which runs out every 5 weeks. Therefore you need to change the variable STEAM_LOGIN_SECURE. This is because Valve don't provide a official API.
2. I don't know how the script handles [when you don't have parental set](https://store.steampowered.com/parental/set).
## How to Fill the variables.
This is how to do it with Firefox, but you can ask the KI for other ways ;)
### STEAM_LOGIN_SECURE, SESSION_ID, STEAM_PARENTAL 
Switch in Firefox to https://store.steampowered.com/account/familymanagement, (Press Shift+F9), click under Cookies on https://store.steampowered.com . Copy everything from Value at steamLoginSecure/sessionid/steamparental
### HA_TOKEN
Click in HA on your Name, then on the Tab Security, then on create Token.
## What paramenters do the script Accept:
MILITARY TIME!  
Example:  
`python3 steam_playtime_week.py Su-Th 09:00 - 20:30 Fri-Sat 09:00 - 22:30`  
(Additional blocks can be added, e.g., `Su-Th 09:00 - 20:30 Fri 09:00 - 22:30 Sat 10:00 - 23:00`, as long as they are always in sets of three).  
[If you want to confuse people, you can also use German abbreviations for the days of the week.]  
## Home Assistant
### Where to save the script when using with HA
Somewhere in the HomeAssistant config folder.  
**DON'T SAVE THE SCRIPT TO python_scripts. SCRIPTS IN THIS FOLDER ARE RESTRICTED!**  
e.g. create a folder scripts. I will use scripts in this README!
### How to add the script to HA
you need to insert the following in the configuration.yaml:
```
shell_command:
  <chooseAUniqueName1: >
    python3 /config/scripts/steam_playtime_week.py Su-Th 09:00 20:30 Fr-Sa 09:00 22:30
```
With variables:
```
shell_command:
  steam_set_weekly_plan: >
    python3 /config/scripts/steam_playtime_week.py {{ states('input_text.kid_good_night_alarm_day_workingDays') }} {{ states('input_datetime.kid_good_night_alarm_heute_morgen')[:5] }} {{ states('input_datetime.kid_good_night_alarm_workingDays')[:5] }} {{ states('input_text.kid_good_night_alarm_day_notWorkingDays') }} {{ states('input_datetime.kid_good_night_alarm_morning')[:5] }} {{ states('input_datetime.kid_good_night_alarm_notWorkingDays')[:5] }}
```
### How to use in HA
https://www.home-assistant.io/integrations/shell_command#examples

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
