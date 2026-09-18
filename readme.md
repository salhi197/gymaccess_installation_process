# MyGym Installer

Windows GUI installer for the **MyGym Laravel Gym Management System**.
One `.exe`. Double-click. Done.

---

## What it does

A single-file Windows installer that sets up MyGym and everything it needs, with zero technical knowledge required from the end user.

The wizard:

1. **Verifies** the system (Windows x64, admin rights, disk space, source files)
2. **Asks in French** whether a **TRIPODE** is present:
   - **Oui** → disables firewall + sets Ethernet NIC to static IP `192.168.0.4`
   - **Non** → keeps `127.0.0.1` (localhost), no network changes
3. **Installs WampServer 3.3.0** silently (Apache + MySQL + PHP 7.4.33)
4. **Extracts MyGym** from `mygym.zip` into `C:\wamp64\www\mygym`
5. **Creates the `mygym` database**, imports `mygym.sql`, generates Laravel `APP_KEY`
6. **Sets WAMP services** (`wampmysqld64`, `wampapache64`) to start **Automatically**
7. **Registers the Laravel server** to start at user login (`shell:startup`), adds PHP to `PATH`, launches it immediately
8. **Creates desktop shortcuts**:
   - `Start MyGym` — server console
   - `TV` — opens `http://localhost:8000/gym/membre/default` in an Edge app window
   - `Gym Access` — opens `http://localhost:8000/gym` in an Edge app window

After installation the user reboots → everything runs automatically.

---

## Requirements

### To build

- **Python 3.10+** (Windows) — check **"Add Python to PATH"** during install
- **PyInstaller 6+** — `pip install pyinstaller`
- **Windows 10/11 x64**

### On the client machine

- **Windows 10 / 11 (x64)**
- **Administrator privileges** (installer self-elevates via UAC)
- **~3 GB free disk space**
- **Microsoft Edge** (pre-installed on Win10/11)

**No Python required on the client.** The EXE bundles the interpreter.

---

## Build

```bat
:: One-time: install PyInstaller
python -m pip install --upgrade pyinstaller

:: Build the EXE
python -m PyInstaller --onefile --windowed --uac-admin --name MyGymInstaller --clean installer.py
```

Output: `dist\MyGymInstaller.exe`

Or from a local script (if you prefer):

```bat
build.bat
```

---

## Ship to a client

Put these **4 files** in one folder:

```
📁 MyGymInstaller/
   ├── MyGymInstaller.exe         ← built above
   ├── wampserver3.3.0_x64.exe    ← WampServer installer
   ├── mygym.zip                  ← your Laravel app
   └── mygym.sql                  ← your database dump
```

**Client steps:**

1. Extract the folder
2. Double-click `MyGymInstaller.exe`
3. UAC prompt → **Yes**
4. Follow the wizard (~2 minutes)
5. Done — the server starts automatically.

> ⚠️ **Do not commit** `wampserver*.exe`, `mygym*.zip`, or `mygym*.sql` to git — they are large binaries. Ship them alongside the EXE, not through the repo.

---

## Configuration

All tunable values are at the top of `installer.py`:

```python
WAMP_DIR       = Path(r"C:\wamp64")
APP_DIR        = WAMP_DIR / "www" / "mygym"
DB_NAME        = "mygym"
DB_USER        = "root"
DB_PASSWORD    = ""

LOCAL_HOST     = "127.0.0.1"
TRIPODE_HOST   = "192.168.0.4"

PHP_DIR_OVERRIDE = Path(r"C:\wamp64\bin\php\php7.4.33")

ETHERNET_IP      = "192.168.0.4"
ETHERNET_MASK    = "255.255.255.0"
ETHERNET_GATEWAY = "192.168.0.1"
ETHERNET_DNS1    = "192.168.0.1"
ETHERNET_DNS2    = "8.8.8.8"

APP_BASE_URL = "http://localhost:8000"
TV_URL       = APP_BASE_URL + "/gym/membre/default"
GYM_URL      = APP_BASE_URL + "/gym"
```

Change any of these and rebuild.

---

## Troubleshooting

| Symptom                                            | Fix                                                                                                                           |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `No application encryption key has been specified` | The installer runs `php artisan key:generate` automatically; if it fails it writes a valid key directly. Reinstall if needed. |
| `php.exe not found`                                | Run `wampserver3.3.0_x64.exe` once manually, then re-run the installer.                                                       |
| `MySQL did not become ready`                       | Open the WampServer tray icon → start MySQL → re-run.                                                                         |
| Client gets "Windows protected your PC"            | Click **More info → Run anyway**. Or code-sign the EXE.                                                                       |
| Server runs but LAN can't reach it                 | Chose TRIPODE=Non during install. Reinstall and pick **Oui**.                                                                 |

---

## License

MIT — do whatever you want with it.
