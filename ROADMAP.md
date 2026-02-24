# vozctl Roadmap

## Architecture

### Current Pipeline (Python Prototype)

```
Mic → [Silero VAD] → speech segments → [Parakeet STT] → transcript
                                                   ↓
                                    [Intent parser / command matcher]
                                     exact -> parameterized -> formatter
                                     -> NATO -> multi-sentence split
                                                   ↓
                                  optional SLM (ambiguous/mixed utterances)
                                                   ↓
                                           action dispatch (CGEvent)
```

Notes:
1. **VAD + STT** are local today (sherpa-onnx).
2. **Intent parsing** is primarily rule-based fast path, with optional SLM fallback.
3. **Current SLM path** uses Anthropic Haiku API as a transitional adapter.
4. **Target SLM direction** is local inference (Qwen3-0.6B candidate) via Rust/Candle behind a provider boundary.

### System Diagram (Current + Near-Term)

```
┌─────────────────────────────────────────────────┐
│                   User Voice                     │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│      Audio Capture Layer (current: sounddevice)   │
│     planned Rust hot path: cpal / native APIs     │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│           VAD (Silero via sherpa-onnx)            │
│         Voice activity → audio segments          │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              STT Engine (sherpa-onnx)            │
│   Current model: Parakeet TDT 0.6B int8          │
│   Batch mode per VAD segment. Local-only.        │
└──────────────────────┬──────────────────────────┘
                       │ raw transcript
┌──────────────────────▼──────────────────────────┐
│           Intent Parser / Grammar Engine          │
│   Fast path rules + formatters + NATO            │
│   Optional SLM for ambiguous mixed utterances    │
│   Multi-sentence split on STT punctuation        │
└─────────┬────────────────────────┬──────────────┘
          │ command                 │ dictation
┌─────────▼──────────┐  ┌─────────▼──────────────┐
│  Action Dispatcher  │  │   Text Output Layer    │
│  OS automation      │  │   macOS CGEvent keys   │
│  app context hooks  │  │   (PyObjC Quartz)      │
└────────────────────┘  └────────────────────────┘
```

### Key Technical Decisions

- **Current runtime:** Python (speed to dogfood and iterate on command UX).
- **Rust migration:** planned as a scoped hot-path rewrite (audio/VAD/STT), likely hybrid before full rewrite.
- **STT:** sherpa-onnx with Parakeet TDT 0.6B (batch, not streaming)
- **VAD:** Silero via sherpa-onnx
- **Key injection:** macOS CGEvent (Phase 0). Cross-platform abstraction later.
- **Command matching:** exact → parameterized → formatter → NATO → dictation fallback
- **SLM today:** optional Anthropic API fallback (transitional adapter)
- **SLM target:** local Qwen3-0.6B via Candle; keep provider interface stable while Python command UX evolves
- **Issue tracking:** `br` (beads-rust) is the source of truth for execution order

---

## Phases

### Phase 0: Dogfood Prototype (In Progress)

**Goal:** Working proof of concept. "Say 'go to line 50' and it works."

- [x] sherpa-onnx + Parakeet TDT integration
- [x] Silero VAD → batch STT pipeline
- [x] Command registry with exact + parameterized + formatter + NATO matching
- [x] Global hotkey toggle (default `ctrl+alt+v`)
- [x] macOS CGEvent key injection
- [x] Unified intent parser (rules fast path + fallback dictation + optional SLM)
- [x] NATO alphabet for spelling
- [x] Multi-sentence split for Parakeet auto-punctuation
- [x] Self-test (`--self-test`)
- [x] Replay mode (`--replay`) and latency diagnostics
- [ ] Latency target: <800ms p95

**Scope:** macOS only, Python runtime, local VAD/STT, hardcoded command registry.

### Phase 1: Core MVP (6–8 weeks)

**Goal:** Usable daily driver for enthusiasts.

- [ ] Fix priority bugs in command matching and speech misrecognitions (`bd-2a1`, `bd-270`)
- [ ] Local SLM migration (Anthropic -> local Qwen3-0.6B candidate via Candle) (`bd-078`) and async intent parsing (`bd-c2f`)
- [ ] Expand fast-path patterns to reduce SLM calls (`bd-6e7`)
- [ ] Menubar app with status indicator (`bd-2t1`)
- [ ] Streaming partial transcripts / visual feedback (`bd-2hu`)
- [ ] App-specific grammar/context switching (`bd-9z9`)
- [ ] Declarative `.voz` grammar files (`bd-250`)
- [ ] Rust hot-path spike: audio/VAD/STT pipeline with Python intent/actions retained (`bd-3af`, scoped)
- [ ] Keep SLM provider boundary stable so local Candle integration can land before/alongside broader Rust migration

### Phase 2: IDE Integration (8–12 weeks)

- [ ] VS Code extension / LSP-aware voice commands (`bd-2m5`)
- [ ] Neovim plugin (`bd-1bz`)
- [ ] JetBrains plugin (`bd-1sw`)
- [ ] Code-aware formatting from editor context (`bd-17r`)
- [ ] LLM intent bridge for voice-to-code tasks (`bd-2do`)

### Phase 3: Polish & Platform (3–6 months)

- [ ] Linux support (audio + injection stack) (`bd-3eo`)
- [ ] Windows support (audio + injection stack) (`bd-dqh`)
- [ ] Custom wake word support (`bd-37s`)
- [ ] User-trainable vocabulary / pronunciations (`bd-2di`)
- [ ] Noise trigger support (`bd-c4u`)
- [ ] Cloud STT fallback option (`bd-319`)

### Phase 4: Community & Scale (6–12 months)

- [ ] Team dictionaries and shared command sets (`bd-c7e`)
- [ ] Compliance logging / audit trail (`bd-2k2`)
- [ ] Enterprise auth / SSO (`bd-jhw`)
- [ ] Mobile companion (`bd-36d`)
- [ ] Shareable command packs / community command repository

---

## Effort Reality Check

| Component | Complexity | Notes |
|-----------|-----------|-------|
| Audio capture | 🔴 High | Platform-specific. macOS permissions, Windows audio routing, Linux fragmentation |
| STT integration | 🟡 Medium | sherpa-onnx is working in Python; Rust crate/runtime parity is the real risk |
| Command grammar parser | 🟡 Medium | Rich rule behavior exists; migration risk is regressions, not greenfield design |
| Intent parsing / SLM | 🔴 High | Latency, ambiguity handling, and fallback behavior determine UX trust |
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
