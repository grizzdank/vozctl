# Open-Source Voice Coding Platform: Project Brief

**Prepared for:** LFG Consulting
**Date:** 2026-02-11
**Version:** 1.0

---

## Executive Brief

There is a clear and growing gap in the voice coding market: Talon Voice offers the best command framework for hands-free development but relies on a closed-source, mediocre recognition engine (Conformer/wav2letter) and has a steep learning curve. Meanwhile, dictation apps like Wispr Flow, SuperWhisper, and Sotto deliver excellent speech-to-text via Whisper/cloud models but have zero awareness of programming constructs — they can transcribe "open paren" but can't execute `(`. No product bridges both worlds with modern, open-source recognition (NVIDIA Parakeet TDT 0.6B at 6.05% WER, sherpa-onnx for local inference) and a programmable command layer. Dragon is effectively dead (Nuance discontinued consumer products; Mac support ended 2018; Windows support tied to Win10 EOL Oct 2025). Serenade still exists but is lightly maintained. The market is ripe for disruption.

Building this platform is a **quarter-to-year project** depending on ambition level. Phase 1 (local STT + basic command grammar) is achievable in 6–8 weeks by a small team leveraging sherpa-onnx and the Talon community command corpus. However, the hard problems — reliable command/dictation mode switching, IDE-aware code generation, cross-platform audio capture, and editor integrations — push a production-quality product into the 6–12 month range. LFG should evaluate this as a potential product line with a phased MVP strategy, not a weekend hack. The open-source angle creates moat through community contribution (like Talon's knausj/community commands), while SaaS tiers (cloud models, team dictionaries, enterprise compliance) generate revenue.

---

## 1. Market Gap Analysis

### What Exists

| Category | Products | Strengths | Weaknesses |
|----------|----------|-----------|------------|
| **Command frameworks** | Talon Voice | Programmable grammar, eye tracking, huge community command set (knausj/community), noise triggers | Closed-source engine, mediocre recognition, steep learning curve, single maintainer (Ryan Hileman), English only |
| **Dictation apps** | Wispr Flow ($15/mo), SuperWhisper ($5/mo), Sotto.to, AquaVoice | Excellent recognition (Whisper/cloud), polished UX, context-aware formatting | No command awareness, can't control IDE, no programmable grammar, subscription lock-in |
| **Code-specific** | Serenade | Natural language code commands, IDE plugins | Lightly maintained, limited language support, small community |
| **Legacy** | Dragon NaturallySpeaking | Mature product, good accuracy historically | Discontinued by Nuance/Microsoft. Mac dead since 2018. Windows tied to Win10 EOL (Oct 2025) |
| **OS built-in** | macOS Dictation, Windows Voice Access | Free, improving quality | No command framework, no code awareness, limited programmability |

### What's Missing

- **Open-source STT + programmable command layer** in one package
- **Modern recognition** (Parakeet/Whisper-class) paired with **code-aware grammar** (formatters, IDE actions, language-specific commands)
- **Mode switching** — seamless transition between dictation ("write an email") and commands ("go to line 50, select word, snake case")
- **Cross-platform** command framework (Talon is desktop-only, no web/remote)
- **LLM-augmented** voice coding — "voice → intent → LLM → code" pipeline for vibe coding

### Demand Drivers

| Driver | Size/Signal |
|--------|------------|
| **RSI/injury** | Core Talon community (~5K–10K active users). Growing as dev careers lengthen |
| **Accessibility compliance** | ADA, EU Accessibility Act (2025), WCAG — enterprise must support alternative input |
| **Vibe coding / AI pair programming** | Voice as natural interface to LLM coding assistants (Cursor, Copilot, Claude Code) |
| **Productivity** | Developers speaking 3x faster than typing; voice for boilerplate, typing for precision |
| **Developer ergonomics trend** | Standing desks → split keyboards → voice. Natural progression |

---

## 2. Technical Architecture

### Existing Components (Build vs. Leverage)

| Component | Exists? | Source | Status |
|-----------|---------|--------|--------|
| **Local STT engine** | ✅ | sherpa-onnx (k2-fsa) | Production-ready. Supports Parakeet TDT 0.6B (6.05% WER), Whisper, Zipformer. Real-time streaming. Cross-platform (macOS/Win/Linux/iOS/Android) |
| **Best-in-class ASR model** | ✅ | NVIDIA Parakeet TDT 0.6B v2/v3 | Open source (Apache 2.0). 600M params. 60min audio in 1 second. v3 adds 25 languages |
| **Whisper models** | ✅ | OpenAI Whisper, distil-whisper | Open source. Various sizes. Good accuracy but slower than Parakeet for streaming |
| **Command grammar/vocabulary** | ✅ | talonhub/community (formerly knausj_talon) | 1000+ commands, formatters, IDE bindings. Python-based `.talon` files. Apache 2.0 |
| **Voice Activity Detection** | ✅ | Silero VAD (via sherpa-onnx) | Production-ready, low latency |
| **Audio capture** | ⚠️ Partial | Platform APIs (CoreAudio, WASAPI, PulseAudio) | Needs cross-platform abstraction layer |
| **Command/dictation mode switching** | ❌ Build | — | Hard problem. Talon uses wake words; dictation apps are always-dictation |
| **Code-aware formatting** | ⚠️ Partial | Talon community commands | Exists for Talon but tightly coupled to Talon runtime |
| **IDE integration** | ⚠️ Partial | Serenade (VS Code), Talon (custom) | Need LSP-aware plugins for VS Code, JetBrains, Neovim |
| **LLM intent layer** | ❌ Build | — | "refactor this function" → LLM → code edit. New component |
| **Platform runtime/daemon** | ❌ Build | — | Core orchestrator: audio → STT → grammar → action dispatch |

### Proposed Architecture

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
│   Streaming or batch. Local or cloud fallback    │
└──────────────────────┬──────────────────────────┘
                       │ raw transcript
┌──────────────────────▼──────────────────────────┐
│        Command Parser / Grammar Engine           │
│   Mode detection: command vs. dictation          │
│   Grammar rules (adapted from Talon community)   │
│   Formatters (snake_case, camelCase, etc.)       │
└─────────┬────────────────────────┬──────────────┘
          │ command                 │ dictation
┌─────────▼──────────┐  ┌─────────▼──────────────┐
│  Action Dispatcher  │  │   Text Output Layer    │
│  IDE commands       │  │   Typed into active    │
│  OS automation      │  │   application          │
│  LLM intent bridge  │  │                        │
└─────────┬──────────┘  └────────────────────────┘
          │
┌─────────▼──────────────────────────────────────┐
│        Editor Plugins (VS Code, JetBrains,      │
│        Neovim) + OS Accessibility APIs           │
└────────────────────────────────────────────────┘
```

### Two-Model Pipeline Architecture (Dave's Insight)

The core innovation opportunity is a **two-model pipeline** that separates recognition from decision-making:

```
Voice → [Parakeet STT] → raw text → [Decision SLM] → formatted output / action
                                          ↑
                                    Window context
                                    (active app, cursor position,
                                     current mode, language)
```

1. **Parakeet** — handles raw speech-to-text. Fast, local, high accuracy. This is a solved problem.
2. **Decision SLM** — a small, fine-tuned language model that takes the raw transcript + active window context and decides:
   - Is this a command or dictation?
   - How should it be formatted? (lowercase for terminal, camelCase for JS, prose caps for email)
   - What action should be taken? (navigate, type, execute)

The Decision SLM could be tiny (sub-1B params), fine-tuned on labeled voice coding sessions, running locally with sub-100ms latency. This is exactly the "task-specific SLM" pattern from Dan Dimick's enterprise AI case study (Phase 2: fine-tuned small language models for specific workflows).

**Why this matters:** Talon solves mode switching with manual commands ("command mode" / "dictation mode"). Sotto ignores it entirely. The Decision SLM makes it **automatic** — speak naturally and the system figures out intent from context. This is the defensible innovation, not the STT layer.

**Training data approach:** Record voice coding sessions with labeled intent (command vs. dictation) + window context snapshots. Community-contributed training data creates a flywheel — more users → better model → more users.

### Key Technical Decisions

- **Language:** Rust core daemon (performance, cross-platform) + Python plugin layer (community accessibility, Talon grammar compat)
- **STT:** sherpa-onnx as primary runtime; supports model hot-swap
- **Grammar format:** `.talon`-compatible or superset for community adoption
- **Plugin protocol:** JSON-RPC or LSP-like for editor integration

---

## 3. Complexity & Lift Assessment

**Overall rating: Quarter project (MVP) / Year project (production)**

### Phase Breakdown

| Phase | Scope | Effort | People | Output |
|-------|-------|--------|--------|--------|
| **Phase 0: Spike** | sherpa-onnx + Parakeet streaming demo, basic command matching | 1–2 weeks | 1 dev | Proof of concept. "Say 'go to line 50' and it works" |
| **Phase 1: Core MVP** | Audio capture → STT → command parser → text output. macOS first. Basic command set (navigation, formatters, dictation) | 6–8 weeks | 2 devs | Usable daily driver for enthusiasts. CLI + menubar app |
| **Phase 2: IDE Integration** | VS Code extension, command/dictation mode switching, code-aware formatting | 8–12 weeks | 2–3 devs | Developer-focused product. Replaces Talon for basic workflows |
| **Phase 3: Polish & Platform** | Windows/Linux parity, JetBrains/Neovim plugins, LLM intent bridge, custom wake words, user-trainable vocabulary | 3–6 months | 3–4 devs | Production product. Competitive with Talon + dictation combo |
| **Phase 4: Enterprise & Scale** | Team dictionaries, compliance logging, SSO, cloud model option, mobile companion | 6–12 months | 4–6 devs | Enterprise-ready. SaaS revenue |

### Effort Reality Check

| Component | Deceptive complexity? | Notes |
|-----------|----------------------|-------|
| Audio capture | 🔴 High | Platform-specific nightmares. macOS permissions, Windows audio routing, Linux fragmentation |
| STT integration | 🟢 Low | sherpa-onnx does the heavy lifting. Well-documented |
| Command grammar parser | 🟡 Medium | Talon's grammar is powerful but undocumented internally. Need to reimplement or create compatible format |
| Mode switching | 🔴 High | The #1 UX challenge. False positives (command interpreted as dictation) destroy trust |
| IDE plugins | 🟡 Medium | VS Code extension API is well-documented. JetBrains less so. Neovim straightforward |
| Cross-platform | 🔴 High | Audio, accessibility APIs, text injection all differ per OS. Triple the surface area |
| LLM integration | 🟡 Medium | API calls are easy; reliable intent extraction from noisy speech is hard |

---

## 4. Competitive Landscape

| Product | Recognition | Commands | Open Source | Platform | Price | Status |
|---------|------------|----------|-------------|----------|-------|--------|
| **Talon Voice** | Conformer (built-in, mediocre) or Dragon | ✅ Excellent (community) | ❌ Engine closed, commands open | macOS, Windows, Linux | Free (beta) / $15/mo (beta supporter) | Active, single maintainer |
| **Wispr Flow** | Cloud (excellent) | ❌ None | ❌ | macOS, Windows, iOS | $15/mo | Active, funded |
| **SuperWhisper** | Local Whisper (good) | ❌ None | ❌ | macOS | $5/mo | Active |
| **Sotto.to** | Cloud (good) | ❌ None | ❌ | macOS | ~$10/mo | Active |
| **Serenade** | Custom (decent) | ✅ Natural language code | Partial (VS Code plugin) | macOS, Windows, Linux | Free | Low maintenance |
| **Dragon** | Legacy (was excellent) | Basic macros | ❌ | Windows (Mac dead) | $500 one-time | **Effectively dead** |
| **macOS Dictation** | Apple (good, improving) | ❌ None | ❌ | macOS/iOS | Free | Active (OS-level) |
| **AquaVoice** | Cloud | ❌ None | ❌ | macOS | $8–10/mo | Active |
| **OpenWhispr** | Whisper (local) | ❌ None | ✅ | Cross-platform | Free | Community project |
| **🆕 This Project** | Parakeet/Whisper (local, SOTA) | ✅ Programmable grammar | ✅ Full | Cross-platform | Free + SaaS tiers | Proposed |

### Competitive Moat Analysis

- **vs. Talon:** Better recognition (Parakeet >> Conformer), fully open source, lower learning curve. Risk: Talon's community loyalty is strong; Ryan could open-source or improve recognition.
- **vs. Wispr/SuperWhisper:** Command awareness, open source, no subscription for core. Risk: They could add command layers.
- **vs. Serenade:** More active development, better models, community-driven. Serenade's natural language approach is interesting but fragile.
- **Key moat:** Open-source community commands + local SOTA recognition + extensible grammar. Hard for closed-source competitors to replicate the community flywheel.

---

## 5. Business Model Options

| Model | Revenue Source | Margin | Difficulty | Notes |
|-------|---------------|--------|------------|-------|
| **Open Core + SaaS** | Cloud STT (higher accuracy), team features, sync | High (80%+) | Medium | Core free and open. Cloud tier for convenience/enterprise. Similar to GitLab model |
| **Enterprise Licensing** | On-prem deployment, compliance logging, SSO, SLA | High | High | Accessibility compliance is a forcing function for enterprise adoption |
| **Consulting/Integration** | Custom voice workflows, accessibility audits, setup services | Medium (60%) | Low | Immediate revenue. LFG's existing model. Pairs well with product |
| **Marketplace** | Premium command packs, IDE plugins, voice profiles | Medium | Medium | Like VS Code extensions marketplace. Community creates, platform monetizes |
| **Training/Certification** | Voice coding bootcamps, enterprise training | Medium | Low | Natural complement. "Voice Coding for Teams" |

### Recommended Approach

1. **Phase 1–2:** Open source everything. Build community. Revenue = $0 (investment)
2. **Phase 3:** Launch cloud tier ($10–15/mo) for enhanced models + sync. Consulting engagements for early enterprise adopters
3. **Phase 4:** Enterprise tier ($50–100/seat/mo). Compliance features, team management, priority support

**Revenue projection (conservative):**
- Year 1: $0–50K (consulting, early adopters)
- Year 2: $200–500K (SaaS + enterprise pilots)
- Year 3: $1–3M (enterprise expansion, if accessibility compliance wave hits)

---

## 6. Risks & Open Questions

### Technical Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Mode switching accuracy** — false command execution or missed commands | 🔴 Critical | Dedicated wake word, confidence thresholds, user-correctable. Research Talon's approach deeply |
| **Audio capture fragmentation** — cross-platform nightmare | 🟡 High | Start macOS-only. Use established crates (cpal for Rust). Don't go cross-platform until Phase 3 |
| **STT latency** — local models on CPU may be too slow for real-time | 🟡 High | Parakeet 110M (smaller) for streaming; 0.6B for batch. GPU acceleration optional. Benchmark early |
| **Talon grammar compatibility** — reimplementing `.talon` format is non-trivial | 🟡 Medium | Start with subset. Engage Talon community contributors early |
| **Model quality regression** — edge cases in noisy environments, accents | 🟡 Medium | Support model hot-swap. Let users choose Whisper vs. Parakeet vs. cloud |

### Business Risks

| Risk | Severity | Notes |
|------|----------|-------|
| **Talon opens up** — Ryan open-sources the engine or ships better STT | 🟡 High | Would reduce differentiation. But single-maintainer risk cuts both ways |
| **Big tech moves** — Apple/Microsoft/Google add command frameworks to OS dictation | 🔴 Critical | Apple Voice Control exists but is accessibility-focused, not dev-focused. Timeline: 2+ years if ever |
| **Small market** — voice coding remains niche | 🟡 Medium | RSI community is dedicated but small. Vibe coding trend could expand TAM 10x |
| **Community adoption** — open source without community is just public code | 🟡 High | Need early champions. Talon community members frustrated by closed engine are ideal targets |
| **Funding runway** — quarter+ of dev before revenue | 🟡 Medium | LFG can offset with consulting revenue. Phase 0 spike is cheap validation |

### Open Questions

1. **Build on Talon or from scratch?** — Talon's `.talon` grammar is powerful but undocumented. Could we contribute an open STT backend to Talon instead of competing?
2. **Rust core or Python?** — Rust is better for performance/cross-platform but limits community contributors. Python is accessible but slower.
3. **What's the minimum viable command set?** — Full Talon parity is years of work. What 50 commands cover 80% of use cases?
4. **LLM integration: feature or distraction?** — "Voice → LLM → code" is trendy but adds complexity. Should it be Phase 1 or Phase 3?
5. **Partnership vs. competition with Talon?** — The community overlap is huge. Adversarial positioning could backfire.
6. **Privacy story** — Local-first is a feature, but enterprise may want cloud. How to handle the tension?
7. **Who's the first user?** — RSI developers? Accessibility compliance? Vibe coders? Each requires different Phase 1 features.

---

## Appendix: Key Resources

- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) — Local STT runtime (Apache 2.0)
- [NVIDIA Parakeet TDT 0.6B v2](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2) — SOTA open ASR model (Apache 2.0)
- [Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) — Multilingual (25 languages)
- [talonhub/community](https://github.com/talonhub/community) — Community command set (Apache 2.0)
- [Talon Wiki](https://talon.wiki/) — Community documentation
- [Silero VAD](https://github.com/snakers4/silero-vad) — Voice activity detection
- [HuggingFace Open ASR Leaderboard](https://huggingface.co/spaces/hf-audio/open_asr_leaderboard) — Model benchmarks
