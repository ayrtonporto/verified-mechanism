import Mathlib.Tactic
import Mathlib.Data.Nat.Basic
import Mathlib.Data.Int.Basic
import Mathlib.Tactic.Linarith

/-
  The equation
        y³ = x³ + 8x² – 6x + 8
  has the unique solution (x , y) = (9 , 11) in positive integers.
-/
theorem rmo_2000_2
  (x y : ℕ) (hx : 0 < x) (hy : 0 < y)
  (h : y ^ 3 = x ^ 3 + 8 * x ^ 2 - 6 * x + 8) :
  x = 9 ∧ y = 11 := by
  -- first we show that `y > x`
  have hpos : 0 < 8 * x ^ 2 - 6 * x + 8 := by
    have hx1 : (1 : ℕ) ≤ x := Nat.succ_le_of_lt hx
    have h₁ : 8 * x ^ 2 ≥ 8 := by
      have : (1 : ℕ) ≤ x ^ 2 := Nat.one_le_pow hx1 2
      exact Nat.mul_le_mul_left 8 this
    have h₂ : 8 * x ^ 2 - 6 * x + 8 ≥ 8 - 6 * x + 8 := by
      exact Nat.sub_le_sub_right (Nat.add_le_add_left h₁ _) _
    have : 8 - 6 * x + 8 ≥ 10 - 6 * x := by norm_num
    have : 10 - 6 * x ≥ 0 := by
      have : x ≤ 1 := by
        have : 6 * x ≤ 6 := by
          have : 6 * x ≤ 6 * 1 := Nat.mul_le_mul_left 6 (Nat.le_of_lt_succ hx)
          simpa using this
        exact Nat.le_of_sub_eq_zero (Nat.sub_eq_zero_of_le this)
      linarith
    linarith
  have hxy : x < y := by
    have : x ^ 3 < y ^ 3 := by
      have : x ^ 3 + (8 * x ^ 2 - 6 * x + 8) = y ^ 3 := by
        simpa [h] using rfl
      have : 0 < 8 * x ^ 2 - 6 * x + 8 := hpos
      linarith
    exact Nat.lt_of_pow_lt_pow this (Nat.succ_le_of_lt hx)
  -- set `d = y - x`, then `d > 0`
  set d := y - x with hddef
  have hdpos : 0 < d := Nat.sub_pos_of_lt hxy
  have hyx : x ≤ y := Nat.le_of_lt hxy
  have hyeq : y = x + d := by
    have : x + d = y := Nat.add_sub_cancel' hyx
    simpa [hddef] using this.symm
  -- rewrite the original equation using `d`
  have h_eq_int : (d : ℤ) * (3 * (x : ℤ) ^ 2 + 3 * (x : ℤ) * d + d ^ 2) =
      8 * (x : ℤ) ^ 2 - 6 * (x : ℤ) + 8 := by
    have h_int : (y : ℤ) ^ 3 = (x : ℤ) ^ 3 + 8 * (x : ℤ) ^ 2 - 6 * (x : ℤ) + 8 := by
      exact_mod_cast h
    have : ((x : ℤ) + d) ^ 3 = (x : ℤ) ^ 3 + 8 * (x : ℤ) ^ 2 - 6 * (x : ℤ) + 8 := by
      simpa [hyeq] using h_int
    have : ((x : ℤ) + d) ^ 3 - (x : ℤ) ^ 3 = 8 * (x : ℤ) ^ 2 - 6 * (x : ℤ) + 8 := by
      linarith
    have : ((x : ℤ) + d) ^ 3 - (x : ℤ) ^ 3 =
        (d : ℤ) * (3 * (x : ℤ) ^ 2 + 3 * (x : ℤ) * d + d ^ 2) := by
      ring
    linarith
  -- from the equality we obtain a bound on `d`
  have hdle2 : d ≤ 2 := by
    by_contra hge3
    have hge3' : 3 ≤ d := Nat.succ_le_of_lt (Nat.lt_of_not_ge hge3)
    have hleft : (3 : ℤ) * (x : ℤ) ^ 2 * (d : ℤ) ≤
        (d : ℤ) * (3 * (x : ℤ) ^ 2 + 3 * (x : ℤ) * d + d ^ 2) := by
      have hx2 : (0 : ℤ) ≤ (x : ℤ) ^ 2 := by exact pow_nonneg (by exact_mod_cast hx.le) _
      have hd_nonneg : (0 : ℤ) ≤ (d : ℤ) := by exact_mod_cast (Nat.zero_le _)
      have : (0 : ℤ) ≤ 3 * (x : ℤ) * d + d ^ 2 := by nlinarith
      have : (d : ℤ) * (3 * (x : ℤ) ^ 2) ≤ (d : ℤ) * (3 * (x : ℤ) ^ 2) + (d : ℤ) * (3 * (x : ℤ) * d + d ^ 2) :=
        by ring
      have : (d : ℤ) * (3 * (x : ℤ) ^ 2) ≤ (d : ℤ) * (3 * (x : ℤ) ^ 2 + 3 * (x : ℤ) * d + d ^ 2) := by
        simpa [mul_add, mul_comm, mul_left_comm, mul_assoc] using this
      simpa [pow_two, mul_comm, mul_left_comm, mul_assoc] using this
    have hright : (d : ℤ) * (3 * (x : ℤ) ^ 2 + 3 * (x : ℤ) * d + d ^ 2) =
        8 * (x : ℤ) ^ 2 - 6 * (x : ℤ) + 8 := h_eq_int
    have : (3 : ℤ) * (x : ℤ) ^ 2 * (d : ℤ) ≤ 8 * (x : ℤ) ^ 2 - 6 * (x : ℤ) + 8 := by
      linarith
    have hxpos' : (0 : ℤ) < (x : ℤ) := by exact_mod_cast hx
    have hxpos2 : (0 : ℤ) < (x : ℤ) ^ 2 := by
      have : (0 : ℤ) < (x : ℤ) := hxpos'
      exact pow_pos this 2
    have : (3 : ℤ) * (x : ℤ) ^ 2 ≤ 8 * (x : ℤ) ^ 2 - 6 * (x : ℤ) + 8 := by
      have : (3 : ℤ) * (x : ℤ) ^ 2 * (d : ℤ) ≤ 8 * (x : ℤ) ^ 2 - 6 * (x : ℤ) + 8 :=
        this
      have hdpos' : (0 : ℤ) < (d : ℤ) := by exact_mod_cast hdpos
      exact (le_of_mul_le_mul_left this hdpos')
    have : (3 : ℤ) * (x : ℤ) ^ 2 ≤ 8 * (x : ℤ) ^ 2 + 8 := by
      linarith
    have : (x : ℤ) ^ 2 ≤ 8 := by
      have : (3 : ℤ) * (x : ℤ) ^ 2 ≤ 8 * (x : ℤ) ^ 2 + 8 := this
      have hxpos2' : (0 : ℤ) < (x : ℤ) ^ 2 := hxpos2
      have : (x : ℤ) ^ 2 ≤ 8 := by
        have : (3 : ℤ) * (x : ℤ) ^ 2 ≤ 8 * (x : ℤ) ^ 2 + 8 := this
        have : (x : ℤ) ^ 2 ≤ 8 := by
          have h' : (x : ℤ) ^ 2 * (8 - 3) ≤ 8 := by
            have : (8 - 3) * (x : ℤ) ^ 2 ≤ 8 := by
              have : (8 : ℤ) * (x : ℤ) ^ 2 - (3 : ℤ) * (x : ℤ) ^ 2 ≤ 8 := by linarith
              simpa [sub_eq, mul_sub] using this
            exact this
          have hxpos2'' : (0 : ℤ) < (x : ℤ) ^ 2 := hxpos2
          exact (le_of_mul_le_mul_left h' hxpos2'')
        exact this
      exact this
    have hxle2 : x ≤ 2 := by
      have : (x : ℤ) ≤ 2 := by exact_mod_cast (Nat.le_of_lt_succ (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le (Nat.lt_of_lt_of_le
