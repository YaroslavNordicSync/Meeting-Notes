"""The call recorder on Windows: what recorder/main.swift is on macOS.

    python winrecorder.py <folder> [<speaking pattern>]

The other people come from a WASAPI loopback of the default speakers (whatever
Windows plays), me from the default microphone, through the `soundcard`
library. Each goes to its own file, <folder>/system.wav and <folder>/mic.wav,
16 kHz mono 16-bit, and Python reads them while they grow, as on macOS.

It speaks the Swift helper's language — one JSON object a line on stdout,
"started", "level" about once a second, "mic_changed", "error", "stopped" — so
recorder.py cannot tell the two apart, and records until its stdin closes.
Plugging in headphones changes Windows' default devices: every few seconds it
looks, and moves to the new ones, filling the gap with silence so the two
files stay in step ("mic_changed", or "system_changed" for the speakers).

The speaking pattern (Teams names) is accepted and not used yet.
"""
import json
import sys
import threading
import time
import wave
from pathlib import Path

RATE = 16000
BUFFER = RATE // 2          # half a second of audio waits in Windows for each stream
CHECK_EVERY = 2.0           # seconds between looks at the default devices
LEVEL_EVERY = 1.0


def say(**event):
    print(json.dumps(event), flush=True)


class Stream:
    """One source into one file. `source` knows Windows' current default device
    (`default()` -> (id, device)); a device records through `recorder()`."""

    def __init__(self, name: str, folder: Path, source):
        self.name = name
        self.source = source
        self.file = wave.open(str(folder / f"{name}.wav"), "wb")
        self.file.setnchannels(1)
        self.file.setsampwidth(2)
        self.file.setframerate(RATE)
        self.written = 0            # frames in the file
        self.frames = 0             # frames since the last level
        self.peak = 0.0
        self.device_id = None
        self.rec = None

    def open(self) -> bool:
        """Record from the current default device. False when there is none."""
        self.close_device()
        try:
            self.device_id, device = self.source.default()
            self.rec = device.recorder(samplerate=RATE, channels=1, blocksize=BUFFER)
            self.rec.__enter__()
            return True
        except Exception:
            self.device_id, self.rec = None, None
            return False

    def close_device(self):
        if self.rec is not None:
            try:
                self.rec.__exit__(None, None, None)
            except Exception:
                pass
        self.rec = None

    def moved(self) -> bool:
        """Windows' default device is no longer the one being recorded."""
        try:
            return self.source.default()[0] != self.device_id
        except Exception:
            return self.device_id is not None

    def read(self):
        """Whatever has come in, into the file. Raises when the device is gone."""
        if self.rec is None:
            return
        data = self.rec.record(None)
        if len(data):
            self.write(data[:, 0])

    def write(self, samples):
        import numpy as np
        pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
        self.file.writeframes(pcm.tobytes())
        self.written += len(pcm)
        self.frames += len(pcm)
        if len(pcm):
            self.peak = max(self.peak, float(np.abs(samples).max()))

    def catch_up(self, seconds: float) -> float:
        """Silence for the time this stream was not recording; how long it was."""
        import numpy as np
        missing = int(seconds * RATE) - self.written
        if missing > 0:
            self.write(np.zeros(missing, dtype="float32"))
        return max(0, missing) / RATE

    def level(self) -> tuple:
        out = (round(self.peak, 3), self.frames)
        self.peak, self.frames = 0.0, 0
        return out

    def close(self):
        self.close_device()
        self.file.close()


def record(folder: Path, system, mic, stopped: threading.Event, clock=time.time) -> int:
    """Record until `stopped` is set. Returns the exit status."""
    streams = {"system": Stream("system", folder, system), "mic": Stream("mic", folder, mic)}
    for name, stream in streams.items():
        if not stream.open():
            say(event="error", what=f"no {'speakers' if name == 'system' else 'microphone'} "
                "to record from", status=-1)
            for s in streams.values():
                s.close()
            return 1
    start = clock()
    form = {"rate": RATE, "channels": 1}
    say(event="started", system=form, mic=form, at=start)
    last_check = last_level = start
    while not stopped.is_set():
        for stream in streams.values():
            try:
                stream.read()
            except Exception:
                stream.close_device()           # gone: taken up again at the next look
        now = clock()
        if now - last_check >= CHECK_EVERY:
            last_check = now
            for name, stream in streams.items():
                if (stream.rec is None or stream.moved()) and stream.open():
                    gap = stream.catch_up(now - start)
                    say(event=f"{name}_changed", rate=RATE, channels=1, gap=round(gap, 1))
        if now - last_level >= LEVEL_EVERY:
            last_level = now
            (system_peak, system_frames), (mic_peak, mic_frames) = (
                streams["system"].level(), streams["mic"].level())
            say(event="level", system=system_peak, mic=mic_peak,
                system_frames=system_frames, mic_frames=mic_frames)
        time.sleep(0.02)
    seconds = clock() - start
    for stream in streams.values():
        stream.close()
    say(event="stopped", seconds=round(seconds, 1))
    return 0


class Speakers:
    """Whatever Windows plays, as a microphone: the loopback of the default output."""

    def default(self):
        import soundcard
        speaker = soundcard.default_speaker()
        return speaker.id, soundcard.get_microphone(speaker.id, include_loopback=True)


class Microphone:
    def default(self):
        import soundcard
        mic = soundcard.default_microphone()
        return mic.id, mic


def main(argv) -> int:
    if len(argv) < 2:
        print("usage: winrecorder.py <folder> [<speaking pattern>]", file=sys.stderr)
        return 2
    folder = Path(argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    stopped = threading.Event()

    def until_stdin_closes():
        for _ in sys.stdin:
            pass
        stopped.set()

    threading.Thread(target=until_stdin_closes, daemon=True).start()
    return record(folder, Speakers(), Microphone(), stopped)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
