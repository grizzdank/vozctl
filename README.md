# vozctl

**Voice control for developers.** Open-source voice coding platform combining state-of-the-art speech recognition with a programmable command framework.

> *voz* (Spanish: voice) + *ctl* (Unix: control)

## Why

- **Talon Voice** has the best command framework but mediocre, closed-source recognition
- **Sotto/Wispr/SuperWhisper** have great recognition but zero command awareness
- **Dragon** is dead
- Nobody combines modern STT (NVIDIA Parakeet, 6% WER) with a programmable command layer

vozctl bridges the gap: **speak naturally, code precisely.**

## Architecture

```
Voice → [Parakeet STT] → raw text → [Decision SLM] → action
                                          ↑
                                   window context
                                   (app, cursor, mode, language)
```

Two-model pipeline:
1. **Parakeet TDT 0.6B** — local speech-to-text via sherpa-onnx. Fast, accurate, private.
2. **Decision SLM** — tiny model that classifies intent (command vs dictation) and formats output based on active window context.

## Features (Planned)

- [ ] Local STT via sherpa-onnx (Parakeet + Whisper models)
- [ ] Programmable command grammar (adapted from Talon community)
- [ ] Context-aware mode switching (terminal → lowercase, IDE → camelCase, prose → natural)
- [ ] Cross-platform (macOS first, Linux, Windows)
- [ ] IDE plugins (VS Code, Neovim, JetBrains)
- [ ] Custom command definitions (YAML/Python)
- [ ] Multi-language dictation

## Tech Stack

- **Runtime:** Rust (audio capture, low-latency core)
- **STT Engine:** sherpa-onnx (Parakeet TDT 0.6B, Whisper, Zipformer)
- **Decision Model:** Fine-tuned SLM (TRM-inspired, <100ms inference)
- **Command Grammar:** Python (Talon community compatible)
- **VAD:** Silero (via sherpa-onnx)

## Project Status

🚧 **Pre-alpha / Research phase**

See [docs/research/](docs/research/) for technical analysis and project brief.

## Getting Started

Coming soon. Phase 0 spike in progress.

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

*Built by [LFG Consulting](https://lfgconsultants.com)* 🐙
