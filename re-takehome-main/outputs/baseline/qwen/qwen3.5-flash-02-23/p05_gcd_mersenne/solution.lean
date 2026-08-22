import Mathlib.Tactic
import Mathlib.Data.Nat.GCD.Basic

theorem p05_gcd_mersenne : Nat.gcd (2 ^ 1001 - 1) (2 ^ 1012 - 1) = 2 ^ 11 - 1 := by
  -- Show that 2^11 - 1 divides both numbers
  have h1 : (2 ^ 11 - 1) ∣ (2 ^ 1001 - 1) := by
    apply dvd_pow_sub_one
    norm_num
  have h2 : (2 ^ 11 - 1) ∣ (2 ^ 1012 - 1) := by
    apply dvd_pow_sub_one
    norm_num
  -- Show that 2^11 - 1 is the greatest common divisor
  have h3 : Nat.gcd (2 ^ 1001 - 1) (2 ^ 1012 - 1) = 2 ^ 11 - 1 := by
    apply Nat.dvd_antisymm
    · apply Nat.gcd_dvd_left
    · apply Nat.dvd_trans _ (Nat.gcd_dvd_right _)
      exact h2
  exact h3
