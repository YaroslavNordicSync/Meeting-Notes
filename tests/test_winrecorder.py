"""The Windows recorder's logic, with fake devices and a fake clock: nothing is
recorded, on any system. Only soundcard itself — talking to WASAPI — is left
for a real call on Windows."""
import json
import threading
import wave

import numpy as np

import winrecorder


class Device:
    """A device that hands over a steady tone, `per_read` frames at a time, and
    raises once it is unplugged."""

    def __init__(self, value, per_read=1600):
        self.value, self.per_read, self.unplugged = value, per_read, False

    def recorder(self, samplerate, channels, blocksize):
        device = self

        class Rec:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def record(self, numframes):
                if device.unplugged:
                    raise RuntimeError("device invalidated")
                return np.full((device.per_read, 1), device.value, dtype="float32")
        return Rec()


class Source:
    """Windows' default device, which a test can switch."""

    def __init__(self, *devices):
        self.devices = {f"dev{i}": d for i, d in enumerate(devices)}
        self.current = "dev0" if devices else None

    def default(self):
        if self.current is None:
            raise RuntimeError("no device")
        return self.current, self.devices[self.current]


def run(monkeypatch, tmp_path, system, mic, seconds=6.0, step=0.1, during=None):
    """Record on a clock that moves `step` seconds a look; `during(t)` changes
    the devices as it goes. Returns (status, events)."""
    stopped, now, lines = threading.Event(), [1000.0], []

    def clock():
        now[0] += step
        t = now[0] - 1000.0
        if during:
            during(t)
        if t >= seconds:
            stopped.set()
        return now[0]

    monkeypatch.setattr(winrecorder, "say", lambda **e: lines.append(json.loads(json.dumps(e))))
    monkeypatch.setattr(winrecorder.time, "sleep", lambda _s: None)
    return winrecorder.record(tmp_path, system, mic, stopped, clock=clock), lines


def frames(path):
    with wave.open(str(path)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        return np.frombuffer(w.readframes(w.getnframes()), "<i2")


def test_both_streams_become_16_khz_mono_files_and_recorder_py_events(monkeypatch, tmp_path):
    status, events = run(monkeypatch, tmp_path, Source(Device(0.5)), Source(Device(0.25)))
    assert status == 0
    kinds = [e["event"] for e in events]
    assert kinds[0] == "started" and kinds[-1] == "stopped" and "level" in kinds
    assert events[0]["mic"] == {"rate": 16000, "channels": 1}
    level = next(e for e in events if e["event"] == "level")
    assert level["system"] == 0.5 and level["mic"] == 0.25 and level["mic_frames"] > 0
    system, mic = frames(tmp_path / "system.wav"), frames(tmp_path / "mic.wav")
    assert len(system) and set(system) == {16383}
    assert len(mic) and set(mic) == {8191}


def test_headphones_plugged_in_move_the_mic_and_keep_the_files_in_step(monkeypatch, tmp_path):
    built_in, headset = Device(0.25, per_read=160), Device(0.75, per_read=160)
    mic = Source(built_in, headset)

    def during(t):
        if t >= 2.0 and mic.current == "dev0":
            built_in.unplugged = True       # Windows drops the old one…
            mic.current = "dev1"            # …and makes the headset the default
    # The headset is reached only at the next look; the time between is silence.
    status, events = run(monkeypatch, tmp_path, Source(Device(0.5)), mic, seconds=8.0,
                         during=during)
    assert status == 0
    changed = [e for e in events if e["event"] == "mic_changed"]
    assert len(changed) == 1 and changed[0]["gap"] > 0
    samples = frames(tmp_path / "mic.wav")
    assert {0, 8191, 24575} <= set(samples)            # before, the gap, after
    gap_starts = int(np.argmax(samples == 0))
    assert samples[:gap_starts].tolist() == [8191] * gap_starts
    assert samples[-1] == 24575


def test_without_a_microphone_it_says_so_and_stops(monkeypatch, tmp_path):
    status, events = run(monkeypatch, tmp_path, Source(Device(0.5)), Source())
    assert status == 1
    assert events == [{"event": "error", "what": "no microphone to record from", "status": -1}]
