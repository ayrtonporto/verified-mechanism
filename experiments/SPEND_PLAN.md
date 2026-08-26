# Spend plan

**Hard cap (lab key):** ~**$50** total.  
**Never paste keys.** Key lives only in WSL `~/verified-mechanism/re-takehome-main/.env`.

## Reserves

| Bucket | Share | Notes |
|--------|-------|--------|
| Core science (S/R/H on S_dev, then frozen eval) | ~60–70% | Priority |
| Final clean reruns / case studies / submit validation | **20–30%** | Do not spend early |
| Contingency / failed runs | ~5–10% | |

## Phases

| Phase | Scope | Soft cap | Status |
|-------|--------|----------|--------|
| **0** | Docs, registry, arm code, cost-path verify | **$0** | done |
| **1** | Calib: cite Qwen p01; run S-G × p01 | **≤ $0.05** | done |
| 2 | Freeze S_dev / S_eval (split accepted 2026-08-26) | $0 | done |
| 3 | S-Q, S-G on S_dev | after calib rates | **done** (fixed kit) |
| 4 | R-Q, R-G on S_dev | after S | **done** (fixed kit) |
| 5 | H-QG, H-GQ on S_dev | after R | **done** (fixed kit) |
| 6–8 | Freeze arms → eval on S_eval → final agent | reserved | next |

**No full 16×6 matrix without a new line here + explicit user OK.** — S_dev 6-arm
matrix authorized and run 2026-08-26 (user OK "dale para adelante con la fila").

## Spent (ledger)

| date | id | usd | running_total | note |
|------|-----|-----|---------------|------|
| 2026-08-24 | CAL-Q-p01 | 0.00017719 | 0.00017719 | Pre-builder canonical Qwen p01 |
| 2026-08-25 | CAL-G-p01 | 0.00007538 | 0.00025257 | S-G factory × p01; partial failed attempts before success may have billed tiny LLM only (~same order) |
| 2026-08-25 | SQ-Sdev (superseded) | 0.07566 | 0.07591 | Pre-fix S-Q on S_dev, 2/9. Superseded by fixed-kit matrix. |
| 2026-08-26 | kit rate-limit fix | 0.00000 | 0.07591 | Adopt upstream 8739a10; no API spend. |
| 2026-08-26 | Mx S_dev matrix (6 arms) | 0.33316 | 0.40907 | Fixed kit, 0×429. S-Q 3, S-G 4, R-Q 4, R-G 5, H-QG 4, H-GQ 3. Per-arm: see REGISTRY Mx-*-Sdev. |

**Running total ≈ $0.41 of ~$50 lab cap / $10 session limit. Ample headroom.**

## Provisional cost rates (from known data)

| Source | Model | Problem | USD | Calls | Note |
|--------|-------|---------|-----|-------|------|
| CAL-Q-p01 | Qwen | p01 | ~1.8e-4 | 1 | Easy pass, 1 turn |
| CAL-G-p01 | GPT-OSS | p01 | ~7.5e-5 | 1 | Local WSL recipe; matches kit-rumor order |

### Provisional exploratory caps (post-calib freeze proposal)

| Family | Cap | Rationale |
|--------|-----|-----------|
| S pilot | `BASELINE_MAX_TURNS=8` (calib used 3) | p01 trivial at 1 turn; harder problems need headroom without full 25 |
| R/H pilot | propose=1, repair=3 | matched H vs R; cheap enough at ~1e-4/call on p01 |

Do not run full S_dev batches until split frozen + user OK.

After Phase 1, freeze exploratory turn caps for S_dev batches.

## Rules

1. No large matrix without a row in this file and user OK.
2. Prefer one arm × one set overnight.
3. Chrome closed; `LEAN_CONTAINER_MEMORY=8g`; `COMPARATOR_TIMEOUT_S=900`.
4. One Lean worker on this laptop RAM.
