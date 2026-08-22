import Mathlib
import Mathlib.Tactic.IntervalCases

/-- The least positive integer `n` such that `77` divides `(n + 2) * (n + 3)`.
Must be a numeric literal. -/
abbrev p07_answer : ℕ := 19

/-- `p07_answer` is the least element of the set of positive `n` with
`77 ∣ (n + 2) * (n + 3)`. -/
theorem p07_least_divisible :
    IsLeast {n : ℕ | 0 < n ∧ 77 ∣ (n + 2) * (n + 3)} p07_answer := by
  constructor
  · -- Prove 19 is in the set
    constructor
    · -- 0 < 19
      norm_num
    · -- 77 ∣ (19 + 2) * (19 + 3)
      norm_num [Nat.dvd_iff_mod_eq_zero]
  · -- Prove 19 is the least
    intro n hn
    by_contra h
    have h_lt : n < 19 := lt_of_not_ge h
    interval_cases n <;> norm_num [Nat.dvd_iff_mod_eq_zero] at hn <;> contradiction
