const SAMPLE_RATES = new Set([8000, 16000, 22050, 24000, 32000, 44100, 48000]);

function appBase() {
  const el = document.querySelector("base");
  if (!el) return "/";
  try {
    const path = new URL(el.href, location.origin).pathname;
    return path.endsWith("/") ? path : `${path}/`;
  } catch {
    return "/";
  }
}

function apiUrl(path) {
  return `${appBase()}${String(path).replace(/^\//, "")}`;
}

function floatToBase64PCM16(float32) {
  const pcm16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  const bytes = new Uint8Array(pcm16.buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function base64PCM16ToFloat32(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const pcm16 = new Int16Array(bytes.buffer);
  const float32 = new Float32Array(pcm16.length);
  for (let i = 0; i < pcm16.length; i++) {
    float32[i] = pcm16[i] / (pcm16[i] < 0 ? 0x8000 : 0x7fff);
  }
  return float32;
}

class AudioPlayer {
  constructor(ctx) {
    this.ctx = ctx;
    this.nextTime = 0;
    this.sources = [];
  }
  play(base64) {
    const samples = base64PCM16ToFloat32(base64);
    if (!samples.length) return;
    const buffer = this.ctx.createBuffer(1, samples.length, this.ctx.sampleRate);
    buffer.copyToChannel(samples, 0);
    const src = this.ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(this.ctx.destination);
    const now = this.ctx.currentTime;
    if (this.nextTime < now) this.nextTime = now;
    src.start(this.nextTime);
    this.nextTime += buffer.duration;
    this.sources.push(src);
    src.onended = () => {
      this.sources = this.sources.filter((s) => s !== src);
    };
  }
  stop() {
    for (const src of this.sources) {
      try {
        src.stop();
      } catch {
        /* already stopped */
      }
    }
    this.sources = [];
    this.nextTime = 0;
  }
}

const els = {
  dbStatus: document.getElementById("db-status"),
  keyStatus: document.getElementById("key-status"),
  voiceStatus: document.getElementById("voice-status"),
  schemaList: document.getElementById("schema-list"),
  preview: document.getElementById("preview"),
  previewTitle: document.getElementById("preview-title"),
  previewTable: document.getElementById("preview-table"),
  talkBtn: document.getElementById("talk-btn"),
  talkCaption: document.getElementById("talk-caption"),
  orbCore: document.getElementById("orb-core"),
  levelBar: document.getElementById("level-bar"),
  transcript: document.getElementById("transcript"),
  tools: document.getElementById("tools"),
  phases: document.getElementById("phases"),
  askForm: document.getElementById("ask-form"),
  askInput: document.getElementById("ask-input"),
  askSend: document.getElementById("ask-send"),
  originStatus: document.getElementById("origin-status"),
  voiceSelect: document.getElementById("voice-select"),
  speedSlider: document.getElementById("speed-slider"),
  speedValue: document.getElementById("speed-value"),
};

const VOICE_KEY = "voice-postgres.voice";
const SPEED_KEY = "voice-postgres.speed";
const SPEED_MIN = 0.7;
const SPEED_MAX = 1.5;

let live = {
  ws: null,
  capturing: false,
  ctx: null,
  stream: null,
  processor: null,
  player: null,
  currentAssistant: null,
  currentUser: null,
};

function setCaption(text) {
  els.talkCaption.textContent = text;
}

function setPhase(phase) {
  for (const li of els.phases.querySelectorAll("li")) {
    li.classList.toggle("on", li.dataset.phase === phase);
  }
}

function setAskEnabled(on) {
  els.askInput.disabled = !on;
  els.askSend.disabled = !on;
}

function sendText(text) {
  const trimmed = (text || "").trim();
  if (!trimmed) return;
  if (!live.ws || live.ws.readyState !== WebSocket.OPEN) {
    els.askInput.value = trimmed;
    setCaption("Click Talk first so the Voice Agent session is open, then Ask.");
    return;
  }
  live.ws.send(
    JSON.stringify({
      type: "conversation.item.create",
      item: {
        type: "message",
        role: "user",
        content: [{ type: "input_text", text: trimmed }],
      },
    })
  );
  live.ws.send(JSON.stringify({ type: "response.create" }));
  live.currentUser = addBubble("user", trimmed);
  live.currentAssistant = null;
  els.askInput.value = "";
  setPhase("tool");
  setCaption("Sent as text on the same realtime session. Waiting for Grok…");
}

function addBubble(role, text) {
  const li = document.createElement("li");
  li.className = `bubble ${role}`;
  li.innerHTML = `<div class="who">${role}</div><div class="body"></div>`;
  li.querySelector(".body").textContent = text;
  els.transcript.appendChild(li);
  els.transcript.scrollTop = els.transcript.scrollHeight;
  return li;
}

function appendAssistant(delta) {
  if (!live.currentAssistant) {
    live.currentAssistant = addBubble("assistant", delta);
  } else {
    live.currentAssistant.querySelector(".body").textContent += delta;
    els.transcript.scrollTop = els.transcript.scrollHeight;
  }
}

function setUserTranscript(text) {
  if (!live.currentUser) {
    live.currentUser = addBubble("user", text);
  } else {
    live.currentUser.querySelector(".body").textContent = text;
  }
}

function addTool(event) {
  const li = document.createElement("li");
  li.className = "tool";
  const args = JSON.stringify(event.arguments ?? {}, null, 2);
  const out = JSON.stringify(event.output ?? event.output_preview ?? {}, null, 2);
  li.innerHTML = `<div class="name">${event.name}</div><pre></pre>`;
  li.querySelector("pre").textContent = `${args}\n→ ${out}`;
  els.tools.prepend(li);
}

async function loadHealth() {
  try {
    const res = await fetch(apiUrl("api/health"));
    const data = await res.json();
    els.dbStatus.textContent = data.ok ? "up" : "down";
    els.dbStatus.className = data.ok ? "ok" : "bad";
    els.keyStatus.textContent = data.has_api_key ? "present" : "missing";
    els.keyStatus.className = data.has_api_key ? "ok" : "bad";
    els.voiceStatus.textContent = data.model;
    if (!data.has_api_key) {
      setCaption("Add XAI_API_KEY to .env, then restart. Postgres can still be browsed on the left.");
    }
    return data;
  } catch {
    els.dbStatus.textContent = "unreachable";
    els.dbStatus.className = "bad";
    return null;
  }
}

async function loadSchema() {
  const res = await fetch(apiUrl("api/schema"));
  const data = await res.json();
  els.schemaList.innerHTML = "";
  for (const rel of data.relations || []) {
    const li = document.createElement("li");
    li.dataset.name = rel.name;
    const cols = (rel.columns || []).map((c) => c.name).join(", ");
    li.innerHTML = `<div><span class="name">${rel.name}</span><span class="kind">${rel.kind}</span></div>
      <div class="cols">${rel.comment || cols}</div>`;
    li.addEventListener("click", () => previewTable(rel.name, li));
    els.schemaList.appendChild(li);
  }
}

async function previewTable(name, li) {
  for (const item of els.schemaList.querySelectorAll("li")) item.classList.remove("active");
  li.classList.add("active");
  const res = await fetch(apiUrl(`api/preview/${encodeURIComponent(name)}`));
  const data = await res.json();
  els.preview.hidden = false;
  els.previewTitle.textContent = name;
  if (data.error) {
    els.previewTable.textContent = data.error;
    return;
  }
  const cols = data.columns || [];
  const rows = data.rows || [];
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  thead.innerHTML = `<tr>${cols.map((c) => `<th>${c}</th>`).join("")}</tr>`;
  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = cols.map((c) => `<td>${escapeHtml(row[c])}</td>`).join("");
    tbody.appendChild(tr);
  }
  table.append(thead, tbody);
  els.previewTable.innerHTML = "";
  els.previewTable.appendChild(table);
}

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  const s = String(value);
  return s.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function isLoopbackHost() {
  const host = location.hostname;
  return host === "localhost" || host === "127.0.0.1" || host === "[::1]";
}

function micSupported() {
  return Boolean(navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === "function");
}

function warnOrigin() {
  if (!els.originStatus) return;
  const label = location.host || location.origin;
  els.originStatus.textContent = label;
  const ok = window.isSecureContext && micSupported();
  els.originStatus.className = ok ? "ok" : "bad";
  if (!ok && !live.ws) {
    setCaption(micHelp());
  }
}

function micHelp() {
  if (location.protocol !== "https:" && !isLoopbackHost()) {
    return (
      `Microphone API is off on ${location.origin}. Restart did not break the mic — this URL is not a ` +
      `secure context. Open http://127.0.0.1:${location.port || "8765"} in the address bar ` +
      `(Uvicorn's http://0.0.0.0:... will not allow getUserMedia).`
    );
  }
  return "Microphone API is unavailable in this browser/webview. You can still type questions after Talk connects.";
}

async function ensurePlayback() {
  if (!live.ctx) {
    live.ctx = new AudioContext({ sampleRate: 24000 });
    live.player = new AudioPlayer(live.ctx);
  }
  if (live.ctx.state === "suspended") await live.ctx.resume();
  return live.ctx.sampleRate;
}

async function startMic() {
  if (!micSupported()) {
    throw new Error(micHelp());
  }
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  const sampleRate = await ensurePlayback();
  const source = live.ctx.createMediaStreamSource(stream);
  const processor = live.ctx.createScriptProcessor(4096, 1, 1);
  const mute = live.ctx.createGain();
  mute.gain.value = 0;
  processor.onaudioprocess = (event) => {
    if (!live.capturing || !live.ws || live.ws.readyState !== WebSocket.OPEN) return;
    const input = event.inputBuffer.getChannelData(0);
    let sum = 0;
    for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
    const rms = Math.sqrt(sum / input.length);
    els.levelBar.style.width = `${Math.min(100, rms * 280)}%`;
    live.ws.send(
      JSON.stringify({
        type: "input_audio_buffer.append",
        audio: floatToBase64PCM16(input),
      })
    );
  };
  source.connect(processor);
  processor.connect(mute);
  mute.connect(live.ctx.destination);
  live.stream = stream;
  live.processor = processor;
  return sampleRate;
}

function stopMic() {
  live.capturing = false;
  live.player?.stop();
  live.processor?.disconnect();
  live.stream?.getTracks().forEach((t) => t.stop());
  live.ctx?.close();
  live.ws?.close();
  live.ws = null;
  live.ctx = null;
  live.stream = null;
  live.processor = null;
  live.player = null;
  live.currentAssistant = null;
  live.currentUser = null;
  els.levelBar.style.width = "0";
}

function handleEvent(event) {
  const type = event.type;
  if (type === "error") {
    setCaption(event.error?.message || "Voice session error");
    setPhase("idle");
    return;
  }
  if (type === "local.voice") {
    if (event.voice) els.voiceSelect.value = event.voice;
    setCaption(`Voice set to ${event.voice}. Next reply uses this voice.`);
    return;
  }
  if (type === "local.speed") {
    if (typeof event.speed === "number") setSpeedUI(event.speed);
    setCaption(`Speed set to ${Number(event.speed).toFixed(2)}×. Next reply uses this rate.`);
    return;
  }
  if (type === "local.ready") {
    if (event.voice) els.voiceSelect.value = event.voice;
    if (typeof event.speed === "number") setSpeedUI(event.speed);
    const speed = Number(event.speed ?? 1).toFixed(2);
    if (live.capturing) {
      setCaption(
        `Mic is streaming ${event.sample_rate} Hz PCM to ${event.voice} at ${speed}×. Speak, or type below.`
      );
    } else {
      setCaption(
        `Connected as ${event.voice} at ${speed}×, text only (no microphone). Type a question and press Ask.`
      );
    }
    setPhase("mic");
    setAskEnabled(true);
    els.askInput.focus();
    return;
  }
  if (type === "local.tool_call") {
    addTool(event);
    setPhase("tool");
    setCaption(`Running ${event.name} against Postgres…`);
    return;
  }
  if (type === "response.output_audio.delta" || type === "response.audio.delta") {
    live.player?.play(event.delta);
    setPhase("speak");
    return;
  }
  if (type === "response.output_audio_transcript.delta") {
    appendAssistant(event.delta || "");
    return;
  }
  if (type === "response.done") {
    live.currentAssistant = null;
    setPhase("mic");
    setCaption("Listening. Speak, or type a follow-up.");
    return;
  }
  if (type === "input_audio_buffer.speech_started") {
    live.player?.stop();
    live.currentAssistant = null;
    live.currentUser = addBubble("user", "…");
    setPhase("speech");
    setCaption("Hearing you… keep talking, then pause.");
    return;
  }
  if (type === "input_audio_buffer.speech_stopped") {
    setCaption("Turn ended (silence). Grok is answering…");
    return;
  }
  if (type === "conversation.item.added" || type === "conversation.item.created") {
    const item = event.item;
    if (item?.role === "user" && Array.isArray(item.content)) {
      for (const part of item.content) {
        if (part.transcript) {
          setUserTranscript(part.transcript);
          break;
        }
      }
    }
    return;
  }
}

async function startSession() {
  const health = await loadHealth();
  if (health && !health.has_api_key) {
    setCaption("XAI_API_KEY is missing. The database browser still works.");
    return;
  }
  els.transcript.innerHTML = "";
  els.tools.innerHTML = "";
  let micError = null;
  let sampleRate = 24000;
  try {
    sampleRate = await startMic();
    live.capturing = true;
  } catch (err) {
    micError = err instanceof Error ? err.message : String(err);
    live.capturing = false;
    await ensurePlayback();
    sampleRate = live.ctx?.sampleRate || 24000;
    setCaption(`${micError} Connecting for typed questions…`);
  }
  const rate = SAMPLE_RATES.has(sampleRate) ? sampleRate : 24000;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}${appBase()}ws`);
  live.ws = ws;
  ws.onopen = () => {
    ws.send(
      JSON.stringify({
        type: "local.start",
        sample_rate: rate,
        voice: selectedVoice(),
        speed: selectedSpeed(),
      })
    );
    els.talkBtn.setAttribute("aria-pressed", "true");
    els.orbCore.textContent = live.capturing ? "Live" : "Text";
    setPhase("mic");
    if (!micError) {
      setCaption("Opening the Voice Agent session… allow the mic if the browser asks.");
    }
  };
  ws.onmessage = (msg) => {
    let event;
    try {
      event = JSON.parse(msg.data);
    } catch {
      return;
    }
    handleEvent(event);
  };
  ws.onerror = () => setCaption("WebSocket error");
  ws.onclose = () => {
    if (els.talkBtn.getAttribute("aria-pressed") === "true" || live.processor) {
      stopTalk();
    }
  };
}

function stopTalk() {
  stopMic();
  els.talkBtn.setAttribute("aria-pressed", "false");
  els.orbCore.textContent = "Talk";
  setAskEnabled(false);
  setPhase("idle");
  setCaption("Session ended. Click Talk to open the mic again.");
}

els.talkBtn.addEventListener("click", () => {
  if (els.talkBtn.getAttribute("aria-pressed") === "true") stopTalk();
  else
    startSession().catch((err) => {
      stopTalk();
      setCaption(err.message || String(err));
    });
});

els.askForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendText(els.askInput.value);
});

document.getElementById("chips").addEventListener("click", (event) => {
  const btn = event.target.closest("button");
  if (!btn) return;
  sendText(btn.textContent);
});

document.getElementById("refresh-schema").addEventListener("click", () => {
  loadSchema().catch((err) => setCaption(err.message));
});

function selectedVoice() {
  return els.voiceSelect.value || localStorage.getItem(VOICE_KEY) || "eve";
}

function clampSpeed(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 1;
  return Math.min(SPEED_MAX, Math.max(SPEED_MIN, Math.round(n * 20) / 20));
}

function selectedSpeed() {
  return clampSpeed(els.speedSlider.value || localStorage.getItem(SPEED_KEY) || 1);
}

function setSpeedUI(value) {
  const speed = clampSpeed(value);
  els.speedSlider.value = String(speed);
  els.speedValue.textContent = `${speed.toFixed(2)}×`;
  localStorage.setItem(SPEED_KEY, String(speed));
}

function sendSpeed(value) {
  const speed = clampSpeed(value);
  setSpeedUI(speed);
  if (live.ws && live.ws.readyState === WebSocket.OPEN) {
    live.ws.send(JSON.stringify({ type: "local.set_speed", speed }));
  }
}

async function loadVoices() {
  const res = await fetch(apiUrl("api/voices"));
  const data = await res.json();
  const groups = { original: "Original", flagship: "Flagship", custom: "Custom" };
  const buckets = new Map();
  for (const voice of data.voices || []) {
    const key = voice.group || "flagship";
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(voice);
  }
  els.voiceSelect.innerHTML = "";
  for (const [key, label] of Object.entries(groups)) {
    const items = buckets.get(key);
    if (!items || !items.length) continue;
    const optgroup = document.createElement("optgroup");
    optgroup.label = label;
    for (const voice of items) {
      const opt = document.createElement("option");
      opt.value = voice.id;
      opt.textContent = voice.description ? `${voice.name} — ${voice.description}` : voice.name;
      optgroup.appendChild(opt);
    }
    els.voiceSelect.appendChild(optgroup);
  }
  const preferred = localStorage.getItem(VOICE_KEY) || data.default || "eve";
  if ([...els.voiceSelect.options].some((o) => o.value === preferred)) {
    els.voiceSelect.value = preferred;
  }
}

els.voiceSelect.addEventListener("change", () => {
  const voice = els.voiceSelect.value;
  localStorage.setItem(VOICE_KEY, voice);
  if (live.ws && live.ws.readyState === WebSocket.OPEN) {
    live.ws.send(JSON.stringify({ type: "local.set_voice", voice }));
  }
});

els.speedSlider.addEventListener("input", () => {
  setSpeedUI(els.speedSlider.value);
});
els.speedSlider.addEventListener("change", () => {
  sendSpeed(els.speedSlider.value);
});

warnOrigin();
loadHealth();
loadVoices().catch((err) => setCaption(err.message));
setSpeedUI(localStorage.getItem(SPEED_KEY) || 1);
loadSchema().catch((err) => setCaption(err.message));
