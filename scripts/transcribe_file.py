"""Transcribe one audio file with faster-whisper and print timing info."""

import argparse
import time
from pathlib import Path

import psutil
from faster_whisper import WhisperModel


def rss_mb() -> float:
    """Current RAM used by this Python process, in megabytes."""
    return psutil.Process().memory_info().rss / (1024 * 1024)


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe an audio file.")
    parser.add_argument("audio", type=Path, help="path to the audio file")
    parser.add_argument("--model", default="small", help="tiny, base, small, ...")
    parser.add_argument("--language", default=None, help="en, ms, zh, ta (default: auto-detect)")
    parser.add_argument("--vad", action="store_true", help="skip silence before transcribing")
    args = parser.parse_args()

    if not args.audio.exists():
        raise SystemExit(f"File not found: {args.audio}")

    # 1) Load the model (downloads it the first time).
    start = time.perf_counter()
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    load_seconds = time.perf_counter() - start

    # 2) Transcribe. `segments` is a generator, so the real work happens
    #    while we loop over it, and the timer must include the loop.
    start = time.perf_counter()
    segments, info = model.transcribe(
        str(args.audio),
        language=args.language,
        beam_size=5,
        vad_filter=args.vad,
    )
    text = " ".join(segment.text.strip() for segment in segments)
    transcribe_seconds = time.perf_counter() - start

    # 3) Report.
    rtf = transcribe_seconds / info.duration if info.duration else 0.0
    print("\n--- Transcript ---")
    print(text)
    print("\n--- Stats ---")
    print(f"Model:             {args.model} (int8, CPU)")
    print(f"Language:          {info.language} (confidence {info.language_probability:.2f})")
    print(f"Audio length:      {info.duration:.1f} s")
    print(f"Model load time:   {load_seconds:.1f} s")
    print(f"Transcribe time:   {transcribe_seconds:.1f} s")
    print(f"Real-time factor:  {rtf:.2f}  (below 1.0 = faster than real time)")
    print(f"RAM used:          {rss_mb():.0f} MB")


if __name__ == "__main__":
    main()