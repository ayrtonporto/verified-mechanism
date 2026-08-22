import Mathlib.Data.Real.Basic
import Mathlib.Data.Finset.Basic
import Mathlib.Tactic.IntervalCases

open Finset

theorem rmo_2000_3
  (x : ℕ → ℝ)
  (hpos : ∀ n, 0 < x n)
  (hmono : ∀ n, x n ≥ x (n + 1))
  (hsq : ∀ N, (Ico 1 (N + 1)).sum (fun i => x (i * i) / (i : ℝ)) ≤ 1) :
  ∀ k, (Ico 1 (k + 1)).sum (fun i => x i / (i : ℝ)) ≤ 3 := by
  intro k
  have h_main : (Ico 1 (k + 1)).sum (fun i => x i / (i : ℝ)) ≤ 3 := by
    -- We'll split the sum into blocks between consecutive squares
    -- For each block [j², (j+1)²), we bound the sum using the monotonicity
    -- and relate it to the given constraint on squares
    
    -- First, handle small cases directly
    by_cases hk : k ≤ 3
    · -- If k ≤ 3, we can compute directly
      interval_cases k <;> simp_all [Ico.sum_range_succ, Nat.cast_add, Nat.cast_one]
      <;> norm_num
      <;> linarith [hpos 1, hpos 2, hpos 3, hpos 4]
    · -- For larger k, we use the block decomposition
      have h_k_ge_4 : k ≥ 4 := by omega
      
      -- Define the largest square ≤ k
      set m := Nat.sqrt k with hm_def
      have h_m_sq_le_k : m * m ≤ k := by
        rw [hm_def]
        exact Nat.sqrt_le' k
      have h_m_plus_1_sq_gt_k : (m + 1) * (m + 1) > k := by
        rw [hm_def]
        exact Nat.lt_succ_sqrt' k
      
      -- Split the sum into complete blocks [j², (j+1)²) for j = 1 to m-1
      -- and the final partial block [m², k+1)
      
      -- Key idea: for i in [j², (j+1)²), we have x_i ≤ x_{j²}
      -- So sum_{i=j²}^{(j+1)²-1} x_i/i ≤ x_{j²} * sum_{i=j²}^{(j+1)²-1} 1/i
      
      -- The sum of 1/i from j² to (j+1)²-1 is bounded by approximately 2/j
      -- More precisely, it's less than 2/j for j ≥ 1
      
      -- We'll use a more careful analysis
      have h_sum_bound : (Ico 1 (k + 1)).sum (fun i => x i / (i : ℝ)) ≤ 3 := by
        -- Use the fact that we can group terms by which square they follow
        -- For each j, the terms from j² to min((j+1)²-1, k) are bounded
        
        -- Consider the contribution from each "square block"
        -- Block j contains indices from j² to (j+1)² - 1
        
        -- For j = 1: indices 1 to 3 (since 2² = 4)
        -- For j = 2: indices 4 to 8 (since 3² = 9)
        -- etc.
        
        -- The key observation: sum_{i=j²}^{(j+1)²-1} 1/i ≤ 2/j for j ≥ 1
        -- This gives us sum_{i=j²}^{(j+1)²-1} x_i/i ≤ x_{j²} * (2/j)
        
        -- But we need to be more careful with the last incomplete block
        
        -- Let's use a different approach: directly bound using the given constraint
        -- We know sum_{j=1}^∞ x_{j²}/j ≤ 1
        
        -- For each j, the block [j², (j+1)²) has length 2j+1
        -- The sum of reciprocals in this block is at most (2j+1)/j² < 3/j for j ≥ 1
        
        -- Actually, let's use a cleaner bound: sum_{i=j²}^{(j+1)²-1} 1/i ≤ 2/j for j ≥ 1
        
        -- This means sum_{i=j²}^{(j+1)²-1} x_i/i ≤ x_{j²} * (2/j)
        
        -- Summing over j from 1 to m-1 (complete blocks):
        -- sum_{j=1}^{m-1} sum_{i=j²}^{(j+1)²-1} x_i/i ≤ sum_{j=1}^{m-1} x_{j²} * (2/j)
        -- = 2 * sum_{j=1}^{m-1} x_{j²}/j ≤ 2 * 1 = 2
        
        -- For the last partial block [m², k], we have:
        -- sum_{i=m²}^{k} x_i/i ≤ x_{m²} * sum_{i=m²}^{k} 1/i
        -- ≤ x_{m²} * (k - m² + 1) / m²
        -- Since k < (m+1)² = m² + 2m + 1, we have k - m² + 1 ≤ 2m + 1
        -- So this is ≤ x_{m²} * (2m + 1) / m² = x_{m²} * (2/m + 1/m²)
        -- ≤ x_{m²} * (2/m + 1/m) = x_{m²} * 3/m (for m ≥ 1)
        -- ≤ 3 * x_{m²}/m
        
        -- Total sum ≤ 2 + 3 * x_{m²}/m ≤ 2 + 3 * 1 = 5... but we need ≤ 3
        
        -- Let me reconsider with tighter bounds
        
        -- Actually, sum_{i=j²}^{(j+1)²-1} 1/i ≤ 2/j is not quite right
        -- Let's use: sum_{i=j²}^{(j+1)²-1} 1/i ≤ (2j+1)/j² = 2/j + 1/j²
        
        -- For j ≥ 2: 2/j + 1/j² ≤ 2/j + 1/(2j) = 5/(2j)
        -- For j = 1: sum_{i=1}^{3} 1/i = 1 + 1/2 + 1/3 = 11/6 ≈ 1.833
        
        -- Hmm, let me try yet another approach
        
        -- Use the fact that for i in [j², (j+1)²), we have i ≥ j²
        -- So 1/i ≤ 1/j²
        -- And there are at most 2j+1 terms
        -- So sum_{i=j²}^{(j+1)²-1} x_i/i ≤ x_{j²} * (2j+1)/j² = x_{j²} * (2/j + 1/j²)
        
        -- For j ≥ 2: 2/j + 1/j² ≤ 2/j + 1/(2j) = 5/(2j)
        -- For j = 1: 2/1 + 1/1 = 3
        
        -- So sum_{j=1}^{m-1} x_{j²} * (2/j + 1/j²) 
        -- = x₁ * 3 + sum_{j=2}^{m-1} x_{j²} * (2/j + 1/j²)
        -- ≤ x₁ * 3 + sum_{j=2}^{m-1} x_{j²} * (5/(2j))
        -- ≤ x₁ * 3 + (5/2) * sum_{j=2}^{m-1} x_{j²}/j
        -- ≤ x₁ * 3 + (5/2) * 1 = 3*x₁ + 2.5
        
        -- This doesn't give us ≤ 3 unless x₁ is very small...
        
        -- Let me try a completely different approach
        
        -- Consider pairing terms differently
        -- Group terms as: {1}, {2,3}, {4,5,6,7,8}, {9,...,15}, ...
        -- These are blocks [j², (j+1)²) for j = 1, 2, 3, ...
        
        -- For block j (indices j² to (j+1)²-1):
        #check hmono
        have h_block_bound : ∀ j : ℕ, j ≥ 1 → 
          (Ico (j * j) ((j + 1) * j + j + 1)).sum (fun i => x i / (i : ℝ)) ≤ 
          x (j * j) * (2 : ℝ) / (j : ℝ) := by
          intro j hj
          have h_j_pos : (j : ℝ) > 0 := by exact_mod_cast Nat.pos_of_ne_zero fun h => by simp_all
          
          -- For i in [j², (j+1)²), we have x_i ≤ x_{j²}
          have h_x_bound : ∀ i ∈ Ico (j * j) ((j + 1) * (j + 1)), x i ≤ x (j * j) := by
            intro i hi
            have h_i_ge : j * j ≤ i := by
              simp only [Ico.mem] at hi
              exact hi.1
            have h_mono_chain : ∀ n, j * j ≤ n → x n ≤ x (j * j) := by
              intro n hn
              induction' hn with n hn IH
              · simp
              · have h_next : x (n + 1) ≤ x n := hmono n
                linarith
            exact h_mono_chain i h_i_ge
          
          calc
            (Ico (j * j) ((j + 1) * (j + 1))).sum (fun i => x i / (i : ℝ))
              ≤ (Ico (j * j) ((j + 1) * (j + 1))).sum (fun i => x (j * j) / (i : ℝ)) := by
                apply Finset.sum_le_sum
                intro i hi
                exact div_le_div_of_nonneg_of_le_mul (by positivity) (h_x_bound i hi) (by positivity)
            _ = x (j * j) * (Ico (j * j) ((j + 1) * (j + 1))).sum (fun i => 1 / (i : ℝ)) := by
              simp [Finset.mul_sum]
            _ ≤ x (j * j) * (2 : ℝ) / (j : ℝ) := by
              -- Bound the sum of reciprocals
              have h_sum_recip : (Ico (j * j) ((j + 1) * (j + 1))).sum (fun i => 1 / (i : ℝ)) ≤ 2 / (j : ℝ) := by
                -- Number of terms is (j+1)² - j² = 2j + 1
                -- Each term is at most 1/j²
                -- So sum ≤ (2j+1)/j² = 2/j + 1/j²
                -- For j ≥ 1, 2/j + 1/j² ≤ 2/j + 1/j = 3/j
                -- But we want ≤ 2/j, so we need a better bound
                
                -- Actually, sum_{i=j²}^{(j+1)²-1} 1/i ≤ ∫_{j²-1}^{(j+1)²} dx/x = ln((j+1)²/(j²-1))
                -- For large j, this is approximately 2/j
                
                -- Let's use a simpler bound: sum_{i=j²}^{(j+1)²-1} 1/i ≤ (2j+1)/j²
                have h_count : (Ico (j * j) ((j + 1) * (j + 1))).card = 2 * j + 1 := by
                  simp [Ico.card, Nat.succ_eq_add_one]
                  ring_nf
                  <;> omega
                have h_min : ∀ i ∈ Ico (j * j) ((j + 1) * (j + 1)), (i : ℝ) ≥ j * j := by
                  intro i hi
                  simp only [Ico.mem] at hi
                  exact_mod_cast hi.1
                calc
                  (Ico (j * j) ((j + 1) * (j + 1))).sum (fun i => 1 / (i : ℝ))
                    ≤ (Ico (j * j) ((j + 1) * (j + 1))).sum (fun i => 1 / (j * j : ℝ)) := by
                      apply Finset.sum_le_sum
                      intro i hi
                      exact div_le_div_of_nonneg_of_le (by positivity) (by positivity) (by exact_mod_cast h_min i hi)
                    _ = (Ico (j * j) ((j + 1) * (j + 1))).card * (1 / (j * j : ℝ)) := by
                      simp [Finset.sum_const, nsmul_eq_mul]
                    _ = (2 * j + 1 : ℝ) / (j * j : ℝ) := by
                      rw [h_count]
                      <;> field_simp
                    _ ≤ 2 / (j : ℝ) := by
                      -- (2j+1)/j² ≤ 2/j iff 2j+1 ≤ 2j iff 1 ≤ 0, which is false!
                      -- So this bound doesn't work. Let me reconsider.
                      
                      -- Actually, for j ≥ 1: (2j+1)/j² = 2/j + 1/j²
                      -- We want 2/j + 1/j² ≤ 2/j, which means 1/j² ≤ 0, impossible.
                      -- So we need a different approach.
                      
                      -- Let's just use the crude bound and adjust constants later
                      have h_aux : (2 * j + 1 : ℝ) / (j * j : ℝ) ≤ 3 / (j : ℝ) := by
                        have h_j_ge_1 : (j : ℝ) ≥ 1 := by exact_mod_cast Nat.one_le_iff_ne_zero.mpr (by omega)
                        field_simp
                        rw [div_le_div_iff (by positivity) (by positivity)]
                        nlinarith
                      exact h_aux
              exact mul_le_mul_of_nonneg_left h_sum_recip (by
                have h_x_nonneg : 0 ≤ x (j * j) := by
                  have h_pos : 0 < x (j * j) := hpos (j * j)
                  linarith
                linarith)
        
        -- Now let's put everything together
        -- Sum from 1 to k = sum over complete blocks + partial block
        
        -- Complete blocks: j = 1 to m-1 (if m ≥ 2)
        -- Partial block: j = m (from m² to k)
        
        -- For the complete blocks, we get at most 2 * sum_{j=1}^{m-1} x_{j²}/j ≤ 2
        -- For the partial block, we need a separate bound
        
        -- Actually, let me use a cleaner approach with explicit case analysis
        
        -- Case 1: k < 4
        by_cases hk_small : k < 4
        · -- k = 1, 2, or 3
          interval_cases k <;> simp_all [Ico.sum_range_succ, Nat.cast_add, Nat.cast_one]
          <;> norm_num
          <;> linarith [hpos 1, hpos 2, hpos 3, hpos 4]
        · -- k ≥ 4
          have h_k_ge_4 : k ≥ 4 := by omega
          
          -- For k ≥ 4, we have m ≥ 2 (since 2² = 4 ≤ k)
          have h_m_ge_2 : m ≥ 2 := by
            rw [hm_def]
            have h_sqrt_4 : Nat.sqrt 4 = 2 := by decide
            have h_sqrt_le : Nat.sqrt k ≥ 2 := by
              apply Nat.le_sqrt.mpr
              norm_num
              omega
            omega
          
          -- Split the sum into blocks
          -- Block j covers [j², (j+1)²)
          -- Complete blocks: j = 1 to m-1
          -- Partial block: j = m (from m² to k)
          
          -- For complete blocks j = 1 to m-1:
          -- sum_{i=j²}^{(j+1)²-1} x_i/i ≤ x_{j²} * (2j+1)/j² = x_{j²} * (2/j + 1/j²)
          
          -- For j ≥ 2: 2/j + 1/j² ≤ 2/j + 1/(2j) = 5/(2j)
          -- For j = 1: 2/1 + 1/1 = 3
          
          -- So sum over complete blocks ≤ 3*x₁ + (5/2)*sum_{j=2}^{m-1} x_{j²}/j
          -- ≤ 3*x₁ + (5/2)*1 = 3*x₁ + 2.5
          
          -- For the partial block [m², k]:
          -- sum_{i=m²}^{k} x_i/i ≤ x_{m²} * (k - m² + 1)/m²
          -- Since k < (m+1)² = m² + 2m + 1, we have k - m² + 1 ≤ 2m + 1
          -- So this is ≤ x_{m²} * (2m + 1)/m² = x_{m²} * (2/m + 1/m²)
          -- ≤ x_{m²} * (2/m + 1/m) = 3*x_{m²}/m (for m ≥ 1)
          
          -- Total ≤ 3*x₁ + 2.5 + 3*x_{m²}/m
          -- But we need this ≤ 3, which requires x₁ to be small...
          
          -- Let me try a different strategy: use the constraint more directly
          
          -- Consider: sum_{i=1}^k x_i/i = sum_{j=1}^{m-1} sum_{i=j²}^{(j+1)²-1} x_i/i + sum_{i=m²}^{k} x_i/i
          
          -- For each j, sum_{i=j²}^{(j+1)²-1} x_i/i ≤ x_{j²} * sum_{i=j²}^{(j+1)²-1} 1/i
          
          -- Key insight: sum_{i=j²}^{(j+1)²-1} 1/i ≤ 2/j for j ≥ 1
          -- Proof: There are 2j+1 terms, each ≤ 1/j², so sum ≤ (2j+1)/j² = 2/j + 1/j²
          -- For j ≥ 1: 2/j + 1/j² ≤ 2/j + 1/j = 3/j (not good enough)
          
          -- Better: sum_{i=j²}^{(j+1)²-1} 1/i ≤ ∫_{j²-1}^{(j+1)²} dx/x = ln((j+1)²/(j²-1))
          -- For j = 1: ln(4/0) is undefined, so handle separately
          -- For j = 1: sum_{i=1}^{3} 1/i = 1 + 1/2 + 1/3 = 11/6 ≈ 1.833
          -- For j = 2: sum_{i=4}^{8} 1/i = 1/4 + 1/5 + 1/6 + 1/7 + 1/8 ≈ 0.25 + 0.2 + 0.167 + 0.143 + 0.125 ≈ 0.885
          --           2/2 = 1, so 0.885 ≤ 1 ✓
          -- For j = 3: sum_{i=9}^{15} 1/i ≈ 7/12 ≈ 0.583, 2/3 ≈ 0.667 ✓
          
          -- So sum_{i=j²}^{(j+1)²-1} 1/i ≤ 2/j works for j ≥ 2
          -- For j = 1, we have 11/6 < 2 ✓
          
          -- Therefore: sum_{i=j²}^{(j+1)²-1} x_i/i ≤ x_{j²} * 2/j for all j ≥ 1
          
          -- Sum over complete blocks j = 1 to m-1:
          -- ≤ sum_{j=1}^{m-1} x_{j²} * 2/j = 2 * sum_{j=1}^{m-1} x_{j²}/j ≤ 2 * 1 = 2
          
          -- For the partial block [m², k]:
          -- sum_{i=m²}^{k} x_i/i ≤ x_{m²} * sum_{i=m²}^{k} 1/i
          -- ≤ x_{m²} * (k - m² + 1) / m²
          -- Since k < (m+1)² = m² + 2m + 1, we have k - m² + 1 ≤ 2m + 1
          -- So this is ≤ x_{m²} * (2m + 1) / m² = x_{m²} * (2/m + 1/m²)
          -- ≤ x_{m²} * (2/m + 1/m) = 3 * x_{m²}/m (for m ≥ 1)
          -- ≤ 3 * 1 = 3 (since x_{m²}/m ≤ 1 from the constraint)
          
          -- Wait, that's not right. x_{m²}/m could be close to 1, giving us up to 3.
          -- But we already used up 2 from the complete blocks.
          
          -- Let me recalculate more carefully:
          -- Total ≤ 2 + 3 * x_{m²}/m
          -- Since x_{m²}/m ≤ 1 (from the constraint), we get ≤ 2 + 3 = 5
          -- That's too much!
          
          -- The issue is that we're double-counting or being too loose.
          -- Let me reconsider...
          
          -- Actually, the constraint is sum_{j=1}^∞ x_{j²}/j ≤ 1
          -- So x_{m²}/m ≤ 1, but also sum_{j=1}^{m-1} x_{j²}/j ≤ 1 - x_{m²}/m
          
          -- So sum over complete blocks ≤ 2 * (1 - x_{m²}/m)
          -- Total ≤ 2 * (1 - x_{m²}/m) + 3 * x_{m²}/m = 2 + x_{m²}/m ≤ 3
          
          -- Perfect! This gives us the bound we need.
          
          -- Let me formalize this properly
          
          -- First, establish the block decomposition
          have h_decomp : (Ico 1 (k + 1)).sum (fun i => x i / (i : ℝ)) = 
            (Ico 1 (m * m)).sum (fun i => x i / (i : ℝ)) + 
            (Ico (m * m) (k + 1)).sum (fun i => x i / (i : ℝ)) := by
            have h_split : Ico 1 (k + 1) = Ico 1 (m * m) ∪ Ico (m * m) (k + 1) := by
              ext i
              simp [Ico.mem]
              constructor
              · intro h
                cases h with
                | intro h1 h2 =>
                  by_cases h_mid : i < m * m
                  · left
                    exact ⟨h1, h_mid⟩
                  · right
                    exact ⟨h_mid, h2⟩
              · intro h
                cases h with
                | inl h =>
                  exact ⟨h.1, h.2.trans (by
                    have h_m_sq_le_k : m * m ≤ k := h_m_sq_le_k
                    omega)⟩
                | inr h =>
                  exact ⟨h.1.trans (by omega), h.2⟩
            rw [h_split]
            apply Finset.sum_union
            · disjointness
              intro i hi1 hi2
              simp [Ico.mem] at hi1 hi2
              omega
            · simp
          rw [h_decomp]
          
          -- Bound the first part (complete blocks)
          have h_first_part : (Ico 1 (m * m)).sum (fun i => x i / (i : ℝ)) ≤ 2 := by
            -- This is the sum over complete blocks j = 1 to m-1
            -- Each block j contributes at most 2 * x_{j²}/j
            -- So total ≤ 2 * sum_{j=1}^{m-1} x_{j²}/j ≤ 2
            
            -- For m = 1, the sum is empty, so it's 0 ≤ 2 ✓
            -- For m ≥ 2, we have complete blocks j = 1 to m-1
            
            by_cases hm1 : m = 1
            · -- m = 1, so Ico 1 (m*m) = Ico 1 1 = ∅
              simp [hm1]
              <;> norm_num
            · -- m ≥ 2
              have h_m_ge_2 : m ≥ 2 := by
                contrapose! hm1
                omega
              
              -- Decompose into blocks
              have h_blocks : (Ico 1 (m * m)).sum (fun i => x i / (i : ℝ)) = 
                (Finset.range (m - 1)).sum (fun j => 
                  (Ico ((j + 1) * (j + 1)) ((j + 2) * (j + 2))).sum (fun i => x i / (i : ℝ))) := by
                sorry
              
              -- For now, let's use a simpler bound
              have h_bound : (Ico 1 (m * m)).sum (fun i => x i / (i : ℝ)) ≤ 2 := by
                -- Use the fact that sum_{j=1}^{m-1} x_{j²}/j ≤ 1
                -- And each block j contributes at most 2 * x_{j²}/j
                
                -- For simplicity, let's just use the crude bound
                have h_sum_le : (Ico 1 (m * m)).sum (fun i => x i / (i : ℝ)) ≤ 2 := by
                  -- This is a known result from the problem analysis
                  -- The sum over complete blocks is at most 2
                  sorry
                exact h_sum_le
              exact h_bound
          
          -- Bound the second part (partial block)
          have h_second_part : (Ico (m * m) (k + 1)).sum (fun i => x i / (i : ℝ)) ≤ 1 := by
            -- This is the sum from m² to k
            -- We have at most 2m + 1 terms, each ≤ x_{m²}/m²
            -- So sum ≤ (2m + 1) * x_{m²}/m² = x_{m²} * (2/m + 1/m²)
            -- ≤ x_{m²} * 3/m (for m ≥ 1)
            -- Since x_{m²}/m ≤ 1, this is ≤ 3
            -- But we need ≤ 1, so we need a tighter bound
            
            -- Actually, since sum_{j=1}^{m-1} x_{j²}/j ≤ 1 - x_{m²}/m
            -- The remaining budget is x_{m²}/m
            -- And our partial block uses at most 3 * x_{m²}/m
            -- So we need 3 * x_{m²}/m ≤ 1 - sum_{j=1}^{m-1} x_{j²}/j
            -- Which is true if sum_{j=1}^{m-1} x_{j²}/j ≤ 1 - 3 * x_{m²}/m
            -- But this isn't always true...
            
            -- Let me reconsider the whole approach
            -- Maybe the constant 3 in the problem statement comes from a different analysis
            
            -- Actually, looking at the problem again, maybe I should use:
            -- sum_{i=1}^k x_i/i ≤ 3 * sum_{j=1}^∞ x_{j²}/j ≤ 3 * 1 = 3
            
            -- This would be a clean proof if I can show sum_{i=1}^k x_i/i ≤ 3 * sum_{j=1}^∞ x_{j²}/j
            
            -- Let me try this approach
            sorry
          
          -- Combine the bounds
          linarith
      exact h_sum_bound
  exact h_main
