# Calculation Methodology

Formulas used for sector analysis and economic-indicator display transforms.
Probability-matrix futures math lives separately in [`PROBABILITY_MATRIX_METHODOLOGY.md`](PROBABILITY_MATRIX_METHODOLOGY.md). Indicator catalog / units live in [`ECONOMIC_INDICATORS.md`](ECONOMIC_INDICATORS.md).

Code references:

- Sector day aggregates (ingest): `market_overview/services/sector_analysis.py`
- Single-name weights (scrapers): `market_overview/services/scrapers/weights/`
- Sector page payload (UI): `data_visualization/services/sector_analysis.py`
- Generic series helpers: `core/services/time_series_calculation.py`
- Indicator mode maps: `data_visualization/services/time_series.py`
- Rel / Contr (charts): `data_visualization/services/economic_charts/indicator_breakdown.py`
- Rel / Contr (recap UI): `data_visualization/static/data_visualization/js/economic_recap.js`

---

## 1. As-of date (shared convention)

Many pages expose a single **as-of** (or section) date at the top. That date is always the **end** of any trailing or YTD window — never the start.

Choosing a past as-of rewinds the whole view to that moment: day pies, contributions, best/worst ranks, and history charts all use data through that end date. Sector history lookback is `SECTOR_ANALYSIS_HISTORY_CALENDAR_DAYS` (400) so YTD windows remain available late in the year.

| Symbol | Meaning |
| --- | --- |
| \(T\) | As-of / section end date (trading day when equity data is used) |
| \(P_t\) | Price (or index level) at the close of trading day \(t\) |
| \(r_t\) | Simple daily return in **percent** for day \(t\): \(r_t = (P_t / P_{t-1} - 1) \times 100\) |

---

## 2. Sector analysis

### 2.1 Single-name day inputs

| Symbol | Meaning |
| --- | --- |
| \(i\) | One equity (ticker) in the index |
| \(P_{i,t}\) | Close price of name \(i\) on trading day \(t\) |
| \(r_{i,T}\) | Simple day return of name \(i\) on as-of day \(T\), in **percent** |
| \(w_i\) | Name \(i\)’s **share of the equity index**, stored in **percent** (sum ≈ 100 across the index). Scraped once per ingest window and reused for every day in that window |
| \(c_i\) | Name \(i\)’s **contribution** to the index day move, in percentage points (pp) |

#### Where \(w_i\) comes from

We do **not** derive weights from prices or free-float market caps in this repo. Each ingest scrapes a published **percent weight** per ticker from a source that already tracks that index (or a close ETF proxy), maps symbols onto our Yahoo catalog tickers, and joins those weights to the single-name catalog. Missing catalog tickers are reported; weights are **not** renormalized to force a sum of 100.

| Equity index | Source | What we read as \(w_i\) | Code |
| --- | --- | --- | --- |
| **S&P 500 (SPX)** | iShares **IVV** latest-holdings CSV | Equity rows’ `Market Weight` (percent of the fund) | `market_overview/services/scrapers/weights/ivv.py` |
| **CAC 40** | whichindex CAC 40 constituents page | Constituent weight column (percent of the index proxy) | `market_overview/services/scrapers/weights/cac.py` |
| **Nikkei 225** | Official Nikkei weight CSV | `Weight` cell (e.g. `1.5067%` → `1.5067`) | `market_overview/services/scrapers/weights/nikkei.py` |

For a multi-day ingest window, weights are scraped **once** and reused on every trading day in that window (returns still vary by day).

For each ticker on day \(T\):

\[
r_{i,T} = \Big(\frac{P_{i,T}}{P_{i,T-1}} - 1\Big) \times 100
\]

| Quantity | Formula | Unit | Meaning |
| --- | --- | --- | --- |
| Name share | \(w_i\) (scraped; see table above) | % of index | Slice of the benchmark that name represents |
| Name contribution | \(c_i = (w_i / 100) \cdot r_{i,T}\) | percentage points (pp) of index | How many pp that name adds to the index day move |

Identity linking share, return, and contribution:

\[
c_i = \underbrace{\frac{w_i}{100}}_{\text{share as a fraction}} \times r_{i,T}
\qquad\Longleftrightarrow\qquad
r_{i,T} = \frac{c_i}{w_i / 100}\quad(w_i \neq 0)
\]

So a 2% weight name up 5% contributes \(0.02 \times 5 = 0.10\) pp to the index.

### 2.2 Subsector day aggregates

For names \(i\) in one (sector, subsector) bucket:

| Symbol | Meaning |
| --- | --- |
| \(W\) | Subsector share of the index (%) — sum of member weights |
| \(R\) | Share-weighted average day return of the subsector (%) |
| \(C\) | Subsector contribution to the index day move (pp) |

\[
W = \sum_i w_i
\]

\[
R = \frac{\sum_i w_i \, r_{i,T}}{W}
\]

\[
C = \sum_i c_i = \sum_i \frac{w_i}{100} \, r_{i,T}
\]

Also \(C = (W / 100) \cdot R\) when \(W > 0\) (same algebra as the name-level identity).

**Top 3 equities** inside a subsector: largest \(|c_i|\) (contribution magnitude), not largest \(|r_{i,T}|\) and not largest \(w_i\).

### 2.3 Sector day aggregates

Roll up stored subsector aggregates the same way (share-weighted return; contributions add). Here \(s\) indexes subsectors inside one sector:

\[
W_{\text{sector}} = \sum_s W_s,
\quad
R_{\text{sector}} = \frac{\sum_s W_s R_s}{W_{\text{sector}}},
\quad
C_{\text{sector}} = \sum_s C_s
\]

Pies use **share** \(W\) / \(W_{\text{sector}}\) for slice size and color from **daily return** \(R\). Tooltips also show contribution \(C\). Line / history points store \(R_{\text{sector}}\) per date.

### 2.4 Holding-period return (Best / Worst performers)

Best / Worst are ranked on **pure return** over a window — **not** contribution-weighted.

| Symbol | Meaning |
| --- | --- |
| \(t_0\) | Window **start** trading day (see table below) |
| \(T\) | Window **end** (page as-of date) |
| \(P_t\) | Sector (or name) close / level on day \(t\) |
| \(r_t\) | Stored simple daily return in percent on day \(t\) |
| \(R_{[t_0, T]}\) | Holding-period return from after \(t_0\) through \(T\), in percent |
| \(I_t\) | Rebased history index level on day \(t\) (\(I_{t_0} = 100\)) |

Definition (price form):

\[
R_{[t_0, T]} = \Big(\frac{P_T}{P_{t_0}} - 1\Big) \times 100
\]

Equivalent form from stored daily percent returns \(r_t\) on trading days **after** \(t_0\) through \(T\):

\[
R_{[t_0, T]} = \Bigg(\prod_{t \in (t_0, T]} \Big(1 + \frac{r_t}{100}\Big) - 1\Bigg) \times 100
\]

Missing \(r_t\) for a sector on a day → skip that day in that sector’s product only (do not treat as 0).

#### Window start \(t_0\) (end is always \(T\))

Week / Month are **trailing**, not WTD / MTD.

| Toggle | \(t_0\) | Notes |
| --- | --- | --- |
| **Week** | Last trading day on or before \(T - 7\) calendar days | Trailing ~1 week |
| **Month** | Last trading day on or before \(T - 1\) calendar month (`relativedelta(months=-1)`) | Trailing ~1 month; equivalent to \(P_T / P_{T-1\text{ month}} - 1\) |
| **YTD** | Last trading day of the **previous calendar year** (or first available trading day of the current year if that close is missing) | Calendar year-to-date through \(T\) |

**Best 3** = highest \(R_{[t_0,T]}\). **Worst 3** = lowest \(R_{[t_0,T]}\). The merged bar chart shows Best (highest at top) then Worst (best-of-worst at top of that block, worst-of-worst at the bottom).

Week / Month / YTD / **Period** controls are **independent per bottom card** (default **YTD**). Period uses a picked start date as \(t_0\) (end remains the page as-of). The performers history chart and the historical multi-select chart both rebase to an **index of 100 at \(t_0\)**, then compound each later daily return:

\[
I_{t_0} = 100,
\qquad
I_t = 100 \times \prod_{u \in (t_0, t]} \Big(1 + \tfrac{r_u}{100}\Big)
\]

Changing the section as-of date moves \(T\); Week / Month / YTD recompute from that new end point. The page payload is Redis-cached (versioned by stored move / earnings state).

---

## 3. Economic indicators — stored levels

Published values are stored as **raw levels** (amounts, indexes, rates, …). Display modes are transforms of those levels. Flow vs stock and SAAR vs period-level conventions are documented in [`ECONOMIC_INDICATORS.md`](ECONOMIC_INDICATORS.md).

| Symbol | Meaning |
| --- | --- |
| \(x_t\) | Stored published level of the indicator at period \(t\) (the raw amount, index, or rate) |
| \(x_{t-k}\) | Same series’ level at the **exact** calendar period \(k\) months earlier (`period - relativedelta(months=k)`) |
| \(k\) | Lookback in **calendar months** between the two periods being compared |
| \(\rho\) | Annualization exponent (`annualized_ratio` in code). For quarterly SAAR-style change, \(\rho = 4\) |

Gaps are not bridged by “previous available observation”: if \(x_{t-k}\) is missing, that change point is dropped.

Generic change helper (`calculate_value_change`):

| Type | Formula | What it measures |
| --- | --- | --- |
| Absolute | \(x_t - x_{t-k}\) | Level difference in the same unit as \(x\) |
| Percent | \((x_t / x_{t-k} - 1) \times 100\) | Percent change of the level |
| BPS | \((x_t - x_{t-k}) \times 100\) | Basis points; used when \(x\) is already a percent rate |
| Annualized percent | \(\big((x_t / x_{t-k})^{\rho} - 1\big) \times 100\) | Compounded change scaled to an annual rate |

---

## 4. Economic indicators — period-over-period modes

Each mode picks \(k\) (and optionally \(\rho\)) and applies the matching change type from §3 to the stored levels \(x\).

| Mode | Lookback \(k\) (months) | Metric |
| --- | --- | --- |
| **Raw** | — | The stored level itself: \(x_t\) |
| **MoM** | 1 | Percent change vs the prior month |
| **QoQ** | 3 | Percent change vs the period 3 months earlier |
| **QoQy** | 3 | Annualized percent with \(\rho = 4\) (quarterly SAAR-style) |
| **YoY** | 12 | Percent change vs the same calendar month / quarter one year earlier |

Annual-frequency series treat QoQ / QoQy like YoY (\(k = 12\)).

---

## 5. Economic indicators — YTD modes

### 5.1 YTD ladder (cumulative sum)

For flow-style series, build a **running calendar year-to-date sum** \(S_t\): the sum of period levels from the start of the calendar year through period \(t\).

| Symbol | Meaning |
| --- | --- |
| \(x_{\tau}\) | Stored (or period-amount) level at each ladder step \(\tau\) in the year |
| \(S_t\) | YTD cumulative sum through period \(t\): \(S_t = \sum_{\tau \in \text{year through } t} x_{\tau}\) |
| \(S_{y,m}\) | Same idea labeled by calendar year \(y\) and month stamp \(m\) (e.g. \(S_{2026,11}\) = Jan–Nov 2026 cumulative) |

Step size depends on publication frequency:

| Frequency | Step (months) | Expected months in year |
| --- | --- | --- |
| Monthly | 1 | Jan, Feb, … |
| Quarterly | 3 | Jan, Apr, Jul, Oct |
| Annual | 12 | Jan only |

Rules:

- Sum starts at period 1 of each calendar year and must stay **contiguous**.
- A missing / out-of-order period **stops** that year (later months are not added).
- Each point keeps its own period date; the value is the cumulative sum through that period.

SAAR / annualized quarterly levels are converted to **period amounts** (÷4) before YTD summing when the mode needs period flows.

### 5.2 YTD display modes

| Mode | Math |
| --- | --- |
| **YTDRaw** | The YTD cumulative level itself: \(S_t\) |
| **YTDYoY** | Percent change of this year’s YTD sum vs the same YTD stamp one year earlier: \((S_{y,m} / S_{y-1,m} - 1) \times 100\) |
| **YTDvsGDP** | \(S^{\text{outstanding}}_t / S^{\text{GDP}}_t \times 100\) after unit alignment; SAAR legs converted to period amounts before summing |

---

## 6. Economic indicators — vsGDP

| Symbol | Meaning |
| --- | --- |
| \(\text{outstanding}_t\) | Level of the series being compared to GDP at period \(t\) (after K/M/B alignment and any annualization scaling below) |
| \(\text{GDP}_t\) | Matching GDP level at the same period \(t\) (same unit alignment / scaling rules) |

\[
\text{vsGDP}_t = \frac{\text{outstanding}_t}{\text{GDP}_t} \times 100
\]

After aligning K/M/B magnitudes. Annualization:

| Outstanding | GDP | Scaling |
| --- | --- | --- |
| Stock | Period-level quarterly GDP | ×4 GDP |
| Stock | SAAR / annualized GDP | No ×4 |
| Flow, period level | SAAR GDP | ×4 flow |
| Flow, SAAR or annual | SAAR / annualized GDP | No ×4 |
| Flow, SAAR or annual | Period-level quarterly GDP | ×4 GDP |

Annual-frequency **flows** use a calendar-year GDP denominator: **sum** of quarters for period-level GDP; **mean** of quarterly SAAR for SAAR GDP. Stocks are never ×4’d.

---

## 7. Economic indicators — Share (Rel) / Contribution (Contr)

Used when a **child** series sits under a **parent** (e.g. Real GDP components, expenditure shares). Amount magnitudes (K / M / B) are aligned before dividing. Periods with missing child, missing parent, or parent level \(0\) are skipped.

| Symbol | Meaning |
| --- | --- |
| \(x^{\text{child}}_t\) | Child series level at period \(t\) (component / subcategory) |
| \(x^{\text{parent}}_t\) | Parent series level at period \(t\) (aggregate the child belongs to) |
| \(k\) | Lookback in calendar months (same convention as §3–§4) |

### 7.1 Share — Rel modes

Share answers: *what fraction of the parent is this child at time \(t\)?*

\[
\text{Share}_t = \frac{x^{\text{child}}_t}{x^{\text{parent}}_t} \times 100
\]

| Property | Detail |
| --- | --- |
| Unit | Percent of parent (not pp of growth) |
| Modes | Rel QoQ, Rel YoY, YTDRelQoQ, YTDRelYoY |
| Level math | Always the same ratio above — QoQ / YoY only pick the calendar lookback used when the UI shows Current vs Previous share |
| Composition pies | Same share formula on overlapping periods (charts); annual pies keep January-stamped year totals only |

Lookback \(k\) for Current / Previous share comparison:

| Variant | \(k\) (months) |
| --- | --- |
| QoQ | 3 (annual-frequency series: treat like YoY, \(k = 12\)) |
| YoY | 12 |

### 7.2 Contribution — Contr modes

Contribution answers: *how many percentage points of the parent’s prior level does the child’s change over the lookback explain?*

\[
\text{Contr}_t = \frac{x^{\text{child}}_t - x^{\text{child}}_{t-k}}{\lvert x^{\text{parent}}_{t-k}\rvert} \times 100
\]

| Property | Detail |
| --- | --- |
| Unit | Percentage points (pp) of the prior parent level |
| Modes | Contr QoQ, Contr YoY, YTDContrQoQ, YTDContrYoY |
| Lookback \(k\) | Same table as Rel (3 for QoQ, 12 for YoY) |
| Requires | Both child and parent observed at \(t\) **and** at \(t-k\) |

Economic Charts Rel/Contr line transforms use the signed prior parent in the denominator when nonzero; Economic Recap uses \(\lvert x^{\text{parent}}_{t-k}\rvert\) so a negative parent level (e.g. some net-export windows) does not flip the contribution sign spuriously.

### 7.3 YTD Rel / Contr

For YTDRel* / YTDContr*:

1. Convert SAAR / annualized quarterly **flows** to period amounts when needed.
2. Build a **calendar YTD cumulative sum** \(S^{\text{child}}\) and \(S^{\text{parent}}\) (same ladder rules as §5).
3. Apply the Share or Contr formula with \(x^{\text{child}} \leftarrow S^{\text{child}}\) and \(x^{\text{parent}} \leftarrow S^{\text{parent}}\) (Contr still uses lookback \(k\) on those YTD series).

### 7.4 Worked mini-example

Parent GDP \(x^{\text{parent}} = 100\), child GFCF \(x^{\text{child}} = 20\) → Share \(= 20\%\).

One quarter later: \(x^{\text{child}}_t = 22\), \(x^{\text{parent}}_{t-k} = 100\), \(k = 3\):

\[
\text{Contr} = \frac{22 - 20}{100} \times 100 = 2\text{ pp}
\]

---

## 8. Market chart period windows (equities / rates UI)

Separate from sector Best/Worst toggles. Chart range chips typically mean:

| Chip | Window end | Window start (approx.) |
| --- | --- | --- |
| 1W / 1M / … | Selected as-of | Trailing calendar lookback |
| YTD | Selected as-of | Start of that calendar year |

Same rule: the UI date is the **end** of the plotted window.

---

## 9. Worked examples

### Sector share and contribution (one day)

One name with index share \(w_i = 4\%\) and day return \(r_{i,T} = +2.5\%\):

\[
c_i = \frac{4}{100} \times 2.5 = 0.10\text{ pp of the index}
\]

Two names in a subsector with \((w_i, r_{i,T}) = (4\%,+2.5\%)\) and \((6\%,-1\%)\):

\[
W = 10\%,\quad
R = \frac{4\cdot 2.5 + 6\cdot(-1)}{10} = 0.4\%,\quad
C = 0.10 + (-0.06) = 0.04\text{ pp}
\]

### Sector Month return

As-of \(T =\) 2026-03-20. Month window start \(t_0 =\) last trading day on/before 2026-02-20.

If closes are \(P_{t_0} = 100\), \(P_T = 104\):

\[
R_{[t_0,T]} = (104 / 100 - 1) \times 100 = 4\%
\]

If daily percent returns \(r_t\) between those closes compound to the same path, the product formula yields \(4\%\) as well.

### Indicator YTDYoY (monthly)

\(S_{2026,11}\) = Jan–Nov 2026 YTD cumulative sum of monthly levels \(x\); \(S_{2025,11}\) = Jan–Nov 2025 YTD cumulative sum:

\[
\text{YTDYoY} = \Big(\frac{S_{2026,11}}{S_{2025,11}} - 1\Big) \times 100
\]
