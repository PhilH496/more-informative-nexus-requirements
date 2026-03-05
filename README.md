# More Informative Nexus Requirements

Utilizes the mo2 API bridge by AlhimikPh at https://www.nexusmods.com/skyrimspecialedition/mods/166125 to provide a more informative requirements tab

## Project Structure

- `extension/`
  - `content.js` - Main content script
  - `popup.html/js/css` - Extension popup interface
  - `styles.css` - Styles for status indicators on Nexus pages
  - `manifest.json` - Extension manifest
- `src/`
  - `__init__.py` - init mo2 plugin 
  - `bridge_client.py` - Client for connecting to MO2 bridge
  - `more_informative_nexus_requirements_server.py` - HTTP server on port 52526
  - `more_informative_nexus_requirements.py` - Functions to extract mod IDs from MO2

### Setup Steps

1. Drag the src folder to mo2's plugin folder
2. Load the extension in Chrome:
   - Open `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked"
   - Select the `extension/` folder

## Settings

- **Show Enabled Mods** - Displays "Enabled" status for mods that are enabled in MO2. When disabled, only shows "Installed" or "Not Installed" status.
- **Nexus Mods API Key** - Your Nexus Mods API key for checking tracked and endorsed mods. Get it from https://www.nexusmods.com/users/myaccount?tab=api. The API key is stored locally in your browser and is not sent to any server except Nexus.
- **Show Tracked Mods** - Displays a pin icon next to tracked mods. API key required. Disabled by default
- **Show Endorsed Mods** - Displays a thumbs up icon next to endorsed mods. API key required. Disabled by default

## Usage

Navigate to any Nexus Mods mod page that has a requirements section. The extension will display status indicators next to each required mod:
- Green ✓ with "Enabled" - Mod ID found and has enabled flag 
- Green ✓ with "Installed" - Mod ID found
- Red ✗ with "Not Installed" - Mod ID is missing 
- Pin icon - Mod is tracked on Nexus Mods
- Thumbs up icon - Mod is endorsed on Nexus Mods

## Notes

- Tested on Fo4, FNV, and SSE mo2 global instances. Feel free to try it on other games.
- After changing settings, you may need to reload the Nexus Mods page to see updated status indicators.
- Initial load can be a bit slow but will eventually persist and mod statuses will show instantly.
- The API key is stored locally in Chrome's storage and is not saved to any external server. Necessary to make requests to the Nexus Mods API.
- Mods can have duplicate ID's across different games. It is recommended you browse the nexus category of the game you have open in MO2 for the best results.
