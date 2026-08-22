import Mathlib.Data.Nat.ModEq
import Mathlib.Tactic

open Nat

/-- IMO 1964 P1 (a): `7 ∣ 2 ^ n - 1` iff `3 ∣ n`, for positive `n`. -/
theorem p09_a (n : ℕ) (hn : 0 < n) : 7 ∣ 2 ^ n - 1 ↔ 3 ∣ n := by
  -- rewrite the divisibility condition as a modular equality
  have h7 : 7 ∣ 2 ^ n - 1 ↔ (2 ^ n) ≡ 1 [MOD 7] := by
    simpa [Nat.dvd_iff_mod_eq_zero, Nat.ModEq, sub_eq, Nat.sub_eq_iff_eq_add] using
      (show 7 ∣ 2 ^ n - 1 ↔ (2 ^ n - 1) % 7 = 0 from Iff.rfl)
  -- the order of 2 modulo 7 is 3
  have h23 : (2 ^ 3 : ℕ) ≡ 1 [MOD 7] := by
    dsimp [Nat.ModEq]; norm_num
  have hpow (k : ℕ) : (2 ^ (3 * k) : ℕ) ≡ 1 [MOD 7] := by
    simpa [pow_mul] using (h23.pow k)
  -- reduce the exponent modulo 3
  have hred : (2 ^ n : ℕ) ≡ 2 ^ (n % 3) [MOD 7] := by
    have hdecomp : n = 3 * (n / 3) + n % 3 := by
      exact (Nat.mod_mul_left_mod? ).symm   -- `Nat.mod_mul_left_mod?` is a placeholder for the standard lemma `Nat.mod_mul_left_mod` giving the decomposition
    -- rewrite using the decomposition
    calc
      (2 ^ n : ℕ)
          = 2 ^ (3 * (n / 3) + n % 3) := by simpa [hdecomp]
      _ = 2 ^ (3 * (n / 3)) * 2 ^ (n % 3) := by
        simpa [pow_add] using rfl
      _ = (2 ^ 3) ^ (n / 3) * 2 ^ (n % 3) := by
        simpa [pow_mul] using rfl
      _ ≡ 1 * 2 ^ (n % 3) [MOD 7] := by
        exact (Nat.ModEq.mul_left _ (hpow (n / 3)))
      _ = 2 ^ (n % 3) := by simp
  -- now finish the equivalence
  have hfinal : (2 ^ n : ℕ) ≡ 1 [MOD 7] ↔ n % 3 = 0 := by
    constructor
    · intro h
      have : 2 ^ (n % 3) ≡ 1 [MOD 7] := (hred.trans h).symm
      have hcases : n % 3 = 0 ∨ n % 3 = 1 ∨ n % 3 = 2 := by
        have hlt : n % 3 < 3 := Nat.mod_lt _ (by decide)
        interval_cases (n % 3) using hlt
      rcases hcases with h0 | h1 | h2
      · exact h0
      · have : (2 ^ (1 : ℕ) : ℕ) % 7 = 2 := by norm_num
        have : (2 ^ (1 : ℕ) : ℕ) ≡ 1 [MOD 7] := by
          dsimp [Nat.ModEq] at *
          simpa [this] using this
        exact (Nat.ModEq.ne_of_lt (by decide) this).elim
      · have : (2 ^ (2 : ℕ) : ℕ) % 7 = 4 := by norm_num
        have : (2 ^ (2 : ℕ) : ℕ) ≡ 1 [MOD 7] := by
          dsimp [Nat.ModEq] at *
          simpa [this] using this
        exact (Nat.ModEq.ne_of_lt (by decide) this).elim
    · intro h0
      have : n % 3 = 0 := h0
      have : 2 ^ (n % 3) = (1 : ℕ) := by simpa [this]
      have : (2 ^ (n % 3) : ℕ) ≡ 1 [MOD 7] := by
        dsimp [Nat.ModEq]; simpa [this]
      exact (hred.trans this)
  simpa [h7, Nat.dvd_iff_mod_eq_zero] using hfinal

/-- IMO 1964 P1 (b): no positive `n` has `7 ∣ 2 ^ n + 1`. -/
theorem p09_b (n : ℕ) (hn : 0 < n) : ¬7 ∣ 2 ^ n + 1 := by
  intro h
  have hmod : (2 ^ n : ℕ) ≡ 6 [MOD 7] := by
    have : (2 ^ n + 1) % 7 = 0 := (Nat.dvd_iff_mod_eq_zero).mp h
    dsimp [Nat.ModEq] at *
    have : (2 ^ n) % 7 = 6 := by
      have : (2 ^ n + 1) % 7 = ((2 ^ n) % 7 + 1 % 7) % 7 := by
        simpa [Nat.add_mod] using rfl
      simpa [Nat.mod_eq_of_lt (by decide : 1 < 7), Nat.mod_eq_of_lt (by decide : 6 < 7)] using this
    simpa [Nat.ModEq] using this
  have hred : (2 ^ n : ℕ) ≡ 2 ^ (n % 3) [MOD 7] := by
    -- same reduction as in part (a)
    have hdecomp : n = 3 * (n / 3) + n % 3 := by
      exact (Nat.mod_mul_left_mod? ).symm
    calc
      (2 ^ n : ℕ)
          = 2 ^ (3 * (n / 3) + n % 3) := by simpa [hdecomp]
      _ = 2 ^ (3 * (n / 3)) * 2 ^ (n % 3) := by
        simpa [pow_add] using rfl
      _ = (2 ^ 3) ^ (n / 3) * 2 ^ (n % 3) := by
        simpa [pow_mul] using rfl
      _ ≡ 1 * 2 ^ (n % 3) [MOD 7] := by
        have h23 : (2 ^ 3 : ℕ) ≡ 1 [MOD 7] := by
          dsimp [Nat.ModEq]; norm_num
        exact (Nat.ModEq.mul_left _ (h23.pow (n / 3)))
      _ = 2 ^ (n % 3) := by simp
  have : (2 ^ (n % 3) : ℕ) ≡ 6 [MOD 7] := hred.trans hmod
  have hcases : n % 3 = 0 ∨ n % 3 = 1 ∨ n % 3 = 2 := by
    have hlt : n % 3 < 3 := Nat.mod_lt _ (by decide)
    interval_cases (n % 3) using hlt
  rcases hcases with h0 | h1 | h2
  · have : (2 ^ (0 : ℕ) : ℕ) ≡ 6 [MOD 7] := by simpa [h0] using this
    have : (1 : ℕ) ≡ 6 [MOD 7] := this
    have : (1 % 7) = (6 % 7) := this
    norm_num at this
  · have : (2 ^ (1 : ℕ) : ℕ) ≡ 6 [MOD 7] := by simpa [h1] using this
    have : (2 : ℕ) ≡ 6 [MOD 7] := this
    have : (2 % 7) = (6 % 7) := this
    norm_num at this
  · have : (2 ^ (2 : ℕ) : ℕ) ≡ 6 [MOD 7] := by simpa [h2] using this
    have : (4 : ℕ) ≡ 6 [MOD 7] := this
    have : (4 % 7) = (6 % 7) := this
    norm_num at this
