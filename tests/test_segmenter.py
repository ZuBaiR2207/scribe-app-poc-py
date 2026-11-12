import numpy as np

from app.speech.segmenter import SAMPLE_RATE, SegmenterConfig, UtteranceSegmenter


def tone(seconds: float, amplitude: int = 5000) -> np.ndarray:
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    return (amplitude * np.sin(2 * np.pi * 220 * t)).astype(np.int16)


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * seconds), dtype=np.int16)


def feed_in_chunks(segmenter: UtteranceSegmenter, audio: np.ndarray, chunk: int = 1600):
    finished = []
    for i in range(0, len(audio), chunk):
        finished.extend(segmenter.feed(audio[i : i + chunk]))
    return finished


def test_silence_only_returns_nothing():
    assert feed_in_chunks(UtteranceSegmenter(), silence(3)) == []


def test_speech_then_silence_returns_one_utterance():
    audio = np.concatenate([silence(0.5), tone(1.0), silence(1.0)])
    result = feed_in_chunks(UtteranceSegmenter(), audio)
    assert len(result) == 1
    assert 1.0 * SAMPLE_RATE <= len(result[0]) <= 2.2 * SAMPLE_RATE


def test_short_blip_is_ignored():
    audio = np.concatenate([silence(0.5), tone(0.1), silence(1.0)])
    assert feed_in_chunks(UtteranceSegmenter(), audio) == []


def test_two_utterances():
    audio = np.concatenate([silence(0.3), tone(0.8), silence(1.0), tone(0.8), silence(1.0)])
    assert len(feed_in_chunks(UtteranceSegmenter(), audio)) == 2


def test_long_speech_is_cut():
    segmenter = UtteranceSegmenter(SegmenterConfig(max_utterance_s=2.0))
    audio = np.concatenate([tone(5.0), silence(1.0)])
    result = feed_in_chunks(segmenter, audio)
    assert len(result) >= 2
    assert all(len(u) <= 2.1 * SAMPLE_RATE for u in result)


def test_flush_returns_unfinished_speech():
    segmenter = UtteranceSegmenter()
    assert feed_in_chunks(segmenter, tone(1.0)) == []
    leftover = segmenter.flush()
    assert leftover is not None
    assert len(leftover) >= 0.9 * SAMPLE_RATE


def test_flush_when_idle_returns_none():
    assert UtteranceSegmenter().flush() is None


def test_uneven_chunk_sizes_give_same_result():
    audio = np.concatenate([silence(0.5), tone(1.0), silence(1.0)])
    result = feed_in_chunks(UtteranceSegmenter(), audio, chunk=777)
    assert len(result) == 1