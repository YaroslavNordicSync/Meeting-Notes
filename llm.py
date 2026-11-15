"""Local Ollama: the one model, map-reduce, schema-constrained JSON."""
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import requests

import paths

log = logging.getLogger("pipeline")

# "Ollama is not running" as opposed to "Ollama refused": a job that hits this is
# held and retried rather than marked failed.
UNREACHABLE = requests.exceptions.ConnectionError

# Settings are read when they are used, not at import: the model or the Ollama
# address can change in the menu while the app is running.
def url() -> str:
    return paths.setting("OLLAMA_URL").rstrip("/")


def timeout() -> int:
    return int(paths.number("REQUEST_TIMEOUT"))


# The one model. What has to fit in memory is the weights plus the KV cache for
# NUM_CTX: 14b at 32k context is ~12 GB resident and swaps on a 16 GB Mac
# (a three-turn file took three minutes instead of fifteen seconds), so the
# notes are written by 9b and the prompts are tuned for it. Check with
# `ollama ps`: anything but "100% GPU" in the PROCESSOR column means offload.
MODEL = "qwen3.5:9b"
ACTION_ITEM = {
    "type": "object",
    "properties": {
        "owner": {"type": "string"},
        "task": {"type": "string"},
        "deadline": {"type": ["string", "null"]},
    },
    "required": ["owner", "task", "deadline"],
}

# Everything in the notes but the summary, which is written apart, in markdown:
# a 9b model asked for prose inside a JSON string beside five other fields
# wrote a flat paragraph.
NOTES_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "date": {"type": "string"},
        "participants": {"type": "array", "items": {"type": "string"}},
        "action_items": {"type": "array", "items": ACTION_ITEM},
        "decisions": {"type": "array", "items": {"type": "string"}},
        "assumptions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "evidence_quote": {"type": "string"},
                },
                "required": ["statement", "confidence", "evidence_quote"],
            },
        },
        "open_questions": {"type": "array", "items": {"type": "string"}},
    },
    # The order is the order the model writes them in. Tasks come before
    # decisions: written the other way round, the tasks went into decisions and
    # were then left out of action_items.
    "required": [
        "title", "date", "participants", "action_items",
        "decisions", "assumptions", "open_questions",
    ],
}

MAP_SCHEMA = {
    "type": "object",
    "properties": {
        # What the fragment was about, point by point: the summary is built from these.
        "topics": {"type": "array", "items": {
            "type": "object",
            "properties": {"topic": {"type": "string"},
                           "points": {"type": "array", "items": {"type": "string"}}},
            "required": ["topic", "points"]}},
        "action_items": {"type": "array", "items": ACTION_ITEM},
        "decisions": {"type": "array", "items": {"type": "string"}},
        "quotes": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["topics", "action_items", "decisions", "quotes", "open_questions"],
}


# ---------------------------------------------------------------- environment

def ollama_up() -> bool:
    try:
        return requests.get(f"{url()}/api/tags", timeout=3).ok
    except Exception:
        return False


def ollama_binary() -> str:
    """Find the ollama executable.

    A bundled .app inherits a bare PATH from launchd, so `which` alone is not
    enough — the usual Homebrew locations are checked explicitly.
    """
    for candidate in ("/opt/homebrew/bin/ollama", "/usr/local/bin/ollama",
                      shutil.which("ollama")):
        if candidate and Path(candidate).exists():
            return candidate
    return ""


class Ollama:
    """Ollama, up only while there is work for it.

    The model takes about 8 GB of memory while it is loaded, so the worker
    calls `ensure` before a job and `release` once the queue is empty, and the
    app calls `release` when it quits. An Ollama someone else started (a
    terminal, brew services) is left running and only the model is unloaded;
    one the app started is stopped again. Its output goes to logs/ollama.log,
    so when it will not start or dies, the reason is there.
    """

    def __init__(self):
        self.proc = None
        self.closed = False
        self._lock = threading.Lock()

    def ensure(self, timeout: float = 60) -> bool:
        """Ollama answering, started if need be. False if it cannot be."""
        if ollama_up():
            return True
        exe = ollama_binary()
        if not exe:
            return False
        with self._lock:
            if self.closed:
                return False
            if self.proc is None or self.proc.poll() is not None:
                log.info("Starting Ollama")
                # The last run only: what matters is why it stopped or would not start.
                with open(paths.logs() / "ollama.log", "wb") as out:
                    self.proc = subprocess.Popen([exe, "serve"], stdout=out,
                                                 stderr=subprocess.STDOUT,
                                                 start_new_session=True)
            proc = self.proc
        deadline = time.time() + timeout
        while time.time() < deadline and proc.poll() is None:
            if ollama_up():
                return True
            time.sleep(0.5)
        log.error("Ollama did not start (see logs/ollama.log)")
        return False

    def release(self):
        """Give the memory back: stop our own Ollama, or unload the model."""
        with self._lock:
            proc, self.proc = self.proc, None
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()
            log.info("Stopped Ollama")
            return
        try:
            requests.post(f"{url()}/api/generate", json={"model": MODEL, "keep_alive": 0},
                          timeout=30)
        except requests.RequestException:
            pass                    # not running: nothing is loaded


    def close(self):
        """The app is quitting: stop it, and start nothing after this — a job cut
        off mid-request would otherwise wake a new Ollama that outlives the app."""
        with self._lock:
            self.closed = True
        self.release()


OLLAMA = Ollama()


def model_on_disk(name: str) -> bool:
    """Is the model downloaded? Read from Ollama's own folder, so it need not run."""
    base, _, tag = name.partition(":")
    parts = base.split("/")
    parts = ["registry.ollama.ai", "library"][:3 - len(parts)] + parts
    root = Path(os.environ.get("OLLAMA_MODELS") or Path.home() / ".ollama" / "models")
    return any((root / folder).joinpath(*parts, tag or "latest").is_file()
               for folder in ("manifests", "manifests-v2"))


def pull_model(name: str, progress_cb=None):
    """Download a model, reporting progress_cb(status, done_bytes, total_bytes)."""
    r = requests.post(f"{url()}/api/pull", json={"model": name, "stream": True},
                      stream=True, timeout=timeout())
    r.raise_for_status()
    for line in r.iter_lines():
        if not line:
            continue
        ev = json.loads(line)
        if ev.get("error"):
            raise RuntimeError(ev["error"])
        if progress_cb:
            progress_cb(ev.get("status", ""), ev.get("completed", 0), ev.get("total", 0))
    return True


# ---------------------------------------------------------------- generation

def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def _extract_json(text: str):
    text = _strip_think(text)
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON in the model response")
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unterminated JSON in the model response")


def with_schema(prompt: str, schema: dict) -> str:
    """The prompt, for a model that cannot be held to a schema: told it instead."""
    return (prompt + "\n\nAnswer with ONLY one JSON object, no prose and no code fence, "
            "matching this JSON schema:\n" + json.dumps(schema, ensure_ascii=False))


def generate_json(prompt: str, schema: dict, model: str) -> dict:
    """One /api/generate call constrained by a JSON schema, with a single retry.

    The schema goes in `format`, so Ollama restricts generation by grammar rather
    than asking the model nicely. Qwen3's thinking mode is switched off twice over:
    `think: false` and a /no_think suffix, because either one alone fails on some
    Ollama or model builds. A model without thinking support answers 400, which is
    handled by dropping the parameter and retrying.
    """
    payload = {
        "model": model,
        "prompt": prompt + "\n/no_think",
        "stream": False,
        "format": schema,
        "think": False,
        "options": {"num_ctx": int(paths.number("NUM_CTX")),
                    "temperature": paths.number("TEMPERATURE")},
    }
    endpoint, limit = f"{url()}/api/generate", timeout()
    last_err = None
    for attempt in (1, 2):
        r = requests.post(endpoint, json=payload, timeout=limit)
        if r.status_code == 400 and "think" in r.text.lower():
            payload.pop("think", None)   # model has no thinking mode
            r = requests.post(endpoint, json=payload, timeout=limit)
        if r.status_code == 501 and "structured output" in r.text.lower():
            # Some model and Ollama builds (qwen3.5 on Ollama 0.40) cannot be
            # constrained by a schema at all. The schema goes into the prompt
            # instead, and _extract_json reads what comes back.
            payload.pop("format", None)
            prompt = with_schema(prompt, schema)
            payload["prompt"] = prompt + "\n/no_think"
            r = requests.post(endpoint, json=payload, timeout=limit)
        r.raise_for_status()
        raw = r.json().get("response", "")
        try:
            return _extract_json(raw)
        except Exception as e:
            last_err = e
            payload["options"]["temperature"] = 0.0
            payload["prompt"] = (
                prompt + "\n\nReturn ONLY valid JSON matching the schema, "
                "no prose.\n/no_think")
    raise ValueError(f"model returned no valid JSON after 2 attempts: {last_err}")


def generate_text(prompt: str, model: str) -> str:
    """One /api/generate call for free text (the markdown summary), thinking off
    as in generate_json. Retried once, colder, if nothing usable comes back."""
    payload = {"model": model, "prompt": prompt + "\n/no_think", "stream": False,
               "think": False,
               "options": {"num_ctx": int(paths.number("NUM_CTX")),
                           "temperature": paths.number("TEMPERATURE")}}
    endpoint, limit = f"{url()}/api/generate", timeout()
    for _ in (1, 2):
        r = requests.post(endpoint, json=payload, timeout=limit)
        if r.status_code == 400 and "think" in r.text.lower():
            payload.pop("think", None)
            r = requests.post(endpoint, json=payload, timeout=limit)
        r.raise_for_status()
        text = clean_summary(r.json().get("response", ""))
        if text:
            return text
        payload["options"]["temperature"] = 0.0
    raise ValueError("the model wrote no summary")


# Sections the notes already have elsewhere; a summary that repeats them is cut there.
ELSEWHERE = re.compile(
    r"(next steps?|action items?|to.?dos?|decisions?|follow.?ups?|open questions?|"
    r"neste steg|oppgaver|beslutninger|åpne spørsmål|"
    r"следующие шаги|задачи|решения|открытые вопросы)\W*$", re.I)


def clean_summary(text: str) -> str:
    """The model's markdown as the notes keep it: no thinking, no code fence
    around it, headings at ## so they sit under the meeting's title, and none of
    the sections the notes hold apart (decisions, action items)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    text = re.sub(r"^```(?:markdown|md)?\s*\n(.*?)\n```$", r"\1", text, flags=re.S).strip()
    out, skipping = [], False
    for line in text.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading:
            skipping = bool(ELSEWHERE.match(heading.group(2).strip("*_ ").split(" и ")[0]
                                            .split(" and ")[0].split(" og ")[0]))
            if skipping:
                continue
            line = "## " + heading.group(2).strip()
        if not skipping:
            out.append(line.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def summary_size(words: int) -> tuple:
    """How long the summary should be, as numbers a 9b model can follow:
    (most sections, top-level bullets). A few minutes get one section, twenty
    about five, an hour six. Tighter than this, 9b ignores the numbers."""
    sections = 1 if words <= 400 else min(6, words // 500 + 2)
    return sections, max(3, min(40, words // 60))


# ---------------------------------------------------------------- map-reduce

def estimate_tokens(text: str) -> int:
    """Rough but good enough to compare against a threshold: ~3 chars per token."""
    return max(1, len(text) // 3)


def chunk_turns(turns, max_tokens=None, overlap=None):
    """Split on turn boundaries, never mid-sentence, with a small overlap.

    Cutting inside a sentence makes nonsense of both halves, and the model then
    invents meaning to fill the gap. The overlap keeps a decision voiced across
    a chunk boundary from falling between two chunks.
    """
    max_tokens = int(max_tokens if max_tokens is not None else paths.number("CHUNK_TOKENS"))
    overlap = int(overlap if overlap is not None else paths.number("OVERLAP_TURNS"))
    chunks, cur, cur_tokens = [], [], 0
    for turn in turns:
        t = estimate_tokens(f"{turn[0]}: {turn[1]}")
        if cur and cur_tokens + t > max_tokens:
            chunks.append(cur)
            cur = cur[-overlap:] if overlap else []
            cur_tokens = sum(estimate_tokens(f"{s}: {x}") for s, x in cur)
        cur.append(turn)
        cur_tokens += t
    if cur:
        chunks.append(cur)
    return chunks


def _prompt(name: str, **vars_) -> str:
    """Load a prompt and substitute {{PLACEHOLDER}}s.

    Plain str.replace rather than Jinja2: the prompts are full of curly braces
    from the JSON examples, which a template engine would trip over.
    """
    text = (paths.CODE / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    for k, v in vars_.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def topic_outline(notes: list) -> str:
    """The per-fragment topics as one outline, in the order they came up."""
    lines = []
    for part in notes:
        lines.append(f"PART {part['part']}")
        for t in part.get("topics") or []:
            lines.append(f"- {t.get('topic', '')}")
            lines += [f"  - {p}" for p in t.get("points") or []]
    return "\n".join(lines)


def summarize(turns, meta: dict, model: str = None, progress_cb=None) -> dict:
    """Turns -> the notes: NOTES_SCHEMA's fields, and `summary` in markdown."""
    from parser import UNKNOWN, speakers, to_text

    model = model or MODEL
    full = to_text(turns)
    named = [s for s in speakers(turns) if s != UNKNOWN]
    who = (", ".join(named) if meta.get("named", True) else
           "not named in this transcript. An owner is only a name spoken in the "
           "text; when nobody is named for a task, leave the owner empty.")
    if any(re.fullmatch(r"Speaker \d+|Them", s) for s in named):
        # A recorded call: "Me" is the user, the others are voices without names.
        who += (". \"Me\" is the person recording the call. \"Speaker N\" and \"Them\" are "
                "the other people, unnamed: when the conversation shows who one of them is "
                "(someone is called by name), use that name and add an assumption with the "
                "quote; otherwise keep the label.")
    meta_line = (f"File: {meta.get('source', '')}\n"
                 f"File date: {meta.get('date', '')}\n"
                 f"Speakers: {who}")

    def report(stage, i=0, n=0):
        if progress_cb:
            progress_cb(stage, i, n)

    sections, bullets = summary_size(len(full.split()))
    size = dict(SECTIONS=sections, BULLETS=bullets)
    if estimate_tokens(full) <= paths.number("MAP_THRESHOLD_TOKENS"):
        report("reduce", 1, 1)
        result = generate_json(
            _prompt("reduce", META=meta_line, NOTES="", TRANSCRIPT=full), NOTES_SCHEMA, model)
        report("summary", 1, 1)
        result["summary"] = generate_text(
            _prompt("summary", META=meta_line, TOPICS="", TRANSCRIPT=full, **size), model)
    else:
        chunks = chunk_turns(turns)
        notes = []
        for i, chunk in enumerate(chunks, 1):
            report("map", i, len(chunks))
            part = generate_json(
                _prompt("map", META=meta_line, PART_INDEX=i, TOTAL_PARTS=len(chunks),
                        CHUNK=to_text(chunk)), MAP_SCHEMA, model)
            notes.append({"part": i, **part})
        report("reduce", len(chunks), len(chunks))
        result = generate_json(
            _prompt("reduce", META=meta_line,
                    NOTES=json.dumps(notes, ensure_ascii=False, indent=2),
                    TRANSCRIPT=""), NOTES_SCHEMA, model)
        report("summary", len(chunks), len(chunks))
        result["summary"] = generate_text(
            _prompt("summary", META=meta_line, TOPICS=topic_outline(notes), TRANSCRIPT="",
                    **size), model)

    if not result.get("participants"):
        result["participants"] = named
    if not result.get("date"):
        result["date"] = meta.get("date", "")
    if not result.get("title"):
        result["title"] = meta.get("source", "Meeting")
    result["_meta"] = {"model": model, "source": meta.get("source", ""),
                       "turns": len(turns), "tokens_est": estimate_tokens(full)}
    return result
