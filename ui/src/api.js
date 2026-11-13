// The loopback API in server.py. Every call carries the session's token.
export async function api(path, body) {
  const r = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-Token": window.TOKEN, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return r.json();
}

const STAGES = {
  map: (j) => `reading part ${j.i}/${j.n}`,
  reduce: () => "writing the notes",
  pull: (j) => `downloading ${j.i}/${j.n} MB`,
  waiting: () => "waiting for Ollama",
  starting: () => "starting",
};

export function jobLine(job) {
  if (!job) return "idle";
  const waiting = job.queued ? ` · ${job.queued} waiting` : "";
  if (!job.active) return job.queued ? `${job.queued} waiting` : "idle";
  const stage = (STAGES[job.stage] || (() => "working"))(job);
  return `${stage}${waiting}`;
}

export const lines = (text) => text.split("\n").map((s) => s.trim()).filter(Boolean);

// /Users/me/Downloads -> ~/Downloads
export function shortPath(p) {
  const m = (p || "").match(/^\/Users\/[^/]+(\/.*)?$/);
  return m ? "~" + (m[1] || "") : p;
}
