"""Latency tracking and performance diagnostics."""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class LatencyRecord:
    """Timing for a single utterance through the pipeline."""
    vad_end_ts: float  # monotonic time when VAD emitted segment
    stt_elapsed: float  # seconds STT took
    dispatch_ts: float  # monotonic time when action dispatched
    audio_duration: float  # seconds of audio in the segment
    intent_elapsed: float = 0.0  # seconds intent parser took (includes SLM if called)

    @property
    def total_latency(self) -> float:
        """End-of-speech → action dispatch."""
        return self.dispatch_ts - self.vad_end_ts

    @property
    def rtf(self) -> float:
        """Real-time factor for STT."""
        return self.stt_elapsed / self.audio_duration if self.audio_duration > 0 else 0


class LatencyTracker:
    """Rolling window latency tracker with percentile reporting."""

    def __init__(self, window_size: int = 100):
        self._records: deque[LatencyRecord] = deque(maxlen=window_size)

    def record(self, rec: LatencyRecord) -> None:
        self._records.append(rec)
        log.info(
            "Latency: total=%.0fms stt=%.0fms intent=%.0fms rtf=%.2f audio=%.2fs",
            rec.total_latency * 1000,
            rec.stt_elapsed * 1000,
            rec.intent_elapsed * 1000,
            rec.rtf,
            rec.audio_duration,
        )

    def p95_latency(self) -> float | None:
        """Return p95 total latency in seconds, or None if no data."""
        if not self._records:
            return None
        latencies = sorted(r.total_latency for r in self._records)
        idx = int(len(latencies) * 0.95)
        return latencies[min(idx, len(latencies) - 1)]

    def report(self) -> str:
        """Generate a human-readable latency report."""
        if not self._records:
            return "No latency data recorded."

        latencies = [r.total_latency * 1000 for r in self._records]
        stt_times = [r.stt_elapsed * 1000 for r in self._records]
        intent_times = [r.intent_elapsed * 1000 for r in self._records]
        rtfs = [r.rtf for r in self._records]

        lines = [
            f"Latency Report ({len(self._records)} samples)",
            "-" * 40,
            f"  Total latency:  p50={_percentile(latencies, 0.5):.0f}ms  "
            f"p95={_percentile(latencies, 0.95):.0f}ms  "
            f"max={max(latencies):.0f}ms",
            f"  STT time:       p50={_percentile(stt_times, 0.5):.0f}ms  "
            f"p95={_percentile(stt_times, 0.95):.0f}ms",
            f"  Intent parse:   p50={_percentile(intent_times, 0.5):.0f}ms  "
            f"p95={_percentile(intent_times, 0.95):.0f}ms",
            f"  RTF:            p50={_percentile(rtfs, 0.5):.2f}  "
            f"p95={_percentile(rtfs, 0.95):.2f}",
        ]

        p95 = _percentile(latencies, 0.95)
        if p95 <= 800:
            lines.append(f"  Target p95<800ms: PASS ({p95:.0f}ms)")
        else:
            lines.append(f"  Target p95<800ms: FAIL ({p95:.0f}ms)")

        return "\n".join(lines)


def _percentile(data: list[float], pct: float) -> float:
    """Simple percentile calculation."""
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * pct)
    return sorted_data[min(idx, len(sorted_data) - 1)]
