"""Run every benchmark clip through several faster-whisper settings and score them."""

import csv
import re
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

import jiwer
from faster_whisper import WhisperModel

MANIFEST = Path("benchmark/manifest.csv")
CLIPS_DIR = Path("benchmark/clips")
RESULTS = Path("benchmark/results.csv")

MODELS = ["base", "small"]
LANGUAGE_MODES = ["auto", "fixed"]  # auto: Whisper detects; fixed: force the clip's language


def normalise(text: str, remove_spaces: bool = False) -> str:
    """Lowercase and strip punctuation so formatting differences are not counted as errors."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[^\w\s]", " ", text)   # punctuation -> space (\w keeps letters, digits, Chinese)
    text = re.sub(r"\s+", " ", text).strip()
    if remove_spaces:
        text = text.replace(" ", "")
    return text


def score(reference: str, hypothesis: str, lang: str) -> tuple[str, float]:
    """Return (metric name, error rate). Mandarin uses CER, everything else WER."""
    if lang == "zh":
        ref = normalise(reference, remove_spaces=True)
        hyp = normalise(hypothesis, remove_spaces=True)
        return "CER", (jiwer.cer(ref, hyp) if hyp else 1.0)
    ref = normalise(reference)
    hyp = normalise(hypothesis)
    return "WER", (jiwer.wer(ref, hyp) if hyp else 1.0)


def load_manifest() -> list[dict[str, str]]:
    with MANIFEST.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def find_clip(clip_id: str) -> Path | None:
    """Find benchmark/clips/<id>.<any extension>, or None if it was not recorded."""
    return next(CLIPS_DIR.glob(f"{clip_id}.*"), None)


def transcribe_clip(model: WhisperModel, path: Path, language: str | None):
    kwargs = {}
    if language == "zh":
        # Whisper often answers in Traditional characters; this prompt nudges it to Simplified.
        kwargs["initial_prompt"] = "以下是普通话的句子。"
    start = time.perf_counter()
    segments, info = model.transcribe(
        str(path), language=language, beam_size=5, vad_filter=True, **kwargs
    )
    text = " ".join(segment.text.strip() for segment in segments)
    seconds = time.perf_counter() - start
    return text, info, seconds


def print_summary(results: list[dict]) -> None:
    errors = defaultdict(list)
    rtfs = defaultdict(list)
    for r in results:
        errors[(r["model"], r["mode"], r["category"])].append(r["error"])
        rtfs[r["model"]].append(r["rtf"])

    print("\nAverage error rate (lower is better)")
    for (model, mode, category), values in sorted(errors.items()):
        print(f"  {model:6} {mode:6} {category:9} {sum(values) / len(values):7.1%}  (n={len(values)})")

    print("\nAverage real-time factor (below 1.0 = faster than real time)")
    for model, values in sorted(rtfs.items()):
        print(f"  {model:6} {sum(values) / len(values):.2f}")


def main() -> None:
    clips = load_manifest()
    results: list[dict] = []

    for model_name in MODELS:
        print(f"\nLoading model: {model_name}")
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        for mode in LANGUAGE_MODES:
            for clip in clips:
                path = find_clip(clip["id"])
                if path is None:
                    print(f"  skip {clip['id']} (no audio file)")
                    continue
                language = clip["lang"] if mode == "fixed" else None
                text, info, seconds = transcribe_clip(model, path, language)
                metric, error = score(clip["reference"], text, clip["lang"])
                results.append({
                    "model": model_name,
                    "mode": mode,
                    "id": clip["id"],
                    "category": clip["category"],
                    "metric": metric,
                    "error": error,
                    "detected_language": info.language,
                    "rtf": seconds / info.duration if info.duration else 0.0,
                    "hypothesis": text,
                })
                print(f"  {model_name} {mode:5} {clip['id']:12} {metric} {error:.1%}")

    if not results:
        raise SystemExit("No clips found. Record some into benchmark/clips first.")

    with RESULTS.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        for r in results:
            writer.writerow({**r, "error": round(r["error"], 4), "rtf": round(r["rtf"], 3)})

    print_summary(results)
    print(f"\nDetails saved to {RESULTS}")


if __name__ == "__main__":
    main()
