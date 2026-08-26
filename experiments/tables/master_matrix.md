# Master matrix (comparator pass = 1)

Fill cells with `0` / `1` / `—` (not run).  
**Union** is derived: `S-Q OR S-G` (not a separate run).

**Results below are the full S_dev matrix run under the FIXED kit** (upstream
rate-limit fix `8739a10`, our commit `7baca49`); pre-fix `SQ-Sdev` is superseded.
S_eval rows are intentionally blank (holdout not run).

| Problem | S-Q | S-G | Union | R-Q | R-G | H-QG | H-GQ |
|---------|----:|----:|------:|----:|----:|-----:|-----:|
| p01_linear | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| p02_frac_cancel | — | — | — | — | — | — | — |
| p03_sq_ge_two_ab | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| p04_sum_sq | — | — | — | — | — | — | — |
| p05_gcd_mersenne | 0 | 1 | 1 | 0 | 1 | 0 | 0 |
| p06_pow_mod | 1 | 0 | 1 | 1 | 0 | 1 | 0 |
| p07_least_divisible | — | — | — | — | — | — | — |
| p08_sum_products | — | — | — | — | — | — | — |
| p09_imo1964 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| p10_factorial_pow | 0 | 0 | 0 | 1 | 1 | 0 | 0 |
| putnam_2018_a1 | 0 | 1 | 1 | 0 | 1 | 1 | 1 |
| putnam_2020_a2 | — | — | — | — | — | — | — |
| rmo_2000_2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| rmo_2000_3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| rmo_2000_6 | — | — | — | — | — | — | — |
| rmo_2001_2 | — | — | — | — | — | — | — |
| **S_dev total** | **3** | **4** | **5** | **4** | **5** | **4** | **3** |

## Notes

- Primary score: comparator accept under ≤ $1 and wall cap.
- Secondary (per REGISTRY): usd, calls_q, calls_g, lean_checks, wall.
- Link each filled cell to a REGISTRY `id` in commit messages or a footnote when results land.
- S_dev matrix run under fixed kit (`7baca49`), 6 arms, 2026-08-26, REGISTRY ids
  `Mx-*-Sdev`; 0 rate-limit errors. Runs `outputs/{s_q,s_g,r_q,r_g,h_qg,h_gq}/20260826T*Z/`.
- Key reads: **R ≥ S per model** (R-Q 4>3, R-G 5>4); repair unlocks
  `p10_factorial_pow` for both R arms (no S/H arm solves it). **Union(S)=5**;
  model complementarity: `p06` Qwen-only, `p05` GPT-OSS-only. Handoff picks up
  `putnam_2018_a1` (H-QG, H-GQ). Never solved by any arm: `p09_imo1964`,
  `rmo_2000_2`, `rmo_2000_3` (hardest H). Overall any-arm union = 6/9.
