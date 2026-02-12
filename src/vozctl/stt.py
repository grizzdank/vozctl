"""Speech-to-text via sherpa-onnx Parakeet TDT."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


class SpeechRecognizer:
    """Offline (non-streaming) recognizer using Parakeet TDT."""

    def __init__(self, model_dir: str | Path):
        import sherpa_onnx

        model_dir = Path(model_dir)

        encoder = model_dir / "encoder.int8.onnx"
        decoder = model_dir / "decoder.int8.onnx"
        joiner = model_dir / "joiner.int8.onnx"
        tokens = model_dir / "tokens.txt"

        for f in (encoder, decoder, joiner, tokens):
            if not f.exists():
                raise FileNotFoundError(
                    f"STT model file not found: {f}\n"
                    "Run: ./scripts/download-models.sh"
                )

        self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(encoder),
            decoder=str(decoder),
            joiner=str(joiner),
            tokens=str(tokens),
            num_threads=4,
            provider="cpu",
            model_type="nemo_transducer",
        )
        log.info("STT loaded: Parakeet TDT (%s)", model_dir)

    def transcribe(self, samples: np.ndarray) -> tuple[str, float]:
        """Transcribe float32 samples. Returns (text, elapsed_seconds)."""
        t0 = time.monotonic()

        stream = self._recognizer.create_stream()
        stream.accept_waveform(16000, samples)
        self._recognizer.decode_stream(stream)
        text = stream.result.text.strip()

        elapsed = time.monotonic() - t0
        duration = len(samples) / 16000
        rtf = elapsed / duration if duration > 0 else 0
        log.info("STT: %.2fs audio → %.3fs (RTF=%.2f) → %r", duration, elapsed, rtf, text)

        return text, elapsed
