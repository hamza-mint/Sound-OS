"""
Sound OS - Executor Action Implementations (v2 Enhanced)
Safe command execution for Ubuntu (X11 / Xorg).
Follows CONTRACT.md: No shell=True, safe argument lists, never raises exceptions.
"""
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

SAFE_FILES_DIR = Path.home() / "SoundOS_Files"
BRIGHTNESS_STATE_FILE = Path("/tmp/.soundos_brightness")


def check_internet_connection(timeout_sec: float = 0.2) -> bool:
    """
    Ultra-fast non-blocking internet connectivity check (DNS socket connect).
    Takes <50ms, well below the 1-second limit in CONTRACT.md §7.
    """
    targets = [("1.1.1.1", 53), ("8.8.8.8", 53)]
    for host, port in targets:
        try:
            with socket.create_connection((host, port), timeout=timeout_sec):
                return True
        except OSError:
            continue
    return False


# Compatibility alias
is_online = check_internet_connection


def _run_subcommand(args: list[str], timeout_sec: float = 0.85) -> Tuple[bool, str]:
    """Run a command safely without shell=True.

    Default timeout reduced to 0.85s per CONTRACT.md §7 (executor must complete under 1 second).
    Multi-step operations (web_search, play_media) should pass remaining budget.
    """
    if not args:
        return False, "Empty arguments list."
    binary = args[0]
    if not shutil.which(binary):
        return False, f"Required utility '{binary}' is not installed."

    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
        )
        if proc.returncode == 0:
            return True, proc.stdout.strip()
        err = proc.stderr.strip() or proc.stdout.strip()
        return False, err or f"Process exited with code {proc.returncode}."
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout_sec}s."
    except Exception as exc:
        return False, str(exc)


def _spawn_detached(args: list[str], timeout_sec: float = 0.85) -> Tuple[bool, str]:
    """Spawn a detached GUI or background process safely."""
    if not args:
        return False, "Empty arguments list."
    binary = args[0]
    if not shutil.which(binary):
        return False, f"Binary '{binary}' is not installed."

    try:
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True, "Launched successfully."
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------
# Volume & Audio Controls (Supports PipeWire, PulseAudio & ALSA)
# ---------------------------------------------------------
def adjust_volume(direction: str) -> Tuple[bool, str]:
    """
    Adjust volume up (+5%) or down (-5%).
    Senior UX enhancement: Automatically unmute when raising volume.
    Prefers wpctl (PipeWire), then pactl (PulseAudio), then amixer (ALSA).
    """
    delta = "+5%" if direction == "up" else "-5%"

    # 1. PipeWire / WirePlumber
    if shutil.which("wpctl"):
        if direction == "up":
            _run_subcommand(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"])
        cmd = ["wpctl", "set-volume", "-l", "1.5", "@DEFAULT_AUDIO_SINK@", delta]
        ok, out = _run_subcommand(cmd)
        if ok:
            return True, "Volume adjusted."

    # 2. PulseAudio fallback
    if shutil.which("pactl"):
        if direction == "up":
            _run_subcommand(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
        cmd = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", delta]
        ok, out = _run_subcommand(cmd)
        if ok:
            return True, "Volume adjusted."

    # 3. ALSA amixer fallback
    if shutil.which("amixer"):
        if direction == "up":
            _run_subcommand(["amixer", "sset", "Master", "unmute"])
        cmd = ["amixer", "sset", "Master", "5%+" if direction == "up" else "5%-"]
        ok, out = _run_subcommand(cmd)
        if ok:
            return True, "Volume adjusted."
        return False, out

    return False, "Neither 'wpctl', 'pactl', nor 'amixer' is installed or responding on this system."


def set_mute() -> Tuple[bool, str]:
    """Mutes the default audio sink (wpctl -> pactl -> amixer)."""
    if shutil.which("wpctl"):
        ok, out = _run_subcommand(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1"])
        if ok:
            return True, "Audio muted."

    if shutil.which("pactl"):
        ok, out = _run_subcommand(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"])
        if ok:
            return True, "Audio muted."

    if shutil.which("amixer"):
        ok, out = _run_subcommand(["amixer", "sset", "Master", "mute"])
        if ok:
            return True, "Audio muted."
        return False, out

    return False, "Neither 'wpctl', 'pactl', nor 'amixer' is installed or responding on this system."


# ---------------------------------------------------------
# Brightness Controls (brightnessctl with VM xrandr fallback)
# ---------------------------------------------------------
def _adjust_vm_xrandr_brightness(direction: str) -> Tuple[bool, str]:
    """
    Software brightness fallback for Virtual Machines (VirtualBox, VMware, QEMU)
    using X11 xrandr gamma scaling.
    """
    if not shutil.which("xrandr"):
        return False, "Neither 'brightnessctl' nor 'xrandr' is available."

    try:
        proc = subprocess.run(
            ["xrandr", "--current"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2,
        )
        if proc.returncode != 0:
            return False, "Failed to query xrandr display."

        connected_output = None
        for line in proc.stdout.splitlines():
            if " connected" in line:
                connected_output = line.split()[0]
                break

        if not connected_output:
            return False, "No active connected X11 display found."

        # Read current software brightness level (default: 1.0)
        current = 1.0
        if BRIGHTNESS_STATE_FILE.exists():
            try:
                current = float(BRIGHTNESS_STATE_FILE.read_text().strip())
            except Exception:
                current = 1.0

        step = 0.1
        new_val = min(1.5, max(0.2, current + step)) if direction == "up" else min(1.5, max(0.2, current - step))
        new_val = round(new_val, 2)

        gamma_str = f"{new_val}:{new_val}:{new_val}"
        ok, out = _run_subcommand(["xrandr", "--output", connected_output, "--gamma", gamma_str])
        if ok:
            try:
                BRIGHTNESS_STATE_FILE.write_text(str(new_val))
            except Exception:
                pass
            return True, f"VM Display brightness adjusted to {int(new_val * 100)}% via xrandr."
        return False, f"xrandr gamma adjustment failed: {out}"

    except Exception as exc:
        return False, f"xrandr error: {exc}"


def adjust_brightness(direction: str) -> Tuple[bool, str]:
    """
    Adjust display brightness up (+10%) or down (-10%).
    1. First tries hardware brightness via brightnessctl.
    2. If on VM or brightnessctl fails, falls back gracefully to software xrandr.
    """
    delta = "10%+" if direction == "up" else "10%-"
    if shutil.which("brightnessctl"):
        ok, out = _run_subcommand(["brightnessctl", "set", delta])
        if ok:
            return True, "Brightness adjusted."

    # VM Fallback
    return _adjust_vm_xrandr_brightness(direction)


# ---------------------------------------------------------
# Application Controls (Open / Graceful Close)
# ---------------------------------------------------------
_last_launched_process: Optional[str] = None
_process_lock = threading.Lock()


def _try_focus_window(proc_name: str) -> bool:
    """Try to bring a running window to focus using wmctrl or KDE KWin DBus."""
    if not proc_name:
        return False

    # 1. wmctrl (X11)
    if shutil.which("wmctrl"):
        ok, _ = _run_subcommand(["wmctrl", "-a", proc_name])
        if ok:
            return True

    # 2. KDE KWin DBus (Wayland & X11)
    if shutil.which("gdbus") and os.environ.get("XDG_CURRENT_DESKTOP") == "KDE":
        try:
            res = subprocess.run(
                ["gdbus", "call", "--session", "--dest", "org.kde.KWin",
                 "--object-path", "/WindowsRunner", "--method", "org.kde.krunner1.Match", proc_name],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=0.3
            )
            if res.returncode == 0 and res.stdout:
                m = re.search(r"'(0_\{[^}]+\})'", res.stdout)
                if m:
                    match_id = m.group(1)
                    run_res = subprocess.run(
                        ["gdbus", "call", "--session", "--dest", "org.kde.KWin",
                         "--object-path", "/WindowsRunner", "--method", "org.kde.krunner1.Run", match_id, ""],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=0.3
                    )
                    if run_res.returncode == 0:
                        return True
        except Exception:
            pass

    return False


def launch_app(app_config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Launch application as a detached background process.
    Senior Enhancement:
    1. If app is already running, bring window to front (Focus) via wmctrl or KDE KWin DBus.
    2. Avoids spawning multiple duplicate windows when app is already running.
    3. Tries primary cmd first, then fallback_cmds / fallbacks for cross-distro compatibility.
    """
    global _last_launched_process
    proc_name = app_config.get("process", "")
    if proc_name:
        with _process_lock:
            _last_launched_process = proc_name

        # Check if app is already running and focus its window
        if _try_focus_window(proc_name):
            return True, f"Focused running {proc_name}."

        # If process is already running in background, check fallbacks to focus or report already running
        if shutil.which("pgrep"):
            ok, _ = _run_subcommand(["pgrep", "-x", proc_name])
            if ok:
                for alias in app_config.get("process_fallbacks", []):
                    if _try_focus_window(alias):
                        return True, f"Focused running {proc_name}."
                # App process exists: avoid spawning multiple redundant instances
                return True, f"{proc_name} is already open and running."

    # Try primary cmd
    cmd = app_config.get("cmd", [])
    if cmd and shutil.which(cmd[0]):
        return _spawn_detached(cmd)

    # Try fallback commands across distributions (Fedora, Arch, Debian, etc.)
    fallback_candidates = app_config.get("fallback_cmds", []) + app_config.get("fallbacks", [])
    for fb_cmd in fallback_candidates:
        if fb_cmd and isinstance(fb_cmd, list) and shutil.which(fb_cmd[0]):
            return _spawn_detached(fb_cmd)

    if cmd:
        return _spawn_detached(cmd)
    return False, "No executable command configured for this application."


def terminate_app(app_config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Terminate application gracefully.
    Senior UX enhancement: Try wmctrl -c first (Graceful close on X11),
    falling back to pkill -x with candidate process names.
    Supports closing the active/current window or running app when process is 'current'.
    """
    global _last_launched_process
    proc_name = app_config.get("process")
    if not proc_name:
        return False, "No process name defined for this application."

    # Generic close: user said "close app" / "اقفل تطبيق" / "اقفل النافذة"
    if proc_name == "current":
        # 1. Close the active window. wmctrl asks the window manager to close it (graceful, the app can
        #    still show "save changes?"), so it goes first; xdotool and KDE DBus follow.
        if shutil.which("wmctrl"):
            ok, _ = _run_subcommand(["wmctrl", "-c", ":ACTIVE:"])
            if ok:
                return True, "Closed active window."
        if shutil.which("xdotool"):
            ok, _ = _run_subcommand(["xdotool", "getactivewindow", "windowclose"])
            if ok:
                return True, "Closed active window."
        if shutil.which("gdbus") and os.environ.get("XDG_CURRENT_DESKTOP") == "KDE":
            ok, _ = _run_subcommand([
                "gdbus", "call", "--session", "--dest", "org.kde.kglobalaccel",
                "--object-path", "/component/kwin",
                "--method", "org.kde.kglobalaccel.Component.invokeShortcut", "Window Close"
            ])
            if ok:
                return True, "Closed active window."

        # 2. Try closing the most recently launched app
        with _process_lock:
            target_proc = _last_launched_process
        if target_proc:
            ok, _ = _run_subcommand(["pkill", "-x", target_proc])
            if ok:
                with _process_lock:
                    if _last_launched_process == target_proc:
                        _last_launched_process = None
                return True, f"Closed {target_proc}."

        # 3. Find any running known desktop application
        known_candidates = [
            "firefox", "google-chrome", "chrome", "chromium", "vlc",
            "thunar", "nautilus", "gnome-calculator", "kcalc",
            "mousepad", "gedit", "xfce4-terminal", "gnome-terminal",
            "code", "telegram-desktop", "spotify", "soffice.bin", "brave-browser", "msedge"
        ]
        if shutil.which("pgrep"):
            for cand in known_candidates:
                ok, _ = _run_subcommand(["pgrep", "-x", cand])
                if ok:
                    _run_subcommand(["pkill", "-x", cand])
                    with _process_lock:
                        if _last_launched_process == cand:
                            _last_launched_process = None
                    return True, f"Closed {cand}."

        # Nothing was closed: say so (reporting success here made the voice answer "Closed" for nothing)
        return False, "No window or known app found to close."

    # 1. Try graceful window close if wmctrl is installed (X11)
    if shutil.which("wmctrl"):
        ok, _ = _run_subcommand(["wmctrl", "-c", proc_name])
        if ok:
            with _process_lock:
                if _last_launched_process == proc_name:
                    _last_launched_process = None
            return True, f"Gracefully closed {proc_name}."

    # 2. Standard pkill termination with fallbacks
    if not shutil.which("pkill"):
        return False, "'pkill' utility is missing."

    procs = [proc_name] + app_config.get("process_fallbacks", [])
    procs = [p for p in procs if p and isinstance(p, str)]

    closed_any = False
    for p in procs:
        ok, _ = _run_subcommand(["pkill", "-x", p])
        if ok:
            closed_any = True
            with _process_lock:
                if _last_launched_process == p:
                    _last_launched_process = None

    if closed_any:
        return True, f"Closed {proc_name}."
    return False, f"Could not close {proc_name} (process might not be running)."


# ---------------------------------------------------------
# File & Folder Management
# ---------------------------------------------------------
_FILE_MANAGERS = ("dolphin", "thunar", "nautilus", "nemo", "pcmanfm-qt", "pcmanfm", "caja")
_DESKTOP_FM = {"KDE": "dolphin", "XFCE": "thunar", "GNOME": "nautilus", "CINNAMON": "nemo",
               "MATE": "caja", "LXQT": "pcmanfm-qt", "LXDE": "pcmanfm"}


def _file_manager_cmd(path: str) -> list:
    """Command that shows `path` in a FILE MANAGER.

    Plain `xdg-open <folder>` opens whatever program is registered for "inode/directory". On a developer machine
    that is often an editor or a browser (real case: antigravity.desktop), so "open downloads" opened the wrong
    app. We use xdg-open only when the registered handler really is a file manager; otherwise we start one.
    SOUNDOS_FILE_MANAGER=<binary> forces a choice."""
    forced = os.environ.get("SOUNDOS_FILE_MANAGER", "").strip()
    if forced and shutil.which(forced):
        return [forced, path]
    try:
        out = subprocess.run(["xdg-mime", "query", "default", "inode/directory"], capture_output=True,
                             text=True, timeout=2).stdout.lower()
        if any(fm in out for fm in _FILE_MANAGERS) and shutil.which("xdg-open"):
            return ["xdg-open", path]
    except Exception:
        pass
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    preferred = [fm for key, fm in _DESKTOP_FM.items() if key in desktop]
    for fm in preferred + list(_FILE_MANAGERS):
        if shutil.which(fm):
            return [fm, path]
    return ["xdg-open", path]


def open_directory(folder_path_str: str) -> Tuple[bool, str]:
    """Open a folder in the file manager (see _file_manager_cmd)."""
    path = Path(os.path.expanduser(folder_path_str)).resolve()
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, f"Folder does not exist and could not be created: {exc}"

    return _spawn_detached(_file_manager_cmd(str(path)))


def create_user_file(filename: str = "new_file.txt") -> Tuple[bool, str]:
    """Create a new empty file inside ~/SoundOS_Files/.

    Rejects if file already exists (no overwrite).
    """
    clean_name = os.path.basename(filename).strip() if filename else "new_file.txt"
    if not clean_name:
        clean_name = "new_file.txt"

    if "/" in filename or "\\" in filename or ".." in filename or os.path.isabs(filename):
        return False, "Invalid filename: path traversal is not permitted."

    SAFE_FILES_DIR.mkdir(parents=True, exist_ok=True)
    target_file = SAFE_FILES_DIR / clean_name

    if target_file.exists():
        return False, f"File '{clean_name}' already exists."

    try:
        target_file.touch(exist_ok=False)
        return True, f"File '{clean_name}' created at {SAFE_FILES_DIR}."
    except Exception as exc:
        return False, f"Failed to create file: {exc}"


def delete_user_file(filename: str, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Safely delete file by sending it to trash via gio trash.
    Strictly sandboxed inside ~/SoundOS_Files/.
    """
    if not filename or "/" in filename or "\\" in filename or ".." in filename or os.path.isabs(filename):
        return False, "Invalid filename: path traversal is not permitted."

    target_file = SAFE_FILES_DIR / filename
    if not target_file.exists():
        return False, f"File '{filename}' does not exist in {SAFE_FILES_DIR}."

    if dry_run:
        return True, f"[DRY-RUN] Simulated trash deletion of {target_file}."

    if not shutil.which("gio"):
        return False, "'gio' utility is missing. Cannot safely trash file."

    ok, out = _run_subcommand(["gio", "trash", str(target_file)])
    if ok:
        return True, f"File '{filename}' moved to trash."
    return False, f"Trash deletion failed: {out}"


# ---------------------------------------------------------
# Web Search & Media
# ---------------------------------------------------------
def search_web(query: str, check_net: bool = True, budget_sec: float = 0.85) -> Tuple[bool, str]:
    """
    Open default browser with Google search.
    Follows CONTRACT.md §4: 'web_search needs internet; say so in the message if offline.'

    Args:
        query: Search query string
        check_net: Whether to check internet connectivity
        budget_sec: Remaining time budget for this operation (default 0.85s)
    """
    t0 = time.monotonic()
    clean_query = (query or "").strip()
    if not clean_query:
        return False, "Empty search query."

    if check_net and not check_internet_connection():
        return False, "offline"

    # Check remaining budget before launching browser
    elapsed = time.monotonic() - t0
    remaining = max(0.1, budget_sec - elapsed)

    encoded = urllib.parse.quote(clean_query)
    url = f"https://www.google.com/search?q={encoded}"
    return _spawn_detached(["xdg-open", url], timeout_sec=remaining)


def play_media_content(query: str = "", budget_sec: float = 0.85) -> Tuple[bool, str]:
    """Open media player or search online media.

    Args:
        query: Media search query (artist, song, etc.)
        budget_sec: Remaining time budget for this operation (default 0.85s)
    """
    t0 = time.monotonic()
    clean_query = (query or "").strip()
    if clean_query:
        # If user asked for a specific artist/song, open YouTube search if online
        if not check_internet_connection():
            return False, "offline"

        # Check remaining budget before launching browser
        elapsed = time.monotonic() - t0
        remaining = max(0.1, budget_sec - elapsed)

        encoded = urllib.parse.quote(clean_query)
        return _spawn_detached(["xdg-open", f"https://www.youtube.com/results?search_query={encoded}"], timeout_sec=remaining)
    else:
        # Default: open VLC / MPV / media player or music folder
        for player in ("vlc", "mpv", "totem", "celluloid"):
            if shutil.which(player):
                return _spawn_detached([player])
        return open_directory(str(Path.home() / "Music"))


# ---------------------------------------------------------
# System Actions (Shutdown)
# ---------------------------------------------------------
def system_shutdown(dry_run: bool = False) -> Tuple[bool, str]:
    """Safely shut down the system via systemctl."""
    if dry_run:
        return True, "[DRY-RUN] Simulated system shutdown."

    if not shutil.which("systemctl"):
        return False, "'systemctl' is not available."

    ok, out = _run_subcommand(["systemctl", "poweroff"])
    if ok:
        return True, "System powering off."
    return False, f"Shutdown command failed: {out}"
