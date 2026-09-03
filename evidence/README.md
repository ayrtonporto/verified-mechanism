# Evidence

Redacted exhibits supporting the claims in the write-up (`writeup.pdf`). Full raw
run artifacts (`result.json`, `transcript.json`, `events.jsonl`) are excluded for
size and may contain unnecessary model content; they are retained by the author
and available on request. Each table in the report lists its immutable run
identifiers for traceability.

- **`putnam_2018_a1_tautology.lean`** — the answer-set tautology a model produces
  on `putnam_2018_a1`: it redefines the answer set to be the left-hand side of the
  question and closes with `rfl`. Comparator-passable but **non-substantive** (it
  proves nothing and silently replaces the statement); rejected by the acceptance
  guard. Cited in Appendix A, Case 1.
- **`p05_gcd_mersenne_working.lean`** — a genuine model-generated proof of `p05`
  (via `Nat.gcd_pow_sub_pow`), the working trajectory that cross-model handoff
  (`H-GQ`) discards. Cited in Appendix A, Case 2.
- **`transcript_notes.md`** — a note on the `p10` same-model repair and the `p05`
  cross-model handoff, described from committed run metadata.
