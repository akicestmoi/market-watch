# Probability Matrix Calculation Mathematics

This document provides a detailed mathematical explanation of how probability matrices are calculated for both **Federal Reserve (FED)** and **Bank of Japan (BOJ)** interest rate changes from futures prices.

## Table of Contents

1. [Notations](#notations)
2. [First Futures Contract](#first-futures-contract)
3. [Subsequent Futures Contracts (Recursion)](#subsequent-futures-contracts-recursion)
4. [Normalization](#normalization)
5. [Final Result](#final-result)
6. [FED-Specific Calculations](#fed-specific-calculations)
7. [BOJ-Specific Calculations](#boj-specific-calculations)

---

## Notations

### Common Variables

- **r₀**: Starting/base rate (e.g., `base_rate`)
- **Δ = 25 bps**: Step size (unit rate change)
- **P_t**: Futures price at date `t`
- **r_t**: Implied rate of futures at date `t`
- **N_t**: Number of meetings before futures expiration at date `t`
- **M*{t,1}, M*{t,2}**: Meeting dates (1st, 2nd)
- **p_t(k)**: Cumulative probability of a total rate change of `k` bps at futures expiration `t`

### Possible Rate Steps

At each meeting, the possible rate steps are:

```
k ∈ {-50, -25, 0, +25, +50} (in basis points)
```

### Constants

- **STEP_SIZE** = 25 basis points (0.25%)
- **PROBABILITY_EXTENSION_STEPS** = 5
- **PROBABILITY_THRESHOLD** = 1.0%
- **DAYS_PER_YEAR** = 365
- **MUTAN_FUTURES_AVERAGE_DAYS** = 90 (for BOJ only)

---

## First Futures Contract

### Case (a): Single Meeting (N₁ = 1)

For a futures contract with one meeting before expiration:

#### Step 1: Calculate Implied Meeting Rate

The implied meeting rate is obtained by inverting the discounting formula:

```
r_{M₁} = f(r₀, P₁, M_{1,1})
```

This corresponds to `get_implied_meeting_rate()` in the code.

#### Step 2: Calculate Fractional Number of Steps

From the implied meeting rate, we derive the fractional number of rate steps:

```
n₁ = (r_{M₁} - r₀) / (Δ / 100)
```

This gives the number of 25 bps steps (can be fractional).

#### Step 3: Decompose into Integer and Fractional Parts

```
fractional, integer = modf(n₁)
sign = copysign(1, n₁)
```

Where:

- **integer** = `int(integer)` - the integer number of steps
- **fractional** = `abs(fractional)` - the fractional part (0 ≤ fractional < 1)
- **sign** = ±1 - indicates direction of change

#### Step 4: Assign Initial Probabilities

The probability of rate change is distributed using linear interpolation:

```
p(+Δ) = fractional
p(0) = 1 - fractional
p(-Δ) = 0
```

Where `fractional(n₁)` is the fractional part (e.g., 0.3 means 30% chance of a 25 bps increase).

For all other steps: **p(step) = 0**

### Case (b): Two Meetings (N₁ = 2)

For a futures contract with two meetings before expiration:

#### Step 1: Calculate Probability Matrix for Both Meetings

We calculate the probability matrix for the two meetings:

```
P₁ = [
  [p₁(Δ_{M_{1,1}} = -50), ..., p₁(Δ_{M_{1,1}} = +50)],
  [p₂(Δ_{M_{1,2}} = -50), ..., p₂(Δ_{M_{1,2}} = +50)]
]
```

Such that:

```
Σᵢ pᵢ = 1
```

#### Step 2: Calculate Total Distribution After Both Meetings

The total distribution after both meetings is:

```
p_total(k) = Σ_{x+y=k} p₁(x) × p₂(y)
```

This is exactly what the code does with:

```python
p_1_X = prob_df[prob_df["first_rate_step"] == X]["probability"].sum()
p_2_X = prob_df[prob_df["total_step"] == X]["probability"].sum()
```

#### Step 3: Rate Combinations

We consider 7 possible rate change combinations:

- **(-25, -25)**: Both meetings decrease by 25 bps
- **(-25, 0)**: First decreases, second unchanged
- **(0, -25)**: First unchanged, second decreases
- **(0, 0)**: Both unchanged
- **(0, 25)**: First unchanged, second increases
- **(25, 0)**: First increases, second unchanged
- **(25, 25)**: Both increase by 25 bps

Note: **(25, -25)** is excluded as it's unlikely.

#### Step 4: Distance Calculation and Inverse Distance Weighting

For each scenario, calculate the distance from market price:

```
distance_i = |future_price - price_i|
```

Then calculate inverse distance:

```
reverse_distance_i = 1 / (distance_i + ε)
```

Where **ε = 10^-10** to avoid division by zero.

```
probability_i = reverse_distance_i / Σ(reverse_distance_j) for j=1 to 7
```

This ensures: **Σ(probability_i) for i=1 to 7 = 1**

---

## Subsequent Futures Contracts (Recursion)

For each futures contract **t > 1**, we start from the last probability vector **p\_{t-1}(k)** and "propagate" the possible transitions induced by the new meetings.

### Case 1: Single Meeting (N_t = 1)

For a subsequent contract with one meeting:

```
p_t(k) = (1 - f_t) × p_{t-1}(k - Δ×n_t) + f_t × p_{t-1}(k - Δ×(n_t + s))
```

Where:

- **f_t = fractional(n_t)** - the fractional part
- **s = sign(n_t)** - the sign of the change

This is exactly the code block:

```python
p_X = (1 - fractional) × p_prev[X - integer × step]
      + fractional × p_prev[X - (integer + sign) × step]
```

#### Probability Extension

Before calculating probabilities for subsequent meetings, we extend the support:

```
extended_keys = {min_step - i × STEP_SIZE, max_step + i × STEP_SIZE}
```

For **i = 1, 2, ..., PROBABILITY_EXTENSION_STEPS**

New steps are initialized with zero probabilities for all previous meetings.

### Case 2: Two Meetings (N_t = 2)

For a subsequent contract with two meetings:

```
p_t(k) = Σ_{x ∈ {-2, -1, 0, 1, 2}} p_{t-1}(k - Δ×x) × p^(2)(x)
```

Where **p^(2)(x)** is the probability from the product of the two meetings:

```
p^(2)(x) = {
  p₁(0) × p₂(0)                    if x = 0
  p₁(+25) × p₂(0) + p₁(0) × p₂(+25) if x = +25
  ...
}
```

This is what the code does with:

```python
p_1_X = p_prev[X] × new_prob_dict[0][0]
        + p_prev[X - step] × new_prob_dict[25][0]
        + ...

p_2_X = ...
```

#### First Meeting Probability Update

```
P₁(step_key) = P_prev(step_key) × P₁(0)
                + P_prev(step_key - 25) × P₁(25)
                + P_prev(step_key + 25) × P₁(-25)
```

Where:

- **P_prev(step_key)** = previous probability at `step_key`
- **P₁(0)**, **P₁(25)**, **P₁(-25)** = new first meeting probabilities from current contract

#### Second Meeting Probability Update

```
P₂(step_key) = P_prev(step_key) × P₂(0)
                + P_prev(step_key - 25) × P₂(25)
                + P_prev(step_key + 25) × P₂(-25)
                + P_prev(step_key - 50) × P₂(50)
                + P_prev(step_key + 50) × P₂(-50)
```

Where:

- **P_prev(step_key)** = previous probability at `step_key`
- **P₂(0)**, **P₂(25)**, **P₂(-25)**, **P₂(50)**, **P₂(-50)** = new second meeting probabilities from current contract

---

## Normalization

After each futures contract, probabilities are normalized:

```
Σ_k p_t(k) = 1
```

And converted to percentages:

```
p_t(k)_% = 100 × p_t(k)
```

Rounded to 2 decimal places.

---

## Final Result

We obtain a matrix equivalent to a transition matrix:

| Meeting   | -50 | -25  | 0   | +25  | +50 | Σ   |
| --------- | --- | ---- | --- | ---- | --- | --- |
| Meeting 1 | 0.0 | 0.3  | 0.7 | 0.0  | 0.0 | 1.0 |
| Meeting 2 | 0.0 | 0.15 | 0.5 | 0.35 | 0.0 | 1.0 |
| ...       | ... | ...  | ... | ...  | ... | ... |

Where:

- Each row corresponds to a meeting date
- Each column corresponds to a rate step change
- Each entry is a probability percentage
- Each row sums to approximately 100% (within rounding)

### Filtering Low-Probability Steps

Remove steps where:

```
Σ(P_%,i) for i=1 to n < PROBABILITY_THRESHOLD
```

---

## FED-Specific Calculations

### Implied Rate Calculation

Fed Funds Futures prices are quoted as: **Price = 100 - Implied Rate**

```
implied_rate = 100 - futures_price
```

The implied rate represents the **average** of daily Fed Funds rates over the contract period.

### Rate Calculation for Contracts with Meetings

For a futures contract with a meeting date, we need to calculate either the start rate (before meeting) or end rate (after meeting).

#### Time Periods

```
days_after_meeting = (settlement_date - meeting_date).days
```

```
days_before_meeting = contract_days - days_after_meeting
```

```
prior_ratio = days_before_meeting / contract_days
```

```
after_ratio = days_after_meeting / contract_days
```

#### Average Rate Relationship

The implied rate is the weighted average of rates before and after the meeting:

```
implied_rate = start_rate × prior_ratio + end_rate × after_ratio
```

#### Solving for Start Rate

If we know the end rate:

```
start_rate = (implied_rate - end_rate × after_ratio) / prior_ratio
```

#### Solving for End Rate

If we know the start rate:

```
end_rate = (implied_rate - start_rate × prior_ratio) / after_ratio
```

### Rate Change Calculation

For each meeting, we calculate the rate change:

```
rate_diff = end_rate - start_rate
```

Convert to basis points:

```
rate_diff_bps = rate_diff × 100
```

### Handling Contracts Without Meetings

For contracts without meetings:

- The implied rate is propagated as the end rate for the previous meeting
- The implied rate becomes the start rate for the next meeting with a meeting

---

## BOJ-Specific Calculations

### Implied Rate Calculation

Mutan Futures prices are quoted as: **Price = 100 - Implied Rate**

```
implied_rate = 100 - futures_price
```

### Single Meeting: Average Rate Calculation

For a contract with one meeting, we calculate the implied rate at the meeting date.

#### Time Periods

```
days_after_meeting = (settlement_date - meeting_date).days
```

```
days_before_meeting = contract_days - days_after_meeting
```

#### Daily Compounding Factors

```
daily_rate_factor = 1 + (base_rate / 100) × (1 / 365)
```

```
discounted_base_rate = (daily_rate_factor)^(-days_before_meeting)
```

```
future_rate_factor = 1 + (contract_days / 365) × (future_rate / 100)
```

#### Meeting Implied Rate

```
compound_factor = (future_rate_factor × discounted_base_rate)^(1 / days_after_meeting)
```

```
meeting_implied_rate = (compound_factor - 1) × 365 × 100
```

### Two Meetings: Price Calculation

For a contract with two meetings, we calculate the futures price for different rate scenarios.

#### Time Periods

```
days_after_second = (settlement_date - second_meeting_date).days
```

```
days_between_meetings = (second_meeting_date - first_meeting_date).days
```

```
days_before_first = contract_days - (days_after_second + days_between_meetings)
```

#### Rate Scenarios

For each scenario, we calculate rates:

```
first_rate = base_rate + (first_rate_step / 100)
```

```
second_rate = base_rate + (second_rate_step / 100)
```

Where `first_rate_step` and `second_rate_step` are from the set: **{-25, 0, 25}** (in basis points)

#### Daily Compounding

```
daily_rate_factor = 1 / (100 × 365)
```

```
compounded_base = (1 + base_rate × daily_rate_factor)^days_before_first
```

```
compounded_first = (1 + first_rate × daily_rate_factor)^days_between_meetings
```

```
compounded_second = (1 + second_rate × daily_rate_factor)^days_after_second
```

#### Par Rate and Price

```
par_rate = compounded_base × compounded_first × compounded_second - 1
```

```
annualized_par_rate = par_rate × 100 × (365 / 90)
```

```
price = 100 - annualized_par_rate
```

---

## Summary

### Key Differences: FED vs BOJ

| Aspect                 | FED                   | BOJ                             |
| ---------------------- | --------------------- | ------------------------------- |
| **Rate Type**          | Average rate          | Compounded rate                 |
| **Price Calculation**  | Simple average        | Daily compounding               |
| **Single Meeting**     | Direct rate change    | Implied rate calculation        |
| **Two Meetings**       | Sequential processing | Joint probability distribution  |
| **Probability Method** | Linear interpolation  | Inverse distance weighting      |
| **Extension Steps**    | 5 steps               | 5 steps (but can be customized) |

### Mathematical Principles

1. **FED**: Uses weighted averages and linear interpolation
2. **BOJ**: Uses compound interest and inverse distance weighting
3. **Both**: Use linear interpolation for probability assignment
4. **Both**: Extend probability support before subsequent calculations
5. **Both**: Filter out low-probability scenarios in final output

### General Formulation

The entire process can be viewed as a sequence of **discrete probability distribution convolutions**:

- **First contract**: Direct calculation from implied rates
- **Subsequent contracts**: Convolution of previous probabilities with new meeting probabilities

This recursive structure ensures that probabilities are properly propagated through time, accounting for all possible rate change paths.

---

## References

- Fed Funds Futures: Based on average daily Fed Funds rate
- Mutan Futures: Based on TONA (Tokyo Overnight Average Rate) compounding
- Day count convention: ACT/365 for both
- Mutan Futures annualization: Uses 90-day convention regardless of actual contract days
