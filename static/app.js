const SAMPLE_RATES = new Set([8000, 16000, 22050, 24000, 32000, 44100, 48000]);

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
};

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
    const res = await fetch("/api/health");
    const data = await res.json();
    els.dbStatus.textContent = data.ok ? "up" : "down";
    els.dbStatus.className = data.ok ? "ok" : "bad";
    els.keyStatus.textContent = data.has_api_key ? "present" : "missing";
    els.keyStatus.className = data.has_api_key ? "ok" : "bad";
    els.voiceStatus.textContent = `${data.voice} · ${data.model}`;
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
  const res = await fetch("/api/schema");
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
  const res = await fetch(`/api/preview/${encodeURIComponent(name)}`);
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

async function startMic() {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  const ctx = new AudioContext({ sampleRate: 24000 });
  const source = ctx.createMediaStreamSource(stream);
  const processor = ctx.createScriptProcessor(4096, 1, 1);
  const mute = ctx.createGain();
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
  mute.connect(ctx.destination);
  live.ctx = ctx;
  live.stream = stream;
  live.processor = processor;
  live.player = new AudioPlayer(ctx);
  if (ctx.state === "suspended") await ctx.resume();
  return ctx.sampleRate;
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
    return;
  }
  if (type === "local.ready") {
    setCaption(`Connected · ${event.voice} · ${event.sample_rate} Hz. Just talk.`);
    return;
  }
  if (type === "local.tool_call") {
    addTool(event);
    return;
  }
  if (type === "response.output_audio.delta" || type === "response.audio.delta") {
    live.player?.play(event.delta);
    return;
  }
  if (type === "response.output_audio_transcript.delta") {
    appendAssistant(event.delta || "");
    return;
  }
  if (type === "response.done") {
    live.currentAssistant = null;
    return;
  }
  if (type === "input_audio_buffer.speech_started") {
    live.player?.stop();
    live.currentAssistant = null;
    live.currentUser = addBubble("user", "…");
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
  const sampleRate = await startMic();
  const rate = SAMPLE_RATES.has(sampleRate) ? sampleRate : 24000;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  live.ws = ws;
  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "local.start", sample_rate: rate }));
    live.capturing = true;
    els.talkBtn.setAttribute("aria-pressed", "true");
    els.orbCore.textContent = "Live";
    setCaption("Listening…");
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
    if (live.capturing) stopTalk();
  };
}

function stopTalk() {
  stopMic();
  els.talkBtn.setAttribute("aria-pressed", "false");
  els.orbCore.textContent = "Talk";
  setCaption("Session ended. Click Talk to start again.");
}

els.talkBtn.addEventListener("click", () => {
  if (els.talkBtn.getAttribute("aria-pressed") === "true") stopTalk();
  else startSession().catch((err) => setCaption(err.message || String(err)));
});

document.getElementById("refresh-schema").addEventListener("click", () => {
  loadSchema().catch((err) => setCaption(err.message));
});

loadHealth();
loadSchema().catch((err) => setCaption(err.message));
