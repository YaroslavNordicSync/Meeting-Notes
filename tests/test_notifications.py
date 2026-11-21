"""Notifications and the buttons on a call offer. Nothing is shown: outside the
app bundle the notifier falls back to osascript, which is replaced here."""
from types import SimpleNamespace

import pytest

pytest.importorskip("rumps", reason="the menu bar and its notifications are macOS only")

import menubar  # noqa: E402
import notifications  # noqa: E402


def test_outside_the_app_it_falls_back_to_a_plain_notification(monkeypatch):
    ran = []
    monkeypatch.setattr(notifications.subprocess, "run", lambda args, **kw: ran.append(args))
    notifier = notifications.Notifier(lambda kind, action: None)
    notifier.start()                        # a test run is no app bundle: nothing to ask
    assert notifier.center is None

    notifier.post('Notes ready', 'The "Q4" sync', kind="record")

    assert ran and ran[0][0] == "osascript" and ran[0][-2:] == ["Notes ready", 'The "Q4" sync']


def test_the_offer_buttons_record_stop_or_drop_it_and_a_click_opens_the_window():
    done = []
    app = SimpleNamespace(
        app=SimpleNamespace(call={"offer": "record"}, dismiss_call=lambda: done.append("dismiss")),
        window=SimpleNamespace(show=lambda: done.append("window")),
        toggle_recording=lambda sender: done.append("toggle"))
    act = lambda kind, action: menubar.TranscriptApp.notification_action(app, kind, action)  # noqa: E731

    act("record", "record")
    act("record", notifications.DISMISSED)
    act("", notifications.OPEN)
    assert done == ["toggle", "dismiss", "window"]

    # An offer that has gone since (the call ended, or recording started by hand)
    # is not acted on from an old notification.
    done.clear()
    act("stop", "stop")
    act("", notifications.DISMISSED)
    assert done == []
