"""Everything that differs between macOS, Windows and Linux, in one place.

The rest of the code asks this module and never looks at the platform itself.
macOS is the whole app; on Windows and Linux the core runs — watching a folder,
notes, email over SMTP, the window's server — and what is not built for them
yet says so instead of failing: recording a call, noticing one, Outlook drafts,
the file pickers.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

MAC = sys.platform == "darwin"
WINDOWS = sys.platform == "win32"
LINUX = not MAC and not WINDOWS

# The Swift helper records a call and notices one; Windows and Linux have none yet.
RECORDING = MAC
NOT_YET = "not available on this system yet"

ACCESSIBILITY_SETTINGS = ("x-apple.systempreferences:com.apple.preference.security"
                          "?Privacy_Accessibility")


def data_dir() -> Path:
    """Where the user's data lives, as each system expects it."""
    if MAC:
        return Path.home() / "Library" / "Application Support" / "Meeting Notes"
    if WINDOWS:
        roaming = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
        return Path(roaming) / "Meeting Notes"
    share = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(share) / "meeting-notes"


# Where a program usually is when it is not on the PATH — an app opened from
# Finder has no Homebrew in its PATH, and Ollama's Windows installer puts it in
# the user's own folder.
PLACES = {
    "ollama": ["/opt/homebrew/bin/ollama", "/usr/local/bin/ollama", "/usr/bin/ollama",
               os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama",
                            "ollama.exe")],
    "whisper-server": ["/opt/homebrew/bin/whisper-server", "/usr/local/bin/whisper-server",
                       "/usr/bin/whisper-server"],
}


def find(program: str) -> str:
    """The path of `program`, or "" when it is not installed."""
    for candidate in (shutil.which(program), *PLACES.get(program, [])):
        if candidate and Path(candidate).is_file():
            return candidate
    return ""


def reveal(path: Path):
    """Show a file in the system's file manager."""
    if MAC:
        subprocess.run(["open", "-R", str(path)], check=False)
    elif WINDOWS:
        subprocess.run(["explorer", f"/select,{path}"], check=False)
    else:
        subprocess.run(["xdg-open", str(Path(path).parent)], check=False)


def open_accessibility_settings():
    """The settings list that lets Meeting Notes read the call's names (macOS)."""
    if MAC:
        subprocess.run(["open", ACCESSIBILITY_SETTINGS], check=False)


# ------------------------------------------------------------------ file pickers

def _osa(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def ask_for_files(extensions) -> list:
    """Transcripts chosen in the system's dialog; [] when it was cancelled."""
    if not MAC:
        raise RuntimeError(f"Choosing files is {NOT_YET}: drop them on the window instead")
    types = ", ".join(f'"{ext[1:]}"' for ext in sorted(extensions))
    return _osa(f'set picked to choose file with prompt "Choose transcripts" of type {{{types}}} '
                'with multiple selections allowed\n'
                'set out to ""\n'
                'repeat with f in picked\n'
                '  set out to out & POSIX path of f & linefeed\n'
                'end repeat\n'
                'return out').splitlines()


def ask_for_folder(prompt: str = "Where transcripts arrive") -> str:
    """A folder chosen in the system's dialog; "" when it was cancelled."""
    if not MAC:
        raise RuntimeError(f"Choosing a folder is {NOT_YET}")
    return _osa(f'POSIX path of (choose folder with prompt "{prompt}")')
