"""
MyGym Installer
===============
Single-file Windows installer for the MyGym Laravel Gym Management System.

Workflow:
    1. Verify system + locate source files (wampserver*.exe, mygym*.zip, mygym*.sql)
    2. Ask (in French) whether a TRIPODE is present:
         - Oui -> disable firewall + configure Ethernet to 192.168.0.4
         - Non -> keep localhost (127.0.0.1), no network changes
    3. Silently install WampServer to C:\\wamp64
    4. Copy & unzip mygym.zip  -> C:\\wamp64\\www\\mygym
    5. Create DB 'mygym', import mygym.sql, generate APP_KEY
    6. Set WAMP services to Automatic (wampmysqld64, wampapache64)
    7. Add C:\\wamp64\\bin\\php\\php7.4.33 to PATH, write startup\\start-server.bat,
       copy it to shell:startup, launch server now
    8. Create Edge app-mode desktop shortcuts: TV and Gym Access

Build to EXE:   pyinstaller --onefile --windowed --uac-admin installer.py
"""

import os
import sys
import re
import time
import base64
import shutil
import zipfile
import subprocess
import threading
import ctypes
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime

# -------------------------------------------------------------------
# CONSTANTS
# -------------------------------------------------------------------
WAMP_DIR     = Path(r"C:\wamp64")
WWW_DIR      = WAMP_DIR / "www"
APP_DIR      = WWW_DIR / "mygym"
DB_NAME      = "mygym"
DB_USER      = "root"
DB_PASSWORD  = ""

# Hosts
LOCAL_HOST   = "127.0.0.1"       # without TRIPODE
TRIPODE_HOST = "192.168.0.4"     # with TRIPODE

# Windows services installed by WampServer 3.3.0
WAMP_SERVICES = ["wampmysqld64", "wampapache64"]

# Explicit PHP install path (WampServer 3.3.0 ships PHP 7.4.33)
PHP_DIR_OVERRIDE = Path(r"C:\wamp64\bin\php\php7.4.33")

# --- Network configuration (applied only when TRIPODE is present) ---
ETHERNET_IP      = "192.168.0.4"
ETHERNET_MASK    = "255.255.255.0"
ETHERNET_GATEWAY = "192.168.0.1"
ETHERNET_DNS1    = "192.168.0.1"
ETHERNET_DNS2    = "8.8.8.8"

# App URLs (used for Edge app-mode desktop shortcuts)
APP_BASE_URL = "http://localhost:8000"
TV_URL       = APP_BASE_URL + "/gym/membre/default"
GYM_URL      = APP_BASE_URL + "/gym"

SOURCE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent


# -------------------------------------------------------------------
# LOGGER
# -------------------------------------------------------------------
class Logger:
    def __init__(self, callback):
        self.callback = callback

    def _ts(self):
        return datetime.now().strftime("%H:%M:%S")

    def info(self, msg):  self.callback(f"[{self._ts()}] {msg}")
    def ok(self, msg):    self.callback(f"[{self._ts()}] OK    {msg}")
    def warn(self, msg):  self.callback(f"[{self._ts()}] WARN  {msg}")
    def error(self, msg): self.callback(f"[{self._ts()}] ERROR {msg}")


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------
def run(cmd, args, cwd=None, on_output=None, check=False):
    full = [cmd] + args
    if on_output:
        on_output("> " + " ".join(str(x) for x in full))

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen(
        full,
        cwd=cwd or str(SOURCE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    out_lines = []
    for line in proc.stdout:
        line = line.rstrip("\r\n")
        out_lines.append(line)
        if on_output:
            on_output(line)
    proc.wait()
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed (exit {proc.returncode}): {' '.join(full)}")
    return proc.returncode, "\n".join(out_lines)


def run_shell(cmdline, cwd=None, on_output=None, check=False):
    if on_output:
        on_output("> " + cmdline)
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen(
        cmdline,
        shell=True,
        cwd=cwd or str(SOURCE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    out_lines = []
    for line in proc.stdout:
        line = line.rstrip("\r\n")
        out_lines.append(line)
        if on_output:
            on_output(line)
    proc.wait()
    if check and proc.returncode != 0:
        raise RuntimeError(f"Shell command failed (exit {proc.returncode}): {cmdline}")
    return proc.returncode, "\n".join(out_lines)


def find_latest(root: Path, pattern: str):
    if not root.exists():
        return None
    matches = sorted(root.rglob(pattern), reverse=True)
    return matches[0] if matches else None


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def get_startup_folder() -> Path:
    """Return the per-user Startup folder (shell:startup)."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA environment variable not found.")
    startup = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup.mkdir(parents=True, exist_ok=True)
    return startup


def find_edge_or_chrome():
    """
    Return the path to msedge.exe (preferred) or chrome.exe (fallback).
    Both support --app=URL for a chromeless app window.
    """
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if Path(c).exists():
            return Path(c)
    return None


def create_edge_app_shortcut(lnk_path: Path, url: str, browser_exe: Path, name: str):
    """Windows .lnk that opens URL in a chromeless Edge/Chrome app window."""
    ps = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{lnk_path}'); "
        f"$s.TargetPath = '{browser_exe}'; "
        f"$s.Arguments = '--app={url}'; "
        f"$s.IconLocation = '{browser_exe},0'; "
        f"$s.Description = '{name}'; "
        f"$s.WindowStyle = 1; "
        f"$s.Save()"
    )
    run_shell(f'powershell -NoProfile -Command "{ps}"', on_output=None)


def create_url_shortcut(lnk_path: Path, url: str, name: str):
    """Fallback when no Edge/Chrome found: plain .url shortcut."""
    content = (
        "[InternetShortcut]\r\n"
        f"URL={url}\r\n"
        f"IconFile={os.path.join(os.environ['SystemRoot'], 'System32', 'SHELL32.dll')}\r\n"
        "IconIndex=13\r\n"
    )
    lnk_path.write_text(content, encoding="ascii")


# -------------------------------------------------------------------
# INSTALLER ENGINE
# -------------------------------------------------------------------
class Installer:
    def __init__(self, log: Logger, progress):
        self.log = log
        self.progress = progress

        self.wamp_installer = None
        self.mygym_zip = None
        self.mygym_sql = None
        self.php_exe = None
        self.mysql_exe = None
        self.php_dir = None

        # Set by ask_tripode() before the network/startup steps run
        self.has_tripode = False
        self.host = LOCAL_HOST

    def ask_tripode(self, parent):
        """
        Ask (in French) whether a TRIPODE is present.
        Sets self.host and self.has_tripode.
        Returns True if answered, None if the user cancelled.
        """
        result = {"ok": False}

        dlg = tk.Toplevel(parent)
        dlg.title("Configuration du serveur")
        dlg.configure(bg="white")
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.grab_set()

        parent.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()

        tk.Label(
            dlg,
            text="Avez-vous un TRIPODE connecté à cette machine ?",
            bg="white", fg="#1c2230",
            font=("Segoe UI Semibold", 12),
            padx=30, pady=20,
        ).pack(fill="x")

        tk.Label(
            dlg,
            text=(
                "• Oui → pare-feu désactivé + IP fixe 192.168.0.4\n"
                "• Non → reste sur localhost (127.0.0.1), aucune modification réseau"
            ),
            bg="white", fg="#555f70",
            font=("Segoe UI", 9),
            justify="left",
            padx=30, pady=0,
        ).pack(fill="x")

        btn_frame = tk.Frame(dlg, bg="white")
        btn_frame.pack(fill="x", padx=20, pady=(20, 20))

        def choose(host, has_tripode):
            self.host = host
            self.has_tripode = has_tripode
            result["ok"] = True
            dlg.destroy()

        tk.Button(
            btn_frame, text="Oui (avec TRIPODE)",
            width=22, height=2,
            bg="#0078d7", fg="white",
            activebackground="#005fa3", activeforeground="white",
            font=("Segoe UI Semibold", 10),
            command=lambda: choose(TRIPODE_HOST, True),
        ).pack(side="left", padx=(0, 10))

        tk.Button(
            btn_frame, text="Non (sans TRIPODE)",
            width=22, height=2,
            bg="#e1e5ea", fg="#1c2230",
            activebackground="#c8cdd5", activeforeground="#1c2230",
            font=("Segoe UI Semibold", 10),
            command=lambda: choose(LOCAL_HOST, False),
        ).pack(side="left")

        tk.Button(
            btn_frame, text="Annuler",
            width=12, height=2,
            bg="white", fg="#555f70",
            relief="flat",
            command=dlg.destroy,
        ).pack(side="right")

        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

        dlg.update_idletasks()
        dw, dh = dlg.winfo_width(), dlg.winfo_height()
        dlg.geometry(f"+{px + (pw - dw)//2}+{py + (ph - dh)//2}")

        parent.wait_window(dlg)
        return True if result["ok"] else None

    # ---------------- STEP 1: system check ----------------
    def step_system_check(self):
        self.progress(0, "Checking Windows...")
        if os.name != "nt":
            raise RuntimeError("This installer only runs on Windows.")

        if not is_admin():
            raise RuntimeError(
                "Administrator privileges required. Right-click the EXE -> Run as administrator."
            )
        self.log.ok("Running as Administrator.")

        self.progress(20, "Checking disk space...")
        free_gb = shutil.disk_usage("C:\\").free / (1024 ** 3)
        self.log.info(f"Free space on C: {free_gb:.1f} GB")
        if free_gb < 3:
            raise RuntimeError("At least 3 GB of free space is required.")

        self.progress(45, "Locating source files...")
        self.wamp_installer = find_latest(SOURCE_DIR, "wampserver*.exe")
        self.mygym_zip      = find_latest(SOURCE_DIR, "mygym*.zip")
        self.mygym_sql      = find_latest(SOURCE_DIR, "mygym*.sql")

        if not self.wamp_installer:
            raise RuntimeError(f"Missing 'wampserver*.exe' in:\n{SOURCE_DIR}")
        if not self.mygym_zip:
            raise RuntimeError(f"Missing 'mygym*.zip' in:\n{SOURCE_DIR}")
        if not self.mygym_sql:
            raise RuntimeError(f"Missing 'mygym*.sql' in:\n{SOURCE_DIR}")

        self.log.ok(f"WampServer : {self.wamp_installer.name}")
        self.log.ok(f"MyGym zip  : {self.mygym_zip.name}")
        self.log.ok(f"MyGym SQL  : {self.mygym_sql.name}")

        self.progress(100, "System check passed.")

    # ---------------- STEP 2: network + firewall (only if TRIPODE) ----------------
    def step_network_setup(self):
        """
        Runs ONLY if the user answered 'Oui' to the TRIPODE question.
        Disables firewall + configures Ethernet NIC to a static IP.
        """
        if not self.has_tripode:
            self.log.info("No TRIPODE -> skipping firewall + Ethernet configuration.")
            self.progress(100, "Network step skipped (no TRIPODE).")
            return

        # ---------- Firewall: Public ----------
        self.progress(0, "Disabling Windows Firewall (Public profile)...")
        try:
            rc, _ = run_shell(
                "netsh advfirewall set publicprofile state off",
                on_output=self.log.info,
            )
            if rc == 0:
                self.log.ok("Public firewall disabled.")
            else:
                self.log.warn(f"Could not disable Public firewall (exit {rc}).")
        except Exception as e:
            self.log.warn(f"Firewall (Public) error: {e}")

        # ---------- Firewall: Domain ----------
        self.progress(15, "Disabling Windows Firewall (Domain profile)...")
        try:
            rc, _ = run_shell(
                "netsh advfirewall set domainprofile state off",
                on_output=self.log.info,
            )
            if rc == 0:
                self.log.ok("Domain firewall disabled.")
            else:
                self.log.warn(f"Could not disable Domain firewall (exit {rc}).")
        except Exception as e:
            self.log.warn(f"Firewall (Domain) error: {e}")

        # ---------- Firewall: Private ----------
        self.progress(25, "Disabling Windows Firewall (Private profile)...")
        try:
            rc, _ = run_shell(
                "netsh advfirewall set privateprofile state off",
                on_output=self.log.info,
            )
            if rc == 0:
                self.log.ok("Private firewall disabled.")
            else:
                self.log.warn(f"Could not disable Private firewall (exit {rc}).")
        except Exception as e:
            self.log.warn(f"Firewall (Private) error: {e}")

        # ---------- Find Ethernet adapter ----------
        self.progress(35, "Looking for an Ethernet adapter...")
        ethernet_name = self._find_ethernet_adapter()

        if not ethernet_name:
            self.log.warn("No Ethernet adapter found - skipping static IP config.")
            self.progress(100, "Network step complete (no Ethernet).")
            return

        self.log.ok(f"Ethernet adapter: {ethernet_name}")

        # ---------- Static IP ----------
        self.progress(50, f"Setting IP {ETHERNET_IP}/{ETHERNET_MASK} on '{ethernet_name}'...")
        rc, out = run_shell(
            f'netsh interface ip set address name="{ethernet_name}" '
            f'static {ETHERNET_IP} {ETHERNET_MASK} {ETHERNET_GATEWAY} 1',
            on_output=self.log.info,
        )
        if rc == 0:
            self.log.ok(f"IP set: {ETHERNET_IP} mask {ETHERNET_MASK} gw {ETHERNET_GATEWAY}")
        else:
            self.log.warn(f"Could not set static IP (exit {rc}).")

        # ---------- DNS ----------
        self.progress(75, "Setting DNS servers...")
        rc, out = run_shell(
            f'netsh interface ip set dns name="{ethernet_name}" '
            f'static {ETHERNET_DNS1} primary',
            on_output=self.log.info,
        )
        if rc == 0:
            self.log.ok(f"Primary DNS: {ETHERNET_DNS1}")
        else:
            self.log.warn(f"Could not set primary DNS (exit {rc}).")

        rc, out = run_shell(
            f'netsh interface ip add dns name="{ethernet_name}" '
            f'{ETHERNET_DNS2} index=2',
            on_output=self.log.info,
        )
        if rc == 0:
            self.log.ok(f"Secondary DNS: {ETHERNET_DNS2}")
        else:
            self.log.warn(f"Could not set secondary DNS (exit {rc}).")

        # ---------- Verify ----------
        self.progress(90, "Verifying configuration...")
        try:
            rc, out = run_shell(
                f'netsh interface ip show config name="{ethernet_name}"',
                on_output=None,
            )
            for line in out.splitlines():
                if "IP Address" in line or "IP address" in line or "Default Gateway" in line:
                    self.log.info(line.strip())
        except Exception:
            pass

        self.progress(100, "Network configured.")

    def _find_ethernet_adapter(self):
        """
        Return the name of the first *wired* Ethernet adapter, or None.
        """
        try:
            rc, out = run_shell("netsh interface show interface", on_output=None)
            if rc != 0:
                return None

            candidates = []
            for line in out.splitlines():
                line = line.rstrip()
                if not line.strip():
                    continue
                if line.strip().startswith("Admin State"):
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    admin_state   = parts[0]
                    connect_state = parts[1]
                    iface_type    = parts[2]
                    name = " ".join(parts[3:]).strip()
                    if not name:
                        continue
                    if iface_type.lower() == "dedicated":
                        candidates.append((connect_state.lower() == "connected", name))

            if not candidates:
                return None

            candidates.sort(reverse=True)
            return candidates[0][1]
        except Exception as e:
            self.log.warn(f"Adapter detection error: {e}")
            return None

    # ---------------- STEP 3: install WAMP ----------------
    def step_install_wamp(self):
        self.progress(0, "Checking for existing WampServer...")

        if (WAMP_DIR / "bin").exists():
            self.log.ok(f"WampServer already installed at {WAMP_DIR} - skipping install.")
        else:
            self.progress(5, "Running WampServer installer (silent, may take 1-2 min)...")
            args = [
                str(self.wamp_installer),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/SP-",
                f"/DIR={WAMP_DIR}",
            ]
            rc, _ = run(args[0], args[1:], on_output=self.log.info)
            if rc != 0:
                raise RuntimeError(f"WampServer installer exited with code {rc}.")
            self.log.ok("WampServer installed.")

        self.progress(60, "Locating PHP & MySQL binaries...")

        php_exe_override = PHP_DIR_OVERRIDE / "php.exe"
        if php_exe_override.exists():
            self.php_exe = php_exe_override
            self.php_dir = PHP_DIR_OVERRIDE
            self.log.ok(f"Using PHP at fixed path: {self.php_exe}")
        else:
            self.log.warn(f"Expected PHP path not found: {php_exe_override}")
            self.log.info("Falling back to auto-discovery...")
            self.php_exe = find_latest(WAMP_DIR / "bin" / "php", "php.exe")
            if not self.php_exe:
                raise RuntimeError(f"php.exe not found under {WAMP_DIR / 'bin' / 'php'}")
            self.php_dir = self.php_exe.parent

        self.mysql_exe = find_latest(WAMP_DIR / "bin" / "mysql", "mysql.exe")
        if not self.mysql_exe:
            raise RuntimeError(f"mysql.exe not found under {WAMP_DIR / 'bin' / 'mysql'}")

        self.log.ok(f"PHP   : {self.php_exe}")
        self.log.ok(f"MySQL : {self.mysql_exe}")

        self.progress(85, "Starting MySQL service...")
        try:
            run_shell("net start wampmysqld64", on_output=self.log.info)
        except Exception as e:
            self.log.warn(f"Could not start MySQL service: {e}")

        self.progress(100, "WampServer ready.")

    # ---------------- STEP 4: extract MyGym ----------------
    def step_extract_mygym(self):
        self.progress(0, "Preparing target folder...")
        WWW_DIR.mkdir(parents=True, exist_ok=True)

        if APP_DIR.exists():
            self.log.warn("Existing MyGym folder found - removing it.")
            shutil.rmtree(APP_DIR, ignore_errors=True)

        APP_DIR.mkdir(parents=True, exist_ok=True)

        self.progress(10, "Opening mygym.zip...")
        with zipfile.ZipFile(self.mygym_zip, "r") as zf:
            names = zf.namelist()
            total = len(names)
            for i, name in enumerate(names, 1):
                zf.extract(name, APP_DIR)
                if i % 25 == 0 or i == total:
                    pct = 10 + int(i * 80 / total)
                    self.progress(pct, f"Extracting {i}/{total}...")

        entries = list(APP_DIR.iterdir())
        if len(entries) == 1 and entries[0].is_dir() and not (APP_DIR / "artisan").exists():
            self.log.info("Detected nested root folder - flattening.")
            nested = entries[0]
            for item in nested.iterdir():
                item.rename(APP_DIR / item.name)
            nested.rmdir()

        if not (APP_DIR / "artisan").exists():
            self.log.warn("'artisan' not found - is this a valid Laravel project?")

        self.progress(100, "MyGym files ready.")

    # ---------------- STEP 5: database ----------------
    def step_database(self):
        self.progress(0, "Waiting for MySQL...")

        ready = False
        for i in range(30):
            try:
                rc, _ = run(str(self.mysql_exe),
                            ["-u", DB_USER, "-e", "SELECT 1;"],
                            on_output=None)
                if rc == 0:
                    ready = True
                    break
            except Exception:
                pass
            time.sleep(1)
            self.progress(min(15, i), "Waiting for MySQL...")

        if not ready:
            raise RuntimeError("MySQL did not become ready. Start WampServer manually and re-run.")

        self.log.ok("MySQL is ready.")

        self.progress(20, f"Creating database '{DB_NAME}'...")
        rc, _ = run(str(self.mysql_exe),
                    ["-u", DB_USER, "-e",
                     f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                     f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"])
        if rc != 0:
            raise RuntimeError("Failed to create database.")
        self.log.ok(f"Database '{DB_NAME}' ensured.")

        self.progress(40, "Importing mygym.sql...")
        import_cmd = f'"{self.mysql_exe}" -u {DB_USER} {DB_NAME} < "{self.mygym_sql}"'
        rc, _ = run_shell(import_cmd, on_output=self.log.info)
        if rc != 0:
            raise RuntimeError("Failed to import mygym.sql.")
        self.log.ok("mygym.sql imported.")

        self.progress(65, "Writing .env...")
        env_path     = APP_DIR / ".env"
        example_path = APP_DIR / ".env.example"

        if example_path.exists():
            content = example_path.read_text(encoding="utf-8", errors="replace")
        else:
            content = ("APP_NAME=Laravel\nAPP_ENV=local\nAPP_KEY=\n"
                       "APP_DEBUG=true\nAPP_URL=http://localhost\n")

        def setkv(text, key, value):
            pattern = rf"(?m)^{re.escape(key)}=.*$"
            if re.search(pattern, text):
                return re.sub(pattern, f"{key}={value}", text)
            return text + f"\n{key}={value}\n"

        content = setkv(content, "DB_CONNECTION", "mysql")
        content = setkv(content, "DB_HOST",       "127.0.0.1")
        content = setkv(content, "DB_PORT",       "3306")
        content = setkv(content, "DB_DATABASE",   DB_NAME)
        content = setkv(content, "DB_USERNAME",   DB_USER)
        content = setkv(content, "DB_PASSWORD",   DB_PASSWORD)

        env_path.write_text(content, encoding="utf-8")
        self.log.ok(".env written.")

        # -------- Generate APP_KEY via artisan ----------
        self.progress(80, "Generating application encryption key (APP_KEY)...")
        try:
            rc, out = run(
                str(self.php_exe),
                ["artisan", "key:generate", "--force"],
                cwd=str(APP_DIR),
                on_output=self.log.info,
            )
            if rc == 0:
                self.log.ok("APP_KEY generated successfully.")
            else:
                self.log.warn(f"key:generate exited with code {rc} - retrying")
                rc2, out2 = run(
                    str(self.php_exe),
                    ["artisan", "key:generate", "--force", "--no-interaction"],
                    cwd=str(APP_DIR),
                    on_output=self.log.info,
                )
                if rc2 == 0:
                    self.log.ok("APP_KEY generated successfully.")
                else:
                    self.log.warn("Could not run 'php artisan key:generate' automatically.")
        except Exception as e:
            self.log.warn(f"Could not run artisan key:generate: {e}")

        # -------- Verify APP_KEY is set (fallback if not) ----------
        try:
            env_now = env_path.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"(?m)^APP_KEY=(.*)$", env_now)
            if m and m.group(1).strip():
                self.log.ok("Verified: APP_KEY is set.")
            else:
                self.log.warn("APP_KEY still empty - writing a fallback key directly.")
                fallback_key = "base64:" + base64.b64encode(os.urandom(32)).decode("ascii")
                env_now = re.sub(r"(?m)^APP_KEY=.*$", f"APP_KEY={fallback_key}", env_now)
                env_path.write_text(env_now, encoding="utf-8")
                self.log.ok("Fallback APP_KEY written.")
        except Exception as e:
            self.log.warn(f"Could not verify APP_KEY: {e}")

        self.progress(100, "Database ready.")

    # ---------------- STEP 6: WAMP services -> Automatic ----------------
    def step_set_services_auto(self):
        self.progress(0, "Configuring WAMP services to start automatically...")

        for i, svc in enumerate(WAMP_SERVICES, 1):
            pct = int(i * 100 / len(WAMP_SERVICES))

            rc, out = run_shell(f'sc config "{svc}" start= auto',
                                on_output=self.log.info)
            if rc == 0:
                self.log.ok(f"Service '{svc}' set to Automatic.")
            else:
                self.log.warn(f"Could not set '{svc}' to Automatic (exit {rc}).")

            rc, out = run_shell(f'sc query "{svc}" | findstr /I "RUNNING"',
                                on_output=None)
            if rc != 0:
                self.log.info(f"Starting service '{svc}'...")
                rc2, _ = run_shell(f'net start "{svc}"', on_output=self.log.info)
                if rc2 == 0:
                    self.log.ok(f"Service '{svc}' started.")
                else:
                    self.log.warn(f"Could not start '{svc}' (may start on next boot).")
            else:
                self.log.info(f"Service '{svc}' already running.")

            self.progress(pct, f"Configured {svc} ({i}/{len(WAMP_SERVICES)})")

        self.progress(100, "WAMP services configured.")

    # ---------------- STEP 7: PATH + startup + serve ----------------
    def step_startup(self):
        # --- 7a. Add PHP to system PATH ---
        self.progress(0, "Adding PHP to system PATH...")
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                0, winreg.KEY_READ | winreg.KEY_WRITE,
            )
            try:
                current, _ = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current = ""

            target = str(PHP_DIR_OVERRIDE).rstrip("\\")
            parts = [p.strip().rstrip("\\") for p in current.split(";") if p.strip()]
            if target.lower() not in [p.lower() for p in parts]:
                new_path = ";".join(parts + [target])
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
                self.log.ok(f"Added to PATH: {target}")
            else:
                self.log.info(f"PHP path already present in PATH: {target}")
            winreg.CloseKey(key)
        except Exception as e:
            self.log.warn(f"Could not update PATH: {e}")

        # --- 7b. Create startup\start-server.bat ---
        self.progress(30, "Creating startup script...")
        startup_dir = APP_DIR / "startup"
        startup_dir.mkdir(parents=True, exist_ok=True)
        bat_path = startup_dir / "start-server.bat"

        php_exe_str = str(self.php_exe)
        app_url = f"http://{self.host}:8000"

        self.log.info(f"Server host: {self.host}")

        bat_content = (
            "@echo off\r\n"
            "title MyGym - Laravel Dev Server\r\n"
            f'cd /d "{APP_DIR}"\r\n'
            "echo ============================================\r\n"
            "echo   MyGym - Laravel Dev Server\r\n"
            f"echo   URL: {app_url}\r\n"
            f"echo   PHP: {php_exe_str}\r\n"
            "echo ============================================\r\n"
            "echo.\r\n"
            f'"{php_exe_str}" artisan serve --host={self.host} --port=8000\r\n'
            "pause\r\n"
        )
        bat_path.write_text(bat_content, encoding="ascii")
        self.log.ok(f"Created: {bat_path}")

        # --- 7c. Copy to shell:startup ---
        self.progress(50, "Registering server for auto-start (shell:startup)...")
        try:
            startup_folder = get_startup_folder()
            dest = startup_folder / "MyGym-Server.bat"
            shutil.copy2(bat_path, dest)
            self.log.ok(f"Auto-start registered: {dest}")
        except Exception as e:
            self.log.warn(f"Could not register auto-start: {e}")

        # --- 7d. Desktop shortcut to start the server ---
        self.progress(65, "Creating Desktop shortcut...")
        try:
            desktop = Path(os.environ["PUBLIC"]) / "Desktop"
            lnk = desktop / "Start MyGym.lnk"
            ps = (
                f"$ws = New-Object -ComObject WScript.Shell; "
                f"$s = $ws.CreateShortcut('{lnk}'); "
                f"$s.TargetPath = '{bat_path}'; "
                f"$s.WorkingDirectory = '{APP_DIR}'; "
                f"$s.Description = 'Start MyGym Laravel server'; "
                f"$s.Save()"
            )
            run_shell(f'powershell -NoProfile -Command "{ps}"', on_output=None)
            self.log.ok(f"Desktop shortcut: {lnk}")
        except Exception as e:
            self.log.warn(f"Shortcut creation failed: {e}")

        # --- 7e. Start the server now ---
        self.progress(85, "Starting php artisan serve...")
        try:
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "MyGym Server", "cmd.exe", "/k", str(bat_path)],
                cwd=str(APP_DIR),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            self.log.ok("Server starting in a new window.")
        except Exception as e:
            self.log.warn(f"Could not auto-start server: {e}")
            self.log.info(f"Start it manually: {bat_path}")

        self.progress(100, "Startup configured.")

    # ---------------- STEP 8: Edge app-mode shortcuts ----------------
    def step_create_app_shortcuts(self):
        self.progress(0, "Creating app shortcuts (Edge app mode)...")

        browser = find_edge_or_chrome()
        if browser:
            self.log.ok(f"Browser found: {browser.name} -> {browser}")
        else:
            self.log.warn("Neither msedge.exe nor chrome.exe found - using plain URL shortcuts.")

        desktop = Path(os.environ["PUBLIC"]) / "Desktop"

        targets = [
            ("TV.lnk",         TV_URL,  "TV - MyGym Member Display"),
            ("Gym Access.lnk", GYM_URL, "Gym Access - MyGym"),
        ]

        for i, (fname, url, name) in enumerate(targets, 1):
            try:
                lnk = desktop / fname
                if browser:
                    create_edge_app_shortcut(lnk, url, browser, name)
                    self.log.ok(f"Created app shortcut: {lnk} -> {url}")
                else:
                    create_url_shortcut(lnk, url, name)
                    self.log.ok(f"Created URL shortcut: {lnk} -> {url}")
            except Exception as e:
                self.log.warn(f"Could not create shortcut '{fname}': {e}")

            self.progress(int(i * 100 / len(targets)), f"Created {fname}")

        self.progress(100, "App shortcuts ready.")


# -------------------------------------------------------------------
# GUI
# -------------------------------------------------------------------
class InstallerApp(tk.Tk):
    STEPS = [
        "Welcome",
        "System Check",
        "Network & Firewall",
        "WampServer",
        "MyGym Files",
        "Database",
        "Services & Startup",
        "Complete",
    ]

    def __init__(self):
        super().__init__()
        self.title("MyGym Installer")
        self.geometry("900x620")
        self.minsize(820, 560)
        self.configure(bg="white")

        self.current_step = 0
        self.worker_thread = None
        self.installer_ctx = None

        self._build_ui()
        self._show_step(0)

    def _build_ui(self):
        header = tk.Frame(self, bg="#1c2230", height=70)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="MyGym Installer", bg="#1c2230", fg="white",
                 font=("Segoe UI Semibold", 18)).place(x=20, y=10)
        tk.Label(header, text="Laravel Gym Management System - Setup Wizard",
                 bg="#1c2230", fg="#b4becd",
                 font=("Segoe UI", 9)).place(x=22, y=42)

        footer = tk.Frame(self, bg="#f5f7fa", height=90)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)

        self.percent_lbl = tk.Label(footer, text="0 %", bg="#f5f7fa",
                                    font=("Segoe UI", 9, "bold"))
        self.percent_lbl.place(x=20, y=30, width=60)

        self.progress = ttk.Progressbar(footer, mode="determinate", maximum=100)
        self.progress.place(x=80, y=30, relwidth=1.0, width=-100, height=18)

        btn_bar = tk.Frame(footer, bg="#f5f7fa")
        btn_bar.place(x=0, y=50, relwidth=1.0, height=40)

        self.cancel_btn = tk.Button(btn_bar, text="Cancel", width=12, command=self._on_cancel)
        self.cancel_btn.pack(side="left", padx=(20, 0))

        self.next_btn = tk.Button(btn_bar, text="Next >", width=12,
                                  bg="#0078d7", fg="white",
                                  activebackground="#005fa3", activeforeground="white",
                                  command=self._on_next)
        self.next_btn.pack(side="right", padx=(0, 20))

        self.back_btn = tk.Button(btn_bar, text="< Back", width=12, command=self._on_back)
        self.back_btn.pack(side="right", padx=(0, 10))

        sidebar = tk.Frame(self, bg="#f5f7fa", width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        self.step_list = tk.Listbox(sidebar, borderwidth=0, highlightthickness=0,
                                    bg="#f5f7fa", fg="#3c4655",
                                    font=("Segoe UI", 10),
                                    selectbackground="#0078d7",
                                    selectforeground="white",
                                    activestyle="none")
        self.step_list.pack(fill="both", expand=True, padx=10, pady=10)
        for i, name in enumerate(self.STEPS, 1):
            self.step_list.insert("end", f"  {i}. {name}")

        content = tk.Frame(self, bg="white")
        content.pack(side="right", fill="both", expand=True)

        self.status_lbl = tk.Label(content, text="Welcome", bg="white",
                                   fg="#1c2230",
                                   font=("Segoe UI Semibold", 11),
                                   anchor="w")
        self.status_lbl.pack(fill="x", padx=20, pady=(16, 6))

        log_frame = tk.Frame(content, bg="white")
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        self.log_box = tk.Text(log_frame, bg="#181c24", fg="#c8dcc8",
                               insertbackground="#c8dcc8",
                               font=("Consolas", 9),
                               wrap="word",
                               borderwidth=0, highlightthickness=0)
        scroll = tk.Scrollbar(log_frame, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log_box.pack(side="left", fill="both", expand=True)
        self.log_box.configure(state="disabled")

    def append_log(self, msg):
        def _do():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _do)

    def set_progress(self, pct, status):
        def _do():
            self.progress["value"] = max(0, min(100, pct))
            self.percent_lbl.config(text=f"{int(self.progress['value'])} %")
            if status:
                self.status_lbl.config(text=status)
        self.after(0, _do)

    def _show_step(self, idx):
        self.current_step = idx
        name = self.STEPS[idx]
        self.step_list.selection_clear(0, "end")
        self.step_list.selection_set(idx)
        self.step_list.see(idx)
        self.status_lbl.config(text=name)
        self.back_btn.config(state="normal" if idx > 0 else "disabled")
        self.next_btn.config(text="Finish" if idx == len(self.STEPS) - 1 else "Next >")

        self.append_log(f"--- {name} ---")

        if idx == 0:
            self.append_log("Welcome to the MyGym installer.")
            self.append_log("")
            self.append_log("This wizard will:")
            self.append_log("  1. Verify system requirements")
            self.append_log("  2. Ask if a TRIPODE is present:")
            self.append_log("       - OUI -> disable firewall, Ethernet = 192.168.0.4")
            self.append_log("       - NON -> keep localhost, no network changes")
            self.append_log("  3. Install WampServer (Apache + MySQL + PHP)")
            self.append_log(r"  4. Copy and unzip MyGym into C:\wamp64\www\mygym")
            self.append_log("  5. Create the 'mygym' database, import mygym.sql,")
            self.append_log("     and generate the Laravel APP_KEY")
            self.append_log("  6. Set WAMP services to start automatically on boot")
            self.append_log(r"  7. Add C:\wamp64\bin\php\php7.4.33 to PATH and register auto-start")
            self.append_log("  8. Create Edge app shortcuts: TV and Gym Access")
            self.append_log("")
            self.append_log(f"Source folder: {SOURCE_DIR}")
            self.append_log("")
            self.append_log("Click Next to begin.")

        if idx == len(self.STEPS) - 1:
            host = self.installer_ctx.host if self.installer_ctx else LOCAL_HOST
            tripode_txt = "OUI" if (self.installer_ctx and self.installer_ctx.has_tripode) else "NON"
            self.append_log("")
            self.append_log("================================================")
            self.append_log("   INSTALLATION COMPLETE")
            self.append_log("================================================")
            self.append_log(f"  TRIPODE         : {tripode_txt}")
            self.append_log(f"  App folder      : {APP_DIR}")
            self.append_log(f"  Database        : {DB_NAME}")
            self.append_log(f"  Server URL      : http://{host}:8000")
            self.append_log(f"  PHP path        : {PHP_DIR_OVERRIDE}")
            self.append_log(f"  Startup script  : {APP_DIR / 'startup' / 'start-server.bat'}")
            self.append_log(f"  Auto-run at login: shell:startup\\MyGym-Server.bat")
            self.append_log("")
            self.append_log("  Desktop shortcuts:")
            self.append_log(f"    - Start MyGym     (server console)")
            self.append_log(f"    - TV              -> {TV_URL}")
            self.append_log(f"    - Gym Access      -> {GYM_URL}")
            self.append_log("")
            self.append_log("Click Finish to exit.")

    def _on_next(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return
        idx = self.current_step

        # Finish
        if idx == len(self.STEPS) - 1:
            host = self.installer_ctx.host if self.installer_ctx else LOCAL_HOST
            try:
                os.startfile(f"http://{host}:8000")
            except Exception:
                pass
            self.destroy()
            return

        # Welcome -> advance
        if idx == 0:
            self._show_step(1)
            return

        # Ask TRIPODE before the Network step (idx == 2)
        if idx == 2:
            if self.installer_ctx is None:
                self.installer_ctx = Installer(Logger(self.append_log), self.set_progress)

            answer = self.installer_ctx.ask_tripode(self)
            if answer is None:
                self.append_log("TRIPODE question cancelled - step skipped.")
                return

            if self.installer_ctx.has_tripode:
                self.append_log("TRIPODE: OUI -> firewall off, Ethernet -> 192.168.0.4")
            else:
                self.append_log("TRIPODE: NON -> keeping localhost, no network changes")

        step_map = {
            1: ("System Check",       "step_system_check"),
            2: ("Network & Firewall", "step_network_setup"),
            3: ("WampServer",         "step_install_wamp"),
            4: ("MyGym Files",        "step_extract_mygym"),
            5: ("Database",           "step_database"),
            6: ("Services & Startup", "step_set_services_auto"),
        }
        if idx not in step_map:
            return

        name, method = step_map[idx]
        self.next_btn.config(state="disabled")
        self.back_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")

        self.append_log("")
        self.append_log(f">> Running: {name}")

        def worker():
            log = Logger(self.append_log)
            try:
                if self.installer_ctx is None:
                    self.installer_ctx = Installer(log, self.set_progress)
                else:
                    self.installer_ctx.log = log
                    self.installer_ctx.progress = self.set_progress

                if method == "step_set_services_auto":
                    self.installer_ctx.step_set_services_auto()
                    self.installer_ctx.step_startup()
                    self.installer_ctx.step_create_app_shortcuts()
                else:
                    getattr(self.installer_ctx, method)()

                self.append_log(f"OK {name} completed.")
                self.after(0, lambda: self._show_step(idx + 1))
            except Exception as e:
                self.append_log(f"ERROR {e}")
                self.after(0, lambda: messagebox.showerror(
                    "Installation Error",
                    f"Step '{name}' failed:\n\n{e}"
                ))
            finally:
                self.after(0, lambda: self.next_btn.config(state="normal"))
                self.after(0, lambda: self.back_btn.config(state="normal"))

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    def _on_back(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return
        if self.current_step > 0:
            self._show_step(self.current_step - 1)

    def _on_cancel(self):
        if messagebox.askyesno("Confirm", "Exit the installer?"):
            self.destroy()


# -------------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------------
def main():
    if os.name != "nt":
        print("MyGym Installer only runs on Windows.")
        sys.exit(1)

    if not is_admin():
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable,
                " ".join(f'"{a}"' for a in sys.argv), None, 1
            )
        except Exception as e:
            print(f"Elevation failed: {e}")
        sys.exit(0)

    app = InstallerApp()
    app.mainloop()


if __name__ == "__main__":
    main()