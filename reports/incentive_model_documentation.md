Because the KPI is a cost, lower is better:

```
delta_m = (Target_T_m - Actual_A_m) / Target_T_m
```

---

## 11) Adjustment Rule

```
If delta_m < 0:
    Adjustment_m = max(delta_m, -F_dir)

If 0 <= delta_m <= H:
    Adjustment_m = 0

If delta_m > H:
    Adjustment_m = min(delta_m - H, F_up)
```

Where:
- `H` = hurdle (no-change zone)
- `F_dir` = downside floor (max penalty)
- `F_up` = upside ceiling (max bonus)

---

## 12) Final Fees

Adjusted variable fee:
```
Adjusted_Variable_Fee_m = Variable_V_m * (1 + Adjustment_m)
```

Total fee:
```
Total_Fee_m = Fixed_Fee_m + Adjusted_Variable_Fee_m
```

---

## 13) Outputs

For each market, the model outputs:

- Target_T  
- Actual_A  
- delta  
- Adjustment  
- alpha_eff / beta_eff  
- Variable_V  
- Fixed_Fee  
- Adjusted_Variable_Fee  
- Total_Fee  
- Zone (Penalty / No change / Reward)

---

## 14) Notes

- All `%` inputs are decimals (e.g., `0.10 = 10%`).
- Volatility is computed **only across the selected calculation markets**.
- Visualization can include a smaller subset without affecting calculation.

