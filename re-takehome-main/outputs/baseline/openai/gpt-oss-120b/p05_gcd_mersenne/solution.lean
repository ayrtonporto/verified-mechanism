import Mathlib

open Nat

theorem p05_gcd_mersenne :
    Nat.gcd (2 ^ 1001 - 1) (2 ^ 1012 - 1) = 2 ^ 11 - 1 := by
  have h_gcd : Nat.gcd 1001 1012 = 11 := by norm_num
  simpa [h_gcd] using (Nat.gcd_pow_sub_pow (a := 2) (m := 1001) (n := 1012))
