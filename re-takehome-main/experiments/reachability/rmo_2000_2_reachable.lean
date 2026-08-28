import Mathlib

theorem rmo_2000_2
  (x y : ℕ)
  (hx : 0 < x)
  (hy : 0 < y)
  (h : y ^ 3 = x ^ 3 + 8 * x ^ 2 - 6 * x + 8) :
  x = 9 ∧ y = 11 := by
  have hxle : 6 * x ≤ x ^ 3 + 8 * x ^ 2 := by nlinarith [hx, sq_nonneg x]
  have hZ : (y:ℤ) ^ 3 = (x:ℤ) ^ 3 + 8 * (x:ℤ) ^ 2 - 6 * (x:ℤ) + 8 := by
    zify [hxle] at h
    linarith [h]
  have hx1 : (1:ℤ) ≤ (x:ℤ) := by exact_mod_cast hx
  have hy0 : (0:ℤ) ≤ (y:ℤ) := by positivity
  have hlo : ((x:ℤ) + 1) ^ 3 < (y:ℤ) ^ 3 := by nlinarith [hZ, hx1, sq_nonneg ((x:ℤ)-1)]
  have hhi : (y:ℤ) ^ 3 < ((x:ℤ) + 3) ^ 3 := by nlinarith [hZ, hx1, sq_nonneg ((x:ℤ))]
  have hyge : (x:ℤ) + 1 < (y:ℤ) := by
    by_contra hc
    push_neg at hc
    nlinarith [hlo, hc, hy0, hx1, mul_nonneg (by linarith : (0:ℤ) ≤ (x:ℤ)+1-(y:ℤ)) hy0,
               sq_nonneg ((x:ℤ)+1-(y:ℤ)), sq_nonneg ((x:ℤ)+1+(y:ℤ))]
  have hyle : (y:ℤ) < (x:ℤ) + 3 := by
    by_contra hc
    push_neg at hc
    nlinarith [hhi, hc, hy0, hx1, mul_nonneg (by linarith : (0:ℤ) ≤ (y:ℤ)-((x:ℤ)+3)) hy0,
               sq_nonneg ((y:ℤ)-((x:ℤ)+3)), sq_nonneg ((y:ℤ)+((x:ℤ)+3))]
  have hy2 : (y:ℤ) = (x:ℤ) + 2 := by omega
  have hZ2 : ((x:ℤ) + 2) ^ 3 = (x:ℤ) ^ 3 + 8 * (x:ℤ) ^ 2 - 6 * (x:ℤ) + 8 := by
    rw [← hy2]; exact hZ
  have hfac : 2 * ((x:ℤ) * ((x:ℤ) - 9)) = 0 := by ring_nf; nlinarith [hZ2]
  have hx9 : (x:ℤ) = 9 := by
    have hpos : (0:ℤ) < (x:ℤ) := by linarith
    rcases mul_eq_zero.mp (by linarith [hfac] : (x:ℤ) * ((x:ℤ) - 9) = 0) with h0 | h0
    · exact absurd h0 (by positivity)
    · linarith
  refine ⟨by exact_mod_cast hx9, ?_⟩
  have : (y:ℤ) = 11 := by rw [hy2, hx9]; norm_num
  exact_mod_cast this
