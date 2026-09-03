# Transcript notes (from run metadata)

These describe the two Part-Two exhibits from committed run metadata (stage, model
calls, outcome). Verbatim model content is omitted here; full transcripts are
available on request.

## p10_factorial_pow — same-model repair (positive)

Arm **R-G**. GPT-OSS proposes a candidate that Lean rejects with an unproven
upper-bound obligation for `n > k`; the **same** model repairs from the failed
proof plus the exact Lean diagnostic and closes the induction. Winning stage:
same-model GPT repair on the snapshot (~387 s), or `independent_slot_fallback`
under the tighter 20-minute validation cap (~17.5 min). This is the decisive
same-model repair win of Part Two (Finding 2).

## p05_gcd_mersenne — cross-model handoff (negative)

GPT-OSS solves `p05` alone (see `p05_gcd_mersenne_working.lean`). Under **H-GQ**
(GPT proposes, Qwen repairs), Qwen's repair rewrites toward a different approach
and abandons the near-closed trajectory, so `p05` is **lost**. This is the
negative cross-model-handoff result of Part Two (Finding 3): the handoff destroyed
a solo-capable win.
