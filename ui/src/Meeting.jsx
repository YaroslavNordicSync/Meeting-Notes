import { useEffect, useState } from "react";
import { api } from "./api.js";
import { More } from "./actions.jsx";
import Notes from "./Notes.jsx";
import { WORDS } from "./Sidebar.jsx";

// The page for one item in the list: a meeting's notes and transcript, or a
// recording that never became a meeting.
export default function Meeting({ item, state, refresh, say, more }) {
  if (item.kind === "recording") return <LoneRecording recording={item.recording} more={more} />;
  return <Detail key={item.key + item.status} meeting={item.meeting} state={state}
                 refresh={refresh} say={say} more={more} />;
}

function Detail({ meeting, state, refresh, say, more }) {
  const [tab, setTab] = useState(meeting.notes ? "notes" : "transcript");

  const head = (
    <header className="head">
      <div className="tabs">
        {[["notes", "Notes"], ["transcript", "Transcript"]].map(([t, label]) => (
          <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>{label}</button>
        ))}
      </div>
      <span className="spacer" />
      <span className={`status ${meeting.status}`}>{WORDS[meeting.status]}</span>
      <More onClick={more} />
    </header>
  );

  if (tab === "transcript") return <Transcript meeting={meeting} head={head} />;

  if (!meeting.notes) {
    const working = meeting.status === "found" || meeting.status === "processing";
    return (
      <div className="page doc">
        {head}
        <h1>{meeting.title}</h1>
        <p className={working ? "dim" : "bad"}>
          {working ? "Being summarised. The notes appear here when they are ready."
                   : meeting.error || "This meeting has no notes."}
        </p>
      </div>
    );
  }
  return <Notes meeting={meeting} state={state} head={head} refresh={refresh} say={say} />;
}

function LoneRecording({ recording, more }) {
  const busy = !!recording.status;
  return (
    <div className="page doc">
      <header className="head">
        <span className="spacer" />
        <span className="status">{busy ? "Transcribing" : "Nothing recognised"}</span>
        {!busy && <More onClick={more} />}
      </header>
      <h1>{recording.title}</h1>
      <p className="dim">
        {busy ? "The speech model is going through the whole recording. The meeting appears in the list when it is done."
              : "The live transcript found no speech in this recording, so it was not summarised. "
                + "Transcribe it again from ⋯ to run the speech model over the whole recording, or delete it."}
      </p>
    </div>
  );
}

// What was said, read again from the source: a downloaded file or a recording.
// The voices can be named here; a name goes into the notes as well.
function Transcript({ meeting, head }) {
  const [data, setData] = useState(null);
  const load = () => api(`/api/meeting/${meeting.hash}/transcript`).then(setData);
  useEffect(() => { load(); }, [meeting.hash]);   // eslint-disable-line react-hooks/exhaustive-deps

  const voices = data && !data.error
    ? [...new Set(data.turns.map((t) => t.speaker))].filter((s) => s !== "Me" && s !== "Unknown")
    : [];

  return (
    <div className="page doc">
      {head}
      <h1>{meeting.title}</h1>
      {!data && <p className="dim">Loading…</p>}
      {data?.error && <p className="bad">{data.error}</p>}
      {meeting.notes && voices.length > 0 && <Voices meeting={meeting} voices={voices} onNamed={load} />}
      {data && !data.error && (
        <div className="transcript">
          {data.turns.map((t, i) => (
            <div key={i} className={`said ${t.speaker === "Me" ? "me" : "them"}`}>
              <span className="who" title={t.speaker}>{t.speaker === "Unknown" ? "" : t.speaker}</span>
              <p>{t.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Voices({ meeting, voices, onNamed }) {
  const [names, setNames] = useState({});
  const [note, setNote] = useState("");

  async function save(voice) {
    const to = (names[voice] || "").trim();
    if (!to || to === voice) return;
    const r = await api(`/api/meeting/${meeting.hash}/speaker`, { from: voice, to });
    setNote(r.ok ? `${voice} is ${to} now — in the notes too` : r.error);
    setNames({ ...names, [voice]: "" });
    onNamed();
  }

  return (
    <section className="voices">
      <h3>Who is who</h3>
      {voices.map((voice) => (
        <label key={voice} className="voice">
          <span>{voice}</span>
          <input placeholder="Name" value={names[voice] || ""}
                 onChange={(e) => setNames({ ...names, [voice]: e.target.value })}
                 onKeyDown={(e) => e.key === "Enter" && save(voice)}
                 onBlur={() => save(voice)} />
        </label>
      ))}
      {note && <p className="hint">{note}</p>}
    </section>
  );
}
