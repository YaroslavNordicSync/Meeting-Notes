"""py2app build: python setup.py py2app   (build.sh is the friendlier way in)"""
from glob import glob

from setuptools import setup

APP = ["menubar.py"]

DATA_FILES = [
    # The React build; build.sh runs `npm run build` first.
    ("ui/dist", ["ui/dist/index.html"]),
    ("ui/dist/assets", glob("ui/dist/assets/*")),
    ("assets", ["assets/icon.png", "assets/icon-paused.png"]),
    ("prompts", ["prompts/map.md", "prompts/reduce.md", "prompts/summary.md"]),
    ("templates", ["templates/email.html"]),
    ("", [".env.example"]),
]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "assets/AppIcon.icns",
    "plist": {
        "CFBundleName": "Meeting Notes",
        "CFBundleDisplayName": "Meeting Notes",
        "CFBundleIdentifier": "local.meetingnotes.app",
        # The version of the commit it was built from: v0.MINOR.PATCH.
        "CFBundleShortVersionString": "0.18.0",
        "CFBundleVersion": "0.18.0",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        # The UI is served from 127.0.0.1, which needs an ATS exception.
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        "NSAppleEventsUsageDescription":
            "Meeting Notes creates the email draft in Outlook for you.",
        # Recording a call: the microphone is me, the system audio is everyone else.
        "NSMicrophoneUsageDescription":
            "Meeting Notes records your side of a call, to transcribe it on this Mac.",
        "NSAudioCaptureUsageDescription":
            "Meeting Notes records the other side of a call, to transcribe it on this Mac.",
    },
    # Traced automatically, but these are imported lazily or by name.
    "includes": ["paths", "parser", "llm", "mailer", "main", "pipeline", "watcher",
                 "controller", "recorder", "transcriber", "archive", "speakers", "calls",
                 "server", "window", "history", "menu", "notifications", "echo", "desktop",
                 "WebKit", "AppKit", "Foundation", "UserNotifications", "objc",
                 "PyObjCTools.AppHelper",
                 # jaraco is a namespace package, so py2app cannot take it whole.
                 "jaraco.classes.properties", "jaraco.context", "jaraco.functools"],
    "packages": ["rumps", "watchdog", "jinja2", "dotenv", "docx", "requests",
                 # Its own dylibs (onnxruntime) travel inside the package folder.
                 "sherpa_onnx",
                 # Its parser rules are loaded by name.
                 "markdown_it", "mdurl",
                 # The echo canceller's own needs; the canceller itself (livekit)
                 # and protobuf are namespace packages, copied in by build.sh.
                 "numpy", "aiofiles",
                 "certifi", "urllib3", "charset_normalizer", "idna",
                 # keyring finds its backends through entry points, which do not
                 # survive the bundle — mailer picks the macOS one by hand.
                 "keyring", "importlib_metadata"],
    # keyring ships test helpers that import pytest, which drags in pygments.
    # livekit and google (protobuf) are namespace packages py2app cannot take:
    # build.sh copies them in whole.
    "excludes": ["keyring.testing", "pytest", "_pytest", "pygments", "livekit", "google"],
}

setup(app=APP, data_files=DATA_FILES, options={"py2app": OPTIONS},
      setup_requires=["py2app"])
