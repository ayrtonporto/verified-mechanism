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
| 2 | Freeze S_dev / S_eval | $0 | not started |
| 3 | S-Q, S-G on S_dev | after calib rates | blocked on split + OK |
| 4 | R-Q, R-G on S_dev | after S | blocked |
| 5 | H-QG, H-GQ on S_dev | after R | blocked |
| 6–8 | Freeze, eval, final agent | reserved | later |

**No full 16×6 matrix without a new line here + explicit user OK.**

## Spent (ledger)

| date | id | usd | running_total | note |
|------|-----|-----|---------------|------|
| 2026-08-24 | CAL-Q-p01 | 0.00017719 | 0.00017719 | Pre-builder canonical Qwen p01 |
| 2026-08-25 | CAL-G-p01 | 0.00007538 | 0.00025257 | S-G factory × p01; partial failed attempts before success may have billed tiny LLM only (~same order) |

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
