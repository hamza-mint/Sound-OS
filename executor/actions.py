"""
Sound OS - Executor Action Implementations (v2 Enhanced)
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


def _run_subcommand(args: list[str]) -> Tuple[bool, str]:
    """Run a command safely without shell=True."""
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
# Volume & Audio Controls (Supports PipeWire and PulseAudio)
# ---------------------------------------------------------
def adjust_volume(direction: str) -> Tuple[bool, str]:
    """
    Adjust volume up (+5%) or down (-5%).
    Senior UX enhancement: Automatically unmute when raising volume.
    Prefers wpctl (PipeWire) then pactl (PulseAudio).
    """
    delta = "+5%" if direction == "up" else "-5%"

    # 1. PipeWire / WirePlumber
    if shutil.which("wpctl"):
        if direction == "up":
            # Auto-unmute when raising volume
            _run_subcommand(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"])
        cmd = ["wpctl", "set-volume", "-l", "1.5", "@DEFAULT_AUDIO_SINK@", delta]
        ok, out = _run_subcommand(cmd)
        if ok:
            return True, "Volume adjusted."
        # If wpctl failed to talk to daemon, try pactl fallback

    # 2. PulseAudio fallback
    if shutil.which("pactl"):
        if direction == "up":
            # Auto-unmute when raising volume
            _run_subcommand(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
        cmd = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", delta]
        ok, out = _run_subcommand(cmd)
        if ok:
            return True, "Volume adjusted."
        return False, out

    return False, "Neither 'wpctl' nor 'pactl' is installed on this system."


def set_mute() -> Tuple[bool, str]:
    """Mutes the default audio sink."""
    if shutil.which("wpctl"):
        ok, out = _run_subcommand(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1"])
        if ok:
            return True, "Audio muted."

    if shutil.which("pactl"):
        ok, out = _run_subcommand(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"])
        if ok:
            return True, "Audio muted."
        return False, out

    return False, "Neither 'wpctl' nor 'pactl' is installed on this system."


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
        # Detect connected display name
        proc = subprocess.run(
            ["xrandr", "--current"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2,
        )
        display_name = None
        for line in proc.stdout.splitlines():
            if " connected" in line:
                display_name = line.split()[0]
                break

        if not display_name:
            return False, "No active connected display detected via xrandr."

        # Read current cached brightness
        curr_brightness = 1.0
        if BRIGHTNESS_STATE_FILE.exists():
            try:
                curr_brightness = float(BRIGHTNESS_STATE_FILE.read_text().strip())
            except Exception:
                curr_brightness = 1.0

        if direction == "up":
            new_brightness = min(1.0, round(curr_brightness + 0.1, 2))
        else:
            new_brightness = max(0.2, round(curr_brightness - 0.1, 2))

        ok, out = _run_subcommand(["xrandr", "--output", display_name, "--brightness", str(new_brightness)])
        if ok:
            try:
                BRIGHTNESS_STATE_FILE.write_text(str(new_brightness))
            except Exception:
                pass
            return True, f"Brightness set to {int(new_brightness * 100)}% via software."
        return False, out
    except Exception as exc:
        return False, str(exc)


def adjust_brightness(direction: str) -> Tuple[bool, str]:
    """
    Adjust display brightness up (+10%) or down (-10%).
    Tries hardware brightnessctl first; gracefully falls back to xrandr in VMs.
    """
    delta = "10%+" if direction == "up" else "10%-"
    if shutil.which("brightnessctl"):
        ok, out = _run_subcommand(["brightnessctl", "set", delta])
        if ok:
            return True, "Brightness adjusted."

    # VM Fallback: If hardware brightnessctl is missing or fails (common in VirtualBox/VMware)
    vm_ok, vm_out = _adjust_vm_xrandr_brightness(direction)
    if vm_ok:
        return True, vm_out

    return False, "Backlight hardware not found, and software brightness via xrandr failed."


# ---------------------------------------------------------
# Application Controls (Open / Graceful Close)
# ---------------------------------------------------------
def launch_app(app_config: Dict[str, Any]) -> Tuple[bool, str]:
    """Launch application as a detached background process."""
    cmd = app_config.get("cmd", [])
    if not cmd:
        return False, "No executable command configured for this application."
    return _spawn_detached(cmd)


def terminate_app(app_config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Terminate application gracefully.
    Senior UX enhancement: Try wmctrl -c first (Graceful close on X11),
    falling back to pkill -x.
    """
    proc_name = app_config.get("process")
    if not proc_name:
        return False, "No process name defined for this application."

    # 1. Try graceful window close if wmctrl is installed (X11)
    if shutil.which("wmctrl"):
        ok, _ = _run_subcommand(["wmctrl", "-c", proc_name])
        if ok:
            return True, f"Gracefully closed {proc_name}."

    # 2. Standard pkill termination
    if not shutil.which("pkill"):
        return False, "'pkill' utility is missing."

    ok, out = _run_subcommand(["pkill", "-x", proc_name])
    if ok:
        return True, f"Closed {proc_name}."
    return False, f"Could not close {proc_name} (process might not be running)."


# ---------------------------------------------------------
# File & Folder Management
# ---------------------------------------------------------
def open_directory(folder_path_str: str) -> Tuple[bool, str]:
    """Open folder in default file manager (Thunar / Nautilus) via xdg-open."""
    path = Path(os.path.expanduser(folder_path_str)).resolve()
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, f"Folder does not exist and could not be created: {exc}"

    return _spawn_detached(["xdg-open", str(path)])


def create_user_file(filename: str = "new_file.txt") -> Tuple[bool, str]:
    """Create a new empty file inside ~/SoundOS_Files/."""
    clean_name = os.path.basename(filename).strip() or "new_file.txt"
    if "/" in filename or ".." in filename:
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
    if not filename or "/" in filename or ".." in filename:
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
def search_web(query: str, check_net: bool = True) -> Tuple[bool, str]:
    """
    Open default browser with Google search.
    Follows CONTRACT.md §4: 'web_search needs internet; say so in the message if offline.'
    """
    if not query:
        return False, "Empty search query."

    if check_net and not check_internet_connection():
        return False, "offline"

    encoded = urllib.parse.quote(query)
    url = f"https://www.google.com/search?q={encoded}"
    return _spawn_detached(["xdg-open", url])


def play_media_content(query: str = "") -> Tuple[bool, str]:
    """Open media player or search online media."""
    if query:
        # If user asked for a specific artist/song, open YouTube search if online
        if check_internet_connection():
            encoded = urllib.parse.quote(query)
            return _spawn_detached(["xdg-open", f"https://www.youtube.com/results?search_query={encoded}"])
        music_dir = Path.home() / "Music"
        if music_dir.exists():
            return _spawn_detached(["xdg-open", str(music_dir)])
        return False, "offline"
    else:
        # Default: open VLC or music folder
        if shutil.which("vlc"):
            return _spawn_detached(["vlc"])
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
