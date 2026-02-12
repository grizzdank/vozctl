# AGENTS.md — vozctl

## Project
Offline voice control for developers: mic → Silero VAD → Parakeet TDT STT → command/dictation dispatch → macOS CGEvent key injection.

## Architecture
- **Package**: `src/vozctl/`, run via `python -m vozctl`
- **Venv**: `venv/` (always use virtual env, never global pip)
- **Models**: `models/` (downloaded via `./scripts/download-models.sh`)
- **State machine**: PAUSED ↔ COMMAND ↔ DICTATION
- **Command precedence**: exact → parameterized → formatter → NATO sequence → dictation fallback
- **Multi-sentence**: VAD segments are split on `.!?` and each part matched independently

## Key Technical Constraints

### sherpa-onnx (v1.12+)
- Use `OfflineRecognizer.from_transducer()` factory method with `model_type="nemo_transducer"`
- VAD `front` property is a **reference invalidated by `pop()`** — always read samples before popping
- Model files: `encoder.int8.onnx`, `decoder.int8.onnx`, `joiner.int8.onnx`, `tokens.txt`, `silero_vad.onnx`

### macOS CGEvent Injection
- Virtual keycodes are **physical QWERTY positions**, not alphabetical (a=0x00, b=0x0B, s=0x01)
- Always call `CGEventSetFlags(event, flags)` even with flags=0 to clear stale modifier state
- `type_text` interval: 2ms per key (lower causes dropped keys, higher adds latency)
- Both pynput (hotkey) and CGEvents (key injection) require Accessibility permissions

### Parakeet TDT Quirks
- Auto-adds punctuation (periods, commas, question marks)
- "cap" often transcribed as "tap"/"hat"/"hap" — all registered as uppercase NATO prefixes
- Number words mapped: "to" → 2, "for" → 4 (common misrecognitions)

## Issue Tracking
Issues tracked via `br` (beads-rust). Run `br list` or `br ready` to see current work.

## Module Guide
| Module | Purpose |
|--------|---------|
| `__main__.py` | CLI entry point, arg parsing, early accessibility check |
| `engine.py` | State machine, hotkey, main processing loop |
| `audio.py` | Mic enumeration, sounddevice stream management |
| `vad.py` | Silero VAD wrapper, segment accumulation |
| `stt.py` | Parakeet TDT offline transcription |
| `commands.py` | Command registry, matching, NATO alphabet, mode switching |
| `formatters.py` | Text formatters (snake_case, camelCase, etc.) |
| `actions.py` | macOS CGEvent key injection, accessibility gating |
| `context.py` | Frontmost app detection (bundle ID, window title) |
| `diagnostics.py` | Latency tracking, p95 reporting |
| `self_test.py` | `--self-test` checks (models, audio, accessibility) |

## Conventions
- Commit messages: no "Co-Authored-By" or "Generated with Claude" lines
- Always use venv, never global installs
- Mic default: ID 3 (HD Pro Webcam C920) for Dave's setup
