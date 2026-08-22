import Mathlib

abbrev putnam_2018_a1_solution : Set (ℤ × ℤ) := 
  {(2018, 4036), (4036, 2018)}

theorem putnam_2018_a1
  (a b : ℤ)
  (h : 0 < a ∧ 0 < b) :
  ((1 : ℚ) / a + (1 : ℚ) / b = (3 : ℚ) / 2018) ↔
    (⟨a, b⟩ ∈ putnam_2018_a1_solution) := by
  constructor
  · -- Forward direction: if the equation holds, then (a,b) is in the solution set
    intro h_eq
    have ha : 0 < a := h.1
    have hb : 0 < b := h.2
    field_simp [ha.ne', hb.ne'] at h_eq
    ring_nf at h_eq
    norm_cast at h_eq
    have h_pos : 0 < a * b := mul_pos ha hb
    have h_div : (a * b) ∣ (2018 * (a + b)) := by
      rw [← sub_eq_zero] at h_eq
      ring_nf at h_eq
      omega
    -- From 2018(a+b) = 3ab, we get 3ab - 2018a - 2018b = 0
    -- Multiply by 3: 9ab - 6054a - 6054b = 0
    -- Add 6054²/9: (3a - 2018)(3b - 2018) = 2018²/3
    -- Since 2018²/3 is not an integer, we need to check directly
    have h_main : a = 2018 ∧ b = 4036 ∨ a = 4036 ∧ b = 2018 := by
      -- Check the two cases manually
      have h1 : a = 2018 → b = 4036 := by
        intro ha_val
        subst ha_val
        field_simp [hb.ne'] at h_eq
        ring_nf at h_eq
        norm_cast at h_eq
        omega
      have h2 : a = 4036 → b = 2018 := by
        intro ha_val
        subst ha_val
        field_simp [hb.ne'] at h_eq
        ring_nf at h_eq
        norm_cast at h_eq
        omega
      -- Verify these are the only solutions by checking the equation
      have h_check : a ≤ 4036 := by
        by_contra h_gt
        have h_a_gt : a ≥ 4037 := by omega
        have h_b_ge : b ≥ 1 := by omega
        have h_sum : (1 : ℚ) / a + (1 : ℚ) / b ≤ (1 : ℚ) / 4037 + (1 : ℚ) / 1 := by
          gcongr <;> omega
        have h_rhs : (3 : ℚ) / 2018 > (1 : ℚ) / 4037 + (1 : ℚ) / 1 := by norm_num
        linarith
      -- Similarly bound b
      have h_b_le : b ≤ 4036 := by
        by_contra h_gt
        have h_b_gt : b ≥ 4037 := by omega
        have h_a_ge : a ≥ 1 := by omega
        have h_sum : (1 : ℚ) / a + (1 : ℚ) / b ≤ (1 : ℚ) / 1 + (1 : ℚ) / 4037 := by
          gcongr <;> omega
        have h_rhs : (3 : ℚ) / 2018 > (1 : ℚ) / 1 + (1 : ℚ) / 4037 := by norm_num
        linarith
      -- Now check all possibilities
      interval_cases a <;> interval_cases b <;> norm_num at h_eq ⊢ <;>
        (try omega) <;> (try { contradiction }) <;>
        (try { aesop })
    cases h_main with
    | inl h_pair =>
      simp [h_pair]
      <;> aesop
    | inr h_pair =>
      simp [h_pair]
      <;> aesop
  · -- Reverse direction: if (a,b) is in the solution set, then the equation holds
    intro h_in
    simp only [putnam_2018_a1_solution, Set.mem_insert_iff, Set.mem_singleton_iff] at h_in
    rcases h_in with (⟨rfl, rfl⟩ | ⟨rfl, rfl⟩)
    · -- Case (2018, 4036)
      norm_num
    · -- Case (4036, 2018)
      norm_num
