"""Core engine: state machine, hotkey, mic → VAD → STT → command dispatch loop."""

from __future__ import annotations

import enum
import logging
import queue
import time
import threading

import numpy as np

from vozctl.audio import open_stream, resolve_mic, SAMPLE_RATE
from vozctl.vad import VoiceActivityDetector
from vozctl.stt import SpeechRecognizer
from vozctl.commands import match
from vozctl.context import get_frontmost_app
from vozctl.diagnostics import LatencyTracker, LatencyRecord

log = logging.getLogger(__name__)


class State(enum.Enum):
    LISTENING = "LISTENING"
    PAUSED = "PAUSED"


class Engine:
    """Main engine: ties audio, VAD, STT, commands together."""

    def __init__(self, args):
        self._args = args
        self._state = State.PAUSED
        self._audio_q: queue.Queue[np.ndarray] = queue.Queue()
        self._tracker = LatencyTracker()
        self._stop = threading.Event()

        # Resolve mic
        self._device_id = resolve_mic(
            mic_name=getattr(args, "mic_name", None),
            mic_id=getattr(args, "mic_id", None),
        )

    def _toggle_state(self) -> None:
        if self._state == State.LISTENING:
            self._state = State.PAUSED
            log.info("State: PAUSED")
        else:
            self._state = State.LISTENING
            log.info("State: LISTENING")

    def _setup_hotkey(self) -> None:
        """Register global hotkey toggle."""
        from pynput import keyboard

        hotkey_str = self._args.hotkey
        log.info("Registering hotkey: %s", hotkey_str)

        # Parse hotkey string like "ctrl+alt+v"
        parts = hotkey_str.lower().split("+")
        key_char = parts[-1]
        mods = set()
        for p in parts[:-1]:
            if p in ("ctrl", "control"):
                mods.add(keyboard.Key.ctrl)
            elif p in ("alt", "option"):
                mods.add(keyboard.Key.alt)
            elif p in ("cmd", "command", "super"):
                mods.add(keyboard.Key.cmd)
            elif p in ("shift",):
                mods.add(keyboard.Key.shift)

        current_mods: set = set()

        def on_press(key):
            if isinstance(key, keyboard.Key) and key in mods:
                current_mods.add(key)
            elif hasattr(key, "char") and key.char == key_char:
                if mods.issubset(current_mods):
                    self._toggle_state()

        def on_release(key):
            if isinstance(key, keyboard.Key) and key in mods:
                current_mods.discard(key)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()

    def _audio_callback(self, indata, frames, time_info, status):
        """sounddevice callback — push audio blocks to queue."""
        if status:
            log.warning("Audio status: %s", status)
        self._audio_q.put(indata[:, 0].copy())

    def run(self) -> None:
        """Run the live engine loop."""
        log.info("Loading models...")
        vad = VoiceActivityDetector(self._args.model_dir)
        stt = SpeechRecognizer(self._args.model_dir)

        self._setup_hotkey()
        self._state = State.LISTENING
        log.info("State: LISTENING")
        log.info("Press %s to toggle pause/listen", self._args.hotkey)

        stream = open_stream(self._device_id, self._audio_callback)
        stream.start()

        try:
            self._process_loop(vad, stt)
        finally:
            stream.stop()
            stream.close()
            print()
            print(self._tracker.report())

    def _process_loop(self, vad: VoiceActivityDetector, stt: SpeechRecognizer) -> None:
        """Main processing loop: drain audio queue, run VAD, transcribe, dispatch."""
        while not self._stop.is_set():
            try:
                block = self._audio_q.get(timeout=0.1)
            except queue.Empty:
                continue

            if self._state == State.PAUSED:
                continue

            vad.accept_waveform(block)

            while vad.has_segment():
                vad_end = time.monotonic()
                samples = vad.pop_segment()
                audio_duration = len(samples) / SAMPLE_RATE

                # Skip very short segments
                if audio_duration < 0.2:
                    log.debug("Skipping short segment: %.2fs", audio_duration)
                    continue

                ctx = get_frontmost_app()
                log.debug("Context: %s (%s) — %s", ctx.app_name, ctx.bundle_id, ctx.window_title)

                text, stt_elapsed = stt.transcribe(samples)
                if not text:
                    continue

                cmd = match(text)
                dispatch_start = time.monotonic()

                try:
                    if cmd.args:
                        cmd.handler(**cmd.args) if cmd.kind == "parameterized" else cmd.handler()
                    else:
                        cmd.handler()
                except Exception as e:
                    log.error("Command %r failed: %s", cmd.name, e)

                dispatch_ts = time.monotonic()

                self._tracker.record(LatencyRecord(
                    vad_end_ts=vad_end,
                    stt_elapsed=stt_elapsed,
                    dispatch_ts=dispatch_ts,
                    audio_duration=audio_duration,
                ))

    def replay(self, wav_path: str) -> int:
        """Replay a .wav file through the pipeline."""
        import wave

        log.info("Replay mode: %s", wav_path)
        log.info("Loading models...")
        vad = VoiceActivityDetector(self._args.model_dir)
        stt = SpeechRecognizer(self._args.model_dir)

        with wave.open(wav_path, "rb") as wf:
            assert wf.getsampwidth() == 2, "Expected 16-bit WAV"
            assert wf.getnchannels() == 1, "Expected mono WAV"
            sr = wf.getframerate()
            raw = wf.readframes(wf.getnframes())

        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        if sr != SAMPLE_RATE:
            log.warning("WAV sample rate %d != %d, results may vary", sr, SAMPLE_RATE)

        # Feed in chunks matching VAD block size
        block_size = int(SAMPLE_RATE * 0.03)  # 30ms
        for i in range(0, len(samples), block_size):
            chunk = samples[i:i + block_size]
            vad.accept_waveform(chunk)

        vad.flush()

        segment_count = 0
        while vad.has_segment():
            vad_end = time.monotonic()
            seg = vad.pop_segment()
            audio_duration = len(seg) / SAMPLE_RATE

            if audio_duration < 0.2:
                log.debug("Skipping short segment: %.2fs", audio_duration)
                continue

            text, stt_elapsed = stt.transcribe(seg)
            dispatch_ts = time.monotonic()

            if text:
                cmd = match(text)
                print(f"[{cmd.kind}] {text!r} → {cmd.name}")
                segment_count += 1

                self._tracker.record(LatencyRecord(
                    vad_end_ts=vad_end,
                    stt_elapsed=stt_elapsed,
                    dispatch_ts=dispatch_ts,
                    audio_duration=audio_duration,
                ))

        print()
        print(self._tracker.report())
        if segment_count == 0:
            print("No speech segments detected.")
        return 0
