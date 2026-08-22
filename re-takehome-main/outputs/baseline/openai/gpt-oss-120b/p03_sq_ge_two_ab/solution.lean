import Mathlib

/-- For any two real numbers `a` and `b`, show that `a ^ 2 + b ^ 2 ≥ 2 * a * b`. -/
theorem p03_sq_ge_two_ab (a b : ℝ) : a ^ 2 + b ^ 2 ≥ 2 * a * b := by
  -- nonnegativity of a square
  have h_nonneg : (0 : ℝ) ≤ (a - b) ^ 2 := by
    exact pow_two_nonneg (a - b)
  -- rewrite the left‑hand side
  have h_eq : a ^ 2 + b ^ 2 - 2 * a * b = (a - b) ^ 2 := by
    ring
  -- deduce the desired inequality
  have : a ^ 2 + b ^ 2 - 2 * a * b ≥ 0 := by
    simpa [h_eq] using h_nonneg
  linarith
