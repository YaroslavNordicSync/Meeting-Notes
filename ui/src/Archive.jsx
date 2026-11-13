import { Sure, act } from "./actions.jsx";

// What was deleted: each item can come back, or go for good now; the rest goes
// by itself after the chosen number of days.
export default function Archive({ state, refresh, say }) {
  const entries = state.archive;
  const base = (e) => `/api/archive/${encodeURIComponent(e.id)}`;
  return (
    <div className="page">
      <header className="head">
        <h1>Deleted</h1>
        <span className="spacer" />
        {entries.length > 0 && (
          <Sure label="Empty now" run={() => act("/api/archive/empty", say, refresh,
                                                 () => say("Deleted items removed for good", "ok"))} />
        )}
      </header>
      <p className="hint">
        A deleted meeting — its notes and its recording — is kept here {state.archive_days} days, then
        removed for good (change it in settings). Restore puts everything back where it was.
      </p>
      {entries.length ? (
        <div className="rows">
          {entries.map((e) => {
            const left = Math.max(0, Math.ceil((e.deletes_at * 1000 - Date.now()) / 86400000));
            return (
              <div key={e.id} className="row-item">
                <div className="what">
                  <div>{e.title}</div>
                  <div className="when">
                    Deleted {new Date(e.archived_at * 1000).toLocaleDateString("en-GB")}
                    {" "}· gone in {left} day{left === 1 ? "" : "s"}
                  </div>
                </div>
                <button onClick={() => act(`${base(e)}/restore`, say, refresh, () => say("Restored", "ok"))}>
                  Restore
                </button>
                <Sure label="Delete for good" run={() => act(`${base(e)}/remove`, say, refresh,
                                                             () => say("Deleted for good", "ok"))} />
              </div>
            );
          })}
        </div>
      ) : <p className="dim">Nothing deleted.</p>}
    </div>
  );
}
