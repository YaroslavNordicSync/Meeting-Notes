import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { Menu, actionsFor } from "./actions.jsx";
import Archive from "./Archive.jsx";
import Live from "./Live.jsx";
import Meeting from "./Meeting.jsx";
import Settings from "./Settings.jsx";
import Sidebar, { items } from "./Sidebar.jsx";

const POLL_MS = 2000;

export default function App() {
  const [state, setState] = useState(null);
  const [view, setView] = useState("meeting");     // meeting | live | settings | archive
  const [selected, setSelected] = useState(
    new URLSearchParams(location.search).get("meeting"));
  const [notice, setNotice] = useState(null);
  const [menu, setMenu] = useState(null);           // {item, x, y}

  const refresh = useCallback(async () => {
    try {
      setState(await api("/api/state"));
    } catch {
      /* the app is quitting, or restarting the server; the next poll will tell */
    }
  }, []);

  const open = useCallback((key) => {
    setView("meeting");
    setSelected(key);
  }, []);

  // Pressing record — here or in the menu bar — brings up the live view.
  const wasRecording = useRef(false);
  useEffect(() => {
    const now = !!state?.recording?.recording;
    if (now && !wasRecording.current) setView("live");
    wasRecording.current = now;
  }, [state?.recording?.recording]);

  useEffect(() => {
    refresh();
    const timer = setInterval(() => document.hidden || refresh(), POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  // The menu bar's "Open notes…" lands here when the window is already up.
  useEffect(() => {
    window.openMeeting = (meeting) => {
      open(meeting);
      refresh();
    };
    return () => delete window.openMeeting;
  }, [open, refresh]);

  const say = useCallback((text, kind = "", lines = []) =>
    setNotice({ text, kind, lines, at: Date.now() }), []);

  // Files brought in by hand — picked, dropped on the window, re-checked — come
  // back through the state, the drop from the native side, so one toast for all.
  const lastImport = useRef(undefined);
  useEffect(() => {
    if (!state) return;
    const at = state.imported?.at ?? null;
    if (lastImport.current !== undefined && at !== lastImport.current) {
      say(...importNotice(state.imported.results));
    }
    lastImport.current = at;
  }, [state, say]);

  const all = state ? items(state) : [];
  // Nothing chosen yet: the newest meeting waiting to be sent, else the newest.
  useEffect(() => {
    if (!selected && all.length) setSelected((all.find((i) => i.status === "ready") || all[0]).key);
  }, [selected, all]);

  async function pick(route) {
    const r = await api(route, {});
    if (r.cancelled) return;
    if (r.error) say(r.error, "bad");
    // One file: show it, whether it is new or summarised before.
    if (r.results?.length === 1 && r.results[0].meeting) open(r.results[0].meeting);
    refresh();
  }

  function openMenu(item, e) {
    e.preventDefault();
    open(item.key);
    setMenu({ item, x: e.clientX, y: e.clientY });
  }

  if (!state) return null;
  const item = all.find((i) => i.key === selected);

  return (
    <div className="shell">
      <Sidebar state={state} view={view} selected={selected} open={open} openMenu={openMenu}
               setView={setView} pick={pick} refresh={refresh} say={say} />
      <main>
        {view === "meeting" && (item
          ? <Meeting item={item} state={state} refresh={refresh} say={say} more={(e) => openMenu(item, e)} />
          : <div className="nothing">
              {all.length ? "Pick a meeting"
                : <span>No meetings yet.<br />Record a call, import transcripts,<br />or drop them on this window.</span>}
            </div>)}
        {view === "live" && <Live recording={state.recording} refresh={refresh} say={say} />}
        {view === "settings" && <Settings state={state} refresh={refresh} say={say} />}
        {view === "archive" && <Archive state={state} refresh={refresh} say={say} />}
      </main>
      {menu && (
        <Menu at={menu} close={() => setMenu(null)}
              actions={actionsFor(menu.item, state, say, refresh, () => setSelected(null))} />
      )}
      {notice && <Toast key={notice.at} notice={notice} onDone={() => setNotice(null)} />}
    </div>
  );
}

const OUTCOMES = [["queued", "queued"], ["seen", "already here"],
                  ["skipped", "not transcripts"], ["error", "unreadable"]];

// "2 queued · 1 not transcripts", and below it what was not taken and why.
export function importNotice(results) {
  if (!results.length) return ["No transcripts there", ""];
  const count = (o) => results.filter((r) => r.outcome === o).length;
  const text = OUTCOMES.filter(([o]) => count(o)).map(([o, word]) => `${count(o)} ${word}`).join(" · ");
  const why = results.filter((r) => r.outcome === "skipped" || r.outcome === "error")
    .map((r) => `${r.name}: ${r.note}`);
  const lines = why.length > 6 ? [...why.slice(0, 5), `and ${why.length - 5} more`] : why;
  return [text, count("queued") ? "ok" : count("error") === results.length ? "bad" : "", lines];
}

function Toast({ notice, onDone }) {
  // Once per toast: onDone is a new function on every poll, and a timer
  // restarted every two seconds would never fire.
  useEffect(() => {
    const timer = setTimeout(onDone, 6000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className={`toast ${notice.kind}`} onClick={onDone}>
      {notice.text}
      {notice.lines?.map((line) => <div key={line} className="why">{line}</div>)}
    </div>
  );
}
