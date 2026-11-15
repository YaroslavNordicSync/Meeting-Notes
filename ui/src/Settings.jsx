import { useState } from "react";
import { api, lines, shortPath } from "./api.js";

const MAIL_MODES = [["outlook_draft", "Draft in Outlook"], ["smtp", "Send over SMTP"]];

export default function Settings({ state, refresh, say }) {
  async function change(values, done) {
    const r = await api("/api/settings", values);
    if (r.error) say(r.error, "bad");
    else if (done) say(done, "ok");
    refresh();
  }

  async function downloadModel() {
    const r = await api("/api/model/download", {});
    if (r.error) say(r.error, "bad");
    refresh();
  }

  async function recheck() {
    const r = await api("/api/recheck", {});
    if (r.error) say(r.error, "bad");
    refresh();
  }

  async function chooseFolder() {
    const r = await api("/api/folder", {});
    if (r.error) say(r.error, "bad");
    refresh();
  }

  return (
    <div className="page">
      <h1>Settings</h1>

      <Group title="Inbox" hint="Where transcripts land: Teams, Zoom, Meet, Otter, subtitles or plain text. New ones are picked up by themselves.">
        <div className="inline">
          <code className="path" title={state.folder}>{shortPath(state.folder)}</code>
          <button onClick={chooseFolder}>Change…</button>
        </div>
        <label className="switch">
          <input type="checkbox" checked={state.watching}
                 onChange={(e) => change({ watching: e.target.checked })} />
          <span className="knob" />
          Watch the folder
        </label>
        {state.skipped > 0 && (
          <div className="inline">
            <span className="hint">{state.skipped} {state.skipped === 1 ? "file was" : "files were"} not taken as transcripts</span>
            <button onClick={recheck}>Check again</button>
          </div>
        )}
      </Group>

      <Group title="Model" hint={state.ollama_installed
        ? "Writes the notes, locally through Ollama. Ollama runs only while there is a meeting to summarise, then gives the memory back."
        : "Ollama is not installed. Install it with: brew install ollama"}>
        <div className="inline">
          <code className="path">{state.model}</code>
          {state.model_ready
            ? <span className="ok">Downloaded</span>
            : state.ollama_installed && <button onClick={downloadModel}>Download · several GB</button>}
        </div>
      </Group>

      <Group title="Mail" hint="Outlook drafts wait in Outlook for you to send. SMTP sends straight away from the account below.">
        <div className="segments">
          {MAIL_MODES.map(([mode, label]) => (
            <button key={mode} className={mode === state.mail_mode ? "on" : ""}
                    onClick={() => change({ mail_mode: mode })}>{label}</button>
          ))}
        </div>
        <Account state={state} refresh={refresh} />
      </Group>

      <Recipients state={state} change={change} />

      <MyName state={state} change={change} />

      <Group title="Calls" hint="When Teams, Zoom or a browser starts using the microphone, offer to record the call: a notification, and a note above the record button. It never records by itself.">
        <label className="switch">
          <input type="checkbox" checked={state.call_detect}
                 onChange={(e) => change({ call_detect: e.target.checked })} />
          <span className="knob" />
          Offer to record calls
        </label>
      </Group>

      <Group title="Deleted meetings" hint="A deleted meeting — its notes and its recording — is kept this long, then removed for good. Until then it can be restored.">
        <div className="segments">
          {[[7, "A week"], [30, "A month"], [90, "3 months"]].map(([n, label]) => (
            <button key={n} className={state.archive_days === n ? "on" : ""}
                    onClick={() => change({ archive_days: n })}>{label}</button>
          ))}
        </div>
      </Group>
    </div>
  );
}

function Group({ title, hint, children }) {
  return (
    <section className="group">
      <h3>{title}</h3>
      {hint && <p className="hint">{hint}</p>}
      {children}
    </section>
  );
}

// The address goes into the settings, the password into the Keychain. The page
// never gets a password back — the field starts empty and stays write-only.
function Account({ state, refresh }) {
  const [address, setAddress] = useState(state.account || "");
  const [secret, setSecret] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    const r = await api("/api/account", { address, password: secret });
    setBusy(false);
    setResult(r.ok ? { ok: true, text: `Saved. Sending as ${address.trim()} over SMTP.` }
                   : { ok: false, text: r.error });
    if (r.ok) setSecret("");
    refresh();
  }

  async function test() {
    setBusy(true);
    setResult({ ok: true, text: "sending…" });
    const r = await api("/api/account/test", { address, password: secret });
    setBusy(false);
    setResult({ ok: r.ok, text: r.message });
  }

  return (
    <div className="fields">
      <label>
        <span>Account</span>
        <input placeholder="you@gmail.com" value={address} onChange={(e) => setAddress(e.target.value)} />
      </label>
      <label>
        <span>App password</span>
        <input type="password" placeholder={state.account ? "saved in the keychain" : ""}
               value={secret} onChange={(e) => setSecret(e.target.value)} />
      </label>
      <div className="inline">
        <button disabled={busy} onClick={save}>Save account</button>
        <button disabled={busy} onClick={test}>Send test email</button>
      </div>
      <p className="hint">Gmail app passwords: myaccount.google.com/apppasswords</p>
      {result && <pre className={`result ${result.ok ? "ok" : "bad"}`}>{result.text}</pre>}
    </div>
  );
}

// Who "Me" is in a recorded call, so the notes say "Anna will send it", not "Me".
function MyName({ state, change }) {
  const [name, setName] = useState(state.my_name || "");
  return (
    <Group title="Your name" hint={'In a recorded call you are "Me". With your name here, the notes and the email name you instead — as the owner of a task, among the participants.'}>
      <div className="inline">
        <input value={name} placeholder="Your name" style={{ maxWidth: 280 }}
               onChange={(e) => setName(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && change({ my_name: name }, "Name saved")} />
        <button onClick={() => change({ my_name: name }, "Name saved")}>Save</button>
      </div>
    </Group>
  );
}

function Recipients({ state, change }) {
  const [text, setText] = useState(state.recipients.join("\n"));
  return (
    <Group title="Default recipients"
           hint={'Everyone here gets every set of notes. One per line: a bare address, or "Name <address>".'}>
      <textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} />
      <div className="inline">
        <button onClick={() => change({ recipients: lines(text) }, "Recipients saved")}>Save</button>
      </div>
    </Group>
  );
}
