import Mathlib.Tactic
import Mathlib.Data.Nat.ModEq
import Mathlib.NumberTheory.Divisors

/-- IMO 1964 P1 (a): `7 ∣ 2 ^ n - 1` iff `3 ∣ n`, for positive `n`. -/
theorem p09_a (n : ℕ) (hn : 0 < n) : 7 ∣ 2 ^ n - 1 ↔ 3 ∣ n := by
  have h_cycle : ∀ k : ℕ, 2 ^ k % 7 = 
    if k % 3 = 0 then 1
    else if k % 3 = 1 then 2
    else 4 := by
    intro k
    induction k using Nat.strong_induction_on with
    | h k ih =>
      match k with
      | 0 => simp
      | k + 1 =>
        have h₁ := ih k (by omega)
        simp [pow_succ, Nat.mul_mod, h₁]
        split_ifs <;> omega
  
  constructor
  · -- Forward: if 7 ∣ 2^n - 1, then 3 ∣ n
    intro h
    have h₁ : (2 ^ n) % 7 = 1 := by
      rw [← Nat.mod_add_div (2 ^ n) 7]
      simp [Nat.dvd_iff_mod_eq_zero] at h
      omega
    have h₂ : n % 3 = 0 := by
      have h₃ := h_cycle n
      simp [h₁] at h₃
      split_ifs at h₃ <;> omega
    exact Nat.dvd_of_mod_eq_zero h₂
  · -- Backward: if 3 ∣ n, then 7 ∣ 2^n - 1
    intro h
    obtain ⟨k, rfl⟩ := h
    rw [pow_mul]
    have : (2 ^ 3) % 7 = 1 := by norm_num
    have h₁ : (2 ^ 3) ^ k % 7 = 1 := by
      induction k with
      | zero => simp
      | succ k ih =>
        simp [pow_succ, Nat.mul_mod, ih, this]
        <;> norm_num
    have h₂ : 7 ∣ (2 ^ 3) ^ k - 1 := by
      rw [← Nat.mod_add_div ((2 ^ 3) ^ k) 7]
      simp [h₁]
      omega
    simpa [pow_mul] using h₂

/-- IMO 1964 P1 (b): no positive `n` has `7 ∣ 2 ^ n + 1`. -/
theorem p09_b (n : ℕ) (hn : 0 < n) : ¬7 ∣ 2 ^ n + 1 := by
  have h_cycle : ∀ k : ℕ, 2 ^ k % 7 = 
    if k % 3 = 0 then 1
    else if k % 3 = 1 then 2
    else 4 := by
    intro k
    induction k using Nat.strong_induction_on with
    | h k ih =>
      match k with
      | 0 => simp
      | k + 1 =>
        have h₁ := ih k (by omega)
        simp [pow_succ, Nat.mul_mod, h₁]
        split_ifs <;> omega
  
  intro h
  have h₁ : (2 ^ n) % 7 = 
    if n % 3 = 0 then 1
    else if n % 3 = 1 then 2
    else 4 := h_cycle n
  have h₂ : (2 ^ n + 1) % 7 ≠ 0 := by
    simp [h₁]
    split_ifs <;> norm_num <;> omega
  rw [Nat.dvd_iff_mod_eq_zero] at h
  contradiction
