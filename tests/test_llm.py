"""The one call to Ollama, with its fallbacks. requests is replaced; no model runs."""
import json
from types import SimpleNamespace

import llm
from helpers import fake_program, wait_until

SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}}


def answers(*replies):
    """A requests.post that answers in turn, and keeps what it was sent."""
    sent = []

    def post(url, json=None, timeout=None):
        sent.append(dict(json))
        code, body = replies[len(sent) - 1]
        return SimpleNamespace(status_code=code, text=body,
                               json=lambda: {"response": body},
                               raise_for_status=lambda: None)
    return post, sent


def test_a_model_without_structured_output_is_told_the_schema_instead(monkeypatch):
    post, sent = answers((501, '{"error":"structured output is unavailable"}'),
                         (200, 'Sure! {"title": "Sprint review"}'))
    monkeypatch.setattr(llm.requests, "post", post)

    assert llm.generate_json("Summarise.", SCHEMA, "qwen3.5:9b") == {"title": "Sprint review"}

    assert "format" in sent[0] and "format" not in sent[1]
    assert json.dumps(SCHEMA) in sent[1]["prompt"]


def test_a_model_with_structured_output_gets_the_schema_as_the_format(monkeypatch):
    post, sent = answers((200, '{"title": "x"}'))
    monkeypatch.setattr(llm.requests, "post", post)

    llm.generate_json("Summarise.", SCHEMA, "qwen3:14b")

    assert sent[0]["format"] == SCHEMA and len(sent) == 1


# ---------------------------------------------------------------- Ollama on demand

def test_the_model_is_found_on_disk_without_ollama_running(tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODELS", str(tmp_path))
    manifest = tmp_path / "manifests/registry.ollama.ai/library/qwen3.5/9b"
    assert not llm.model_on_disk("qwen3.5:9b")
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}")
    assert llm.model_on_disk("qwen3.5:9b")
    assert not llm.model_on_disk("qwen3.5:27b")


def test_an_ollama_the_app_started_is_stopped_again(tmp_path, monkeypatch):
    import subprocess
    import paths
    monkeypatch.setattr(paths, "DATA", tmp_path)
    fake = fake_program(tmp_path / "ollama",
                        "import time\nprint('serving', flush=True)\ntime.sleep(60)\n")
    monkeypatch.setattr(llm, "ollama_binary", lambda: str(fake))
    started = []
    real_popen = subprocess.Popen
    monkeypatch.setattr(llm.subprocess, "Popen",
                        lambda *a, **kw: started.append(a[0]) or real_popen(*a, **kw))
    monkeypatch.setattr(llm, "ollama_up", lambda: bool(started))     # up once started
    posted = []
    monkeypatch.setattr(llm.requests, "post", lambda *a, **kw: posted.append(kw["json"]))

    own = llm.Ollama()
    assert own.ensure(timeout=5)
    assert started == [[str(fake), "serve"]]
    proc = own.proc
    # What it says goes to a log, so a failed start can be read about later.
    assert wait_until(lambda: "serving" in (tmp_path / "logs" / "ollama.log").read_text())
    own.release()

    assert proc.poll() is not None, "the app's own Ollama is still running"
    assert posted == []                 # stopping it unloads everything anyway


def test_once_the_app_quits_a_cut_off_job_cannot_wake_a_new_ollama(tmp_path, monkeypatch):
    import subprocess
    import paths
    monkeypatch.setattr(paths, "DATA", tmp_path)
    fake = fake_program(tmp_path / "ollama", "import time\ntime.sleep(60)\n")
    monkeypatch.setattr(llm, "ollama_binary", lambda: str(fake))
    started = []
    real_popen = subprocess.Popen
    monkeypatch.setattr(llm.subprocess, "Popen",
                        lambda *a, **kw: started.append(a[0]) or real_popen(*a, **kw))
    own = llm.Ollama()
    # Up only while the process it started is alive, as with the real one.
    monkeypatch.setattr(llm, "ollama_up", lambda: bool(own.proc) and own.proc.poll() is None)
    assert own.ensure(timeout=5)
    proc = own.proc

    own.close()
    # The job whose request the quit cut off asks for Ollama again.
    assert not own.ensure(timeout=1)

    assert proc.poll() is not None
    assert len(started) == 1, "a new Ollama was started after the app quit"


def test_someone_elses_ollama_keeps_running_and_only_the_model_goes(monkeypatch):
    monkeypatch.setattr(llm, "ollama_up", lambda: True)
    posted = []
    monkeypatch.setattr(llm.requests, "post", lambda *a, **kw: posted.append(kw["json"]))

    other = llm.Ollama()
    assert other.ensure() and other.proc is None
    other.release()

    assert posted == [{"model": llm.MODEL, "keep_alive": 0}]


def test_without_ollama_installed_nothing_starts(monkeypatch):
    monkeypatch.setattr(llm, "ollama_up", lambda: False)
    monkeypatch.setattr(llm, "ollama_binary", lambda: "")
    assert not llm.Ollama().ensure()


def test_the_summary_is_markdown_without_what_the_notes_hold_elsewhere():
    raw = ("<think>hm</think>```markdown\n# Pricing\n- Price seen as too low\n"
           "  - raise to 949\n\n\n## Next steps\n- Filip changes the price\n"
           "### Ads\n- Meta ads: Jakov\n## Open questions and risks\n- who owns it\n```")
    assert llm.clean_summary(raw) == (
        "## Pricing\n- Price seen as too low\n  - raise to 949\n\n## Ads\n- Meta ads: Jakov")


def test_a_short_call_gets_a_short_summary_and_an_hour_a_long_one():
    assert llm.summary_size(300) == (1, 5)              # a few minutes
    assert llm.summary_size(1500) == (5, 25)            # twenty
    assert llm.summary_size(9000) == (6, 40)            # an hour


def test_the_summary_is_written_in_its_own_call_from_the_transcript_or_the_topics(monkeypatch):
    notes = json.dumps({"title": "Sync", "date": "", "participants": ["Anna"], "action_items": [],
                        "decisions": [], "assumptions": [], "open_questions": []})
    part = json.dumps({"topics": [{"topic": "Pricing", "points": ["too cheap"]}],
                       "action_items": [], "decisions": [], "quotes": [], "open_questions": []})
    turns = [("Anna", "We talk about pricing. " * 10)] * 3

    post, sent = answers((200, notes), (200, "## Pricing\n- too cheap"))
    monkeypatch.setattr(llm.requests, "post", post)
    out = llm.summarize(turns, {"source": "x.vtt", "date": ""}, model="m")
    assert out["summary"] == "## Pricing\n- too cheap" and out["title"] == "Sync"
    assert "format" in sent[0] and "format" not in sent[1]          # JSON, then free text
    assert "We talk about pricing" in sent[1]["prompt"]

    # A long call: parts first, then the notes, then the summary from the parts' topics.
    sizes = {"MAP_THRESHOLD_TOKENS": 10, "CHUNK_TOKENS": 80, "OVERLAP_TURNS": 0}
    monkeypatch.setattr(llm.paths, "number", lambda k: sizes.get(k, 0.2))
    post, sent = answers((200, part), (200, part), (200, part), (200, notes),
                         (200, "## Pricing\n- too cheap"))
    monkeypatch.setattr(llm.requests, "post", post)
    out = llm.summarize(turns, {"source": "x.vtt", "date": ""}, model="m")
    assert out["summary"] == "## Pricing\n- too cheap"
    assert "PART 1\n- Pricing\n  - too cheap" in sent[-1]["prompt"]
    assert "We talk about pricing" not in sent[-1]["prompt"]


def test_a_decision_that_is_a_task_goes_and_an_assumption_that_is_a_quote_too():
    notes = {
        "decisions": ["Release moves to 8 October", "Ivan hands load testing to Dima on Thursday"],
        "action_items": [{"owner": "Ivan", "task": "hand load testing to Dima",
                          "deadline": "Thursday"},
                         {"owner": "Me", "task": "send the contract", "deadline": None}],
        "assumptions": [
            {"statement": "Dima takes over load testing", "confidence": "high",
             "evidence_quote": "I'll talk to Dima and he takes over load testing"},
            *[{"statement": f"Guess {i} about the budget", "confidence": "low",
               "evidence_quote": "we'll see"} for i in range(5)]],
        "participants": ["Ivan", "Me"],
    }
    llm.tidy(notes, me="Yaroslav")
    assert notes["decisions"] == ["Release moves to 8 October"]
    assert [a["statement"] for a in notes["assumptions"]] == [
        "Guess 0 about the budget", "Guess 1 about the budget", "Guess 2 about the budget"]
    assert notes["action_items"][1]["owner"] == "Yaroslav"
    assert notes["participants"] == ["Ivan", "Yaroslav"]


def test_the_model_is_told_who_me_is(monkeypatch):
    prompts = []
    monkeypatch.setattr(llm, "generate_json", lambda p, s, m: prompts.append(p) or {"title": "t"})
    monkeypatch.setattr(llm, "generate_text", lambda p, m: "")
    monkeypatch.setenv("MY_NAME", "Yaroslav")
    llm.summarize([("Me", "hi"), ("Speaker 1", "hello")], {"source": "Call.vtt"}, model="m")
    assert '"Me" is Yaroslav, the person recording the call' in prompts[0]
