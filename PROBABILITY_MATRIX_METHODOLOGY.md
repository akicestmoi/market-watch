# Probability Matrix Calculation Mathematics

This document provides a detailed mathematical explanation of how probability matrices are calculated for both **Federal Reserve (FED)** and **Bank of Japan (BOJ)** interest rate changes from futures prices.

## Table of Contents

1. [Common Concepts](#common-concepts)
2. [Federal Reserve (FED) Calculations](#federal-reserve-fed-calculations)
3. [Bank of Japan (BOJ) Calculations](#bank-of-japan-boj-calculations)
4. [Probability Matrix Construction](#probability-matrix-construction)

---

## Common Concepts

### Constants

- **STEP_SIZE** = 25 basis points (0.25%)
- **STANDARD_STEP_SCENARIOS** = [-50, -25, 0, 25, 50] (in basis points)
- **PROBABILITY_EXTENSION_STEPS** = 5
- **PROBABILITY_THRESHOLD** = 1.0%
- **DAYS_PER_YEAR** = 365
- **MUTAN_FUTURES_AVERAGE_DAYS** = 90 (for BOJ only)

### Rate Change Decomposition

Given a rate change in basis points, we decompose it into integer steps and a fractional part:

\[
\text{meeting\_steps} = \frac{\text{rate\_change\_bps}}{\text{STEP\_SIZE}}
\]

\[
\text{fractional}, \text{integer} = \text{modf}(\text{meeting\_steps})
\]

\[
\text{sign} = \text{copysign}(1, \text{meeting\_steps})
\]

Where:
- **nb_steps** = `int(integer)` - the integer number of steps
- **proportion** = `abs(fractional)` - the fractional part (0 ≤ proportion < 1)
- **sign** = ±1 - indicates direction of change

### Linear Interpolation

For probability assignment, we use linear interpolation between adjacent rate steps.

#### Initial Assignment (First Meeting)

For the first meeting, probabilities are assigned to three adjacent steps:

\[
\text{step\_up} = \text{int}((\text{nb\_steps} + \text{sign}) \times \text{STEP\_SIZE})
\]

\[
\text{step\_current} = \text{int}(\text{nb\_steps} \times \text{STEP\_SIZE})
\]

\[
P(\text{step\_up}) = \text{proportion}
\]

\[
P(\text{step\_current}) = 1 - \text{proportion}
\]

\[
P(\text{step\_down}) = 0
\]

For all other steps: \(P(\text{step}) = 0\)

#### Subsequent Assignment

For subsequent meetings, probabilities are calculated using linear interpolation from the previous meeting's probabilities:

\[
\text{prev\_step\_key} = \text{step\_key} - \text{nb\_steps} \times \text{STEP\_SIZE}
\]

\[
\text{next\_step\_key} = \text{step\_key} - \text{int}((\text{nb\_steps} + \text{sign}) \times \text{STEP\_SIZE})
\]

\[
P_X = (1 - \text{proportion}) \times P_{\text{prev}} + \text{proportion} \times P_{\text{next}}
\]

Where:
- \(P_{\text{prev}}\) = probability at `prev_step_key` from previous meeting
- \(P_{\text{next}}\) = probability at `next_step_key` from previous meeting
- \(P_X\) = new probability for step `step_key`

---

## Federal Reserve (FED) Calculations

### 1. Implied Rate Calculation

Fed Funds Futures prices are quoted as: **Price = 100 - Implied Rate**

\[
\text{implied\_rate} = 100 - \text{futures\_price}
\]

The implied rate represents the **average** of daily Fed Funds rates over the contract period.

### 2. Rate Calculation for Contracts with Meetings

For a futures contract with a meeting date, we need to calculate either the start rate (before meeting) or end rate (after meeting).

#### Time Periods

\[
\text{days\_after\_meeting} = (\text{settlement\_date} - \text{meeting\_date}).\text{days}
\]

\[
\text{days\_before\_meeting} = \text{contract\_days} - \text{days\_after\_meeting}
\]

\[
\text{prior\_ratio} = \frac{\text{days\_before\_meeting}}{\text{contract\_days}}
\]

\[
\text{after\_ratio} = \frac{\text{days\_after\_meeting}}{\text{contract\_days}}
\]

#### Average Rate Relationship

The implied rate is the weighted average of rates before and after the meeting:

\[
\text{implied\_rate} = \text{start\_rate} \times \text{prior\_ratio} + \text{end\_rate} \times \text{after\_ratio}
\]

#### Solving for Start Rate

If we know the end rate:

\[
\text{start\_rate} = \frac{\text{implied\_rate} - \text{end\_rate} \times \text{after\_ratio}}{\text{prior\_ratio}}
\]

#### Solving for End Rate

If we know the start rate:

\[
\text{end\_rate} = \frac{\text{implied\_rate} - \text{start\_rate} \times \text{prior\_ratio}}{\text{after\_ratio}}
\]

### 3. Rate Change Calculation

For each meeting, we calculate the rate change:

\[
\text{rate\_diff} = \text{end\_rate} - \text{start\_rate}
\]

Convert to basis points:

\[
\text{rate\_diff\_bps} = \text{rate\_diff} \times 100
\]

### 4. Handling Contracts Without Meetings

For contracts without meetings:
- The implied rate is propagated as the end rate for the previous meeting
- The implied rate becomes the start rate for the next meeting with a meeting

### 5. Probability Matrix Generation

1. Calculate rate changes for all meetings
2. For each meeting (in chronological order):
   - Convert rate change to basis points
   - Apply linear interpolation (initial for first meeting, subsequent for others)
3. Format probabilities:
   - Convert to percentages: \(P_{\%} = P \times 100\)
   - Round to 2 decimal places
   - Remove steps where sum of probabilities < PROBABILITY_THRESHOLD

---

## Bank of Japan (BOJ) Calculations

### 1. Implied Rate Calculation

Mutan Futures prices are quoted as: **Price = 100 - Implied Rate**

\[
\text{implied\_rate} = 100 - \text{futures\_price}
\]

### 2. Single Meeting: Average Rate Calculation

For a contract with one meeting, we calculate the implied rate at the meeting date.

#### Time Periods

\[
\text{days\_after\_meeting} = (\text{settlement\_date} - \text{meeting\_date}).\text{days}
\]

\[
\text{days\_before\_meeting} = \text{contract\_days} - \text{days\_after\_meeting}
\]

#### Daily Compounding Factors

\[
\text{daily\_rate\_factor} = 1 + \frac{\text{base\_rate}}{100} \times \frac{1}{365}
\]

\[
\text{discounted\_base\_rate} = (\text{daily\_rate\_factor})^{-\text{days\_before\_meeting}}
\]

\[
\text{future\_rate\_factor} = 1 + \frac{\text{contract\_days}}{365} \times \frac{\text{future\_rate}}{100}
\]

#### Meeting Implied Rate

\[
\text{compound\_factor} = (\text{future\_rate\_factor} \times \text{discounted\_base\_rate})^{\frac{1}{\text{days\_after\_meeting}}}
\]

\[
\text{meeting\_implied\_rate} = (\text{compound\_factor} - 1) \times 365 \times 100
\]

### 3. Two Meetings: Price Calculation

For a contract with two meetings, we calculate the futures price for different rate scenarios.

#### Time Periods

\[
\text{days\_after\_second} = (\text{settlement\_date} - \text{second\_meeting\_date}).\text{days}
\]

\[
\text{days\_between\_meetings} = (\text{second\_meeting\_date} - \text{first\_meeting\_date}).\text{days}
\]

\[
\text{days\_before\_first} = \text{contract\_days} - (\text{days\_after\_second} + \text{days\_between\_meetings})
\]

#### Rate Scenarios

For each scenario, we calculate rates:

\[
\text{first\_rate} = \text{base\_rate} + \frac{\text{first\_rate\_step}}{100}
\]

\[
\text{second\_rate} = \text{base\_rate} + \frac{\text{second\_rate\_step}}{100}
\]

Where `first_rate_step` and `second_rate_step` are from the set: {-25, 0, 25} (in basis points)

#### Daily Compounding

\[
\text{daily\_rate\_factor} = \frac{1}{100 \times 365}
\]

\[
\text{compounded\_base} = (1 + \text{base\_rate} \times \text{daily\_rate\_factor})^{\text{days\_before\_first}}
\]

\[
\text{compounded\_first} = (1 + \text{first\_rate} \times \text{daily\_rate\_factor})^{\text{days\_between\_meetings}}
\]

\[
\text{compounded\_second} = (1 + \text{second\_rate} \times \text{daily\_rate\_factor})^{\text{days\_after\_second}}
\]

#### Par Rate and Price

\[
\text{par\_rate} = \text{compounded\_base} \times \text{compounded\_first} \times \text{compounded\_second} - 1
\]

\[
\text{annualized\_par\_rate} = \text{par\_rate} \times 100 \times \frac{365}{90}
\]

\[
\text{price} = 100 - \text{annualized\_par\_rate}
\]

### 4. Probability Distribution for Two Meetings

#### Rate Combinations

We consider 7 possible rate change combinations:
- (-25, -25): Both meetings decrease by 25 bps
- (-25, 0): First decreases, second unchanged
- (0, -25): First unchanged, second decreases
- (0, 0): Both unchanged
- (0, 25): First unchanged, second increases
- (25, 0): First increases, second unchanged
- (25, 25): Both increase by 25 bps

Note: (25, -25) is excluded as it's unlikely.

#### Distance Calculation

For each scenario, calculate the distance from market price:

\[
\text{distance}_i = |\text{future\_price} - \text{price}_i|
\]

#### Inverse Distance Weighting

\[
\text{reverse\_distance}_i = \frac{1}{\text{distance}_i + \epsilon}
\]

Where \(\epsilon = 10^{-10}\) to avoid division by zero.

\[
\text{probability}_i = \frac{\text{reverse\_distance}_i}{\sum_{j=1}^{7} \text{reverse\_distance}_j}
\]

This ensures: \(\sum_{i=1}^{7} \text{probability}_i = 1\)

### 5. Probability Aggregation

#### First Meeting Probabilities

For each step \(X\):

\[
P_1(X) = \sum_{i: \text{first\_rate\_step}_i = X} \text{probability}_i
\]

#### Second Meeting Probabilities

For each step \(X\):

\[
P_2(X) = \sum_{i: \text{total\_step}_i = X} \text{probability}_i
\]

Where \(\text{total\_step}_i = \text{first\_rate\_step}_i + \text{second\_rate\_step}_i\)

### 6. Subsequent Meetings: Probability Update

For subsequent contracts with two meetings, we update probabilities based on previous probabilities.

#### First Meeting Probability Update

\[
P_1(\text{step\_key}) = P_{\text{prev}}(\text{step\_key}) \times P_1(0) + P_{\text{prev}}(\text{step\_key} - 25) \times P_1(25) + P_{\text{prev}}(\text{step\_key} + 25) \times P_1(-25)
\]

Where:
- \(P_{\text{prev}}(\text{step\_key})\) = previous probability at `step_key`
- \(P_1(0)\), \(P_1(25)\), \(P_1(-25)\) = new first meeting probabilities from current contract

#### Second Meeting Probability Update

\[
\begin{align}
P_2(\text{step\_key}) &= P_{\text{prev}}(\text{step\_key}) \times P_2(0) \\
&\quad + P_{\text{prev}}(\text{step\_key} - 25) \times P_2(25) \\
&\quad + P_{\text{prev}}(\text{step\_key} + 25) \times P_2(-25) \\
&\quad + P_{\text{prev}}(\text{step\_key} - 50) \times P_2(50) \\
&\quad + P_{\text{prev}}(\text{step\_key} + 50) \times P_2(-50)
\end{align}
\]

Where:
- \(P_{\text{prev}}(\text{step\_key})\) = previous probability at `step_key`
- \(P_2(0)\), \(P_2(25)\), \(P_2(-25)\), \(P_2(50)\), \(P_2(-50)\) = new second meeting probabilities from current contract

### 7. Probability Matrix Generation

1. Process contracts in chronological order
2. For each contract:
   - **Initial contract**:
     - Single meeting: Calculate implied rate, apply linear interpolation
     - Two meetings: Calculate probability distribution, aggregate probabilities
   - **Subsequent contracts**:
     - Single meeting: Calculate implied rate, apply linear interpolation with extension
     - Two meetings: Calculate probability distribution, update probabilities using previous probabilities
3. Format probabilities:
   - Convert to percentages: \(P_{\%} = P \times 100\)
   - Round to 2 decimal places
   - Remove steps where sum of probabilities < PROBABILITY_THRESHOLD

---

## Probability Matrix Construction

### Matrix Structure

The probability matrix is a list of probability distributions, one for each meeting date:

\[
\text{Probability Matrix} = \begin{bmatrix}
P_1(-50) & P_1(-25) & P_1(0) & P_1(25) & P_1(50) & \cdots \\
P_2(-50) & P_2(-25) & P_2(0) & P_2(25) & P_2(50) & \cdots \\
\vdots & \vdots & \vdots & \vdots & \vdots & \ddots
\end{bmatrix}
\]

Where each row represents a meeting date, and each column represents a rate step change.

### Probability Extension

Before calculating probabilities for subsequent meetings, we extend the support:

\[
\text{extended\_keys} = \{\text{min\_step} - i \times \text{STEP\_SIZE}, \text{max\_step} + i \times \text{STEP\_SIZE}\}
\]

For \(i = 1, 2, \ldots, \text{PROBABILITY\_EXTENSION\_STEPS}\)

New steps are initialized with zero probabilities for all previous meetings.

### Final Formatting

1. **Convert to percentages**:
   \[
   P_{\%,i} = \text{round}(P_i \times 100, 2)
   \]

2. **Filter low-probability steps**:
   Remove steps where:
   \[
   \sum_{i=1}^{n} P_{\%,i} < \text{PROBABILITY\_THRESHOLD}
   \]

3. **Result**: A matrix where:
   - Each row corresponds to a meeting date
   - Each column corresponds to a rate step change
   - Each entry is a probability percentage
   - Each row sums to approximately 100% (within rounding)

---

## Summary

### Key Differences: FED vs BOJ

| Aspect | FED | BOJ |
|--------|-----|-----|
| **Rate Type** | Average rate | Compounded rate |
| **Price Calculation** | Simple average | Daily compounding |
| **Single Meeting** | Direct rate change | Implied rate calculation |
| **Two Meetings** | Sequential processing | Joint probability distribution |
| **Probability Method** | Linear interpolation | Inverse distance weighting |
| **Extension Steps** | 5 steps | 5 steps (but can be customized) |

### Mathematical Principles

1. **FED**: Uses weighted averages and linear interpolation
2. **BOJ**: Uses compound interest and inverse distance weighting
3. **Both**: Use linear interpolation for probability assignment
4. **Both**: Extend probability support before subsequent calculations
5. **Both**: Filter out low-probability scenarios in final output

---

## References

- Fed Funds Futures: Based on average daily Fed Funds rate
- Mutan Futures: Based on TONA (Tokyo Overnight Average Rate) compounding
- Day count convention: ACT/365 for both
- Mutan Futures annualization: Uses 90-day convention regardless of actual contract days

