import { useMemo, useState } from "react";
import { api, jobLine } from "./api.js";
import { Menu } from "./actions.jsx";
import { clock, useElapsed } from "./Live.jsx";

// Everything the list can hold, as one shape: a meeting, or a recording that
// never became one (nothing was recognised in it).
export function items(state) {
  const meetings = state.meetings.map((m) => ({
    key: m.hash, kind: "meeting", title: m.title, date: m.date, status: m.status, meeting: m }));
  const recordings = state.recordings.map((r) => ({
    key: `rec:${r.name}`, kind: "recording", title: r.title, date: r.date,
    status: r.status ? "transcribing" : "recorded", recording: r }));
  return [...meetings, ...recordings].sort((a, b) => (b.date || "").localeCompare(a.date || ""));
}

export const WORDS = { found: "Queued", processing: "Summarising", ready: "To send", sent: "Sent",
                       failed: "Failed", recorded: "Nothing recognised", transcribing: "Transcribing" };

// "Today", "Yesterday", "Mon 10 Nov", or "Earlier" for a date it cannot read.
export function dayGroup(value) {
  const d = /^\d{4}-\d{2}-\d{2}/.test(value || "") ? new Date(value.slice(0, 10) + "T00:00:00") : null;
  if (!d || isNaN(d)) return "Earlier";
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const days = Math.round((today - d) / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short",
                                         ...(d.getFullYear() !== today.getFullYear() && { year: "numeric" }) });
}

export default function Sidebar({ state, view, selected, open, openMenu, setView, pick, refresh, say }) {
  const [query, setQuery] = useState("");
  const [importAt, setImportAt] = useState(null);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const out = [];
    for (const item of items(state)) {
      if (q && !item.title.toLowerCase().includes(q)) continue;
      const label = dayGroup(item.date);
      if (out.at(-1)?.label !== label) out.push({ label, items: [] });
      out.at(-1).items.push(item);
    }
    return out;
  }, [state, query]);

  const rec = state.recording;
  const job = state.job;
  const problem = !state.ollama_installed ? "Ollama is not installed"
    : !state.model_ready ? "The notes model is not downloaded" : "";

  return (
    <aside className="side">
      <Record recording={rec} call={state.call} refresh={refresh} say={say} onStart={() => setView("live")} />
      <input className="search" placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} />

      <div className="list">
        {(rec.recording || rec.transcribing) && (
          <div className={`item live ${view === "live" ? "on" : ""}`} onClick={() => setView("live")}>
            <span className="title">{rec.recording ? "Live call" : "Last call"}</span>
            <span className="dot live" />
          </div>
        )}
        {groups.map((g) => (
          <div key={g.label}>
            <h4>{g.label}</h4>
            {g.items.map((i) => (
              <div key={i.key} title={WORDS[i.status] || i.status}
                   className={`item ${view === "meeting" && i.key === selected ? "on" : ""}`}
                   onClick={() => open(i.key)}
                   onDoubleClick={(e) => openMenu(i, e)} onContextMenu={(e) => openMenu(i, e)}>
                <span className="title">{i.title}</span>
                <span className={`dot ${i.status}`} />
              </div>
            ))}
          </div>
        ))}
        {!groups.length && <p className="empty">{query ? "Nothing matches" : "No meetings yet"}</p>}
      </div>

      <div className="foot">
        {job.active || job.queued ? (
          <div className="job">
            {jobLine(job)}
            {job.active && <span className="file" title={job.file}>{job.file}</span>}
          </div>
        ) : null}
        {problem && <div className="warn" onClick={() => setView("settings")}>{problem} — open settings</div>}
        <div className="row">
          <button className={`ghost ${view === "settings" ? "on" : ""}`} onClick={() => setView("settings")}>Settings</button>
          <button className={`ghost ${view === "archive" ? "on" : ""}`} onClick={() => setView("archive")}>
            Deleted{state.archive.length > 0 && <span className="count">{state.archive.length}</span>}
          </button>
          <span className="spacer" />
          <button className="ghost" title="Summarise transcript files — or drop them on the window"
                  onClick={(e) => { const r = e.currentTarget.getBoundingClientRect();
                                    setImportAt({ x: r.left, y: r.top - 80 }); }}>+ Import</button>
        </div>
      </div>
      {importAt && (
        <Menu at={importAt} close={() => setImportAt(null)} actions={[
          { label: "Transcript files…", run: () => pick("/api/pick") },
          { label: "A whole folder…", run: () => pick("/api/pick/folder") },
        ]} />
      )}
    </aside>
  );
}

// The call recorder's button. The clock and the meters live in the live view.
// When a call app takes or lets go of the microphone, the offer sits above it.
const OFFERS = { record: "is using the microphone.", stop: "let go of the microphone — call over?" };

function Record({ recording, call, refresh, say, onStart }) {
  const seconds = useElapsed(recording);
  async function toggle() {
    const starting = !recording.recording;
    const r = await api("/api/record", { on: starting });
    if (r.error) say(r.error, "bad");
    else if (starting) onStart();
    refresh();
  }
  async function dismiss() {
    await api("/api/call/dismiss", {});
    refresh();
  }
  return (
    <div className={`record ${recording.recording ? "on" : ""}`}>
      {call.offer && (
        <p className="offer">
          <b>{call.app}</b> {OFFERS[call.offer]}
          <button className="link" onClick={dismiss}>{call.offer === "stop" ? "Keep going" : "Not now"}</button>
        </p>
      )}
      <button className={recording.recording ? "" : "primary"} onClick={toggle}>
        {recording.recording
          ? <>■ Stop <span className="clock">{clock(seconds)}</span></>
          : call.offer === "record" ? `● Record the ${call.app} call` : "● Record a call"}
      </button>
    </div>
  );
}
