import Mathlib

/-- The largest natural `n` with `n ! < 3 ^ n`. Must be a numeric literal. -/
abbrev p10_answer : ℕ := 6

/-- `p10_answer` is the greatest element of `{n : ℕ | n ! < 3 ^ n}`. -/
theorem p10_factorial_pow :
    IsGreatest {n : ℕ | Nat.factorial n < 3 ^ n} p10_answer := by
  -- `6` belongs to the set
  have hmem : Nat.factorial 6 < 3 ^ 6 := by
    norm_num
  refine ⟨hmem, ?_⟩
  intro n hn
  by_contra hle
  have hgt : 6 < n := Nat.lt_of_not_ge hle
  have hseven : (7 : ℕ) ≤ n := Nat.succ_le_of_lt hgt
  -- for `n ≥ 7` we have `n! ≥ 3^n`
  have hge : Nat.factorial n ≥ 3 ^ n := by
    have : ∀ m, (7 : ℕ) ≤ m → Nat.factorial m ≥ 3 ^ m := by
      intro m hm
      refine Nat.le_induction (motive := fun k => Nat.factorial k ≥ 3 ^ k) ?base ?step hm
      · -- base case `m = 7`
        norm_num
      · intro k hk hk_ih
        have h3le : (3 : ℕ) ≤ k + 1 := by
          have : (3 : ℕ) ≤ (7 : ℕ) := by decide
          exact Nat.le_trans this hk
        calc
          Nat.factorial (k + 1) = (k + 1) * Nat.factorial k := by
            simpa [Nat.factorial_succ]
          _ = Nat.factorial k * (k + 1) := by
            simpa [Nat.mul_comm]
          _ ≥ Nat.factorial k * 3 := by
            exact Nat.mul_le_mul_left _ h3le
          _ = 3 * Nat.factorial k := by
            simpa [Nat.mul_comm]
          _ ≥ 3 * 3 ^ k := by
            exact Nat.mul_le_mul_left _ hk_ih
          _ = 3 ^ (k + 1) := by
            simpa [pow_succ, Nat.mul_comm]
    exact this n hseven
  exact (not_lt.mpr hge) hn
