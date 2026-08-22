import Mathlib

abbrev putnam_2020_a2_solution : ℕ → ℕ := fun k => 4 ^ k

theorem putnam_2020_a2
  (k : ℕ) :
  (∑ j in Finset.Icc 0 k, 2 ^ (k - j) * Nat.choose (k + j) j) = putnam_2020_a2_solution k := by
  induction k with
  | zero => simp [putnam_2020_a2_solution]
  | succ k ih =>
    rw [Finset.sum_Icc_succ_top (by norm_num : 0 ≤ k.succ)]
    simp [putnam_2020_a2_solution, pow_add, pow_one, Nat.choose_succ_succ, mul_add, add_mul, mul_comm, mul_left_comm] at ih ⊢
    ring_nf at ih ⊢
    omega
