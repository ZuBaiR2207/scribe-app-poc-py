const els = {
  table: document.querySelector("#sessionTable tbody"),
  detail: document.getElementById("detail"),
  transcript: document.getElementById("detailTranscript"),
  note: document.getElementById("detailNote"),
  noteStatus: document.getElementById("detailNoteStatus"),
  edit: document.getElementById("detailEdit"),
  save: document.getElementById("detailSave"),
  approve: document.getElementById("detailApprove"),
  status: document.getElementById("detailStatus"),
};

let currentSession = null;

async function loadList() {
  const response = await fetch("/api/sessions");
  const rows = await response.json();
  els.table.textContent = "";
  for (const row of rows) {
    const tr = document.createElement("tr");
    const date = document.createElement("td");
    date.textContent = new Date(row.created_at).toLocaleString();
    const status = document.createElement("td");
    status.textContent = row.status;
    const consent = document.createElement("td");
    consent.textContent = row.consent ? "Yes" : "No";
    const open = document.createElement("td");
    const link = document.createElement("button");
    link.type = "button";
    link.textContent = "Open";
    link.addEventListener("click", () => openSession(row.id));
    open.appendChild(link);
    tr.append(date, status, consent, open);
    els.table.appendChild(tr);
  }
}

async function openSession(id) {
  currentSession = id;
  const response = await fetch(`/api/sessions/${id}`);
  const session = await response.json();
  els.detail.hidden = false;
  els.transcript.textContent = session.transcript || "(no transcript)";
  els.note.textContent = session.approved || session.edited || session.draft || "(no note yet)";
  const locked = session.status === "approved";
  els.edit.hidden = locked;
  els.edit.value = session.edited || session.draft || "";
  els.save.disabled = locked || session.status === "recording";
  els.approve.disabled = locked || session.status === "recording";
  els.noteStatus.textContent = locked ? "Approved (locked)." : "";
  els.status.textContent = "";
}

async function saveEdit() {
  if (!currentSession) {
    return;
  }
  const response = await fetch(`/api/sessions/${currentSession}/note`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note: els.edit.value }),
  });
  const data = await response.json();
  els.noteStatus.textContent = response.ok
    ? "Edit saved."
    : (typeof data.detail === "string" ? data.detail : "Could not save edit.");
  if (response.ok) {
    els.note.textContent = data.edited || data.draft || "";
  }
}

async function approve() {
  if (!currentSession) {
    return;
  }
  if (els.edit.value.trim()) {
    await saveEdit();
  }
  const response = await fetch(`/api/sessions/${currentSession}/approve`, { method: "POST" });
  const data = await response.json();
  if (!response.ok) {
    els.noteStatus.textContent = typeof data.detail === "string" ? data.detail : "Could not approve.";
    return;
  }
  await openSession(currentSession);
}

els.save.addEventListener("click", saveEdit);
els.approve.addEventListener("click", approve);
loadList();
