# Probability Matrix Calculation Methodology

This document provides a detailed mathematical explanation of how probability matrices are calculated for the **Federal Reserve (FRB)**, the **European Central Bank (ECB)** and the **Bank of Japan (BOJ)**.

The probabilities are derived directly from Short-Term Interest Rate Futures (or STIR futures), namely the **1-Month Fedfunds futures** for FRB, **3-Month ESTR futures** for ECB and **3-Month TONA futures** for BOJ, listed respectively on CME, ICE and TFX.

## Table of Contents

1. [Base Modelling Assumptions](#base-modelling-assumptions)
2. [STIR Futures Contracts Pricing](#stir-futures-contracts-pricing)
   1. [1-Month Fedfunds Futures](#1-month-fedfunds-futures)
   2. [3-Month ESTR Futures](#3-month-estr-futures)
   3. [3-Month TONA Futures](#3-month-tona-futures)
3. [FRB Probability Matrix Methodology](#frb-probability-matrix-methodology)
    1. [General Framework](#general-framework)
    2. [Step 0: Validation of Meeting Coverage by Futures](#step-0-validation-of-meeting-coverage-by-futures)
    3. [Step 1: Fill Start/End Prices For Periods Without Meeting](#step-1-fill-startend-prices-for-periods-without-meeting)
    4. [Step 2: Infer Implied Rates At Meeting Date](#step-2-infer-implied-rates-at-meeting-date)
    5. [Step 3: Linear Interpolation](#step-3-linear-interpolation)
    6. [Step 4: Probability Convolution For Cumulative Probabilities](#step-4-probability-convolution-for-cumulative-probabilities)
4. [ECB and BOJ Probability Matrix Methodology](#ecb-and-boj-probability-matrix-methodology)
   1. [General Framework](#general-framework-1)
   2. [Step 1: Infer Single meeting implied rates](#step-1-infer-single-meeting-implied-rates)
   3. [Step 2: Generate all meetings scenario](#step-2-generate-all-meetings-scenario)
   4. [Step 3: Calculate Scenario Prices](#step-3-calculate-scenario-prices)
   5. [Step 4: Inverse Distance Weighting (Joint Probability Calculation)](#step-4-inverse-distance-weighting-joint-probability-calculation)
   6. [Step 5: Aggregate Individual Meeting Probabilities (Marginalization)](#step-5-aggregate-individual-meeting-probabilities-marginalization)
   7. [Step 6: Convolution For Cumulative Probabilities](#step-6-convolution-for-cumulative-probabilities)
   8. [Final Notes](#final-notes)
5. [Caveats and Limitations](#caveats-and-limitations)

---

## Base Modelling Assumptions

- (1) There is at most one central bank meeting in one month.
- (2) Rates stay constant until a central bank rate cut or rate hike decision.
- (3) Central banks have only 3 choices: cut rate, leave unchanged, hike rate.
- (4) Central banks rate path has a certain rigidity: they cannot revert their decision (e.g. hike rate after rate cut and vice-versa) for a few years, which translates to $p_{\text{hike}}(\text{cut}) = 0$ and $p_{\text{cut}}(\text{hike}) = 0$.
- (5) Rates can only change by $\Delta$ at each meeting, which is defined to be $\Delta = 25$ bps.

---

## STIR Futures Contracts Pricing

STIR futures are the most practical financial instruments as their pricing depends on daily central banks target rates effective fixing, thus reflecting the market view on central banks' policy decisions. They also present the benefit of having all their historical data publicly available.

For all contracts, the future price is given by:

$$P = 100 - r_{implied}$$

Where $P$ is the Futures price, $r_{implied}$ is the Future implied rate (in percentage).

However, the way each future calculates its implied rate can differ extensively as it depends on the contract specificities.

#### 1-Month Fedfunds Futures

Fed Funds Futures are priced based on the **average** of daily Fed Funds rates over the contract period. Accrual days begin every first day of the month, and end the last day of this month.

$$ r_{implied} = \frac{1}{T} \sum_{i=1}^{T} (r_{i}) $$

Where $T$ is the total contract days, $r_{i}$ is the effective target rate for day $i$.

*Source: https://www.cmegroup.com/markets/interest-rates/stirs/30-day-federal-fund.html*

#### 3-Month ESTR Futures

ESTR Futures are priced using **daily compounding** following an ACT/360 day count convention. Accrual days begin the third Wednesday of the Delivery Month, and end the business day prior to the third Wednesday of the third calendar month after the start of the first Accrual Day. As an example, a future annotated "September 2025" **BEGINS** on September and ends 3 months later in December.

$$r_{\text{implied}} = r_{\text{par}} \times 100 \times \frac{360}{T}$$

And:

$$r_{\text{par}} = \left[\prod_{i=0}^{n} \left(1 + r_i \times \frac{d_i}{100 \times 360}\right)\right] - 1$$

Where $T$ is the total contract days, $r_{\text{i}}$ is the effective target rate for day $i$, $n$ is the number of rate fixing over the period (e.g. the number of weekdays), $d_{\text{i}}$ is the days applied between rate fixing $i-1$ and rate fixing $i$ (${d_i} = 1$ on weekdays except for Friday, and ${d_i} \in {1, 3}$ over the weekend starting from Friday, where its value depending on whether the rate fixing is on Friday or not).

*Source: https://www.ice.com/products/82908552/Three-Month-ESTR-Indexed-Future*

#### 3-Month TONA Futures

TONA Futures are priced using **daily compounding** following a 30/365 day count convention. Hence, a 3-month contract implies total contract days of 90 (only used when converting to annual rate, as par rate still needs to count each fixing of every contract day). Accrual days are not calculated on our side: we directly get accrual days from its source.

$$r_{\text{implied}} = r_{\text{par}} \times 100 \times \frac{365}{90}$$

And the par rate is:

$$r_{\text{par}} = \left[\prod_{i=0}^{n} \left(1 + r_i \times \frac{d_i}{100 \times 365}\right)\right] - 1$$

Where $T$ is the total contract days, $r_{\text{i}}$ is the effective target rate for day $i$, $n$ is the number of rate fixing over the period (e.g. the number of weekdays), $d_{\text{i}}$ is the days applied between rate fixing $i-1$ and rate fixing $i$ (${d_i} = 1$ on weekdays except for Friday, and ${d_i} \in {1, 3}$ over the weekend starting from Friday, where its value depending on whether the rate fixing is on Friday or not).

*Source: https://www.tfx.co.jp/en/wholesale/products/tona.html*

*Accrual days source: https://www.tfx.co.jp/historical/futures/tradingcalendar.html*

---

## FRB Probability Matrix Methodology

Here we follow the same methodology as CME's FedWatch that can be found here: *https://www.cmegroup.com/articles/2023/understanding-the-cme-group-fedwatch-tool-methodology.html*.

### General Framework

Fedfunds futures use a simpler methodology since they are 1-month contracts typically containing at most one meeting per contract. The global process consists in inferring the implied rate priced in at the meeting dates from the futures prices, then converting these implied rates into probabilities of rate changes.

For each contract, we have:
- $r_{implied}$: The implied average rate from the futures price
- $T$: Total contract days (accrual days)

As futures contracts are calculated as average rates over the accrual period, we can determine the implied meeting rate $r_{end}$ using a weighted average of 2 different rates: the rate before the meeting $r_{start}$ and the rate after the meeting $r_{end}$. Therefore, both $r_{implied}$ (the average rate from the futures price) and $r_{start}$ are needed to solve for $r_{end}$ using one single equation (the futures price calculation equation).

These 2 rates, e.g.:
- $r_{start}$: Rate before the meeting (start of period)
- $r_{end}$: Rate after the meeting (end of period)

These will be used later to calculate the rate differential which represents the market implied probability of central banks' decisions. Hence, the first step is to obtain these 2 rates.

### Step 0: Validation of Meeting Coverage by Futures

Before processing the probability matrix, we validate that all meeting dates are properly covered by futures contracts. This ensures that we have sufficient data to calculate the required rates.

**Validation Requirements:**

1. **Meeting Coverage**: All meeting dates must fall within at least one future contract's accrual period.

2. **Last Meeting Requirement**: The last meeting must have a future contract **after** it. This is required to determine the `end_rate` for the last meeting.

3. **Meeting Limit**: Only the first 8 meetings are processed to limit computational complexity. In addition, there is no real value in inferring prices that are too far away.

If any of these requirements are not met, a `ValueError` is raised and the probability matrix calculation is aborted.

Note that there is no requirement on the first meeting as current effective rate is used as a fallback.

### Step 1: Fill Start/End Prices For Periods Without Meeting

This step handles non-FOMC months (contracts without meetings). The key principle is that implied rates from non-FOMC anchor months propagate in specific directions to minimize discontinuities in the path of implied rates.

**Rules for Non-FOMC Months:**

For every non-FOMC month $T$ (contract without a meeting), the implied rate $r_{\text{implied}}(T)$ is used to populate:
- **$r_{\text{end}}(T-1)$**: The end rate of the previous contract (if $T-1$ has a meeting)
- **$r_{\text{start}}(T+1)$**: The start rate of the next contract (if $T+1$ has a meeting)

**Implementation Process:**

1. **Initialize**: For the first contract:
   - If it has a meeting: $r_{\text{start}}$ is set to $r_{\text{base}}$ (initial base rate)

2. **Direct Propagation**: For each non-FOMC month $T$:
   - Set $r_{\text{end}}(T-1) = r_{\text{implied}}(T)$ if contract $T-1$ has a meeting
   - Set $r_{\text{start}}(T+1) = r_{\text{implied}}(T)$ if contract $T+1$ has a meeting (only from immediately preceding non-FOMC month)

**Important Notes:**
- When multiple non-FOMC months precede a meeting, only the **immediately preceding** non-FOMC month sets the meeting's start rate
- This step only does direct propagation from non-FOMC months. The calculation of missing rates and backward propagation of calculated rates happens in Step 2 (see below)

### Step 2: Infer Implied Rates At Meeting Date

This step consists of three sub-steps that calculate missing rates, propagate calculated rates backward, and compute rate differences.

#### Step 2.1: Calculate Missing Rates Using Formulas

For each contract containing a meeting, we calculate the missing rate (either $r_{\text{start}}$ or $r_{\text{end}}$) using the average rate formula for Fedfunds futures.

Given:
- $r_{\text{start}}$: Rate before the meeting (start rate)
- $r_{\text{end}}$: Rate after the meeting (end rate)
- $r_{\text{implied}}$: Implied average rate from the futures price
- $d_{\text{before}}$: Days before the meeting
- $d_{\text{after}}$: Days after the meeting
- $T = d_{\text{before}} + d_{\text{after}}$: Total contract days

The average rate formula gives:

$$r_{\text{implied}} = \frac{1}{T} \sum_{i=1}^{T} r_i = \frac{d_{\text{before}} \times r_{\text{start}} + d_{\text{after}} \times r_{\text{end}}}{T}$$

**Solving for $r_{\text{end}}$ (when $r_{\text{start}}$ is known):**

$$r_{\text{end}} = \frac{T \times r_{\text{implied}} - d_{\text{before}} \times r_{\text{start}}}{d_{\text{after}}}$$

**Solving for $r_{\text{start}}$ (when $r_{\text{end}}$ is known):**

$$r_{\text{start}} = \frac{T \times r_{\text{implied}} - d_{\text{after}} \times r_{\text{end}}}{d_{\text{before}}}$$

**For months immediately before/after non-FOMC month:**
- If $r_{\text{end}}$ was set from a non-FOMC month: Calculate $r_{\text{start}}$ using $r_{\text{end}}$ and $r_{\text{implied}}$
- If $r_{\text{start}}$ was set from a non-FOMC month: Calculate $r_{\text{end}}$ using $r_{\text{start}}$ and $r_{\text{implied}}$

**Refining rates when both are available:**

In some cases, both $r_{\text{start}}$ and $r_{\text{end}}$ may be initially set (e.g., from Step 1 propagation). However, to ensure accuracy, we recalculate $r_{\text{start}}$ using the actual futures implied rate and the known $r_{\text{end}}$. This refinement step ensures that the start rate is consistent with the futures contract pricing, as the futures price reflects the market's expectation and should be used to refine the start rate when both values are available.

#### Step 2.2: Backward Propagation of Calculated Rates

Calculated rates from non-FOMC months are propagated backward to ensure continuity:

**Rule**: The calculated $r_{\text{start}}(T-1)$ (from non-FOMC month $T$) is copied to populate $r_{\text{end}}(T-2)$, continuing backward until another non-FOMC anchor month is reached.

**Process:**
1. For each meeting with a calculated $r_{\text{start}}$ (set from a non-FOMC month), propagate it backward as $r_{\text{end}}$ of the previous meeting
2. Continue backward propagation until we hit a non-FOMC anchor month (a contract without a meeting between meetings)
3. When propagating, if a previous meeting's $r_{\text{end}}$ is set, recalculate its $r_{\text{start}}$ using the formula above

**Important**: Forward propagation is limited to one step only. The calculated $r_{\text{end}}(T+1)$ is **NOT** used to populate $r_{\text{start}}(T+2)$.

#### Step 2.3: Calculate Rate Differences

After all rates are calculated and propagated, the rate change in basis points at each meeting is:

$$\Delta r_{\text{bps}} = (r_{\text{end}} - r_{\text{start}}) \times 100$$

This rate change represents the market's expectation of the rate change at that meeting.

### Step 3: Linear Interpolation

The rate change $\Delta r_{\text{bps}}$ previously calculated is typically not an exact multiple of $\Delta = 25$ bps. We use linear interpolation to distribute probabilities between the two nearest step values.

**Decompose the rate change:**

First, we decompose $\Delta r_{\text{bps}}$ into an integer number of steps and a fractional part:

$$\Delta r_{\text{bps}} = n \times \Delta + f \times \Delta \times \text{sign}(\Delta r_{\text{bps}})$$

Where:
- $n = \lfloor |\Delta r_{\text{bps}}| / \Delta \rfloor$ is the number of steps (integer)
- $f = (|\Delta r_{\text{bps}}| / \Delta) - n$ is the fractional part ($0 \leq f < 1$), which is what we will use to make the linear distribution
- $\text{sign}(\Delta r_{\text{bps}})$ is $+1$ if the rate change is positive, $-1$ if negative

**For the initial contract:**

Probabilities are assigned to the two nearest step values using linear interpolation:

$$p(n \times \Delta \times \text{sign}) = 1 - f$$
$$p((n + 1) \times \Delta \times \text{sign}) = f$$

All other step values receive probability 0.

**Example**: If $\Delta r_{\text{bps}} = 37.5$ bps, then:
- $n = \lfloor 37.5 / 25 \rfloor = 1$
- $f = (37.5 / 25) - 1 = 0.5$
- $p(+25 \text{ bps}) = 1 - 0.5 = 0.5$
- $p(+50 \text{ bps}) = 0.5$

**For subsequent contracts:**

We need to convolve with previous probabilities. For each possible cumulative step $k$:

$$p_{\text{new}}(k) = (1 - f) \times p_{\text{prev}}(k - n \times \Delta \times \text{sign}) + f \times p_{\text{prev}}(k - (n + 1) \times \Delta \times \text{sign})$$

Where:
- $p_{\text{prev}}(j)$ is the probability of cumulative rate step $j$ from previous contracts (0 if $j$ is not a valid step)
- $p_{\text{new}}(k)$ is the new probability of cumulative rate step $k$ after including this meeting

This formula linearly interpolates between the two nearest previous probability values, weighted by the fractional part $f$.

### Step 4: Probability Convolution For Cumulative Probabilities

When processing subsequent contracts, the new probabilities must be convolved with existing probabilities to account for the cumulative effect of multiple meetings. This creates conditional probabilities that respect the sequential nature of central bank decisions.

**Convolution formula:**

For each possible cumulative rate step $k$ after processing all contracts up to the current one:

$$p_{\text{total}}(k) = \sum_{j} p_{\text{prev}}(j) \times p_{\text{new}}(k - j)$$

Where:
- $p_{\text{total}}(k)$ is the probability of cumulative rate step $k$ after all contracts processed so far
- $p_{\text{prev}}(j)$ is the probability of cumulative rate step $j$ from previous contracts
- $p_{\text{new}}(k - j)$ is the probability that the new meeting results in rate step $(k - j)$
- The sum is over all $j$ such that the transition from $j$ to $k$ is valid

**Rigidity constraints:**

The convolution must respect the rigidity constraint from assumption **(4)**: central banks cannot reverse their policy direction. This means:
- If $j > 0$ (previous cumulative step is positive, indicating a hiking path), then $k - j \geq 0$ (cannot cut rates)
- If $j < 0$ (previous cumulative step is negative, indicating a cutting path), then $k - j \leq 0$ (cannot hike rates)
- If $j = 0$ (no previous change), then any transition is allowed

**Normalization:**

After convolution, the probabilities are normalized to ensure they sum to 1:

$$\sum_{k} p_{\text{total}}(k) = 1$$

**Iterative process:**

The convolution is applied iteratively for each contract:
1. Start with initial probabilities from the first contract
2. For each subsequent contract, convolve new meeting probabilities with current cumulative probabilities
3. Update cumulative probabilities: $p_{\text{prev}} \leftarrow p_{\text{total}}$
4. Repeat until all contracts are processed

**Final output:**

The final probability matrix contains, for each meeting date, the probability distribution over possible rate steps, where each probability represents the conditional probability given the outcomes of previous meetings.

---

## ECB and BOJ Probability Matrix Methodology

The methodology for ECB and BOJ follows a similar approach, as both use 3-month futures with multiple meetings per contract. The key difference is that these contracts can span multiple central bank meetings, requiring a more complex probability calculation.

### General Framework

The same Linear Interpolation approach is used for contracts containing only one single meeting, while $r_{implied}$ is inferred based on the appropriate pricing methodology given in the STIR Futures Contracts Pricing section above. For contracts containing more than one meeting however, we have to take a different approach. We calculate futures prices based on several different scenarios (restricted by our assumptions), which in turn provides us a price differential from the market price, used to assess the more likely scenario. We can then extract total probabilities based on the inferred joint probability distribution to convolve the final probability matrix.

### Step 1: Infer Single meeting implied rates

As opposed to FedFunds implied meeting rate calculation, we do not need $r_{end}$, we only need $r_{par}$ (given by $100 - P$) and $r_{start}$ which is the base rate, and is assumed to be constant based on assumption **(2)**. We have then:

$$r_{par} = \left[\prod_{i=1}^{d_0} \left(1 + r_{start} \times \frac{d_i}{100 \times D}\right) \times \prod_{i=d_0+1}^{T} \left(1 + r_{implied} \times \frac{d_i}{100 \times D}\right) \right ] - 1$$

Where $d_0$ is the number of days before the meeting, $T$ is the total accrual days, and $D$ is the Contract Day Count Convention (ACT/360 for ESTR Futures and 30/365 for TONA Futures). Solving for $r_{implied}$ using the above equation might not necessarily converge, and as such we approximate the futures pricing formula:

$$r_{\text{par}} = \left[\prod_{i=1}^{T} \left(1 + r_i \times \frac{1}{100 \times D}\right)\right] - 1$$

This gives a simpler formula to solve:

$$r_{par} = \left(1 + r_{start} \times \frac{1}{100 \times D}\right)^{d_0} \times \left(1 + r_{implied} \times \frac{1}{100 \times D}\right)^{d_1} - 1$$

Where we consider $d_i = 1$ in all cases including weekends. As per our assumption **(2)**, rates are assumed to be constant throughout the period except after a central bank meeting, and thus instead of compounding once for a 3-day period over the weekend, our model considers each day including weekend to be a fixing date compounded for 1 day.

**Caveat:** This approximation has the benefit of making it easier to solve for the implied rate when a meeting occurs, but comes with a cost: the error is negligible for rates below 4% (as it is in the order of $10^{-5}$, lower than 1 basis point), but can have higher magnitude above 4% being in the order of $10^{-4}$ (few basis points difference). The impact however should be minimal as the likelihood of having only one single meeting during a 3-month contract accrual period is low.

We can then solve for $r_{implied}$ using the above approximated function:

$$r_{implied} = \left(\left[\frac{r_{par} + 1}{\left(1 + r_{start} \times \frac{1}{100 \times D}\right)^{d_0}}\right]^{\frac{1}{d_1}} - 1\right) \times 100 \times D$$

Where $d_0$ is the number of days before the meeting and $d_1 = T - d_0$ is the number of days after the meeting.

### Step 2: Generate All Meeting Scenarios

For $n$ meetings, we generate all possible rate step combinations. Each meeting can have a rate change of $-\Delta$, $0$, or $+\Delta$ (where $\Delta = 25$ bps), subject to the rigidity constraint from assumption **(4)**.

The rate combinations include:
- All zeros: $(0, 0, \ldots, 0)$
- Single non-zero: All combinations with exactly one meeting having $-\Delta$ or $+\Delta$, rest are $0$
- All same direction: All combinations where all meetings have the same sign (all $-\Delta$ or all $+\Delta$)
- Adjacent pairs: Combinations where adjacent meetings have the same non-zero direction

For $n = 2$, the combinations are (in order):
$$(0, 0), (-\Delta, 0), (0, -\Delta), (+\Delta, 0), (0, +\Delta), (-\Delta, -\Delta), (+\Delta, +\Delta)$$

Note: The missing two combinations $(-\Delta, +\Delta)$ and $(+\Delta, -\Delta)$ are excluded as they violate rigidity constraints.

### Step 3: Calculate Scenario Prices

For each rate combination scenario $S = (s_1, s_2, \ldots, s_n)$ where $s_i \in \{-\Delta, 0, +\Delta\}$, using future prices formula and the constant rate assumption **(4)**, we calculate the corresponding futures price $P(S)$:

$$r_{\text{par}}(S) = \left[\prod_{i=0}^{n} \left(1 + r_i \times \frac{1}{100 \times D}\right)^{d_i}\right] - 1$$

Where:
- $D$ is the contract's Day Count Convention (360 for ESTR, 365 for TONA)
- $n$ is the number of meetings in the contract
- $r_0$ is the base rate (rate before the first meeting)
- $r_i$ is the rate after meeting $i$ (for $i = 1, 2, \ldots, n$), where $r_i = r_0 + s_i$ and $s_i$ is the rate step from scenario $S$
- $d_i$ is the number of accrual days in period $i$, where:
  - $d_0$: Days before the first meeting
  - $d_i$: Days between meeting $i-1$ and meeting $i$ (for $i = 1, 2, \ldots, n-1$)
  - $d_n$: Days after the last meeting
- The total accrual days $T = \sum_{i=0}^{n} d_i$

**Note**: We do not use any approximation formula to calculate scenario prices as we want to assess the real distance between scenario prices and market price.

This gives:

$$r_{\text{par, annualized}}(S) = r_{\text{par}}(S) \times 100 \times \frac{D}{T_{average}}$$

Note that due to each product day count convention, $T_{average} = 90$ for TONA Futures and  $T_{average} = T$ for ESTR Futures.

Finally:

$$P(S) = 100 - r_{\text{par, annualized}}(S)$$

### Step 4: Inverse Distance Weighting (Joint Probability Calculation)

We calculate the probability of each scenario using **inverse distance weighting** based on how close the scenario price is to the observed market price.

First, calculate the distance for each scenario:

$$d(S) = |P_{\text{market}} - P(S)|$$

Where $P_{\text{market}}$ is the observed market futures price.

However, we need to allocate the highest probability to the scenario with the closest price, e.g. $p(S)$ should be higher when $d(S)$ is smaller. As such, we need to calculate the reverse distance (inverse distance):

$$d_{\text{reverse}}(S) = \frac{1}{d(S) + \epsilon}$$

Where $\epsilon$ is a small constant (typically $10^{-10}$) to avoid division by zero.

Finally, normalize to get probabilities:

$$p(S) = \frac{d_{\text{reverse}}(S)}{\sum_{S'} d_{\text{reverse}}(S')}$$

This ensures that:
$$\sum_{S} p(S) = 1$$

**Intuition**: Scenarios with prices closer to the market price receive higher probabilities. The inverse distance weighting gives exponentially more weight to scenarios that are very close to the market price.

### Step 5: Aggregate Individual Meeting Probabilities (Marginalization)

The previous reverse distance probability calculation gave us $p(S_1 \cap S_2 \cap \ldots \cap S_n)$ - the joint probability of a complete scenario across all $n$ meetings in a contract. As such, using the **total probability theorem**, we can get the **marginal probability** - the probability that meeting $i$ results in rate step $s$, regardless of what happens at other meetings in the same contract.

For each meeting $i$ and each possible rate step $s \in \{-\Delta, 0, +\Delta\}$, we aggregate probabilities by summing over all scenarios where meeting $i$ has rate step $s$:

$$p_i(s) = \sum_{s_1, \ldots, s_{i-1}, s_{i+1}, \ldots, s_n} p(s_1, \ldots, s_{i-1}, s, s_{i+1}, \ldots, s_n)$$

Where the sum is over all possible combinations of rate steps for the other meetings.

For each meeting, the probabilities sum to 1:

$$\sum_{s \in \{-\Delta, 0, +\Delta\}} p_i(s) = 1$$

### Step 6: Convolution For Cumulative Probabilities

**Initial Contract Processing:**

For the first futures contract in the sequence, Steps 1-5 are applied:
- Step 1: Infer implied rates for single-meeting contracts (if applicable)
- Steps 2-5: For multi-meeting contracts, generate scenarios, calculate prices, apply inverse distance weighting, and marginalize to get individual meeting probabilities

The probabilities from the first contract become the baseline cumulative probabilities.

**Subsequent Contract Processing:**

For subsequent contracts, we first apply Steps 1-5 again to get the new meeting probabilities. Then, we use a **convolution** approach (similar to Fedfunds Futures) to combine these new probabilities with the cumulative probabilities from previous contracts.

**Convolution with Previous Probabilities**

The convolution combines the cumulative probability distribution from previous contracts with the new meeting probabilities.

For a contract with $n$ meetings, we process each meeting sequentially. Let $p_{\text{prev}}(j)$ be the probability of cumulative rate step $j$ from previous contracts.

**For the first meeting in the new contract ($i = 1$):**

$$p_{\text{after meeting 1}}(k) = \sum_{j} p_{\text{prev}}(j) \times p_{\text{new},1}(k - j)$$

Where:
- $k$ is the new cumulative rate step after meeting 1
- $j$ ranges over all valid previous cumulative steps
- $p_{\text{new},1}(k - j)$ is the probability that meeting 1 results in rate step $(k - j)$
- The sum is over all $j$ such that the transition is valid

**For subsequent meetings in the same contract ($i = 2, 3, \ldots, n$):**

$$p_{\text{after meeting i}}(k) = \sum_{j} p_{\text{after meeting i-1}}(j) \times p_{\text{new},i}(k - j)$$

This is applied iteratively for each meeting in the contract.

**Key constraint**: The transition must respect rigidity constraints. If the previous cumulative step is positive (hiking path), we cannot transition to a negative step (cutting path), and vice versa.

**Transition Step Limits**

For a contract with $n$ meetings, we consider transitions up to $\pm n \times \Delta$ for the cumulative effect. However, for each individual meeting $i$, we limit transitions to $\pm (i+1) \times \Delta$ to maintain computational efficiency while capturing the relevant probability mass.

The transition steps considered for meeting $i$ are:

$$\text{transitions}_i = \{t \times \Delta : t \in \{-i-1, -i, \ldots, -1, 0, 1, \ldots, i, i+1\}\}$$

But limited by the maximum number of meetings constraint.

**Final Probability Update**

After processing all meetings in the contract, the new cumulative probabilities become the baseline for the next contract:

$$p_{\text{prev}} \leftarrow p_{\text{after meeting n}}$$

**Extend Probability Support**

Note that the probability distribution may need to be extended to accommodate new possible rate levels. If the new contract can result in cumulative rate steps beyond the current support, we extend the probability matrix to include these new step values.

### Final Notes

**Probability Aggregation and Matrix Structure**

The final probability matrix is structured as:

- **Rows**: Each row corresponds to a possible rate step $s \in \{\ldots, -2\Delta, -\Delta, 0, +\Delta, +2\Delta, \ldots\}$
- **Columns**: Each column corresponds to a meeting date (in chronological order)
- **Values**: $p_i(s)$ - the probability (as a percentage) that meeting $i$ results in rate step $s$

**Normalization**

The probabilities for each meeting sum to 100%:

$$\sum_{s} p_i(s) = 1 \quad \forall i$$

This is ensured by:
1. Normalizing scenario probabilities in the inverse distance weighting
2. Proper marginalization when extracting individual meeting probabilities
3. Normalizing after convolution operations

**Dependencies Between Meetings**

**Important**: Probabilities across different meetings are **not independent**. They are conditional on the outcomes of previous meetings due to:

1. **Rigidity Constraint**: The policy path cannot reverse direction (assumption 4)
2. **Convolution Dependencies**: Each meeting's probabilities depend on the cumulative probabilities from previous contracts
3. **Joint Probability Structure**: The original scenario probabilities $p(S)$ represent joint probabilities, and marginalization preserves some of this dependency structure

However, when we extract individual meeting probabilities through marginalization, we are effectively assuming that within a contract, the meetings are conditionally independent given the contract structure. This is an approximation that simplifies the calculation.

---

## Caveats and Limitations

1. **Approximation Error**: The weekend approximation method introduces small errors, especially for rates above 4%. For precise calculations, the exact weekend-adjusted formula should be used.

2. **Rigidity Constraint**: The assumption that central banks cannot reverse their policy direction may not hold in all market conditions, especially during crisis periods.

3. **Single Meeting per Month**: The assumption of at most one meeting per month may be violated during emergency meetings or special circumstances.

4. **Step Size**: The fixed 25 bps step size may not capture all possible rate changes, especially for central banks that can move in different increments (e.g., 10 bps, 50 bps).

5. **Multiple Meetings per Contract**: When a contract spans multiple meetings, the probabilities calculated represent joint probabilities. Individual meeting probabilities are extracted by marginalization, which assumes independence conditional on the contract structure.

6. **Base Rate Fallback**: If the current target rate is not available, the system falls back to the last known non-null price before the target date. This may introduce slight inaccuracies if market conditions have changed significantly.
___
