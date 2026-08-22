import Mathlib.Data.Nat.Basic
import Mathlib.Order.Bounds.Basic
import Mathlib.Tactic

theorem rmo_2000_6 :
  (IsLeast {n | ∃ a b : ℕ, 0 < a ∧ 0 < b ∧ 2000 ∣ a ^ 2 * b ^ 5 ∧ n = a * b} 10) ∧
  (IsLeast {n | ∃ a b : ℕ, 0 < a ∧ 0 < b ∧ 2000 ∣ a ^ 3 * b ^ 4 ∧ n = a * b} 20) := by
  constructor
  · -- Part 1: IsLeast for a²b⁵ divisible by 2000
    constructor
    · -- Show 10 is achievable
      use 1, 10
      constructor
      · norm_num
      · constructor
        · norm_num
        · constructor
          · norm_num
          · rfl
    · -- Show no smaller value exists
      intro n hn hlt
      rcases hn with ⟨a, b, ha, hb, hdiv, heq⟩
      rw [heq] at hlt
      have : 1 ≤ n := by linarith
      -- Analyze prime factorization constraints
      have h₁ : 2000 ∣ a ^ 2 * b ^ 5 := hdiv
      have h₂ : n = a * b := heq
      -- Since 2000 = 2⁴ × 5³, we need sufficient powers of 2 and 5
      -- For minimal ab, we need to balance the exponents
      -- Through case analysis on prime factors, we can show n ≥ 10
      have : n ≥ 10 := by
        by_contra h
        have : n ≤ 9 := by linarith
        -- Check all possible values from 1 to 9
        interval_cases n <;> 
        (try contradiction) <;>
        (try {
          rcases hn with ⟨a', b', ha', hb', hdiv', heq'⟩
          simp_all [heq']
          have : 2000 ∣ a' ^ 2 * b' ^ 5 := hdiv'
          have : a' * b' ≤ 9 := by linarith
          have : 0 < a' := ha'
          have : 0 < b' := hb'
          -- Exhaustive search shows no solution for n < 10
          have : a' ≤ 9 := by nlinarith
          have : b' ≤ 9 := by nlinarith
          interval_cases a' <;> interval_cases b' <;> norm_num at this ⊢ <;> omega
        })
      linarith
  · -- Part 2: IsLeast for a³b⁴ divisible by 2000
    constructor
    · -- Show 20 is achievable
      use 2, 10
      constructor
      · norm_num
      · constructor
        · norm_num
        · constructor
          · norm_num
          · rfl
    · -- Show no smaller value exists
      intro n hn hlt
      rcases hn with ⟨a, b, ha, hb, hdiv, heq⟩
      rw [heq] at hlt
      have : 1 ≤ n := by linarith
      -- Similar analysis for the second case
      have h₁ : 2000 ∣ a ^ 3 * b ^ 4 := hdiv
      have h₂ : n = a * b := heq
      have : n ≥ 20 := by
        by_contra h
        have : n ≤ 19 := by linarith
        -- Check all possible values from 1 to 19
        interval_cases n <;> 
        (try contradiction) <;>
        (try {
          rcases hn with ⟨a', b', ha', hb', hdiv', heq'⟩
          simp_all [heq']
          have : 2000 ∣ a' ^ 3 * b' ^ 4 := hdiv'
          have : a' * b' ≤ 19 := by linarith
          have : 0 < a' := ha'
          have : 0 < b' := hb'
          have : a' ≤ 19 := by nlinarith
          have : b' ≤ 19 := by nlinarith
          -- Exhaustive search shows no solution for n < 20
          revert a' b' ha' hb' hdiv'
          intros a' b' ha' hb' hdiv'
          have : a' ≤ 19 := by nlinarith
          have : b' ≤ 19 := by nlinarith
          interval_cases a' <;> interval_cases b' <;> norm_num at hdiv' ⊢ <;> omega
        })
      linarith
