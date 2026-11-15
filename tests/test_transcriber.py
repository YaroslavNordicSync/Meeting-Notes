"""Live transcription without a microphone or a model: the audio is made up
here (tone bursts and silence), and Whisper is a function that says which
piece it was given.
"""
import math
import wave
from array import array

import parser as tparser
import transcriber
from helpers import wait_until
from transcriber import RATE, Heard, Line, Live, Segmenter, WavTail, echoes, is_speech


def tone(seconds, level=8000):
    return array("h", (int(level * math.sin(2 * math.pi * 220 * i / RATE))
                       for i in range(int(seconds * RATE))))


def quiet(seconds):
    return array("h", [0] * int(seconds * RATE))


def start_wav(path):
    """A WAV header the way a writer leaves it while still recording, with an
    extra chunk before the data, as Apple's writer adds one."""
    with open(path, "wb") as f:
        f.write(b"RIFF\x00\x00\x00\x00WAVE")
        f.write(b"fmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
                + (1).to_bytes(2, "little") + RATE.to_bytes(4, "little")
                + (RATE * 2).to_bytes(4, "little") + (2).to_bytes(2, "little")
                + (16).to_bytes(2, "little"))
        f.write(b"FLLR" + (6).to_bytes(4, "little") + b"\x00" * 6)
        f.write(b"data\x00\x00\x00\x00")


def append(path, samples):
    with open(path, "ab") as f:
        f.write(samples.tobytes())


# ---------------------------------------------------------------- reading

def test_a_growing_wav_is_read_from_where_it_left_off(tmp_path):
    path = tmp_path / "mic.wav"
    tail = WavTail(path)
    assert len(tail.read()) == 0                    # not there yet

    start_wav(path)
    append(path, array("h", [1, 2, 3]))
    assert list(tail.read()) == [1, 2, 3]
    with open(path, "ab") as f:                     # half a sample arrives first
        f.write(b"\x04")
    assert list(tail.read()) == []
    with open(path, "ab") as f:
        f.write(b"\x00\x05\x00")
    assert list(tail.read()) == [4, 5]


def test_utterances_are_cut_at_the_pauses(tmp_path):
    seg = Segmenter()
    pieces = seg.feed(quiet(1) + tone(2) + quiet(1) + tone(1.5) + quiet(1))
    assert len(pieces) == 2
    (s1, e1, _), (s2, e2, _) = pieces
    assert 0.6 <= s1 <= 1.0 and 3.0 <= e1 <= 3.9
    assert 3.6 <= s2 <= 4.0 and 5.5 <= e2 <= 6.4


def test_a_click_is_not_an_utterance_and_a_monologue_is_cut(tmp_path):
    assert Segmenter().feed(quiet(1) + tone(0.1) + quiet(2)) == []
    pieces = Segmenter().feed(tone(20))
    assert len(pieces) == 1 and pieces[0][1] - pieces[0][0] == 15


def test_the_last_utterance_is_kept_when_the_recording_stops():
    seg = Segmenter()
    assert seg.feed(quiet(0.5) + tone(1)) == []
    assert len(seg.flush()) == 1


# ---------------------------------------------------------------- what came out

def test_my_line_that_is_their_line_heard_again_is_an_echo():
    theirs = Line("them", 10, 14, "Давайте перенесём релиз на пятницу")
    assert echoes(Line("me", 10.2, 14.1, "давайте перенесем релиз на пятницу"), theirs)
    assert not echoes(Line("me", 10.2, 14.1, "I can take the migration"), theirs)
    assert not echoes(Line("me", 30, 34, "давайте перенесем релиз на пятницу"), theirs)


def test_what_whisper_says_over_silence_is_not_kept():
    for text in ("Thank you.", "[Music]", "(музыка)", "Продолжение следует...", "", "..."):
        assert not is_speech(text), text
    assert is_speech("Thank you, that works for me.")


# ---------------------------------------------------------------- a whole call

def test_a_call_becomes_a_transcript_the_pipeline_reads(tmp_path):
    """Them on system.wav, me on mic.wav — with their first sentence leaking
    into my microphone — growing while the call goes on."""
    said = {}

    def whisper(samples, usual):
        # Each burst is a different length; the length says which one it was.
        return Heard(said.get(round(len(samples) / RATE), "Thank you."), "english")

    system, mic = tmp_path / "system.wav", tmp_path / "mic.wav"
    start_wav(system)
    start_wav(mic)
    live = Live(tmp_path, transcribe=whisper)
    live.POLL = 0.05
    live.start()

    said.update({3: "Let's move the release to Friday", 2: "Who takes the migration?",
                 4: "I can take the migration",
                 # After the call their two sentences, a second apart, are one chunk.
                 6: "Let's move the release to Friday. Who takes the migration?"})
    append(system, quiet(1) + tone(2.4) + quiet(1))     # them
    append(mic, quiet(1) + tone(2.4, 2000) + quiet(1))  # their words, back through my mic
    assert wait_until(lambda: live.snapshot()["count"] >= 1)
    append(system, tone(1.4) + quiet(5.5))
    append(mic, quiet(1.4) + quiet(0.5) + tone(3.4) + quiet(1.6))

    transcript = live.finish()

    turns = tparser.parse(transcript).turns
    assert turns == [("Them", "Let's move the release to Friday. Who takes the migration?"),
                     ("Me", "I can take the migration")]


def test_a_silent_call_writes_only_an_empty_transcript_as_its_done_mark(tmp_path):
    start_wav(tmp_path / "system.wav")
    start_wav(tmp_path / "mic.wav")
    live = Live(tmp_path, transcribe=lambda s, u: Heard("Thank you.", "english"))
    live.start()
    assert live.finish() is None
    [mark] = tmp_path.glob("*.vtt")
    assert mark.read_text() == "WEBVTT\n"


def test_no_whisper_installed_keeps_the_recording_and_says_why(tmp_path, monkeypatch):
    monkeypatch.setattr(transcriber, "server_binary", lambda: "")
    live = Live(tmp_path)
    live.start()
    assert wait_until(lambda: live.snapshot()["status"] == "no transcription")
    assert "brew install whisper-cpp" in live.snapshot()["error"]
    live.finish()


def test_the_vtt_is_what_the_parser_expects():
    vtt = transcriber.to_vtt([Line("me", 61.5, 63.25, "a <b> & c")])
    assert "00:01:01.500 --> 00:01:03.250" in vtt
    assert "<v Me>a &lt;b&gt; &amp; c</v>" in vtt


def test_wav_bytes_is_a_wav_whisper_can_read(tmp_path):
    out = tmp_path / "x.wav"
    out.write_bytes(transcriber.wav_bytes(tone(0.5)))
    with wave.open(str(out)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getnframes()) == (RATE, 1, RATE // 2)


def test_words_show_while_they_are_said_and_the_line_takes_over_at_the_pause(tmp_path):
    start_wav(tmp_path / "system.wav")
    start_wav(tmp_path / "mic.wav")
    heard = {"text": "so we were thinking"}
    live = Live(tmp_path, transcribe=lambda samples, usual: Heard(heard["text"], "english"))
    live.POLL = 0.05
    live.start()

    append(tmp_path / "system.wav", quiet(0.5) + tone(2))       # still talking
    assert wait_until(lambda: live.snapshot()["partial"])
    snap = live.snapshot()
    assert snap["lines"] == []
    assert [(p["who"], p["text"]) for p in snap["partial"]] == [("them", "so we were thinking")]

    heard["text"] = "So we were thinking about Friday."
    append(tmp_path / "system.wav", quiet(1.5))                   # the pause
    assert wait_until(lambda: live.snapshot()["lines"])
    snap = live.snapshot()
    assert [line["text"] for line in snap["lines"]] == ["So we were thinking about Friday."]
    assert snap["partial"] == []
    live.finish()


def test_whisper_is_told_the_language_that_side_has_been_speaking(tmp_path):
    """Before a side's first line the other side's language; after it, its own."""
    said = {1: ("Мы выпускаем в пятницу.", "russian"), 2: ("And tell the client.", "english"),
            3: ("Хорошо.", "russian")}
    usual = {}

    def whisper(samples, language):
        text, spoken = said[round(len(samples) / RATE - 1)]
        usual[text] = language
        return Heard(text, spoken)

    for name, bursts in (("mic.wav", (1,)), ("system.wav", (2, 3))):
        start_wav(tmp_path / name)
        for seconds in bursts:      # far enough apart to stay separate chunks
            append(tmp_path / name, quiet(2) + tone(seconds) + quiet(2))
    Live(tmp_path, transcribe=whisper).finish_all()

    assert usual["Мы выпускаем в пятницу."] == ""           # nobody has spoken yet
    assert usual["And tell the client."] == "russian"       # theirs, from my line
    assert usual["Хорошо."] == "english"                     # their own last line


class Server:
    """whisper.cpp's /inference, answering each language it is asked for."""

    def __init__(self, monkeypatch, answers):
        self.asked = []
        self.answers = answers

        class Reply:
            def __init__(self, body):
                self.body = body

            def raise_for_status(self):
                pass

            def json(self):
                return self.body

        def post(url, files, data, timeout):
            self.asked.append(data["language"])
            return Reply(self.answers[data["language"]])

        monkeypatch.setattr(transcriber.requests, "post", post)
        monkeypatch.setenv("WHISPER_LANGUAGE", "auto")


def test_an_unsure_guess_gives_way_to_the_usual_language(monkeypatch):
    """The founder call: English, with a Russian accent, heard as Russian at 0.5."""
    server = Server(monkeypatch, {
        "auto": {"text": " Мы говорим", "language": "russian",
                 "detected_language_probability": 0.51},
        "english": {"text": " we were\n saying", "language": "english"}})

    heard = transcriber.WhisperServer().transcribe(tone(1), "english")

    assert heard == Heard("we were saying", "english")
    assert server.asked == ["auto", "english"]


def test_a_sure_guess_is_a_real_switch_of_language(monkeypatch):
    server = Server(monkeypatch, {
        "auto": {"text": "Давайте по-русски", "language": "russian",
                 "detected_language_probability": 0.99}})

    heard = transcriber.WhisperServer().transcribe(tone(1), "english")

    assert heard == Heard("Давайте по-русски", "russian")
    assert server.asked == ["auto"], "asked twice for a language it was sure of"


def test_the_first_line_takes_whatever_whisper_heard(monkeypatch):
    Server(monkeypatch, {"auto": {"text": "Hi", "language": "english",
                                  "detected_language_probability": 0.4}})
    assert transcriber.WhisperServer().transcribe(tone(1)) == Heard("Hi", "english")


# ---------------------------------------------------------------- after the call

def test_utterances_a_short_pause_apart_are_one_chunk_up_to_thirty_seconds():
    pieces = [(0, 5, None), (5.5, 14, None), (14.2, 29, None), (29.3, 35, None),
              (40, 42, None)]
    assert transcriber.chunks(pieces) == [[0, 29], [29.3, 35], [40, 42]]


def test_the_whole_call_is_transcribed_again_and_its_sentences_kept_apart(tmp_path):
    """The preview heard pieces; after the call Whisper hears the whole chunk
    and splits it into its own sentences, with their times."""
    def whisper(samples, usual):
        if round(len(samples) / RATE) == 6:       # the chunk after the call
            return Heard("We ship Friday. Who migrates?", "english",
                         [(0.2, 2.5, "We ship Friday."), (3.6, 5.0, "Who migrates?")])
        return Heard("we ship", "english")        # what the preview heard

    start_wav(tmp_path / "mic.wav")
    start_wav(tmp_path / "system.wav")
    live = Live(tmp_path, transcribe=whisper)
    live.POLL = 0.05
    live.start()
    append(tmp_path / "system.wav", quiet(1) + tone(2.4) + quiet(1) + tone(1.4) + quiet(5.5))
    assert wait_until(lambda: live.snapshot()["count"] >= 1)

    vtt = live.finish()

    assert [(line["start"], line["text"]) for line in live.snapshot()["lines"]] == [
        (0.95, "We ship Friday."), (4.35, "Who migrates?")]
    assert "we ship" not in vtt.read_text()


def test_a_failed_second_pass_keeps_the_preview(tmp_path):
    start_wav(tmp_path / "mic.wav")
    start_wav(tmp_path / "system.wav")
    live = Live(tmp_path, transcribe=lambda s, u: Heard("We ship Friday.", "english"))
    live.lines = [Line("them", 0, 2, "We ship Friday.")]

    def broken():
        raise RuntimeError("the speech model went away")

    live._final = broken
    vtt = live.finish()

    assert tparser.parse(vtt).turns == [("Them", "We ship Friday.")]
