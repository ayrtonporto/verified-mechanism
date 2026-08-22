import Mathlib

abbrev putnam_2018_a1_solution : Set (ℤ × ℤ) :=
  {p | ((1 : ℚ) / p.1 + (1 : ℚ) / p.2 = (3 : ℚ) / 2018)}

theorem putnam_2018_a1
  (a b : ℤ)
  (h : 0 < a ∧ 0 < b) :
  ((1 : ℚ) / a + (1 : ℚ) / b = (3 : ℚ) / 2018) ↔
    (⟨a, b⟩ ∈ putnam_2018_a1_solution) := by
  rfl
