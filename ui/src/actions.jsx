import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";

// Call one action route; say what went wrong, or run `done`, then redraw.
export async function act(path, say, refresh, done) {
  const r = await api(path, {});
  if (r.ok === false || r.error) say(r.error, "bad");
  else if (done) done();
  refresh();
  return r;
}

// What can be done to an item, in the order the menu shows it.
export function actionsFor(item, state, say, refresh, gone) {
  if (item.kind === "recording") {
    const base = `/api/recording/${encodeURIComponent(item.recording.name)}`;
    if (item.recording.status) return [];
    return [
      { label: "Transcribe again", run: () => act(`${base}/transcribe`, say, refresh,
                                                  () => say("Transcribing the whole recording", "ok")) },
      { label: "Delete", danger: true, confirm: true,
        run: () => act(`${base}/archive`, say, refresh, gone) },
    ];
  }
  const m = item.meeting, base = `/api/meeting/${m.hash}`;
  return [
    { label: "Show in Finder", run: () => act(`${base}/reveal`, say, refresh) },
    ...(m.recorded ? [{ label: "Transcribe again", hint: "the whole recording, with the speech model",
                        run: () => act(`${base}/transcribe`, say, refresh,
                                       () => say("Transcribing the whole recording again", "ok")) }] : []),
    { label: "Summarise again", run: async () => {
      const r = await api(`${base}/retry`, {});
      say(r.error || (r.queued ? "Queued again" : r.note), r.error ? "bad" : "ok");
      refresh();
    } },
    { label: "Delete", danger: true, confirm: true,
      run: () => act(`${base}/archive`, say, refresh, () => {
        say(`Moved to deleted for ${state.archive_days} days`, "ok");
        gone();
      }) },
  ];
}

// A small menu where it was asked for. Delete asks once more inside it.
export function Menu({ at, actions, close }) {
  const [armed, setArmed] = useState(null);
  const box = useRef(null);
  useEffect(() => {
    const away = (e) => { if (!box.current?.contains(e.target)) close(); };
    const key = (e) => { if (e.key === "Escape") close(); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", key);
    };
  }, [close]);
  // Kept inside the window, whichever corner it was opened near.
  const x = Math.min(at.x, window.innerWidth - 210), y = Math.min(at.y, window.innerHeight - 40 * actions.length - 20);
  if (!actions.length) return null;
  return (
    <div className="menu" ref={box} style={{ left: x, top: y }}>
      {actions.map((a, i) => (
        <button key={a.label} className={a.danger ? "danger" : ""} title={a.hint || ""}
                onClick={() => {
                  if (a.confirm && armed !== i) return setArmed(i);
                  close();
                  a.run();
                }}>
          {a.confirm && armed === i ? `${a.label} — sure?` : a.label}
        </button>
      ))}
    </div>
  );
}

// A button that does something for good: the first click arms it, the second does it.
export function Sure({ label, run, className = "" }) {
  const [armed, setArmed] = useState(false);
  return (
    <button className={`danger ${armed ? "armed" : ""} ${className}`} onBlur={() => setArmed(false)}
            onClick={() => {
              if (!armed) return setArmed(true);
              setArmed(false);
              run();
            }}>
      {armed ? `${label} — sure?` : label}
    </button>
  );
}

export function More({ onClick }) {
  return <button className="ghost more" title="More — or right-click the meeting in the list"
                 onClick={(e) => { const r = e.currentTarget.getBoundingClientRect();
                                   onClick({ preventDefault() {}, clientX: r.right - 200, clientY: r.bottom + 4 }); }}>⋯</button>;
}
