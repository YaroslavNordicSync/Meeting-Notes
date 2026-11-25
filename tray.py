"""The app on Windows (and Linux): the window and a tray icon.

menubar.py is the app on macOS; this is the same app elsewhere, on the same
Controller, server and page. The window is the page in the system's web view
(pywebview: Edge WebView2 on Windows), and closing it only hides it: the tray
icon keeps the app running and brings it back. Recording a call is not here yet.

Threads: pywebview owns the main thread; the tray runs in its own; the watcher,
the jobs and the server in theirs. pywebview's and pystray's calls can be made
from any of them.
"""
import threading

import pystray
import webview
from PIL import Image
from webview.dom import DOMEventHandler

import desktop
import main
import menu
import parser as tparser
import paths
import pipeline
import server
from controller import Controller

TITLE = "Meeting Notes"
WIDTH, HEIGHT = 1180, 780
MIN_SIZE = (820, 520)
PAPER = "#f6f8fb"                   # the sidebar's white, behind the page until it has drawn
BLUE = (37, 99, 235, 255)           # the tray icon: the menu bar icon's shape in the accent
PROBE_EVERY = 20                    # seconds between checks on Ollama


def tray_image(paused: bool) -> Image.Image:
    """The menu bar icon is black for macOS to tint; a tray can be light or
    dark, so here its shape is filled with the accent."""
    shape = Image.open(paths.CODE / "assets" / ("icon-paused.png" if paused else "icon.png"))
    image = Image.new("RGBA", shape.size, BLUE)
    image.putalpha(shape.convert("RGBA").getchannel("A"))
    return image


class Picker:
    """desktop.PICKER: the file dialogs, drawn by the window's toolkit."""

    def __init__(self, window):
        self.window = window

    def files(self, extensions) -> list:
        pattern = ";".join(f"*{ext}" for ext in sorted(extensions))
        chosen = self.window.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=True,
            file_types=(f"Transcripts ({pattern})",))
        return list(chosen or [])

    def folder(self, prompt: str) -> str:
        chosen = self.window.create_file_dialog(webview.FileDialog.FOLDER)
        return chosen[0] if chosen else ""


class TrayApp:
    def __init__(self):
        self.quitting = False
        self.stopped = threading.Event()
        self.app = Controller()
        self.app.on_change = self.changed
        self.app.on_notice = self.notify
        self.app.on_offer = lambda offer, app: None     # no recording here yet
        pipeline.WORKER.on_event = self.on_job_event

        url, _token, self.httpd = server.serve(self.app)
        self.window = webview.create_window(
            TITLE, url, width=WIDTH, height=HEIGHT, min_size=MIN_SIZE,
            background_color=PAPER)
        self.window.events.closing += self.closing
        self.window.events.loaded += self.loaded
        desktop.PICKER = Picker(self.window)

        self.icon = pystray.Icon("meeting-notes", tray_image(False), TITLE, pystray.Menu(
            pystray.MenuItem("Open Meeting Notes", lambda: self.show(), default=True),
            pystray.MenuItem("Process files…", self.pick_files),
            pystray.MenuItem("Watch the folder", self.toggle_watching,
                             checked=lambda _item: self.app.watching),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.quit)))

    def run(self):
        self.icon.run_detached()
        self.app.start()
        threading.Thread(target=self.probe_loop, name="probe", daemon=True).start()
        webview.start()             # returns once the window is destroyed
        self.shutdown()

    # ------------------------------------------------------------ the window

    def show(self, meeting: str = None):
        self.window.show()
        self.window.restore()
        if meeting:
            self.window.evaluate_js(f"window.openMeeting && window.openMeeting('{meeting}')")

    def closing(self):
        """The window's ✕ hides it; only Quit ends the app."""
        if self.quitting:
            return True
        self.window.hide()
        return False

    def loaded(self):
        """A page only gets a dropped file's contents, never where it is; pywebview
        knows the path, so the drop is taken here, as on macOS."""
        document = self.window.dom.document
        document.events.dragover += DOMEventHandler(lambda _e: None, prevent_default=True)
        document.events.drop += DOMEventHandler(self.dropped, prevent_default=True)

    def dropped(self, event):
        files = event.get("dataTransfer", {}).get("files", [])
        chosen = [f["pywebviewFullPath"] for f in files if f.get("pywebviewFullPath")]
        if chosen:
            # Read off this thread: a folder can hold hundreds. The page shows
            # what became of them.
            threading.Thread(target=self.app.import_files, args=(chosen,),
                             name="import", daemon=True).start()

    # ------------------------------------------------------------ the tray

    def changed(self):
        self.icon.icon = tray_image(not self.app.watching)
        self.icon.update_menu()

    def notify(self, title: str, message: str):
        self.icon.notify(message, title)

    def on_job_event(self, kind, target, payload):
        notice = menu.job_notice(kind, target, payload)
        if notice:
            self.notify(*notice)

    def pick_files(self):
        chosen = desktop.ask_for_files(tparser.EXTENSIONS)
        if not chosen:
            return
        results = self.app.import_files(chosen)["results"]
        failed = [r for r in results if r["outcome"] == "error"]
        if failed:
            self.notify("Could not read " + ", ".join(r["name"] for r in failed),
                        failed[0]["note"])
        elif len(results) == 1 and results[0]["notes"]:
            self.show(results[0]["meeting"])

    def toggle_watching(self):
        self.app.set_watching(not self.app.watching)

    def probe_loop(self):
        while not self.stopped.wait(PROBE_EVERY):
            self.app.probe()

    # ------------------------------------------------------------ quitting

    def quit(self):
        self.quitting = True
        self.window.destroy()       # webview.start() returns, and run() shuts down

    def shutdown(self):
        if self.stopped.is_set():
            return
        self.stopped.set()
        self.app.stop()
        self.httpd.shutdown()
        self.icon.stop()


def run():
    main.init()
    TrayApp().run()


if __name__ == "__main__":
    run()
