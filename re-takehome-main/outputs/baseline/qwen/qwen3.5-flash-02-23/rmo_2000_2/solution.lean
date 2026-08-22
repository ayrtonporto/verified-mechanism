import Mathlib.Tactic

theorem rmo_2000_2
  (x y : ℕ)
  (hx : 0 < x)
  (hy : 0 < y)
  (h : y ^ 3 = x ^ 3 + 8 * x ^ 2 - 6 * x + 8) :
  x = 9 ∧ y = 11 := by
  have h_y_lt_x_plus_3 : y < x + 3 := by
    have h1 : x ^ 3 + 8 * x ^ 2 - 6 * x + 8 < (x + 3) ^ 3 := by
      cases x with
      | zero => contradiction
      | succ x' =>
        simp [Nat.pow_succ, Nat.mul_sub_left_distrib, Nat.mul_sub_right_distrib]
        ring_nf at *
        omega
    rw [h] at h1
    exact h1
  
  have h_ge_x_plus_2 : x ≥ 10 → False := by
    intro hx_ge_10
    have h1 : (x + 2) ^ 3 < y ^ 3 := by
      have h2 : (x + 2) ^ 3 < x ^ 3 + 8 * x ^ 2 - 6 * x + 8 := by
        cases x with
        | zero => contradiction
        | succ x' =>
          simp [Nat.pow_succ, Nat.mul_add, Nat.add_mul]
          ring_nf at *
          omega
      linarith
    have h2 : (x + 2) ^ 3 < (x + 3) ^ 3 := by
      apply Nat.pow_lt_pow_of_lt_right
      · omega
      · omega
    have h3 : y < x + 3 := h_y_lt_x_plus_3
    have h4 : y ≥ x + 2 := by
      by_contra h4
      have h5 : y ≤ x + 1 := by omega
      have h6 : y ^ 3 ≤ (x + 1) ^ 3 := by
        exact Nat.pow_le_pow_of_le_left h5 3
      have h7 : (x + 1) ^ 3 < (x + 2) ^ 3 := by
        apply Nat.pow_lt_pow_of_lt_right
        · omega
        · omega
      have h8 : y ^ 3 < (x + 2) ^ 3 := by
        linarith
      linarith
    have h5 : y = x + 2 := by omega
    rw [h5] at h
    have h6 : (x + 2) ^ 3 = x ^ 3 + 8 * x ^ 2 - 6 * x + 8 := by
      linarith
    have h7 : (x + 2) ^ 3 = x ^ 3 + 6 * x ^ 2 + 12 * x + 8 := by
      ring_nf
    have h8 : x ^ 3 + 6 * x ^ 2 + 12 * x + 8 = x ^ 3 + 8 * x ^ 2 - 6 * x + 8 := by
      linarith
    have h9 : 6 * x ^ 2 + 12 * x = 8 * x ^ 2 - 6 * x := by
      omega
    have h10 : 2 * x ^ 2 - 18 * x = 0 := by
      omega
    have h11 : 2 * x * (x - 9) = 0 := by
      cases x with
      | zero => contradiction
      | succ x' =>
        simp [Nat.mul_sub_left_distrib, Nat.mul_sub_right_distrib] at h10 ⊢
        ring_nf at h10 ⊢
        omega
    have h12 : x = 9 := by
      cases x with
      | zero => contradiction
      | succ x' =>
        simp [Nat.mul_eq_zero] at h11
        omega
    omega
  
  have h_x_le_9 : x ≤ 9 := by
    by_contra h_x_gt_9
    have h_x_ge_10 : x ≥ 10 := by omega
    exact h_ge_x_plus_2 h_x_ge_10
  
  interval_cases x <;> norm_num at h ⊢ <;>
    (try omega) <;>
    (try {
      have h_y_pos : 0 < y := hy
      have h_y_bound : y < 11 := by
        nlinarith
      interval_cases y <;> norm_num at h ⊢ <;> omega
    }) <;>
    (try {
      have h_y_pos : 0 < y := hy
      have h_y_bound : y < 12 := by
        nlinarith
      interval_cases y <;> norm_num at h ⊢ <;> omega
    }) <;>
    (try {
      have h_y_pos : 0 < y := hy
      have h_y_bound : y < 13 := by
        nlinarith
      interval_cases y <;> norm_num at h ⊢ <;> omega
    }) <;>
    (try {
      have h_y_pos : 0 < y := hy
      have h_y_bound : y < 14 := by
        nlinarith
      interval_cases y <;> norm_num at h ⊢ <;> omega
    }) <;>
    (try {
      have h_y_pos : 0 < y := hy
      have h_y_bound : y < 15 := by
        nlinarith
      interval_cases y <;> norm_num at h ⊢ <;> omega
    }) <;>
    (try {
      have h_y_pos : 0 < y := hy
      have h_y_bound : y < 16 := by
        nlinarith
      interval_cases y <;> norm_num at h ⊢ <;> omega
    }) <;>
    (try {
      have h_y_pos : 0 < y := hy
      have h_y_bound : y < 17 := by
        nlinarith
      interval_cases y <;> norm_num at h ⊢ <;> omega
    }) <;>
    (try {
      have h_y_pos : 0 < y := hy
      have h_y_bound : y < 18 := by
        nlinarith
      interval_cases y <;> norm_num at h ⊢ <;> omega
    }) <;>
    (try {
      have h_y_pos : 0 < y := hy
      have h_y_bound : y < 19 := by
        nlinarith
      interval_cases y <;> norm_num at h ⊢ <;> omega
    })
  
  <;> simp_all
  <;> omega
