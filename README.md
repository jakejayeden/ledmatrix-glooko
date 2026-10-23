# LEDMatrix Glooko

Unofficial Glooko display plugin for ChuckBuilds/LEDMatrix. It shows the newest glucose data currently available from Glooko, trend, glucose age, insulin-on-board (IOB), Omnipod 5 pump mode, and a compact glucose history graph.

> **Important:** Glooko data can be delayed or uploaded in batches. This plugin is an informational display only. Do not use it for dosing, alarms, or treatment decisions.

## Requirements

- LEDMatrix 3.8.x or later (developed on 3.8.7)
- Raspberry Pi OS / the system Python used by LEDMatrix
- Network access from the Pi to Glooko and GitHub
- A Glooko account

Python dependencies are declared in `requirements.txt`. LEDMatrix's plugin loader can install plugin dependencies automatically. The important dependency is the unofficial `glooko-reader` package from GitHub.

## Recommended installation: LEDMatrix Web UI

1. Open the LEDMatrix Web UI.
2. Open **Plugin Manager**.
3. Scroll to **Install from GitHub** → **Install Single Plugin**.
4. Paste this repository URL: `https://github.com/jakejayeden/ledmatrix-glooko`
5. For testing a release branch, enter the branch if the UI offers that field. For normal use, use the default `main` branch.
6. Confirm the unverified-plugin warning and install.
7. Restart the LEDMatrix display/service when prompted or from the Web UI.
8. Open the Glooko plugin configuration and enter the Glooko email/password plus display preferences.

The Glooko credentials are secrets. They should be stored by LEDMatrix locally in `config/config_secrets.json`; never commit them to this repository.

## Updating after GitHub installation

Once installed from this GitHub repository, normal updates should not require SCP or manually copying files. Publish the new plugin files/version to GitHub, then use **Plugin Manager → Update** (or **Check & Update All**) and restart the display.

## One-time Pi setup / dependency recovery

A normal Web UI installation should read `requirements.txt` and install the Python dependencies. If dependency installation fails, SSH to the Pi and use LEDMatrix's dependency installer:

```bash
ssh ledpi@ledpi
cd ~/LEDMatrix
sudo ./scripts/install_plugin_dependencies.sh
sudo systemctl restart ledmatrix
```

To verify the Glooko reader is importable by the same system Python LEDMatrix uses:

```bash
/usr/bin/python3 -c "from glooko import GlookoClient; print('glooko-reader OK')"
```

If you need to install only this plugin's requirements manually:

```bash
cd ~/LEDMatrix
sudo /usr/bin/python3 -m pip install --break-system-packages -r plugin-repos/glooko/requirements.txt
sudo systemctl restart ledmatrix
```

These SSH steps are intended as initial setup/recovery only; routine releases should be deployed through GitHub and the Web UI.

## Migrating the existing manually copied installation

Our original development copy was placed directly in `plugin-repos/glooko`. To put that installation under the normal GitHub/Web UI workflow:

1. Back up `config/config.json` and `config/config_secrets.json` on the Pi.
2. In **Plugin Manager → Install from GitHub**, install this repository using the same plugin ID (`glooko`). LEDMatrix supports replacing an existing copy with the repository version.
3. Restart the display.
4. Open Glooko configuration and confirm the existing settings and secrets are still present before deleting any backup.

## Settings

- **Glucose units:** mmol/L or mg/dL.
- **Refresh interval:** how often the plugin asks Glooko for current available data.
- **Stale after:** age at which the displayed CGM reading is visibly marked stale.
- **Graph history:** 3, 6, 12, or 24 hours. New installations default to 6 hours; an existing saved value is retained until changed.
- **Colourise graph:** optional range colouring. In mmol/L, <=3.9 is yellow, 4.0–9.9 is green, and >=10.0 is red. With the setting off, the graph is white.
- **Display duration:** time this mode remains on screen during rotation.

## v0.3.3

- Adds a selectable 3 / 6 / 12 / 24-hour graph-history setting.
- Uses 6 hours as the default for new installations.
- Exposes the Colourise graph option in the installable configuration schema.
- Keeps graph colours at <=3.9 yellow, 4.0–9.9 green, >=10.0 red.
- Fixes the trend arrow at a reserved x-position to avoid variable-width glucose text overlap.
- Documents GitHub/Web UI installation, updates, credentials, dependency installation and recovery.

## Troubleshooting

Check that the plugin files compile and inspect recent service logs:

```bash
cd ~/LEDMatrix
python3 -m py_compile plugin-repos/glooko/manager.py plugin-repos/glooko/glooko_provider.py
sudo systemctl restart ledmatrix
sleep 10
sudo journalctl -u ledmatrix --since "30 seconds ago" --no-pager -l | grep -iE "glooko|error|failed|traceback"
```

Avoid posting unredacted logs publicly: upstream Glooko-client logs may contain account or patient identifiers.

## Privacy and security

Do not commit `config.json`, `config_secrets.json`, credentials, exported Glooko data, logs containing identifiers, or captured health data. The repository should contain code, schemas and documentation only.
