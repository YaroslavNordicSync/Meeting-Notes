"""The Windows app's own pieces. The window and the tray can't be clicked in a
test; this is what can be checked without showing them."""
import sys
from types import SimpleNamespace

import pytest

if sys.platform != "win32":
    pytest.skip("the tray app is the Windows app", allow_module_level=True)

import tray  # noqa: E402
from helpers import wait_until  # noqa: E402
import parser as tparser  # noqa: E402
from webview.util import parse_file_type  # noqa: E402


def test_the_tray_icon_is_the_app_icon_faded_while_paused():
    watching, paused = (tray.tray_image(p).convert("RGBA") for p in (False, True))
    assert watching.size == paused.size == (64, 64)
    assert paused.getchannel("A").getextrema()[1] < watching.getchannel("A").getextrema()[1]


def test_the_pickers_ask_for_transcripts_and_report_a_cancel():
    asked = []

    class Window:
        def create_file_dialog(self, kind, **kw):
            asked.append((kind, kw))
            return None                             # cancelled

    picker = tray.Picker(Window())
    assert picker.files(tparser.EXTENSIONS) == []
    assert picker.folder("Where") == ""
    (_, opened), (folder_kind, _) = asked
    description, pattern = parse_file_type(opened["file_types"][0])
    assert sorted(pattern.split(";")) == sorted(f"*{e}" for e in tparser.EXTENSIONS)
    assert folder_kind == tray.webview.FileDialog.FOLDER


def test_closing_the_window_hides_it_until_quit():
    hidden = []
    app = SimpleNamespace(quitting=False, window=SimpleNamespace(hide=lambda: hidden.append(1)))
    assert tray.TrayApp.closing(app) is False
    assert wait_until(lambda: hidden == [1])
    app.quitting = True
    assert tray.TrayApp.closing(app) is True and hidden == [1]
