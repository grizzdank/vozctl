"""Self-test: verify models, audio devices, and accessibility permissions."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def run_self_test(args) -> int:
    """Run all self-test checks. Returns 0 on success, 1 on failure."""
    results = []
    print("vozctl self-test")
    print("=" * 50)

    results.append(_check_models(args.model_dir))
    results.append(_check_audio())
    results.append(_check_accessibility())
    results.append(_check_vad(args.model_dir))
    results.append(_check_stt(args.model_dir))
    results.append(_check_intent_parser())

    print("=" * 50)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Results: {passed}/{total} checks passed")

    if all(results):
        print("All checks passed!")
        return 0
    else:
        print("Some checks failed — see above for details.")
        return 1


def _check(name: str, fn) -> bool:
    """Run a check function and print result."""
    try:
        fn()
        print(f"  [PASS] {name}")
        return True
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        return False


def _check_models(model_dir: str) -> bool:
    model_dir = Path(model_dir)
    required = ["silero_vad.onnx", "encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"]

    def check():
        missing = [f for f in required if not (model_dir / f).exists()]
        if missing:
            raise FileNotFoundError(f"Missing: {', '.join(missing)}. Run ./scripts/download-models.sh")

    return _check("Model files present", check)


def _check_audio() -> bool:
    def check():
        import sounddevice as sd
        devices = sd.query_devices()
        inputs = [d for d in devices if d["max_input_channels"] > 0]
        if not inputs:
            raise RuntimeError("No input audio devices found")

    return _check("Audio devices available", check)


def _check_accessibility() -> bool:
    def check():
        from vozctl.actions import check_accessibility
        if not check_accessibility():
            raise PermissionError("Accessibility permission not granted")

    return _check("Accessibility permission", check)


def _check_vad(model_dir: str) -> bool:
    def check():
        from vozctl.vad import VoiceActivityDetector
        VoiceActivityDetector(model_dir)

    return _check("VAD model loads", check)


def _check_stt(model_dir: str) -> bool:
    def check():
        from vozctl.stt import SpeechRecognizer
        SpeechRecognizer(model_dir)

    return _check("STT model loads", check)


def _check_intent_parser() -> bool:
    import os

    def check():
        from vozctl.intent import IntentParser
        parser = IntentParser(use_slm=True)
        # Verify fast path works
        result = parser.parse("save")
        assert result.actions[0].name == "save", f"Expected 'save', got {result.actions[0].name}"
        assert result.source == "fast_path", f"Expected fast_path, got {result.source}"

    ok = _check("Intent parser (fast path)", check)

    # SLM availability is informational, not a failure
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        print(f"  [INFO] SLM enabled (ANTHROPIC_API_KEY set)")
    else:
        print(f"  [INFO] SLM disabled (no ANTHROPIC_API_KEY) — rules-only mode")

    return ok
