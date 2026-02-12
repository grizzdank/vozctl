"""Voice Activity Detection via sherpa-onnx Silero VAD."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


class VoiceActivityDetector:
    """Wraps sherpa-onnx's VAD with segment accumulation."""

    def __init__(self, model_dir: str | Path):
        import sherpa_onnx

        model_dir = Path(model_dir)
        vad_model = model_dir / "silero_vad.onnx"
        if not vad_model.exists():
            raise FileNotFoundError(
                f"VAD model not found: {vad_model}\n"
                "Run: ./scripts/download-models.sh"
            )

        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(vad_model)
        config.silero_vad.min_silence_duration = 0.25
        config.silero_vad.min_speech_duration = 0.15
        config.silero_vad.threshold = 0.5
        config.sample_rate = 16000

        self._vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=30)
        log.info("VAD loaded: %s", vad_model.name)

    def accept_waveform(self, samples: np.ndarray) -> None:
        """Feed raw float32 audio samples into the VAD."""
        self._vad.accept_waveform(samples)

    def has_segment(self) -> bool:
        """Check if a complete speech segment is available."""
        return not self._vad.empty()

    def pop_segment(self) -> np.ndarray:
        """Pop the next completed speech segment as float32 samples."""
        segment = self._vad.front
        self._vad.pop()
        samples = np.array(segment.samples, dtype=np.float32)
        duration = len(samples) / 16000
        log.debug("VAD segment: %.2fs (%d samples)", duration, len(samples))
        return samples

    def flush(self) -> None:
        """Flush any remaining audio through the VAD."""
        self._vad.flush()
