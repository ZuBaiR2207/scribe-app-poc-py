const els = {
  consent: document.getElementById("consent"),
  language: document.getElementById("language"),
  start: document.getElementById("start"),
  stop: document.getElementById("stop"),
  status: document.getElementById("status"),
  transcript: document.getElementById("transcript"),
  partial: document.getElementById("partial"),
  generate: document.getElementById("generate"),
  noteStatus: document.getElementById("noteStatus"),
  noteOutput: document.getElementById("noteOutput"),
  saveNote: document.getElementById("saveNote"),
  approveNote: document.getElementById("approveNote"),
};

const segments = [];
let ws = null;
let stream = null;
let audioContext = null;
let finishTimer = null;
let hadError = false;
let sessionId = null;

function setStatus(text) {
  els.status.textContent = text;
}

function appendFinal(text) {
  segments.push(text);
  const p = document.createElement("p");
  p.textContent = text;
  els.transcript.appendChild(p);
}

function stopMicrophone() {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
    stream = null;
  }
}

function closeAudioContext() {
  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }
}

function resetButtons() {
  els.start.disabled = false;
  els.stop.disabled = true;
  els.language.disabled = false;
  els.generate.disabled = segments.length === 0;
  els.consent.disabled = false;
}

function handleMessage(event) {
  const msg = JSON.parse(event.data);
  if (msg.type === "partial") {
    els.partial.textContent = msg.text;
  } else if (msg.type === "final") {
    els.partial.textContent = "";
    if (msg.text) {
      appendFinal(msg.text);
    }
    setStatus(
      `Last segment: ${msg.audio_seconds.toFixed(1)} s of audio transcribed in ` +
        `${msg.processing_seconds.toFixed(1)} s (detected: ${msg.language})`
    );
  } else if (msg.type === "error") {
    setStatus(msg.message);
  } else if (msg.type === "done") {
    clearTimeout(finishTimer);
    if (ws) {
      ws.close();
    }
  }
}

async function start() {
  if (!els.consent.checked) {
    setStatus("Tick the consent box before recording.");
    return;
  }
  hadError = false;
  segments.length = 0;
  sessionId = null;
  els.start.disabled = true;
  els.language.disabled = true;
  els.generate.disabled = true;
  els.consent.disabled = true;
  els.noteOutput.value = "";
  els.noteOutput.disabled = true;
  els.saveNote.disabled = true;
  els.approveNote.disabled = true;
  els.transcript.textContent = "";
  els.partial.textContent = "";
  els.noteStatus.textContent = "";
  setStatus("Requesting microphone...");

  try {
    const sessionResponse = await fetch("/api/sessions", { method: "POST" });
    if (!sessionResponse.ok) {
      throw new Error("Could not create a session record.");
    }
    sessionId = (await sessionResponse.json()).id;

    audioContext = new AudioContext({ sampleRate: 16000 });
    if (audioContext.sampleRate !== 16000) {
      throw new Error(`Browser gave ${audioContext.sampleRate} Hz audio; 16000 Hz is required.`);
    }
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }
    await audioContext.audioWorklet.addModule("audio-worklet.js");

    const source = audioContext.createMediaStreamSource(stream);
    const worklet = new AudioWorkletNode(audioContext, "pcm-capture");
    const mute = audioContext.createGain();
    mute.gain.value = 0; // keeps the audio graph running without playing the mic back
    source.connect(worklet);
    worklet.connect(mute);
    mute.connect(audioContext.destination);

    const scheme = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${scheme}://${location.host}/ws/transcribe?language=${els.language.value}`);
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
      worklet.port.onmessage = (event) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(event.data);
        }
      };
      els.stop.disabled = false;
      setStatus("Listening...");
    };
    ws.onmessage = handleMessage;
    ws.onerror = () => {
      hadError = true;
      setStatus("Connection error. Is the server running?");
    };
    ws.onclose = () => {
      clearTimeout(finishTimer);
      stopMicrophone();
      closeAudioContext();
      resetButtons();
      ws = null;
      if (!hadError) {
        setStatus("Stopped");
      }
    };
  } catch (error) {
    hadError = true;
    setStatus(`Could not start: ${error.message}`);
    stopMicrophone();
    closeAudioContext();
    resetButtons();
  }
}

function stop() {
  els.stop.disabled = true;
  setStatus("Finishing...");
  stopMicrophone();
  // Short delay so the last audio chunks reach the server before the stop command.
  setTimeout(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "stop" }));
      finishTimer = setTimeout(() => {
        if (ws) {
          ws.close();
        }
      }, 20000);
    } else {
      closeAudioContext();
      resetButtons();
    }
  }, 300);
}

async function finishSession() {
  if (!sessionId || segments.length === 0) {
    return;
  }
  try {
    const response = await fetch(`/api/sessions/${sessionId}/finish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript: segments.join("\n") }),
    });
    if (!response.ok) {
      throw new Error("Could not save the session transcript.");
    }
    els.noteOutput.disabled = false;
    els.noteOutput.value = "";
  } catch (error) {
    els.noteStatus.textContent = error.message;
  }
}

async function generateNote() {
  els.generate.disabled = true;
  els.noteOutput.value = "";
  els.noteStatus.textContent = "Generating note...";
  try {
    await finishSession();
    let data;
    if (sessionId) {
      const response = await fetch(`/api/sessions/${sessionId}/note`, { method: "POST" });
      data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Request was rejected.");
      }
    } else {
      const response = await fetch("/api/notes/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: segments.join("\n") }),
      });
      data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Request was rejected.");
      }
    }
    const note = typeof data.note === "string" ? data.note : data.draft;
    els.noteOutput.value = note;
    els.noteOutput.disabled = false;
    els.saveNote.disabled = !sessionId;
    els.approveNote.disabled = !sessionId;
    els.noteStatus.textContent = "Draft note ready (AI-generated: review before use).";
  } catch (error) {
    els.noteStatus.textContent = `Could not generate note: ${error.message}`;
  } finally {
    els.generate.disabled = segments.length === 0;
  }
}

async function saveNote() {
  if (!sessionId) {
    return;
  }
  els.saveNote.disabled = true;
  try {
    const response = await fetch(`/api/sessions/${sessionId}/note`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: els.noteOutput.value }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : "Request was rejected.");
    }
    els.noteStatus.textContent = "Edit saved.";
  } catch (error) {
    els.noteStatus.textContent = `Could not save edit: ${error.message}`;
  } finally {
    els.saveNote.disabled = false;
  }
}

async function approveNote() {
  if (!sessionId) {
    return;
  }
  els.approveNote.disabled = true;
  els.saveNote.disabled = true;
  try {
    if (els.noteOutput.value.trim()) {
      await fetch(`/api/sessions/${sessionId}/note`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: els.noteOutput.value }),
      });
    }
    const response = await fetch(`/api/sessions/${sessionId}/approve`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : "Request was rejected.");
    }
    els.noteOutput.value = data.approved;
    els.noteOutput.disabled = true;
    els.noteStatus.textContent = "Note approved and locked.";
  } catch (error) {
    els.noteStatus.textContent = `Could not approve: ${error.message}`;
    els.approveNote.disabled = false;
    els.saveNote.disabled = false;
  }
}

els.start.addEventListener("click", start);
els.stop.addEventListener("click", stop);
els.generate.addEventListener("click", generateNote);
els.saveNote.addEventListener("click", saveNote);
els.approveNote.addEventListener("click", approveNote);
