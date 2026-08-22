import Mathlib

/-- The largest natural `n` with `n ! < 3 ^ n`. Must be a numeric literal. -/
abbrev p10_answer : ℕ := 6

/-- `p10_answer` is the greatest element of `{n : ℕ | n ! < 3 ^ n}`. -/
theorem p10_factorial_pow :
    IsGreatest {n : ℕ | Nat.factorial n < 3 ^ n} p10_answer := by
  constructor
  · -- Show 6 is in the set: 6! < 3^6
    norm_num [Nat.factorial]
  · -- Show any n in the set is ≤ 6
    intro n hn
    by_contra h
    -- If n > 6, then n ≥ 7
    have h₁ : n ≥ 7 := by omega
    -- Prove that for n ≥ 7, n! ≥ 3^n by induction
    have h₂ : ∀ k ≥ 7, Nat.factorial k ≥ 3 ^ k := by
      intro k hk
      induction' hk with k hk IH
      · -- Base case: k = 7
        norm_num [Nat.factorial]
      · -- Inductive step: k → k+1
        simp_all [Nat.factorial, pow_succ]
        nlinarith
    -- Apply this to our n
    have h₃ : Nat.factorial n ≥ 3 ^ n := h₂ n h₁
    -- Contradiction with hn: n! < 3^n
    linarith
