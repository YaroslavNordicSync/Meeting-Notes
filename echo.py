"""The others' voices taken out of my microphone, after the call.

On speakers, the microphone hears the call a second time, and their words came
back as mine. Both streams are recorded, so the sound that makes the echo is
known exactly: WebRTC's echo canceller (the one Chrome, Meet and Teams run,
through LiveKit's build) is given the system audio as the far end and takes it
back out of the microphone. It subtracts rather than mutes, so what I say over
them is kept.

The two files do not start at the same instant: the microphone was measured
both 26 ms behind the system audio and 89 ms ahead of it. The canceller looks
for an echo only after its cause, so the system audio is first moved to come
LEAD before the echo.

Only the transcription after the call uses this; mic.wav itself is never
changed.
"""
from array import array

RATE = 16000
FRAME = RATE // 100             # the canceller works on 10 ms frames
LEAD = RATE * 30 // 1000        # the system audio is lined up 30 ms ahead of its echo
SEARCH = RATE                   # an offset is looked for within ±1 s
MEASURE = 60 * RATE             # over the first minute


def offset(mic, system) -> int:
    """How many samples the echo in `mic` comes after its sound in `system`;
    negative when the microphone's file runs ahead."""
    import numpy as np
    n = min(len(mic), len(system), MEASURE)
    if n < SEARCH:
        return 0
    m, s = np.asarray(mic[:n], float), np.asarray(system[:n], float)
    size = 1 << (2 * n - 1).bit_length()
    corr = np.fft.irfft(np.fft.rfft(m, size) * np.conj(np.fft.rfft(s, size)), size)
    around = np.concatenate([corr[-SEARCH:], corr[:SEARCH]])     # lags -1 s .. +1 s
    return int(np.argmax(np.abs(around))) - SEARCH


def cancel(mic: array, system: array) -> array:
    """The microphone with the system audio's echo taken out, same length."""
    import numpy as np
    from livekit import rtc

    m = np.frombuffer(mic, np.int16)
    s = np.frombuffer(system, np.int16)
    shift = LEAD - offset(mic, system)          # move the system audio this much earlier
    far = np.zeros(len(m), np.int16)
    src = s[max(0, shift):]
    at = max(0, -shift)
    take = max(0, min(len(src), len(m) - at))
    far[at:at + take] = src[:take]

    apm = rtc.AudioProcessingModule(echo_cancellation=True, high_pass_filter=True)
    out = m.copy()
    for i in range(0, len(m) - FRAME + 1, FRAME):
        reverse = rtc.AudioFrame.create(RATE, 1, FRAME)
        np.frombuffer(reverse.data, np.int16)[:] = far[i:i + FRAME]
        apm.process_reverse_stream(reverse)
        frame = rtc.AudioFrame.create(RATE, 1, FRAME)
        np.frombuffer(frame.data, np.int16)[:] = m[i:i + FRAME]
        apm.process_stream(frame)
        out[i:i + FRAME] = np.frombuffer(frame.data, np.int16)
    return array("h", out.tobytes())
