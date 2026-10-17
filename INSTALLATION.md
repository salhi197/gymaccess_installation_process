# MyGym — Installation Guide

**For the person installing MyGym on a Windows PC.**

This guide walks you through installing the MyGym gym management system and everything it needs, in about 5 minutes. No technical knowledge required.

---

## 📋 Table of Contents

- [What you need](#-what-you-need)
- [Before you start](#-before-you-start)
- [Step-by-step installation](#-step-by-step-installation)
- [What gets installed](#-what-gets-installed)
- [After installation](#-after-installation)
- [Using MyGym day-to-day](#-using-mygym-day-to-day)
- [Troubleshooting](#-troubleshooting)
- [Uninstalling](#-uninstalling)

---

## 🧰 What you need

| Item                     | Details                                                                         |
| ------------------------ | ------------------------------------------------------------------------------- |
| **Computer**             | Windows 10 or Windows 11 (64-bit)                                               |
| **Privileges**           | Administrator account on this PC                                                |
| **Disk space**           | At least 3 GB free on `C:`                                                      |
| **Internet**             | Not required after the initial setup — everything is on the installation folder |
| **The installer folder** | Given to you by your supplier (USB, download link, or network share)            |

The installer folder contains these 4 files:

```
📁 MyGymInstaller/
   ├── MyGymInstaller.exe         ← the installer program
   ├── wampserver3.3.0_x64.exe    ← the web server package
   ├── mygym.zip                  ← the MyGym application
   └── mygym.sql                  ← the database
```

**Do not rename, move, or delete any of these files** before running the installer.

---

## ⚠️ Before you start

1. **Save your work.** The installer will briefly change your network settings — if the PC is on Wi-Fi, it stays connected, but any active download may pause.
2. **Close other installers.** Make sure Windows Update or any other setup wizard is not running.
3. **If you are remote (RDP / AnyDesk / TeamViewer):** Ask someone to be near the PC, or run the install locally. Setting a static IP (only when a **TRIPODE** is detected) will disconnect your remote session.
4. **Antivirus:** Some antivirus tools flag `.exe` files that are not code-signed. If Windows Defender or your AV shows a warning, choose **"Run anyway"** or **"Allow"**.

---

## 🚀 Step-by-step installation

### Step 1 — Extract the installer folder

1. Copy the `MyGymInstaller` folder to the **Desktop** of the target PC.
2. Do **not** run the installer from inside a ZIP or USB drive — extract it first.

### Step 2 — Run the installer as Administrator

1. Right-click **`MyGymInstaller.exe`**
2. Choose **"Run as administrator"**
3. Windows will ask: _"Do you want to allow this app to make changes to your device?"_ → click **Yes**

> If the installer starts without asking for admin rights, it will auto-elevate and ask you again. That is normal.

### Step 3 — Welcome screen

You will see a wizard-style window titled **MyGym Installer** with a step list on the left:

```
1. Welcome
2. System Check
3. Network & Firewall
4. WampServer
5. MyGym Files
6. Database
7. Services & Startup
8. Complete
```

Click **Next >** to continue.

### Step 4 — System Check

The installer verifies that:

- Windows is 64-bit ✔
- You have Administrator rights ✔
- You have at least 3 GB of free disk space ✔
- The 3 source files (`wampserver3.3.0_x64.exe`, `mygym.zip`, `mygym.sql`) are present ✔

If anything is missing, the installer tells you exactly which file and where it expects to find it. Fix the problem, then click **Next >** again.

### Step 5 — TRIPODE question (Network & Firewall)

A dialog appears in French:

> **Avez-vous un TRIPODE connecté à cette machine ?**

Two buttons:

| Button                 | Meaning                           | What happens                                      |
| ---------------------- | --------------------------------- | ------------------------------------------------- |
| **Oui (avec TRIPODE)** | A TRIPODE device **is** connected | Firewall disabled + Ethernet set to `192.168.0.4` |
| **Non (sans TRIPODE)** | No TRIPODE                        | Keeps `127.0.0.1` (localhost), nothing changes    |

**Choose according to your setup:**

- Choose **Oui** if the gym has a **TRIPODE** device (turnstile / access control) that needs to reach MyGym over the local network.
- Choose **Non** if MyGym will only be used on this single PC.

Click the appropriate button. The installer runs the network step automatically.

> ⚠️ **If you choose Oui:** The Ethernet port on this PC will be set to a static IP `192.168.0.4`. Make sure no other device on the network already uses that IP. If you are unsure, choose **Non** and contact your supplier.

### Step 6 — WampServer installation

The installer silently installs **WampServer 3.3.0** (Apache + MySQL + PHP 7.4.33) into `C:\wamp64`.

This takes **1–2 minutes**. The progress bar shows progress. Do **not** close the window.

When done, the log shows `WampServer ready.`

### Step 7 — MyGym Files

The installer copies and extracts `mygym.zip` into:

```
C:\wamp64\www\mygym
```

This takes **10–30 seconds**.

### Step 8 — Database

The installer:

1. Creates the database `mygym` in MySQL
2. Imports your data from `mygym.sql`
3. Writes the Laravel `.env` configuration
4. Generates the Laravel **application encryption key**

This takes **30–60 seconds**.

### Step 9 — Services & Startup

The installer:

- Sets WAMP services (`wampapache64`, `wampmysqld64`) to **start automatically** every time Windows boots
- Adds PHP to the system `PATH`
- Creates `C:\wamp64\www\mygym\startup\start-server.bat`
- Registers the server to **auto-start at every login**
- Creates a **Start MyGym** shortcut on the Desktop
- **Starts the server immediately** in a new console window

At this point, MyGym is running.

### Step 10 — Complete

The installer shows a summary and creates two more Desktop shortcuts:

- **TV** — opens the member display page
- **Gym Access** — opens the access control page

Click **Finish**. Your browser opens automatically at `http://127.0.0.1:8000` (or `http://192.168.0.4:8000` if TRIPODE was chosen).

Installation is complete. ✔

---

## 📦 What gets installed

| Component                         | Location                                       |
| --------------------------------- | ---------------------------------------------- |
| WampServer (Apache + MySQL + PHP) | `C:\wamp64`                                    |
| MyGym application                 | `C:\wamp64\www\mygym`                          |
| Database                          | MySQL database `mygym`                         |
| Startup script                    | `C:\wamp64\www\mygym\startup\start-server.bat` |
| Auto-start entry                  | `shell:startup\MyGym-Server.bat`               |
| Desktop shortcuts                 | `Start MyGym`, `TV`, `Gym Access`              |
| Windows services                  | `wampapache64`, `wampmysqld64` (Automatic)     |

---

## ✅ After installation

### Verify everything is running

Open a Command Prompt and run:

```cmd
sc query wampapache64
sc query wampmysqld64
```

Both should say **`STATE : 4 RUNNING`**.

Check that the server is responding:

```cmd
curl http://127.0.0.1:8000
```

You should see HTML output.

### Test the shortcuts

Double-click each shortcut on the Desktop:

- **Start MyGym** — opens a black console window running the Laravel server. **Keep this window open while using MyGym.**
- **TV** — opens the member display in a clean app window (no browser tabs, no address bar)
- **Gym Access** — opens the access control page

### Test auto-start

1. Restart the PC (Start → Restart)
2. Log in as the same user
3. Within ~30 seconds, a **MyGym - Laravel Dev Server** window should appear automatically
4. Wait 5–10 seconds, then open **TV** — the member display loads

If the window does **not** appear, see [Troubleshooting](#-troubleshooting).

---

## 🖥 Using MyGym day-to-day

**You do not need to do anything.** After a normal reboot:

1. Windows starts the WAMP services automatically
2. Your login triggers the `MyGym-Server.bat` script in the Startup folder
3. The Laravel server starts on port 8000
4. The Desktop shortcuts work immediately

### To start MyGym manually

If the auto-start did not run (e.g., you logged in too fast), just double-click **Start MyGym** on the Desktop.

### To stop MyGym

Close the black **MyGym - Laravel Dev Server** console window (the X button or `Ctrl+C`).

### To restart MyGym

Close the console window, then double-click **Start MyGym** again.

### To access from another PC on the same network

If you chose **Oui (avec TRIPODE)**, other devices can reach MyGym at:

```
http://192.168.0.4:8000
```

If you chose **Non**, only this PC can access MyGym.

---

## 🛠 Troubleshooting

### "Windows protected your PC" (SmartScreen warning)

**Cause:** The installer is not code-signed.

**Fix:**

1. Click **More info**
2. Click **Run anyway**

### Error: "No application encryption key has been specified"

**Cause:** The Laravel `APP_KEY` was not generated during install.

**Fix:**

1. Open a Command Prompt **as Administrator**
2. Run:
   ```cmd
   cd /d C:\wamp64\www\mygym
   C:\wamp64\bin\php\php7.4.33\php.exe artisan key:generate
   ```
3. Close the MyGym server window and re-open **Start MyGym** from the Desktop.

### Error: "php.exe not found"

**Cause:** WampServer did not install correctly.

**Fix:**

1. Run `wampserver3.3.0_x64.exe` manually (double-click it)
2. Complete the WampServer setup wizard
3. Re-run `MyGymInstaller.exe`

### The server window flashes and closes immediately

**Cause:** Usually a missing PHP extension or a corrupted install.

**Fix:**

1. Open **Start MyGym** from the Desktop
2. Read the error message in the console
3. Take a screenshot and send it to your supplier

### MySQL did not become ready in time

**Cause:** The MySQL service did not start.

**Fix:**

1. Look at the WampServer icon in the system tray (bottom-right of the screen)
2. If it's orange or red, right-click it → **MySQL → Service → Start/Resume service**
3. Wait until the icon turns **green**
4. Open **Start MyGym** from the Desktop

### The Desktop shortcuts don't open anything

**Cause:** The Laravel server is not running.

**Fix:**

1. Double-click **Start MyGym**
2. Wait 10 seconds
3. Try **TV** or **Gym Access** again

### The gym's TRIPODE cannot reach MyGym

**Cause:** Firewall is blocking, or you chose **Non** during setup.

**Fix:**

1. Re-run the installer and choose **Oui**
2. Or manually run in an Administrator Command Prompt:
   ```cmd
   netsh advfirewall set allprofiles state off
   ```

### I chose the wrong TRIPODE answer

**Fix:** Re-run `MyGymInstaller.exe`. The installer will re-apply the network settings based on your new choice.

### Everything stopped working after a Windows update

**Fix:**

1. Restart the PC
2. If still broken, double-click **Start MyGym** manually
3. If it still fails, run `MyGymInstaller.exe` again — it is safe to re-run

---

## 🗑 Uninstalling

There is currently no automatic uninstaller. To remove MyGym manually:

1. **Stop the server** — close the _MyGym - Laravel Dev Server_ console window
2. **Remove auto-start** — press `Win + R`, type `shell:startup`, press Enter, delete `MyGym-Server.bat`
3. **Remove Desktop shortcuts** — delete _Start MyGym_, _TV_, _Gym Access_
4. **Remove the application** — delete the folder `C:\wamp64\www\mygym`
5. **Remove the database** (optional) — open `C:\wamp64\bin\mysql\mysql8.x.x\bin\mysql.exe` and run:
   ```sql
   DROP DATABASE mygym;
   ```
6. **Remove WampServer** (optional) — Control Panel → **Programs and Features** → uninstall WampServer

> ⚠️ **Before deleting**, back up any data you want to keep: the folder `C:\wamp64\www\mygym\storage\app` and the SQL file `mygym.sql`.

---

## 📞 Need help?

Contact your MyGym supplier with:

1. A description of the problem
2. A screenshot of the installer window (if possible)
3. The last few lines from the **MyGym - Laravel Dev Server** console window

Include this information if you can:

- Windows version (`Win + R` → `winver` → Enter)
- Whether you chose **Oui** or **Non** for the TRIPODE question

---

**End of guide.**
