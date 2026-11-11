"""
Sound OS - Executor Action Implementations
Safe command execution for Ubuntu (X11 / Xorg).
Follows CONTRACT.md: No shell=True, safe argument lists, never raises exceptions.
"""
import os
import shutil
import socket
import subprocess
import urllib.parse
from pathlib import Path
from typing import Tuple, Dict, Any

SAFE_FILES_DIR = Path.home() / "SoundOS_Files"


def _run_subcommand(args: list[str]) -> Tuple[bool, str]:
    """Run a command safely without shell=True."""
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
            timeout=5,
        )
        if proc.returncode == 0:
            return True, proc.stdout.strip()
        err = proc.stderr.strip() or proc.stdout.strip()
        return False, err or f"Process exited with code {proc.returncode}."
    except Exception as exc:
        return False, str(exc)


def _spawn_detached(args: list[str]) -> Tuple[bool, str]:
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


def is_online(timeout: float = 0.3) -> bool:
    """Fast non-blocking check for network connectivity (CONTRACT.md §4)."""
    for host in ("1.1.1.1", "8.8.8.8"):
        try:
            with socket.create_connection((host, 53), timeout=timeout):
                return True
        except OSError:
            continue
    return False


# ---------------------------------------------------------
# Volume & Audio Controls (PipeWire, PulseAudio, and ALSA)
# ---------------------------------------------------------
def adjust_volume(direction: str) -> Tuple[bool, str]:
    """
    Adjust volume up (+5%) or down (-5%).
    Prefers wpctl (PipeWire), then pactl (PulseAudio), then amixer (ALSA).
    """
    delta = "+5%" if direction == "up" else "-5%"

    if shutil.which("wpctl"):
        cmd = ["wpctl", "set-volume", "-l", "1.5", "@DEFAULT_AUDIO_SINK@", delta]
        ok, out = _run_subcommand(cmd)
        if ok:
            return True, "Volume adjusted."

    if shutil.which("pactl"):
        cmd = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", delta]
        ok, out = _run_subcommand(cmd)
        if ok:
            return True, "Volume adjusted."

    if shutil.which("amixer"):
        # ALSA fallback
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
# Brightness Controls (brightnessctl)
# ---------------------------------------------------------
def adjust_brightness(direction: str) -> Tuple[bool, str]:
    """
    Adjust display brightness up (+10%) or down (-10%).
    Note: Virtual machines typically do not have a virtual backlight device.
    """
    delta = "10%+" if direction == "up" else "10%-"
    if not shutil.which("brightnessctl"):
        return False, "Utility 'brightnessctl' is not installed."

    ok, out = _run_subcommand(["brightnessctl", "set", delta])
    if ok:
        return True, "Brightness adjusted."
    return False, f"Brightness adjustment failed: {out}"


# ---------------------------------------------------------
# Application Controls (Open / Close)
# ---------------------------------------------------------
def launch_app(app_config: Dict[str, Any]) -> Tuple[bool, str]:
    """Launch application as a detached background process with fallback binaries."""
    candidates = [app_config.get("cmd", [])] + app_config.get("fallbacks", [])
    for c in candidates:
        if c and isinstance(c, list) and shutil.which(c[0]):
            return _spawn_detached(c)

    # If no alternative found, attempt primary cmd
    cmd = app_config.get("cmd", [])
    if not cmd:
        return False, "No executable command configured for this application."
    return _spawn_detached(cmd)


def terminate_app(app_config: Dict[str, Any]) -> Tuple[bool, str]:
    """Terminate application by process name using pkill with fallback names."""
    procs = [app_config.get("process")] + app_config.get("process_fallbacks", [])
    procs = [p for p in procs if p and isinstance(p, str)]
    if not procs:
        return False, "No process name defined for this application."

    if not shutil.which("pkill"):
        return False, "'pkill' utility is missing."

    closed_any = False
    for p in procs:
        ok, _ = _run_subcommand(["pkill", "-x", p])
        if ok:
            closed_any = True

    if closed_any:
        return True, f"Closed {procs[0]}."
    return False, f"Could not close {procs[0]} (process might not be running)."


# ---------------------------------------------------------
# File & Folder Management
# ---------------------------------------------------------
def open_directory(folder_path_str: str) -> Tuple[bool, str]:
    """Open folder in default file manager (Thunar / Nautilus / Dolphin) via xdg-open."""
    path = Path(os.path.expanduser(folder_path_str)).resolve()
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, f"Folder does not exist and could not be created: {exc}"

    return _spawn_detached(["xdg-open", str(path)])


def create_user_file(filename: str = "new_file.txt") -> Tuple[bool, str]:
    """Create a new empty file inside ~/SoundOS_Files/."""
    clean_name = os.path.basename(filename).strip() if filename else "new_file.txt"
    if not clean_name:
        clean_name = "new_file.txt"

    if "/" in filename or "\\" in filename or ".." in filename or os.path.isabs(filename):
        return False, "Invalid filename: path traversal is not permitted."

    SAFE_FILES_DIR.mkdir(parents=True, exist_ok=True)
    target_file = SAFE_FILES_DIR / clean_name

    try:
        target_file.touch(exist_ok=True)
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
def search_web(query: str) -> Tuple[bool, str]:
    """Open default browser with Google search (CONTRACT.md §4)."""
    clean_query = (query or "").strip()
    if not clean_query:
        return False, "Empty search query."

    if not is_online():
        return False, "No internet connection available."

    encoded = urllib.parse.quote(clean_query)
    url = f"https://www.google.com/search?q={encoded}"
    return _spawn_detached(["xdg-open", url])


def play_media_content(query: str = "") -> Tuple[bool, str]:
    """Open media player or default media folder."""
    clean_query = (query or "").strip()
    if clean_query:
        music_dir = Path.home() / "Music"
        if music_dir.exists():
            return _spawn_detached(["xdg-open", str(music_dir)])
        return search_web(f"play {clean_query}")
    else:
        # Default: open VLC / MPV / media player or music folder
        for player in ("vlc", "mpv", "totem", "celluloid"):
            if shutil.which(player):
                return _spawn_detached([player])
        music_dir = Path.home() / "Music"
        return _spawn_detached(["xdg-open", str(music_dir)])


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
