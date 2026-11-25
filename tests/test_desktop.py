"""What differs between macOS, Windows and Linux. Each system's answer is checked
on any machine by switching desktop's flags; nothing is opened or shown."""
from pathlib import Path

import pytest

import desktop
import mailer
import recorder


def as_system(monkeypatch, name):
    monkeypatch.setattr(desktop, "MAC", name == "mac")
    monkeypatch.setattr(desktop, "WINDOWS", name == "windows")
    monkeypatch.setattr(desktop, "LINUX", name == "linux")
    monkeypatch.setattr(desktop, "RECORDING", name in ("mac", "windows"))
    monkeypatch.setattr(desktop, "NOTICING_CALLS", name == "mac")


def test_the_data_folder_is_where_each_system_keeps_it(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    as_system(monkeypatch, "mac")
    assert desktop.data_dir() == tmp_path / "Library" / "Application Support" / "Meeting Notes"
    as_system(monkeypatch, "windows")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert desktop.data_dir() == tmp_path / "Roaming" / "Meeting Notes"
    as_system(monkeypatch, "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert desktop.data_dir() == tmp_path / ".local" / "share" / "meeting-notes"


def test_a_program_is_found_on_the_path_or_where_it_usually_is(monkeypatch, tmp_path):
    usual = tmp_path / "ollama"
    usual.write_text("")
    monkeypatch.setattr(desktop.shutil, "which", lambda name: None)
    monkeypatch.setitem(desktop.PLACES, "ollama", [str(tmp_path / "nowhere"), str(usual)])
    assert desktop.find("ollama") == str(usual)
    assert desktop.find("not-a-program") == ""


@pytest.mark.parametrize("system, command", [
    ("mac", ["open", "-R", "{f}"]),
    ("windows", ["explorer", "/select,{f}"]),
    ("linux", ["xdg-open", "{d}"]),
])
def test_a_file_is_shown_in_each_systems_file_manager(monkeypatch, tmp_path, system, command):
    ran = []
    monkeypatch.setattr(desktop.subprocess, "run", lambda args, check: ran.append(args))
    as_system(monkeypatch, system)
    f = tmp_path / "a.vtt"
    desktop.reveal(f)
    assert ran == [[c.format(f=f, d=tmp_path) for c in command]]


def test_what_only_macos_has_yet_says_so_elsewhere(monkeypatch, temp_env):
    as_system(monkeypatch, "windows")
    with pytest.raises(RuntimeError, match="not available on this system yet"):
        desktop.ask_for_files({".vtt"})
    with pytest.raises(RuntimeError, match="not available on this system yet"):
        desktop.ask_for_folder()
    with pytest.raises(RuntimeError, match="choose SMTP"):
        mailer.create_outlook_draft("s", "<p>x</p>", ["a@b.c"])
    as_system(monkeypatch, "linux")
    with pytest.raises(RuntimeError, match="recording calls is not available"):
        recorder.Recorder().start()


def test_elsewhere_the_windows_toolkit_draws_the_pickers(monkeypatch):
    as_system(monkeypatch, "windows")
    asked = []

    class Picker:
        def files(self, extensions):
            asked.append(sorted(extensions))
            return ["C:\\a.vtt"]

        def folder(self, prompt):
            asked.append(prompt)
            return ""                   # cancelled

    monkeypatch.setattr(desktop, "PICKER", Picker())
    assert desktop.ask_for_files({".vtt", ".docx"}) == ["C:\\a.vtt"]
    assert desktop.ask_for_folder("Where") == ""
    assert asked == [[".docx", ".vtt"], "Where"]
