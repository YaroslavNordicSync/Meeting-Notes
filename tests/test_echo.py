"""Taking the call's echo out of the microphone. Synthetic sound only: noise
shaped like speech stands for both voices; nothing is recorded or played."""
from array import array

import numpy as np

import echo

RATE = 16000


def voice(seconds, seed):
    """Noise through a moving vowel-like filter, in syllables of random length
    with pauses between: enough like speech for the canceller."""
    rng = np.random.default_rng(seed)
    n = seconds * RATE
    out, at = np.zeros(n), 0
    while at < n:
        length = int(rng.uniform(0.12, 0.35) * RATE)
        f = rng.uniform(300, 2500)
        t = np.arange(length) / RATE
        vowel = np.cos(2 * np.pi * f * t[:64]) * np.hanning(64)
        tone = np.convolve(rng.standard_normal(length), vowel, "same")
        out[at:at + length] = (tone * np.hanning(length))[:n - at]
        at += length + int(rng.uniform(0.05, 0.3) * RATE)
    return out / (np.abs(out).max() + 1e-9) * 8000


def call(delay_ms, seconds=30):
    """(mic, system, my voice): the system's sound reaches the mic delay_ms late
    (negative: the mic's file runs ahead), quieter; they talk alone for the
    first 10 s, then I talk every other 4 s."""
    theirs = voice(seconds, 1)
    t = np.arange(seconds * RATE)
    mine = voice(seconds, 2) * ((t >= 10 * RATE) & (t // (4 * RATE) % 2 == 1))
    heard = np.roll(theirs, int(delay_ms * RATE / 1000)) * 0.3
    mic = np.clip(heard + mine, -32768, 32767).astype(np.int16)
    return array("h", mic.tobytes()), array("h", theirs.astype(np.int16).tobytes()), mine


def rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, float) ** 2)) + 1e-9)


def test_the_offset_is_found_whichever_file_runs_ahead():
    for delay in (26, 120, -89):
        mic, system, _ = call(delay)
        assert abs(echo.offset(mic, system) - delay * RATE // 1000) <= 2


def test_their_voice_goes_and_mine_stays():
    for delay in (26, -89):
        mic, system, mine = call(delay)
        out = np.frombuffer(echo.cancel(mic, system), np.int16).astype(float)
        before = np.frombuffer(mic, np.int16).astype(float)
        theirs_only = mine == 0
        theirs_only[:5 * RATE] = False                  # the canceller learns at first
        me = mine != 0
        assert len(out) == len(before)
        assert rms(out[theirs_only]) < rms(before[theirs_only]) / 5, f"echo left at {delay} ms"
        assert rms(out[me]) > rms(before[me]) / 2, f"my voice lost at {delay} ms"


def test_too_short_to_measure_is_left_in_place():
    assert echo.offset(array("h", [0] * 100), array("h", [0] * 100)) == 0
