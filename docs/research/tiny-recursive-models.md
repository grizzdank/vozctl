# Tiny Recursive Models (TRM) — Research Brief

**Date:** 2026-02-11 | **Source:** Samsung SAIL Montréal (Jolicoeur-Martineau, Oct 2025) | **Paper:** [arXiv:2510.04871](https://arxiv.org/abs/2510.04871)

---

## Summary

Tiny Recursive Models achieve remarkable reasoning performance with **7 million parameters** by recursively applying a single 2-layer transformer to iteratively refine answers through latent-space reasoning (no chain-of-thought tokens). TRM achieves **45% on ARC-AGI-1** and **8% on ARC-AGI-2**, beating DeepSeek R1, o3-mini, and Gemini 2.5 Pro on these benchmarks.

**Relevance to vozctl:** TRM's architecture is a candidate for the Decision SLM — the intent classifier that takes raw STT output + window context and decides command vs. dictation. A 7M-param model would run in sub-millisecond on any device, far faster than even small LLMs.

---

## How It Works

### Core Concept: Depth Through Recursion, Not Size

A tiny 2-layer network runs the same computation many times, progressively improving its answer in latent space.

### Architecture

Three latent streams with a **single shared-weight module** (~7M params):

| Stream | Role |
|--------|------|
| **x** (input) | Embedded question (frozen after encoding) |
| **y** (answer) | Current best answer — refined at low frequency |
| **z** (latent) | Internal reasoning state — refined at high frequency |

### The Recursive Loop

```
Initialize: x = embed(input), y = zeros, z = zeros

For each supervision step (up to 16):
  ├─ REASONING: Repeat n times (e.g., n=8):
  │    z ← f(x + y + z)
  ├─ ANSWER UPDATE: Once:
  │    y ← f(y + z)        ← NO input x (forces role separation)
  └─ Repeat...

Final: output = output_head(y)
```

**Key design:** When updating `y`, the model does NOT see input `x`. This forces shared weights to learn two distinct roles. Effective depth: 2 layers × (n+1) recursions × 16 steps = hundreds of effective layers.

---

## Results

| Model | Params | ARC-AGI-1 | ARC-AGI-2 |
|-------|--------|-----------|-----------|
| **TRM** | **7M** | **45%** | **8%** |
| HRM | 27M | 40% | 5% |
| DeepSeek R1 | ~671B | 21.2% | — |
| o3-mini | — | 39.7% | — |
| Gemini 2.5 Pro | — | — | 4.9% |

### Caveats

- Task-specific — trained separately per benchmark, not a general model
- No text generation — classifier/puzzle-solver only
- Not compared to specialized ARC program-synthesis solvers

---

## Relevance to Decision SLM

| Aspect | TRM Approach | Traditional SLM |
|--------|-------------|-----------------|
| Model size | ~7M params, ~28 MB | 1–3B params, 2–6 GB |
| Latency | Sub-millisecond | 100ms+ |
| On-device | Yes, even mobile | Requires capable hardware |
| Training data | ~1,000 labeled examples | 10K+ |

**Fit for intent classification:** ⭐⭐⭐⭐ — Strong. Intent classification (command vs. dictation, given window context) is a structured reasoning task with finite output space — exactly TRM's sweet spot. The recursive refinement could handle ambiguous voice inputs by iteratively narrowing intent. Limitation: TRM doesn't do text generation, so it's a classifier only — pair with formatters for output.

### Training a Custom TRM

| Requirement | Details |
|-------------|---------|
| Training data | ~1,000 labeled (transcript, context) → intent examples |
| Hardware | Single consumer GPU sufficient |
| Training time | Hours, not days |
| Framework | PyTorch (official implementation) |

---

## Resources

- **Paper:** [arXiv:2510.04871](https://arxiv.org/abs/2510.04871)
- **Code:** [github.com/SamsungSAILMontreal/TinyRecursiveModels](https://github.com/SamsungSAILMontreal/TinyRecursiveModels)
- **Community:** [nano-trm](https://www.reddit.com/r/LocalLLaMA/comments/1pi4qmg/nanotrm_train_your_own_trm_in_a_few_minutes/)
