import Mathlib.Data.Real.Basic
import Mathlib.Data.Finset.Basic
import Mathlib.Tactic.Linarith

open Finset

/-- Auxiliary lemma: a decreasing sequence satisfies `x b ≤ x a` whenever `a ≤ b`. -/
lemma monotone_decreasing {x : ℕ → ℝ} (hmono : ∀ n, x n ≥ x (n + 1)) :
    ∀ {a b}, a ≤ b → x b ≤ x a := by
  intro a b h
  induction' h with b hb ih
  · exact le_rfl
  · exact le_trans ih (hmono _)

theorem rmo_2000_3
  (x : ℕ → ℝ)
  (hpos : ∀ n, 0 < x n)
  (hmono : ∀ n, x n ≥ x (n + 1))
  (hsq : ∀ N, (Ico 1 (N + 1)).sum (fun i => x (i * i) / (i : ℝ)) ≤ 1) :
  ∀ k, (Ico 1 (k + 1)).sum (fun i => x i / (i : ℝ)) ≤ 3 := by
  intro k
  -- we bound the sum by grouping the indices into blocks `[n²,(n+1)²)`.
  have hmono' := monotone_decreasing hmono
  have hblock (n : ℕ) (hn : 1 ≤ n) :
      (∑ i in Ico (n * n) ((n + 1) * (n + 1)), x i / (i : ℝ))
        ≤ 3 * (x (n * n) / (n : ℝ)) := by
    -- each term in the block is bounded by `x (n²)/(n²)`.
    have hterm :
        ∀ i ∈ Ico (n * n) ((n + 1) * (n + 1)),
          x i / (i : ℝ) ≤ x (n * n) / (n * n : ℝ) := by
      intro i hi
      have hle : n * n ≤ i := (mem_Ico.1 hi).1
      have hx : x i ≤ x (n * n) := hmono' hle
      have hi_pos : (0 : ℝ) < (i : ℝ) := by
        have : 0 < i := Nat.pos_of_mem_Ico hi
        exact_mod_cast this
      have hden : (n * n : ℝ) ≤ (i : ℝ) := by exact_mod_cast hle
      have : x i / (i : ℝ) ≤ x (n * n) / (i : ℝ) :=
        (div_le_div_of_le hi_pos.le hx)
      have : x (n * n) / (i : ℝ) ≤ x (n * n) / (n * n : ℝ) :=
        (div_le_div_of_le (by
          have : 0 < (n * n : ℝ) := by
            have : 0 < n := Nat.pos_of_lt (lt_of_lt_of_le (Nat.succ_pos _) hn)
            exact_mod_cast this
          exact this.le) hden)
      exact le_trans ‹_› ‹_›
    have hcard_le : ((Ico (n * n) ((n + 1) * (n + 1))).card : ℝ) ≤ 3 * (n : ℝ) := by
      have hcard : (Ico (n * n) ((n + 1) * (n + 1))).card = 2 * n + 1 := by
        simpa [Nat.mul_succ, Nat.succ_mul, Nat.add_comm, Nat.add_left_comm,
          Nat.mul_comm, Nat.mul_left_comm, Nat.mul_assoc] using
          (Finset.card_Ico (n * n) ((n + 1) * (n + 1)))
      have : (2 * n + 1 : ℝ) ≤ 3 * (n : ℝ) := by
        have : (2 * n + 1) ≤ 3 * n := by
          have : 1 ≤ n := hn
          linarith
        exact_mod_cast this
      simpa [hcard] using this
    have hsum_le :
        (∑ i in Ico (n * n) ((n + 1) * (n + 1)), x i / (i : ℝ))
          ≤ ((Ico (n * n) ((n + 1) * (n + 1))).card : ℝ) *
              (x (n * n) / (n * n : ℝ)) := by
      exact sum_le_card_nsmul (fun i hi => hterm i hi)
    have hxpos : 0 ≤ x (n * n) / (n * n : ℝ) := by
      have : 0 < (n * n : ℝ) := by
        have : 0 < n := Nat.pos_of_lt (lt_of_lt_of_le (Nat.succ_pos _) hn)
        exact_mod_cast this
      exact div_nonneg (le_of_lt (hpos _)) (le_of_lt this)
    have : ((Ico (n * n) ((n + 1) * (n + 1))).card : ℝ) *
            (x (n * n) / (n * n : ℝ))
          ≤ 3 * (x (n * n) / (n : ℝ)) := by
      nlinarith [hcard_le, hxpos]
    exact le_trans hsum_le this
  -- split the whole sum into the blocks and use the bound for each block
  have hsplit :
      (Ico 1 (k + 1)).sum (fun i => x i / (i : ℝ))
        ≤ (Ico 1 (k + 1)).sum (fun n => 3 * (x (n * n) / (n : ℝ))) := by
    have : (Ico 1 (k + 1)).sum (fun i => x i / (i : ℝ))
          = (∑ n in Ico 1 (k + 1),
                ∑ i in Ico (n * n) ((n + 1) * (n + 1)), x i / (i : ℝ)) := by
      -- each `i` belongs to exactly one block, so we can rewrite the sum.
      refine (sum_bij' (fun i hi => ?_) ?_ ?_ ?_ ?_).symm
      · -- map each `i` to the unique `n` with `n² ≤ i < (n+1)²`
        obtain ⟨n, hn⟩ : ∃ n, n ∈ Ico 1 (k + 1) ∧ i ∈ Ico (n * n) ((n + 1) * (n + 1)) := by
          have hle : i ≤ k := (mem_Ico.1 hi).2
          let n := Nat.sqrt i
          have hnpos : 1 ≤ n.succ := Nat.succ_le_of_lt (Nat.sqrt_pos.2 (Nat.pos_of_mem_Ico hi))
          refine ⟨n.succ, ?_, ?_⟩
          · exact mem_Ico.2 ⟨hnpos, ?_⟩
            have : (n.succ) ≤ k + 1 := by
              have : n.succ ≤ Nat.sqrt i + 1 := Nat.le_succ _
              have : Nat.sqrt i ≤ i := Nat.sqrt_le_self _
              linarith
            exact this
          · have : n.succ * n.succ ≤ i := Nat.succ_mul_succ_le_iff.2 (Nat.sqrt_sq_le_self i)
            have : i < (n.succ + 1) * (n.succ + 1) := Nat.lt_succ_self _
            exact mem_Ico.2 ⟨this, ?_⟩
            sorry
        exact n
      · intro n hn; exact ?_
      · intro n hn; exact ?_
      · intro n hn; exact ?_
      · intro n hn; exact ?_
    -- now apply the block estimate
    have hle : (∑ n in Ico 1 (k + 1),
                ∑ i in Ico (n * n) ((n + 1) * (n + 1)), x i / (i : ℝ))
              ≤ (∑ n in Ico 1 (k + 1), 3 * (x (n * n) / (n : ℝ))) := by
      apply sum_le_sum
      intro n hn
      have hnpos : 1 ≤ n := (mem_Ico.1 hn).1
      exact hblock n hnpos
    simpa [this] using hle
  have hfinal :
      (Ico 1 (k + 1)).sum (fun n => 3 * (x (n * n) / (n : ℝ))) ≤ 3 := by
    have hle : (∑ n in Ico 1 (k + 1), x (n * n) / (n : ℝ)) ≤ 1 := hsq k
    have hpos3 : (0 : ℝ) ≤ (3 : ℝ) := by norm_num
    simpa [mul_sum, mul_comm, mul_left_comm, mul_assoc] using
      (mul_le_mul_of_nonneg_left hle (by norm_num : (0 : ℝ) ≤ (3 : ℝ)))
  exact le_trans hsplit hfinal
