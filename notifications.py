"""Notifications through UserNotifications, the API macOS shows today.

rumps posts through NSUserNotification, deprecated since macOS 11: current macOS
drops its banners without a word, so the offers to record a call were made and
never seen. Here macOS asks once whether Meeting Notes may notify, and an offer
carries its own buttons (Record / Not now, Stop / Keep going).

A run from source is not an app bundle, and UserNotifications refuses to work
without one: it falls back to osascript, with no buttons; the window still
shows every offer.
"""
import logging
import subprocess
import uuid

import objc
from Foundation import NSBundle, NSObject

log = logging.getLogger("pipeline")

# An offer's kind -> its buttons, (action id, title). The first one does it; none
# brings the app to the front, a call is going on.
OFFERS = {"record": (("record", "Record"), ("dismiss", "Not now")),
          "stop": (("stop", "Stop"), ("keep", "Keep going"))}
OPEN = "open"            # the notification itself was clicked
DISMISSED = "dismiss"    # closed with its ✕, or "Not now"


APP_ID = "local.meetingnotes.app"       # setup.py's CFBundleIdentifier


def bundled() -> bool:
    """Running as Meeting Notes.app — not merely inside some bundle: Python
    itself is one (org.python.python) when run from source."""
    return NSBundle.mainBundle().bundleIdentifier() == APP_ID


def _osascript(title: str, message: str):
    # The text goes in as arguments, so no quote in a file name can break it.
    subprocess.run(["osascript", "-e", "on run argv",
                    "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
                    "-e", "end run", title, message], capture_output=True)


class _Delegate(NSObject):
    """What macOS calls back: a button pressed, or a notification about to show."""

    def initWithHandler_(self, handler):
        self = objc.super(_Delegate, self).init()
        self.handler = handler
        return self

    def userNotificationCenter_didReceiveNotificationResponse_withCompletionHandler_(
            self, center, response, done):
        import UserNotifications as UN
        action = str(response.actionIdentifier())
        if action == UN.UNNotificationDefaultActionIdentifier:
            action = OPEN
        elif action == UN.UNNotificationDismissActionIdentifier:
            action = DISMISSED
        kind = str(response.notification().request().content().categoryIdentifier() or "")
        try:
            self.handler(kind, action)
        except Exception as e:
            log.error("Notification action failed: %s", e)
        done()

    def userNotificationCenter_willPresentNotification_withCompletionHandler_(
            self, center, notification, done):
        # Shown even while the app is in front, which is when an offer matters most.
        import UserNotifications as UN
        done(UN.UNNotificationPresentationOptionBanner | UN.UNNotificationPresentationOptionList
             | UN.UNNotificationPresentationOptionSound)


class Notifier:
    def __init__(self, on_action):
        """on_action(kind, action): kind is "record", "stop" or "" for a plain
        notification; action is a button's id, OPEN or DISMISSED. Called on
        whatever thread macOS picks."""
        self.center = None
        self.delegate = _Delegate.alloc().initWithHandler_(on_action)

    def start(self):
        """Ask for permission (macOS asks the user only the first time) and
        register the offers' buttons. Main thread."""
        if not bundled():
            log.info("Notifications: not an app bundle, falling back to osascript")
            return
        import UserNotifications as UN
        self.center = UN.UNUserNotificationCenter.currentNotificationCenter()
        self.center.setDelegate_(self.delegate)
        categories = set()
        for kind, buttons in OFFERS.items():
            actions = [UN.UNNotificationAction.actionWithIdentifier_title_options_(ident, title, 0)
                       for ident, title in buttons]
            categories.add(UN.UNNotificationCategory
                           .categoryWithIdentifier_actions_intentIdentifiers_options_(
                               kind, actions, [],
                               UN.UNNotificationCategoryOptionCustomDismissAction))
        self.center.setNotificationCategories_(categories)
        self.center.requestAuthorizationWithOptions_completionHandler_(
            UN.UNAuthorizationOptionAlert | UN.UNAuthorizationOptionSound,
            lambda granted, error: log.info(
                "Notifications: %s", "allowed" if granted else
                f"not allowed ({error})" if error else
                "not allowed — turn them on in System Settings › Notifications"))

    def post(self, title: str, message: str, kind: str = ""):
        """A notification; with kind "record" or "stop", one with that offer's buttons."""
        if self.center is None:
            _osascript(title, message)
            return
        import UserNotifications as UN
        content = UN.UNMutableNotificationContent.alloc().init()
        content.setTitle_(title)
        content.setBody_(message)
        content.setCategoryIdentifier_(kind)
        if kind:
            content.setSound_(UN.UNNotificationSound.defaultSound())
        request = UN.UNNotificationRequest.requestWithIdentifier_content_trigger_(
            str(uuid.uuid4()), content, None)
        self.center.addNotificationRequest_withCompletionHandler_(
            request, lambda error: error and log.error("Notification not shown: %s", error))
