# vozctl Roadmap

## Architecture

### Two-Model Pipeline

```
Voice → [Parakeet STT] → raw text → [Decision SLM] → action
                                          ↑
                                   window context
                                   (app, cursor, mode, language)
```

1. **Parakeet TDT 0.6B** — local speech-to-text via sherpa-onnx. Fast, accurate, private.
2. **Decision SLM** — tiny model that classifies intent (command vs dictation) and formats output based on active window context.

### System Diagram

```
┌─────────────────────────────────────────────────┐
│                   User Voice                     │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│         Audio Capture Layer (platform-specific)  │
│   CoreAudio / WASAPI / PulseAudio / ALSA        │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              VAD (Silero via sherpa-onnx)         │
│         Voice activity → audio segments          │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│         STT Engine (sherpa-onnx)                 │
│   Models: Parakeet TDT 0.6B / Whisper / custom  │
│   Batch mode. Local-only.                        │
└──────────────────────┬──────────────────────────┘
                       │ raw transcript
┌──────────────────────▼──────────────────────────┐
│        Command Parser / Grammar Engine           │
│   Mode detection: command vs. dictation          │
│   Grammar rules, formatters                      │
│   (snake_case, camelCase, etc.)                  │
└─────────┬────────────────────────┬──────────────┘
          │ command                 │ dictation
┌─────────▼──────────┐  ┌─────────▼──────────────┐
│  Action Dispatcher  │  │   Text Output Layer    │
│  OS automation      │  │   CGEvent key injection│
│  LLM intent bridge  │  │                        │
└────────────────────┘  └────────────────────────┘
```

### Key Technical Decisions

- **Phase 0:** Python (speed to dogfood). Rust rewrite planned for Phase 1+.
- **STT:** sherpa-onnx with Parakeet TDT 0.6B (batch, not streaming)
- **VAD:** Silero via sherpa-onnx
- **Key injection:** macOS CGEvent (Phase 0). Cross-platform abstraction later.
- **Command matching:** exact → parameterized → formatter → NATO → dictation fallback

---

## Phases

### Phase 0: Spike ✅ (In Progress)

**Goal:** Working proof of concept. "Say 'go to line 50' and it works."

- [x] sherpa-onnx + Parakeet TDT integration
- [x] Silero VAD → batch STT pipeline
- [x] ~20 hardcoded commands (navigation, mode switching, formatters)
- [x] Hotkey toggle (Ctrl+Shift+V)
- [x] macOS CGEvent key injection
- [x] State machine: PAUSED ↔ COMMAND ↔ DICTATION
- [x] NATO alphabet for spelling
- [x] Self-test (`--self-test`)
- [ ] Latency target: <800ms p95

**Scope:** macOS only, single mic, Python, no grammars.

### Phase 1: Core MVP (6–8 weeks)

**Goal:** Usable daily driver for enthusiasts.

- [ ] Vim voice grammar — natural phrases → vim motions ([#1](https://github.com/grizzdank/vozctl/issues/1))
- [ ] Custom command definitions (YAML or Python)
- [ ] Improved mode switching (confidence-based)
- [ ] Menubar app (macOS)
- [ ] User-configurable mic selection
- [ ] Expanded command set (50+ covering 80% of use cases)
- [ ] Rust rewrite of audio + VAD hot path (latency)

### Phase 2: IDE Integration (8–12 weeks)

- [ ] Neovim plugin (priority — vim grammar from Phase 1)
- [ ] Zed integration (via remote commands / keystroke simulation)
- [ ] Command/dictation mode switching via Decision SLM
- [ ] Code-aware formatting (language-dependent)
- [ ] Context-aware output (terminal vs editor vs prose)

### Phase 3: Polish & Platform (3–6 months)

- [ ] Linux support
- [ ] Windows support
- [ ] JetBrains plugin
- [ ] LLM intent bridge ("refactor this function" → action)
- [ ] Custom wake words
- [ ] User-trainable vocabulary
- [ ] Multi-language dictation (Parakeet v3)

### Phase 4: Community & Scale (6–12 months)

- [ ] Shareable command packs
- [ ] Community command repository
- [ ] Cloud model option (for users without GPU)
- [ ] Team/enterprise features
- [ ] Mobile companion

---

## Effort Reality Check

| Component | Complexity | Notes |
|-----------|-----------|-------|
| Audio capture | 🔴 High | Platform-specific. macOS permissions, Windows audio routing, Linux fragmentation |
| STT integration | 🟢 Low | sherpa-onnx does the heavy lifting |
| Command grammar parser | 🟡 Medium | Need extensible format without reimplementing Talon internals |
| Mode switching | 🔴 High | #1 UX challenge. False positives destroy trust |
| IDE plugins | 🟡 Medium | Neovim straightforward, JetBrains less so |
| Cross-platform | 🔴 High | Audio, accessibility APIs, text injection all differ per OS |
| LLM integration | 🟡 Medium | API calls easy; reliable intent extraction from noisy speech is hard |

---

## Design Principles

1. **Local-first** — no cloud dependency for core functionality
2. **Natural language** — if you'd feel stupid saying it out loud, the grammar is wrong
3. **Unix philosophy** — do one thing well, compose with other tools
4. **Open everything** — engine, commands, models. No closed-source bottlenecks
5. **Dogfood early** — Phase 0 exists to use daily, not to demo
