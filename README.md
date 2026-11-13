# Wellness Scribe (POC)

A proof-of-concept documentation assistant for wellness practitioners: record a session in the browser, transcribe it live, and let an LLM draft a structured session note for the practitioner to edit and approve.

**POC, test data only. Do not use real patient or client data.**

## What it does

1. **Record** — the browser captures microphone audio via an AudioWorklet at 16 kHz and streams it over a WebSocket. Consent is required (tick the box) before recording starts, and the session is created server-side.
2. **Transcribe live** — a VAD chunks speech and [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (`small`, `int8`, CPU-only) produces partial and final segments on the fly.
3. **Draft a note** — on stop, the transcript is saved and the text (never audio) is sent to an OpenAI-compatible LLM API which drafts a structured consultation record (session summary, goals, discussion points, recommendations, follow-up, items to confirm).
4. **Edit and approve** — the practitioner edits the draft, saves edits, and approves. Approved notes are locked. Everything is stored in SQLite.

## Privacy

- Audio never leaves this computer and is not stored.
- Only transcript text is sent to the external LLM API.
- The transcript is wrapped in delimiter tags and treated as data; instructions inside it are ignored.
- Nothing is logged; secrets live only in `.env` (git-ignored). Free-tier LLM APIs may use submitted data for training — hence test data only.

## Requirements

- Windows (or any OS with Python), Python 3.12
- 8 GB RAM, CPU only — no GPU needed for `small`/`int8`
- A modern Chrome/Edge for the microphone (AudioWorklet)
- An API key for any OpenAI-compatible LLM endpoint (e.g. Google AI Studio Gemini, OpenRouter, Groq)

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your LLM settings:

```ini
SCRIBE_LLM_API_KEY=<your key>
SCRIBE_LLM_MODEL=<model id, e.g. gemini-2.5-flash>
```

Defaults point at Google AI Studio's OpenAI-compatible endpoint; any provider works by changing `SCRIBE_LLM_BASE_URL`. See `.env.example` for all options (Whisper model, VAD tuning, timeouts, DB path).

## Run

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Open http://localhost:8000 in Chrome/Edge.

- `/` — recorder: consent → Start → live transcript → Generate note → edit → Approve
- `/sessions.html` — past sessions: list, open, edit drafts, approve

## CLI (transcribe an audio file)

```powershell
python scripts\transcribe_file.py samples\test_en.m4a
```

## Tests

```powershell
pytest
```

No test calls the real LLM or loads a real Whisper model; fakes are used throughout.

## Benchmark

```powershell
python scripts\run_benchmark.py
```

WER/CER results across models and language settings live in `benchmark/results.csv` and `docs/BENCHMARK.md`. Measured accuracy is reported, never claimed.

## Known limitations

- CPU-only: real-time factor depends on hardware; `small`/`int8` is the practical ceiling for live transcription on 8 GB RAM.
- Mixed-language sentences (EN/MS/zh/TA) can confuse language detection within a segment.
- Speaker labels are not detected; attribution is left to the "Items to confirm" section.
- The LLM is remote by design — do not run a local LLM in this POC.
- SQLite is single-file; fine for a POC, not for concurrent multi-user use.

## Project layout

```
app/
  main.py            FastAPI wiring
  config.py          pydantic-settings (env vars)
  db.py              SQLite sessions/notes storage
  api/               thin routers (transcribe WS, notes, sessions)
  speech/            SpeechEngine protocol, faster-whisper engine, VAD segmenter, WS handler
  notes/             NoteGenerator protocol, OpenAI-compatible adapter, prompt builder
static/              plain HTML + vanilla JS (ES modules)
scripts/             CLI transcription, benchmark runner
tests/               pytest (fakes only)
docs/                benchmark, privacy, decisions, user manual
```

## Milestones

- **M0** FastAPI skeleton + health endpoint
- **M1** CLI: audio file → transcript
- **M2** WER/CER benchmark across models/languages
- **M3** Real-time browser mic → WebSocket → live transcript
- **M4** LLM note generation (OpenAI-compatible adapter)
- **M5** Sessions: consent, SQLite, draft → edit → approve, past sessions
- **M6** Tidy UI, consultation-record note template
- **M7** Docs: architecture diagram, user manual, demo
