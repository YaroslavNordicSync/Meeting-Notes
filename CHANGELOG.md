# Changelog

What changed in each version of Meeting Notes, newest first. The reasons behind a change live in
its commit message; open problems live in the project note, not here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow the commit
messages: `v0.MINOR.PATCH`, MINOR for a feature or substantial change, PATCH for a fix.

## v0.15.1 — 2026-11-15
### Fixed
- A call cut off before its transcript was written — the app quit, crashed or was
  reinstalled right after the call — is transcribed and summarised at the next start,
  one at a time. A transcript that never reached the notes is summarised.
### Changed
- A call with no speech in it keeps an empty transcript as the mark that it is done.

## v0.15.0 — 2026-11-15
### Changed
- The summary is markdown now, laid out like Granola: a heading per topic, short bullets
  with who said it first, numbers and names as spoken. It is written in a model call of
  its own instead of as one field of the notes JSON.
- Long meetings note their topics part by part; the summary is written from those.
- The window shows the summary formatted (click it to edit the markdown); the email
  renders it the same way. Older prose summaries still read as before.

## v0.14.3 — 2026-11-15
### Fixed
- Quitting while notes were being written left an Ollama running on its own, and the
  Dock kept showing Meeting Notes as "Running in Background". Once the app quits, Ollama
  is stopped and nothing can start it again.

## v0.14.2 — 2026-11-13
### Fixed
- Plugging in headphones or connecting AirPods during a call no longer stops your side
  of the recording: the microphone is reopened on the new input by itself, and the gap
  is written as silence so the timing stays right.
- A microphone that goes quiet without notice is reopened every few seconds before it
  is reported as stopped.

## v0.14.1 — 2026-11-13
### Fixed
- The "Live call" item in the sidebar filled the whole list with a long red streak while
  recording; it is one row with a small dot again.
### Changed
- In Deleted, the per-item button is just *Delete* (it still asks "sure?").

## v0.14.0 — 2026-11-13
### Changed
- The window is redone white and blue, laid out like Granola: a sidebar with the record
  button, search and the meetings grouped by day, and the selected meeting's notes as a
  clean page, with its transcript as a second tab.
- A meeting's state is a dot in the list: blue waits to be sent, red failed.
- Settings, Deleted and + Import (files or a folder) sit at the foot of the sidebar; Deleted
  is a page with Restore, Delete for good and Empty now on it.
### Removed
- The night-sky background, the status panel (a job line and a warning show only when
  needed) and the filter chips above the list.

## v0.13.1 — 2026-11-13
### Added
- An archived item can be deleted for good right away: *delete for good* in its ⋯ menu,
  asked once more before it goes.
- *empty now* above the archive list removes everything in the archive at once, also
  after a second click. The history still remembers each meeting, so nothing is
  summarised again.

## v0.13.0 — 2026-11-12
### Changed
- After a call, the whole recording is transcribed again in one pass, in chunks of up to
  30 s cut at real pauses; that is the transcript that is kept. The live lines during the
  call are only a preview. If the second pass fails, the preview is kept.
- *Transcribe again* on a recording runs the same single pass instead of replaying the call.

## v0.12.4 — 2026-11-11
### Fixed
- A call in Russian came out partly in English (and an English one could have come out in
  Russian): the text hint from v0.10.2 held each side to the language of its first line, and
  Whisper translated instead. Now Whisper's own guess is kept when it is sure (0.8 or more),
  and an unsure line is written in the language that side has been speaking.

## v0.12.3 — 2026-11-11
### Added
- The live view's "names need the Accessibility permission" warning has an *open settings*
  button that opens that list in System Settings.

## v0.12.2 — 2026-11-11
### Added
- `./build.sh --make-identity`: a self-signed certificate in the login keychain, made once;
  builds are signed with it, so a rebuilt app keeps its Accessibility, microphone and system
  audio permissions. Without it builds stay ad-hoc, as before.

## v0.12.1 — 2026-11-11
### Fixed
- Without the Accessibility permission a call silently came out as *Them*: the window and a
  notification now say so during the call, and the names start as soon as it is given,
  without starting the recording again.

## v0.12.0 — 2026-11-11
### Added
- Names from Teams in a browser too (Chrome, Edge, Arc, Brave, Safari, Firefox): the
  recorder reads the window whose open tab is Teams. Teams must stay the open tab in its
  window; the window itself can be behind others.
- `logs/pipeline.log` notes, for each call, which app was read and how much of it.

## v0.11.1 — 2026-11-11
### Fixed
- Spotlight showed two Meeting Notes apps: `build.sh` now builds into `dist.noindex/`, which
  Spotlight skips, so only the installed app is found.

## v0.11.0 — 2026-11-07
### Added
- Real names for the other side of a Teams call: while recording, the helper reads Teams'
  window through the accessibility API (no screenshots) and notes who is shown speaking;
  after the call those names replace *Speaker N*, line by line, with the voice as fallback.
- The *Accessibility* permission is asked for on the first recording. Without it, or in
  other call apps, speakers stay *Speaker N*. What was seen is kept as `speaking.json`.

## v0.10.2 — 2026-11-04
### Fixed
- A recorded call no longer turns English into Russian or Japanese now and then: each line
  is transcribed with what that side said just before it, so Whisper keeps to the language.
- One person on the other side of a call is no longer split into a dozen speakers: another
  voice model (NeMo TitaNet, downloaded once, about 40 MB), a looser threshold, and a voice
  heard for less than ten seconds counts as a scrap of a real one, not a new person.

## v0.10.1 — 2026-11-04
### Changed
- Ollama runs only while there is work: the app no longer starts it on launch; the worker
  wakes it for a summary or the model download and, once the queue is empty, stops it (or,
  if it was already running, unloads the model). Quitting the app does the same.
- The status says Ollama is *asleep* rather than *down*; whether the model is downloaded is
  read from disk. A job that cannot wake Ollama says why; its output goes to `logs/ollama.log`.
### Fixed
- An Ollama that died after the app started was never started again; jobs waited for ever.

## v0.10.0 — 2026-11-01
### Added
- Transcripts from other apps: `.srt`, `.txt` and `.md` next to `.vtt` and `.docx`; Zoom,
  Google Meet, Otter and Markdown layouts, a time before or after the name, UTF-16 text.
  Subtitles that name nobody are one turn per cue; the watcher turns them down (a film?).
- *Process files…* takes several files, *or a whole folder…* a folder and its subfolders
  (checked like the watcher's, with no age limit), and files or folders can be dropped on
  the window. A toast says, file by file, what was queued, already there or turned down.
- Settings → *inbox* counts the files turned down, and *check again* re-reads them.

## v0.9.0 — 2026-11-01
### Changed
- One model, `qwen3.5:9b`: the model choice, `OLLAMA_MODEL` and the RAM thresholds are gone;
  settings and the menu only offer to download it when it is missing.
- Better notes from 9b: a task someone takes on themselves ("I'll send it tomorrow") becomes an
  action item; tasks are no longer repeated as decisions; a turned-down proposal is not a
  decision; "nobody knows yet" goes to open questions; tasks noted in several parts of a long
  meeting are merged. The model now writes action items before decisions.
- *archived* is its own place in the sidebar, under *meetings*.

## v0.8.0 — 2026-11-01
### Added
- Call detection: when Teams, Zoom or a browser starts using the microphone, a notification
  offers *Record*, and the window and the menu name the call. When the call app lets go of the
  microphone during a recording, it offers *Stop*. It never records or stops by itself.
- `mn-recorder --watch` reports which apps hold the microphone (Core Audio process objects,
  no permission needed). Settings → *calls* turns it off (`CALL_DETECT`).

## v0.7.1 — 2026-11-01
### Changed
- New app icon in the Microsoft 365 manner: on a light plate, a sheet of violet bands and an
  indigo tile with a white waveform. Drawn at build time by `assets/app_icon.swift`
  (CoreGraphics); the menu bar icon is unchanged.

## v0.7.0 — 2026-11-01
### Added
- After a call, the other side's voices are told apart (sherpa-onnx speaker diarization, about
  30 MB of models downloaded on first use): the transcript says Speaker 1, Speaker 2… instead of
  one "Them". One voice stays "Them".
- *Who is who* above a meeting's transcript: naming a voice replaces it everywhere in the notes
  and in the transcript, without running the model again.
### Changed
- The model is told that "Me" records the call and the speakers are unnamed, and to use a name
  only when the conversation gives it, as an assumption with the quote.
### Fixed
- The bundle's `CFBundleVersion` still said 0.5.0.

## v0.6.0 — 2026-11-01
### Added
- Recording a call: *Record the call* in the menu and the window. A Swift helper
  (`recorder/main.swift`, built into the app) records system audio through a Core Audio tap and
  the microphone into `recordings/<date time>/`, and warns when a stream delivers nothing.
- Live transcription: a local whisper.cpp server (`brew install whisper-cpp`, model downloaded on
  first use) turns both sides into text during the call, shown in the window's live view. Lines
  of mine that repeat theirs are dropped as echo.
- After the call the transcript is saved as a `.vtt` and summarised like a downloaded one; every
  meeting has a notes / transcript switch, and a recorded call can be transcribed again from its
  whole recording. A recording with nothing recognised still shows in the list.
- Delete: a meeting (notes and recording) moves to an archive, restorable, removed for good
  after a week, a month or 3 months (`ARCHIVE_DAYS`, in settings).
- The live view shows the sentence still being said, refreshed about every second, and replaces
  it with the final line at the pause. A meeting's actions (show in Finder, transcribe again,
  summarise again, delete) are in a menu: double-click or right-click it, or its ⋯.
### Fixed
- A model that cannot take a JSON schema (qwen3.5 on Ollama 0.40: "structured output is
  unavailable") is given the schema in the prompt instead of failing.
### Changed
- `build.sh` and `run.sh` compile the recorder with `swiftc`; the app asks for microphone and
  system audio permission the first time it records.

## v0.5.0 — 2026-10-31
### Added
- A main window: meeting list with search and status filters, the notes editor, Reprocess and
  Show transcript, Process a file…, settings (folder, watching, model, mail mode and account,
  recipients) and the job with a progress bar. React + Vite in `ui/`; a dithered night sky under one pane of glass.
- A Dock icon, an app menu with Edit (copy and paste work in the window), and *Open Meeting
  Notes* (⌘O) in the dropdown. The window opens at launch; the Dock icon reopens it.
### Changed
- The menu bar and the window act through one `Controller` (`controller.py`); the API gained
  state, settings, account, pick, folder, retry and reveal routes.
- `build.sh` and `run.sh` build the window with npm; Node.js is now a build requirement.

## v0.4.0 — 2026-10-31
### Added
- The parser reads old Teams `.vtt` / `.docx`, the current Teams `.docx` header, and
  speech-to-text exports with no speakers (`[start - end] text`); the model is told when nobody is named.
- Meetings left found or processing by a quit or a crash are queued again at start-up.
### Changed
- `main.py` split into `pipeline.py` (decide, summarise, the worker), `watcher.py` and the CLI.
  Importing a module no longer writes to the data folder. All settings and their defaults are
  in `paths.DEFAULTS`, which `.env.example` matches.
- The review window's API works by meeting, not by file path, and refuses other Host headers.
- Picking a failed or skipped file by hand summarises it. The fingerprint ignores punctuation.
### Removed
- `people.yaml` and its never-called recipient lookup; the `.env` mail password fallback.
### Fixed
- The same meeting as `.vtt` and `.docx` was summarised twice. `MIN_TURNS` and the other
  transcript-check settings in `.env` were ignored. A failed `codesign` no longer passes the build.

## v0.3.0 — 2026-10-06
### Added
- Settings ▸ Mail account…: email address, Gmail app password and a "Send test email" button.
  Gmail addresses imply smtp.gmail.com:465; `SMTP_HOST` / `SMTP_PORT` / `SMTP_FROM` still override.
- The mail password is stored in the macOS Keychain. A password left in `.env` is offered to be
  moved there once, at startup.
- Readable error for a rejected Gmail password, next to the server's own message.
### Changed
- `SMTP_PASSWORD` removed from `.env.example`.
- py2app build excludes `keyring.testing`, pytest, numpy and pygments (the bundle had grown to
  117 MB and lost its signature); `jaraco` modules are included by name.

## v0.2.0 — 2026-10-06
### Added
- History of meetings in `history.db`, keyed by a fingerprint of the conversation (speaker and
  text), not the file bytes. A meeting already seen is not summarised again.
- Statuses found → processing → ready → sent, plus failed and skipped. A job interrupted by Quit
  is queued again on the next start.
- Jobs wait for Ollama instead of failing when it is not running.
- Menu bar dropdown: status lines (Ollama, model, watched folder, current job and queue),
  Recent meetings with Open notes / Reprocess / Show transcript in Finder, Settings submenus
  (folder, model, mail mode, default recipients).
- CLI: `--parse-only` prints the fingerprint; `--once` refuses a known meeting unless `--force`.
### Changed
- One data folder for the app, `run.sh` and the CLI: `~/Library/Application Support/Meeting
  Notes`, overridable with `MEETING_NOTES_DATA`. Settings, notes and `people.yaml` are copied
  there once; nothing is overwritten.
- All paths and settings come from `paths.py` and are re-read after a change; no module keeps its
  own copy.
- The window shows one meeting only: editable notes, recipients and Send. Settings moved to the menu.
### Removed
- Moving transcripts into `processed/` and `failed/`: source files are never touched. `FAILED_DIR`.
- `Build Meeting Notes.command`.
### Fixed
- Edits to action items and assumptions in the window were not saved, and Send sent the unedited notes.
- Ollama was queried on the main thread every 20 s, which could freeze the menu.

## v0.1.2 — 2026-10-04
### Changed
- The watcher only detects stable files and queues them; a single worker runs the model, one job
  at a time, for watcher files and files picked by hand alike. Picking a file while busy queues it.
- Every menu, icon and notification update runs on the main thread.
### Fixed
- Changing a setting during processing started a second watcher on the same folder
  ("already scheduled").
- The window stopped refreshing after the first job.

## v0.1.1 — 2026-10-04
### Added
- pytest and ruff (`requirements-dev.txt`, `pyproject.toml`); parser tests moved to `tests/`.
### Removed
- Unused `UI_PORT` setting and two unused imports.

## v0.1.0 — 2026-09-23
### Added
- First version: folder watcher, Teams `.vtt` / `.docx` parser with a "is this a transcript"
  check, local Ollama summary with a JSON schema and map-reduce for long meetings, review window,
  Outlook draft or Gmail SMTP sending, menu bar app and py2app build.
