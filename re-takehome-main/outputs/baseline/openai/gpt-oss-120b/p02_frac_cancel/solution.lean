import Mathlib

/-- What is the value of `x` if `x = (2009 ^ 2 - 2009) / 2009`? Show that it is `2008`. -/
theorem p02_frac_cancel (x : ℝ) (h : x = (2009 ^ 2 - 2009) / 2009) : x = 2008 := by
  have hcalc : (2009 ^ 2 - 2009) / (2009 : ℝ) = (2008 : ℝ) := by
    field_simp [pow_two]
    ring
  calc
    x = (2009 ^ 2 - 2009) / (2009 : ℝ) := h
    _ = 2008 := hcalc
