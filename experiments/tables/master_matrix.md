# Master matrix (comparator pass = 1)

Fill cells with `0` / `1` / `—` (not run).  
**Union** is derived: `S-Q OR S-G` (not a separate run).

| Problem | S-Q | S-G | Union | R-Q | R-G | H-QG | H-GQ |
|---------|----:|----:|------:|----:|----:|-----:|-----:|
| p01_linear | 1 (CAL-Q) | 1 (CAL-G) | 1 | — | — | — | — |
| p02_frac_cancel | | | | | | | |
| p03_sq_ge_two_ab | 1 | | | | | | |
| p04_sum_sq | | | | | | | |
| p05_gcd_mersenne | 0 | | | | | | |
| p06_pow_mod | 0 | | | | | | |
| p07_least_divisible | | | | | | | |
| p08_sum_products | | | | | | | |
| p09_imo1964 | 0 | | | | | | |
| p10_factorial_pow | 0 | | | | | | |
| putnam_2018_a1 | 0 | | | | | | |
| putnam_2020_a2 | | | | | | | |
| rmo_2000_2 | 0 | | | | | | |
| rmo_2000_3 | 0 | | | | | | |
| rmo_2000_6 | | | | | | | |
| rmo_2001_2 | | | | | | | |

## Notes

- Primary score: comparator accept under ≤ $1 and wall cap.
- Secondary (per REGISTRY): usd, calls_q, calls_g, lean_checks, wall.
- Link each filled cell to a REGISTRY `id` in commit messages or a footnote when results land.
- S-Q column (S_dev) filled from REGISTRY `SQ-Sdev` — run `outputs/s_q/20260825T164554Z/`, 2/9 pass ($0.076). p01 shows the CAL-Q reference (also passed under SQ-Sdev). S-G and R/H columns for S_dev still pending; S_eval rows intentionally blank (holdout not run).
