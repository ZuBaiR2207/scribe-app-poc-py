const els = {
  language: document.getElementById("language"),
  start: document.getElementById("start"),
  stop: document.getElementById("stop"),
  status: document.getElementById("status"),
  transcript: document.getElementById("transcript"),
  partial: document.getElementById("partial"),
};

let ws = null;
let stream = null;
let audioContext = null;
let finishTimer = null;
let hadError = false;

function setStatus(text) {
  els.status.textContent = text;
}

function appendFinal(text) {
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
  hadError = false;
  els.start.disabled = true;
  els.language.disabled = true;
  els.transcript.textContent = "";
  els.partial.textContent = "";
  setStatus("Requesting microphone...");

  try {
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

els.start.addEventListener("click", start);
els.stop.addEventListener("click", stop);