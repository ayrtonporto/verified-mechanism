import Mathlib
import Mathlib.Tactic.IntervalCases

/-- The least positive integer `n` such that `77` divides `(n + 2) * (n + 3)`. -/
abbrev p07_answer : ℕ := 19

/-- `p07_answer` is the least element of the set of positive `n` with
`77 ∣ (n + 2) * (n + 3)`. -/
theorem p07_least_divisible :
    IsLeast {n : ℕ | 0 < n ∧ 77 ∣ (n + 2) * (n + 3)} p07_answer := by
  refine ⟨?mem, ?min⟩
  · -- `p07_answer` belongs to the set
    have hpos : (0 : ℕ) < 19 := by decide
    have hdiv : 77 ∣ (19 + 2) * (19 + 3) := by
      norm_num
    simpa [p07_answer] using And.intro hpos hdiv
  · -- minimality
    intro m hm
    rcases hm with ⟨hmpos, hdiv⟩
    by_contra hnot
    have hlt : m < 19 := Nat.lt_of_not_ge hnot
    have hle : m ≤ 18 := Nat.le_of_lt_succ hlt
    have hfalse : ¬ 77 ∣ (m + 2) * (m + 3) := by
      interval_cases m
      all_goals norm_num
    exact hfalse hdiv
