import Mathlib

set_option maxRecDepth 1000
set_option exponentiation.threshold 3000

/-- The last two digits of `7 ^ 2026`. Must be a numeric literal. -/
abbrev p06_answer : ℕ := 49

/-- Compute `7 ^ 2026 % 100`. -/
theorem p06_pow_mod : 7 ^ 2026 % 100 = p06_answer := by
  norm_num [p06_answer]
