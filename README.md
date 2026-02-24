# vozctl

**Voice control for developers.** Open-source voice coding platform combining state-of-the-art speech recognition with a programmable command framework.

> *voz* (Spanish: voice) + *ctl* (Unix: control)

## Why

- **Talon Voice** has the best command framework but mediocre, closed-source recognition
- **Sotto/Wispr/SuperWhisper** have great recognition but zero command awareness
- **Dragon** is dead
- Nobody combines modern STT (NVIDIA Parakeet, 6% WER) with a programmable command layer

vozctl bridges the gap: **speak naturally, code precisely.**

## Architecture (Current)

```
Mic → [Silero VAD] → speech segments → [Parakeet STT] → transcript
                                                   ↓
                                      [Intent parser / command matcher]
                                       fast path (rules) first
                                       optional SLM for ambiguous cases
                                                   ↓
                                        [macOS CGEvent key injection]
```

Current runtime behavior:
1. **Silero VAD** (via sherpa-onnx) segments audio.
2. **Parakeet TDT 0.6B** (via sherpa-onnx) transcribes each segment offline.
3. **Intent parser** runs fast-path command matching (exact -> parameterized -> formatter -> NATO -> multi-sentence split).
4. **Optional SLM path** (currently Anthropic Haiku API) is used only for ambiguous mixed utterances.
5. **Planned SLM direction** is local inference, with **Qwen3-0.6B** as the current candidate and a Rust/Candle implementation path.
6. **Actions** dispatch via macOS CGEvent key injection.

## Features

Current (implemented):

- [x] Offline STT via sherpa-onnx (Parakeet TDT)
- [x] Silero VAD segmentation
- [x] macOS CGEvent key injection
- [x] Global hotkey toggle (`ctrl+alt+v` default)
- [x] Unified intent parser (fast path + fallback dictation + optional SLM)
- [x] Command precedence: exact -> parameterized -> formatter -> NATO -> dictation fallback
- [x] Multi-sentence splitting for Parakeet auto-punctuation
- [x] Replay mode (`--replay`) and self-test (`--self-test`)

Planned / in backlog:

- [ ] Local SLM (replace Haiku API path) using Qwen3-0.6B candidate; async intent parsing
- [ ] Declarative `.voz` grammar files / custom command definitions
- [ ] App-specific grammar/context switching (IDE vs terminal vs browser)
- [ ] Streaming partial transcripts with visual feedback
- [ ] Menubar app with COMMAND/DICTATION/PAUSED status indicator
- [ ] Cross-platform (macOS first, Linux, Windows)
- [ ] IDE plugins (VS Code, Neovim, JetBrains)
- [ ] Rust hot-path rewrite (audio/VAD/STT pipeline) with hybrid migration path
- [ ] Multi-language dictation

## Tech Stack

- **Current Runtime:** Python 3.11 (`python -m vozctl`)
- **Audio:** `sounddevice` (PortAudio)
- **VAD:** Silero via `sherpa-onnx`
- **STT Engine:** `sherpa-onnx` (Parakeet TDT 0.6B int8)
- **Intent Parsing:** Python rules + optional Anthropic Haiku API fallback (transitional)
- **Automation (macOS):** PyObjC Quartz / ApplicationServices CGEvent
- **Planned SLM Evolution:** Local Qwen3-0.6B via Rust/Candle provider (likely introduced behind a provider boundary before full Rust port)
- **Planned Runtime Evolution:** Rust hot path (audio/VAD/STT) with Python command grammar during migration

## Project Status

🚧 **Pre-alpha / Research phase**

Current implementation target: **macOS (dogfooding prototype)**.

Status summary (February 2026):

- Python prototype is functional for live mic and replay workflows
- Command matching and dictation behavior are actively evolving
- Latency diagnostics are implemented; p95 target work remains
- Rust rewrite is tracked in issues as a scoped migration effort, not yet started

See [docs/research/](docs/research/) for technical analysis and project brief.

## Getting Started

Prototype workflow (macOS):

- Create/activate `venv/`
- Install package + dependencies
- Download models with `./scripts/download-models.sh`
- Run `python -m vozctl --self-test`
- Run `python -m vozctl` or `python -m vozctl --replay tests/fixtures/test_speech.wav`

## Contributing

We welcome contributions! This project exists because the voice coding community deserves open-source tools with modern recognition. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache 2.0

## Acknowledgments

- [Talon Voice](https://talonvoice.com) & the [talonhub/community](https://github.com/talonhub/community) for pioneering voice coding
- [NVIDIA Parakeet](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2) for state-of-the-art open ASR
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) for local inference runtime
- [Samsung Montréal TRM research](https://arxiv.org/abs/2510.04871) for the tiny recursive model approach

---

*voz + ctl = voice control* 🐙
