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
2. The KI told me, that the [new unofficial API](https://steamapi.xpaw.me/IParentalService) can't be used. So at the moment you only can use presets in the Script and not flexible Change the times. I will try to find out if the KI is right...
3. I don't know how the script handles [when you don't have parental set](https://store.steampowered.com/parental/set).
## How to Fill the variables.
This is how to do it with Firefox, but you can ask the KI for other ways ;)
### STEAM_LOGIN_SECURE, SESSION_ID, STEAM_PARENTAL 
Switch in Firefox to https://store.steampowered.com/account/familymanagement, (Press Shift+F9), click under Cookies on https://store.steampowered.com. Kopie Everything from Value at steamLoginSecure/sessionid/steamparental
### HA_TOKEN
Click in HA on your Name, then on the Tab Security, then on create Token.
### Payloads
Switch to the Playtime of your kid on the Steam Homepage. Change the Time to your needs, Press CRTL+Shift+E, click on confirm on the Steam HomePage.
In the column method there will appear POST. Right click on it -> Copy Value -> Copy Post Data. You only need the Long string between  
```
------geckoformboundarya43bcd1dcf50c7b5ca8f18d3a404d80f
Content-Disposition: form-data; name="input_protobuf_encoded"
```
and
```
------geckoformboundarya43bcd1dcf50c7b5ca8f18d3a404d80f--
```
You can use as many payloads as you want, just add another
```
"<your-name-here>": "ENTER_YOUR_PAYLOAD_FOR_LOCKED_HERE",
```
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
    python3 /config/scripts/steam_playtime.py "<Payload-Name1>"
  <chooseAUniqueName2: >
    python3 /config/scripts/steam_playtime.py "<Payload-Name2>"
```
If you use the example, it could look like this:
```
shell_command:
  steam_set_normal: >
    python3 /config/scripts/steam_playtime.py "normal"
  steam_set_unrestricted: >
    python3 /config/scripts/steam_playtime.py "unrestricted"
  steam_set_locked: >
    python3 /config/scripts/steam_playtime.py "locked"
  steam_set_weekdays: >
    python3 /config/scripts/steam_playtime.py "weekdays"
  steam_set_weekend: >
    python3 /config/scripts/steam_playtime.py "weekend"
```
### How to use in HA
https://www.home-assistant.io/integrations/shell_command#examples
