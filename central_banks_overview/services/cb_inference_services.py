import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional, TypedDict

import numpy as np
import pandas as pd

import central_banks_overview.services.cb_meetings_services as cb_meetings_services
import central_banks_overview.services.stir_prices_ingestion_services as stir_prices_services
from central_banks_overview.models import CentralBankChoices, StirFuturesModel
from core.services import logger
from market_overview.models import MarketPriceModel

# Step size for probability calculations
STEP_SIZE = 25
MAX_MEETINGS = 3
STANDARD_STEP_SCENARIOS = [
    i * STEP_SIZE for i in range(-MAX_MEETINGS, MAX_MEETINGS + 1)
]


# Number of steps to extend probability support in each direction
PROBABILITY_EXTENSION_STEPS = 5
# Threshold for probability removal
PROBABILITY_THRESHOLD = 1.0
# Number of meetings to cover with futures contracts
MAX_MEETINGS_TO_COVER = 8


@dataclass(frozen=True)
class FuturesCalculationConfig:
    """Configuration for futures calculation parameters."""

    days_per_year: int
    futures_days_compounding_convention: Optional[int] = (
        None  # None means use contract_days
    )


CENTRAL_BANK_TARGET_RATE_MAP = {
    CentralBankChoices.FRB: "EFFR",
    CentralBankChoices.ECB: "ESTR",
    CentralBankChoices.BOJ: "MUTAN",
}


class RateChangePerStep(TypedDict):
    """Rate change per step."""

    nb_steps: int
    proportion: float
    sign: float


class MeetingsByFutures(TypedDict):
    """Meetings information for a futures contract."""

    accrual_start_date: date
    accrual_end_date: date
    accrual_days: int
    futures_price: float
    futures_implied_rate: float
    nb_meetings: int
    meeting_dates: List[date]


class AccrualDaysInformation(TypedDict):
    """Accrual days information for a date range."""

    nb_weekdays: int
    accrual_days_over_weekend: List[int]


class ProbabilitiesByStep(TypedDict):
    """Probabilities for a step."""

    expected_rate_step: int
    probabilities: List[float]


class CentralBankProbabilityMatrix(TypedDict):
    """Central bank probability matrix."""

    central_bank: CentralBankChoices
    meeting_dates: List[date]
    probability_matrix: List[ProbabilitiesByStep]


class MeetingTotalProbabilityByStep(TypedDict):
    """Total probabilities for each step for a given meeting."""

    step: int
    meeting_i: int
    probability: float


class FedFuturesRateType(str, Enum):
    """Type of rate to calculate for Fed Funds Futures."""

    START = "START"
    END = "END"


class FedMeetingRateInfo(TypedDict):
    """Meeting rate information for Fed Funds Futures."""

    meeting_date: date
    start_rate: Optional[float]
    end_rate: Optional[float]
    rate_diff: Optional[float]


class ProbabilityMatrixBaseService(ABC):
    """Base service for probability matrix calculation."""

    def __init__(
        self,
        initial_base_rate: float,
        future_prices: List[StirFuturesModel],
        meeting_dates: List[datetime],
        remove_na: bool = True,
    ):
        self.initial_base_rate = initial_base_rate
        self.future_prices = future_prices
        self.meeting_dates = meeting_dates
        self.meetings_by_futures = (
            self._merge_future_prices_information_with_meeting_dates(remove_na)
        )
        self.meetings_in_period = self._get_meetings_in_period()
        self.probability_matrix: List[ProbabilitiesByStep] = [
            ProbabilitiesByStep(
                expected_rate_step=step_key,
                probabilities=[],
            )
            for step_key in STANDARD_STEP_SCENARIOS
        ]

    def _merge_future_prices_information_with_meeting_dates(
        self, remove_na: bool
    ) -> List[MeetingsByFutures]:
        """Merge future prices dataframe with meeting dates information."""
        meetings_by_futures: List[MeetingsByFutures] = []

        for future_price in self.future_prices:
            period_start = future_price.first_accrual_date
            period_end = future_price.last_accrual_date

            meetings_in_period = [
                meeting_date.date()
                for meeting_date in self.meeting_dates
                if period_start <= meeting_date.date() < period_end
            ]
            if len(meetings_in_period) > MAX_MEETINGS:
                logger.error(
                    f"Meetings in period {period_start} to {period_end}: {meetings_in_period}"
                )
                raise ValueError(
                    f"Too many meetings ({len(meetings_in_period)}) within period "
                    f"{period_start} to {period_end}"
                )

            if (remove_na and len(meetings_in_period) != 0) or not remove_na:
                meetings_by_futures.append(
                    MeetingsByFutures(
                        accrual_start_date=period_start,
                        accrual_end_date=period_end,
                        accrual_days=(period_end - period_start).days + 1,
                        futures_price=future_price.price,
                        futures_implied_rate=round(100 - future_price.price, 8),
                        nb_meetings=len(meetings_in_period),
                        meeting_dates=sorted(meetings_in_period),
                    )
                )

        return meetings_by_futures

    def _get_meetings_in_period(self) -> List[date]:
        """Get meetings in period."""
        all_meeting_dates: set[date] = set()
        for meeting_by_future in self.meetings_by_futures:
            meeting_dates = meeting_by_future.get("meeting_dates")
            all_meeting_dates.update(meeting_dates)

        return sorted(all_meeting_dates)

    def _extend_probability_support(self):
        """Extend meeting probabilities with additional steps if needed."""
        if not self.probability_matrix:
            return

        current_length = len(self.probability_matrix[0]["probabilities"])
        existing_steps = {mp["expected_rate_step"] for mp in self.probability_matrix}
        previous_min = min(existing_steps)
        previous_max = max(existing_steps)

        # Generate extended keys: extend support in both directions
        extended_keys = [
            *[
                previous_min - i * STEP_SIZE
                for i in range(1, PROBABILITY_EXTENSION_STEPS + 1)
            ],
            *[
                previous_max + i * STEP_SIZE
                for i in range(1, PROBABILITY_EXTENSION_STEPS + 1)
            ],
        ]
        # Add new steps if they don't exist
        for key in extended_keys:
            if key not in existing_steps:
                self.probability_matrix.append(
                    ProbabilitiesByStep(
                        expected_rate_step=key,
                        probabilities=[0.0] * current_length,
                    )
                )

    def _format_probabilities(self):
        """Convert probabilities to percentages, round, and remove low entries."""
        # Convert to percentages and round
        for meeting_probability in self.probability_matrix:
            meeting_probability["probabilities"] = [
                round(prob * 100, 2) for prob in meeting_probability["probabilities"]
            ]

        # Filter out entries where sum of probabilities is below threshold
        self.probability_matrix = [
            meeting_probability
            for meeting_probability in self.probability_matrix
            if sum(meeting_probability["probabilities"]) >= PROBABILITY_THRESHOLD
        ]

    def _calculate_rate_change_per_step(
        self, rate_change_bps: float
    ) -> RateChangePerStep:
        """Calculate number of steps and proportion of rate change."""
        meeting_steps = rate_change_bps / STEP_SIZE
        fractional, integer = math.modf(meeting_steps)
        return RateChangePerStep(
            nb_steps=int(integer),
            proportion=abs(fractional),
            sign=math.copysign(1, meeting_steps),
        )

    def _get_last_probability_index(self) -> int:
        """Get the index of the last probability entry."""
        if not self.probability_matrix:
            return -1
        return len(self.probability_matrix[0]["probabilities"]) - 1

    def _get_probability_value(
        self,
        step_key: int,
        prob_idx: int,
        default: float = 0.0,
    ) -> float:
        """Safely get probability value for a given step key."""
        meeting_probability = next(
            (
                mp
                for mp in self.probability_matrix
                if mp["expected_rate_step"] == step_key
            ),
            None,
        )
        if meeting_probability and prob_idx < len(meeting_probability["probabilities"]):
            return meeting_probability["probabilities"][prob_idx]
        return default

    def _apply_linear_interpolation(
        self,
        rate_change_bps: float,
        is_initial: bool = False,
        apply_convolution: bool = True,
    ):
        """Apply linear interpolation for probability calculation.

        Args:
            rate_change_bps: Rate change in basis points
            is_initial: Whether this is the first meeting
            apply_convolution: Whether to apply convolution with previous probabilities.
                If False and is_initial=False, probabilities are added directly
                without convolution (useful for debugging).
        """
        rate_change_per_step = self._calculate_rate_change_per_step(rate_change_bps)
        nb_steps = rate_change_per_step["nb_steps"]
        proportion = rate_change_per_step["proportion"]
        sign = rate_change_per_step["sign"]
        if is_initial:
            step_up = int((nb_steps + sign) * STEP_SIZE)
            step_current = int(nb_steps * STEP_SIZE)

            for meeting_probability in self.probability_matrix:
                step_key = meeting_probability["expected_rate_step"]
                if step_key == step_up:
                    meeting_probability["probabilities"].append(proportion)
                elif step_key == step_current:
                    meeting_probability["probabilities"].append(1 - proportion)
                else:
                    meeting_probability["probabilities"].append(0.0)
        else:
            if apply_convolution:
                # Apply convolution with previous probabilities
                self._extend_probability_support()
                last_prob_idx = self._get_last_probability_index()

                for meeting_probability in self.probability_matrix:
                    step_key = meeting_probability["expected_rate_step"]

                    prev_step_key = step_key - nb_steps * STEP_SIZE
                    next_step_key = step_key - int((nb_steps + sign) * STEP_SIZE)

                    prev_prob = self._get_probability_value(
                        prev_step_key, last_prob_idx
                    )
                    next_prob = self._get_probability_value(
                        next_step_key, last_prob_idx
                    )

                    p_x = (1 - proportion) * prev_prob + proportion * next_prob
                    meeting_probability["probabilities"].append(p_x)
            else:
                # Add probabilities directly without convolution (for debugging)
                step_current = int(nb_steps * STEP_SIZE)
                step_up = int((nb_steps + sign) * STEP_SIZE)

                for meeting_probability in self.probability_matrix:
                    step_key = meeting_probability["expected_rate_step"]
                    if step_key == step_up:
                        meeting_probability["probabilities"].append(proportion)
                    elif step_key == step_current:
                        meeting_probability["probabilities"].append(1 - proportion)
                    else:
                        meeting_probability["probabilities"].append(0.0)

    @abstractmethod
    def generate_probability_matrix(self, apply_convolution: bool = True):
        """Generate probability matrix for the futures contracts.

        Args:
            apply_convolution: If True, applies convolution with previous probabilities
                              for subsequent meetings. If False, probabilities are added
                              directly without convolution (useful for debugging).
        """
        pass


class ThreeMonthFuturesProbabilityMatrixService(ProbabilityMatrixBaseService):
    """Service for probability matrix calculation for Three Month Futures."""

    def __init__(
        self,
        initial_base_rate: float,
        future_prices: List[StirFuturesModel],
        meeting_dates: List[datetime],
        config: FuturesCalculationConfig,
    ):
        super().__init__(initial_base_rate, future_prices, meeting_dates)
        self.config = config

    # __________________________________________________________
    # 1. IMPLIED RATE / PRICE CALCULATION
    # __________________________________________________________

    def _get_accrual_days_information(
        self, start_date: date, end_date: date
    ) -> AccrualDaysInformation:
        """Get the accrual days information for a date range.

        Counting the number of weekdays that are NOT Friday (Monday-Thursday),
        and the number of weekend sequences (Friday-Sunday) sequences.
        This returns a list instead of an integer, as the first (or the last) day of the
        period may be a day within the weekend sequence, changing the accrual days count.
        """
        num_days = (end_date - start_date).days + 1
        dates = np.arange(num_days, dtype="timedelta64[D]") + np.datetime64(start_date)

        weekdays_vector = dates.astype("datetime64[D]").astype(
            "datetime64[W]"
        ) - dates.astype("datetime64[D]")
        weekdays_vector = weekdays_vector.astype(int)

        weekday_mask = weekdays_vector < 4
        nb_weekdays = int(np.sum(weekday_mask))

        # Find weekend blocks: transitions from weekday to weekend and vice versa
        weekend_mask = ~weekday_mask

        # Find transitions: True where there's a change from previous to current
        # Weekend starts: transition from weekday (False) to weekend (True)
        # Weekend ends: transition from weekend (True) to weekday (False)
        diff_mask = np.diff(weekend_mask.astype(int))
        weekend_starts = (
            np.where(diff_mask == 1)[0] + 1
        )  # +1 because diff is one element shorter
        weekend_ends = np.where(diff_mask == -1)[0] + 1

        # Handle edge cases: period starts/ends in weekend
        if weekend_mask[0]:
            weekend_starts = np.insert(weekend_starts, 0, 0)
        if weekend_mask[-1]:
            weekend_ends = np.append(weekend_ends, num_days)

        # Calculate length of each weekend block
        if len(weekend_starts) == len(weekend_ends):
            accrual_days_over_weekend = (weekend_ends - weekend_starts).tolist()
        else:
            # This shouldn't happen, but handle gracefully
            accrual_days_over_weekend = []

        # Validation: ensure the total number of days is correct
        assert (
            nb_weekdays + sum(accrual_days_over_weekend) == num_days
        ), f"Accrual mismatch for {start_date} to {end_date}: weekdays={nb_weekdays}, weekend={sum(accrual_days_over_weekend)}, total={num_days}"

        return AccrualDaysInformation(
            nb_weekdays=nb_weekdays,
            accrual_days_over_weekend=accrual_days_over_weekend,
        )

    def _calculate_three_month_futures_average_rate_for_single_meeting(
        self,
        future_settlement_date: date,
        contract_days: int,
        meeting_date: date,
        future_rate: float,
        base_rate: float,
    ) -> float:
        """Calculate the average rate for a given Three Month Futures.

        This calculation assumes that the base rate stays constant until meeting date,
        and the meeting rate stays constant until future end date.
        """
        days_after_meeting = (future_settlement_date - meeting_date).days
        days_before_meeting = contract_days - days_after_meeting

        if days_after_meeting <= 0:
            raise ValueError("Meeting date must be before settlement date")

        daily_rate_factor = 1 + (base_rate / 100) / self.config.days_per_year
        discounted_base_rate = daily_rate_factor ** (-days_before_meeting)

        future_rate_factor = 1 + (contract_days / self.config.days_per_year) * (
            future_rate / 100
        )
        compound_factor = (future_rate_factor * discounted_base_rate) ** (
            1 / days_after_meeting
        )

        return round((compound_factor - 1) * self.config.days_per_year * 100, 8)

    def _calculate_three_month_futures_price(
        self,
        base_rate: float,
        rates: List[float],
        meeting_dates: List[date],
        accrual_start_date: date,
        accrual_end_date: date,
        accrual_days: int,
    ) -> float:
        """Calculate the price for a given Three Month Futures."""
        if len(rates) < 1 or len(meeting_dates) < 1:
            raise ValueError(
                "At least one rate is required and one meeting date is required"
            )
        if len(rates) != len(meeting_dates):
            raise ValueError("Rates and meeting dates must have the same length")

        start_periods = [accrual_start_date] + meeting_dates
        end_periods = meeting_dates + [accrual_end_date]
        rates = [base_rate] + rates

        daily_rate_factor = 1 / (100 * self.config.days_per_year)
        compounded_rate = 1.0
        for rate, start_period, end_period in zip(rates, start_periods, end_periods):
            accrual_days_information = self._get_accrual_days_information(
                start_period, end_period
            )
            nb_weekdays = accrual_days_information["nb_weekdays"]
            accrual_days_over_weekend = accrual_days_information[
                "accrual_days_over_weekend"
            ]
            compounded_rate *= (1 + rate * 1 * daily_rate_factor) ** nb_weekdays

            for accrual_days in accrual_days_over_weekend:
                compounded_rate *= 1 + rate * accrual_days * daily_rate_factor

        par_rate = compounded_rate - 1
        average_days = (
            self.config.futures_days_compounding_convention
            if self.config.futures_days_compounding_convention is not None
            else accrual_days
        )
        annualized_par_rate = par_rate * 100 * self.config.days_per_year / average_days

        return round(100 - annualized_par_rate, 8)

    # __________________________________________________________
    # 2. ONE PERIOD PROBABILITY CALCULATION
    # __________________________________________________________

    def _generate_rate_combinations(self, n_meetings: int) -> List[tuple]:
        """Generate rate step combinations for n meetings.

        The rate combination rules are:
        - All same direction (both -STEP_SIZE or both STEP_SIZE)
        - Single non-zero at first position
        - Single non-zero at second position
        - All zeros
        - Single non-zero at second position (positive)
        - Single non-zero at first position (positive)
        - All same direction (both positive)

        For n=2: 7 combinations in specific order
        For n=3: Extended pattern maintaining consistency
        """
        if n_meetings < 1:
            return []

        combinations = []
        # 1. All same direction (negative)
        combinations.append(tuple([-STEP_SIZE] * n_meetings))

        # 2. Single non-zero at each position (negative first, then positive)
        for i in range(n_meetings):
            # Negative step
            combo = [0] * n_meetings
            combo[i] = -STEP_SIZE
            combinations.append(tuple(combo))

        # 3. All zeros
        combinations.append(tuple([0] * n_meetings))

        # 4. Single non-zero at each position (positive)
        for i in range(n_meetings):
            # Positive step
            combo = [0] * n_meetings
            combo[i] = STEP_SIZE
            combinations.append(tuple(combo))

        # 5. All same direction (positive)
        combinations.append(tuple([STEP_SIZE] * n_meetings))

        # 6. Adjacent pairs (for n >= 3)
        if n_meetings >= 3:
            for step in [-STEP_SIZE, STEP_SIZE]:
                # First two meetings
                combo = [step, step] + [0] * (n_meetings - 2)
                if tuple(combo) not in combinations:
                    combinations.append(tuple(combo))
                # Last two meetings
                combo = [0] * (n_meetings - 2) + [step, step]
                if tuple(combo) not in combinations:
                    combinations.append(tuple(combo))
                # Middle pairs
                for i in range(1, n_meetings - 1):
                    combo = [0] * i + [step, step] + [0] * (n_meetings - i - 2)
                    if tuple(combo) not in combinations:
                        combinations.append(tuple(combo))

        return combinations

    def _calculate_reverse_distance_probabilities(
        self,
        base_rate: float,
        future_price: float,
        accrual_start_date: date,
        accrual_end_date: date,
        accrual_days: int,
        meeting_dates: List[date],
    ) -> pd.DataFrame:
        """Calculate reverse distance probabilities for Futures with n meetings.

        Creates a dataframe with different rate scenarios and their probabilities
        based on inverse distance weighting from the actual future price.

        Final dataframe columns:
        - {i}_rate_step: Rate step change for meeting i (for i=1..n)
        - total_step: Cumulative rate step change (sum of all rate_step columns)
        - {i}_rate: Rate after meeting i (for i=1..n)
        - price: Futures price based on rates of scenario
        - distance: Absolute distance between market future price and price of scenario.
            The closer the distance, the more likely the scenario is reflecting
            the market price.
        - reverse_distance: Reverse distance to allocate heavier weight to scenarios
            closer to the market price
        - probability: Probability for each scenario based on inverse distance weighting.
        """
        n_meetings = len(meeting_dates)
        # Generate all possible outcomes of rate changes for n meetings
        rate_combinations = self._generate_rate_combinations(n_meetings)

        # Create DataFrame with dynamic column names for each meeting
        df_data = {
            f"{i+1}_rate_step": [fc[i] for fc in rate_combinations]
            for i in range(n_meetings)
        }
        df_prob = pd.DataFrame(df_data)

        # Calculate total step (sum of all rate steps)
        rate_step_columns = [f"{i+1}_rate_step" for i in range(n_meetings)]
        df_prob["total_step"] = df_prob[rate_step_columns].sum(axis=1)

        # Calculate rates for each meeting
        for i in range(n_meetings):
            df_prob[f"{i+1}_rate"] = base_rate + df_prob[f"{i+1}_rate_step"] / 100

        # Vectorized price calculation
        df_prob["price"] = df_prob.apply(
            lambda row: self._calculate_three_month_futures_price(
                base_rate,
                [row[f"{i+1}_rate"] for i in range(n_meetings)],
                meeting_dates,
                accrual_start_date,
                accrual_end_date,
                accrual_days,
            ),
            axis=1,
        )
        # Calculate probabilities using inverse distance weighting
        df_prob["distance"] = abs(future_price - df_prob["price"])
        df_prob["reverse_distance"] = 1 / (
            df_prob["distance"] + 1e-10
        )  # Avoid division by zero
        df_prob["probability"] = (
            df_prob["reverse_distance"] / df_prob["reverse_distance"].sum()
        )
        return df_prob

    # __________________________________________________________
    # 3. FINAL PROBABILITY MATRIX CALCULATION
    # __________________________________________________________

    def _get_total_probabilities_from_dataframe(
        self, prob_df: pd.DataFrame, step_keys: List[int], n_meetings: int
    ) -> List[MeetingTotalProbabilityByStep]:
        """Calculate total probabilities for each step from probability dataframe
        for each meeting date.

        For each step value X in step_keys, we calculate:
        - Meeting i probability: Sum of all probabilities where {i}_rate_step == X
          (for individual meeting probabilities)
        """
        total_probabilities: List[MeetingTotalProbabilityByStep] = []
        for step_key in step_keys:
            # Aggregate probabilities for each individual meeting
            for i in range(1, n_meetings + 1):
                rate_step_col = f"{i}_rate_step"
                if rate_step_col in prob_df.columns:
                    # P_i(X_j) = Sum(P(X_j.[...].X_k))
                    # Where i is the meeting index
                    # And j is the step index at meeting i such that X_j = rate_step_j
                    # j belongs to STEP_SIZE * [1, n_meetings]
                    # k belongs to [1, i] and k != j
                    # P(X_i.[...].X_k) is the reverse distance probability of one scenario
                    meeting_mask = prob_df[rate_step_col] == step_key
                    probability = (
                        float(prob_df.loc[meeting_mask, "probability"].sum())
                        if meeting_mask.any()
                        else 0.0
                    )
                    total_probabilities.append(
                        MeetingTotalProbabilityByStep(
                            step=step_key,
                            meeting_i=i,
                            probability=probability,
                        )
                    )

        return total_probabilities

    def _calculate_initial_single_meeting_probabilities(
        self,
        base_rate: float,
        accrual_start_date: date,
        accrual_end_date: date,
        accrual_days: int,
        meeting_date: date,
        future_implied_rate: float,
        apply_convolution: bool = True,
    ):
        """Calculate initial probabilities for single meeting case."""
        logger.info("Calculating initial probabilities for single meeting case.")
        meeting_implied_rate = (
            self._calculate_three_month_futures_average_rate_for_single_meeting(
                accrual_end_date,
                accrual_days,
                meeting_date,
                future_implied_rate,
                base_rate,
            )
        )

        # Calculate rate change in basis points
        rate_change_bps = (meeting_implied_rate - base_rate) * 100
        self._apply_linear_interpolation(
            rate_change_bps, is_initial=True, apply_convolution=apply_convolution
        )

    def _calculate_initial_n_meetings_probabilities(
        self,
        base_rate: float,
        future_price: float,
        accrual_start_date: date,
        accrual_end_date: date,
        accrual_days: int,
        meeting_dates: List[date],
        apply_convolution: bool = True,
    ):
        """Calculate initial probabilities for n meetings case."""
        logger.info("Calculating initial probabilities for n meetings case.")
        prob_df = self._calculate_reverse_distance_probabilities(
            base_rate,
            future_price,
            accrual_start_date,
            accrual_end_date,
            accrual_days,
            meeting_dates,
        )

        step_keys = [
            meeting_probability["expected_rate_step"]
            for meeting_probability in self.probability_matrix
        ]
        total_probabilities_by_step = self._get_total_probabilities_from_dataframe(
            prob_df, step_keys, len(meeting_dates)
        )

        # Create a lookup dict: step -> list of probabilities ordered by meeting_i
        prob_lookup: Dict[int, List[float]] = {}
        default_probabilities = [0.0] * len(meeting_dates)
        for prob_by_step in total_probabilities_by_step:
            step_key = prob_by_step["step"]
            if step_key not in prob_lookup:
                prob_lookup[step_key] = default_probabilities.copy()
            # meeting_i is 1-based, convert to 0-based index
            prob_lookup[step_key][prob_by_step["meeting_i"] - 1] = prob_by_step[
                "probability"
            ]

        # Update meeting_probabilities with the calculated probabilities
        for meeting_probability in self.probability_matrix:
            step_key = meeting_probability["expected_rate_step"]
            probabilities = prob_lookup.get(step_key, default_probabilities.copy())
            meeting_probability["probabilities"].extend(probabilities)

    def _calculate_single_meeting_probabilities(
        self,
        base_rate: float,
        accrual_end_date: date,
        accrual_days: int,
        first_meeting_date: date,
        future_implied_rate: float,
        apply_convolution: bool = True,
    ):
        """Calculate probabilities for subsequent single meeting."""
        logger.info("Calculating probabilities for subsequent single meeting.")
        meeting_implied_rate = (
            self._calculate_three_month_futures_average_rate_for_single_meeting(
                accrual_end_date,
                accrual_days,
                first_meeting_date,
                future_implied_rate,
                base_rate,
            )
        )
        # Calculate rate change in basis points
        rate_change_bps = (meeting_implied_rate - base_rate) * 100
        self._apply_linear_interpolation(
            rate_change_bps, is_initial=False, apply_convolution=apply_convolution
        )

    def _calculate_n_meetings_probabilities(
        self,
        base_rate: float,
        future_price: float,
        accrual_start_date: date,
        accrual_end_date: date,
        accrual_days: int,
        meeting_dates: List[date],
        apply_convolution: bool = True,
    ):
        """Calculate probabilities for subsequent n meetings case."""
        logger.info("Calculating probabilities for subsequent n meetings case.")
        if not self.probability_matrix:
            return

        # Calculate new probabilities
        prob_df = self._calculate_reverse_distance_probabilities(
            base_rate,
            future_price,
            accrual_start_date,
            accrual_end_date,
            accrual_days,
            meeting_dates,
        )

        # Extract probabilities for standard step keys
        new_total_probabilities = self._get_total_probabilities_from_dataframe(
            prob_df, STANDARD_STEP_SCENARIOS, len(meeting_dates)
        )

        # Create lookup: step -> list of probabilities ordered by meeting_i
        new_prob_lookup: Dict[int, List[float]] = {}
        default_probabilities = [0.0] * len(meeting_dates)
        for prob_by_step in new_total_probabilities:
            step_key = prob_by_step["step"]
            if step_key not in new_prob_lookup:
                # Create a copy of the list, not a reference
                new_prob_lookup[step_key] = default_probabilities.copy()
            # meeting_i is 1-based, convert to 0-based index
            new_prob_lookup[step_key][prob_by_step["meeting_i"] - 1] = prob_by_step[
                "probability"
            ]

        if apply_convolution:
            # Extend support
            self._extend_probability_support()

            # Update probabilities for each step
            last_prob_idx = self._get_last_probability_index()
            n_meetings = len(meeting_dates)

            # Determine the maximum step transition to consider
            # For n meetings, we consider transitions up to ±n*STEP_SIZE
            # but limit to available step keys in new_prob_lookup for efficiency
            max_transition_steps = min(n_meetings, MAX_MEETINGS)

            for meeting_probability in self.probability_matrix:
                step_key = meeting_probability["expected_rate_step"]

                # Calculate probabilities for each meeting
                meeting_probabilities = []
                for i in range(n_meetings):
                    # For meeting i, consider transitions up to ±(i+1)*STEP_SIZE
                    max_steps_for_meeting = min(i + 1, max_transition_steps)
                    meeting_transition_steps = [
                        step * STEP_SIZE
                        for step in range(
                            -max_steps_for_meeting, max_steps_for_meeting + 1
                        )
                    ]

                    # Sum over all possible transitions
                    p_i = 0.0
                    for transition_step in meeting_transition_steps:
                        # Get previous probability at step_key - transition_step
                        prev_step = step_key - transition_step
                        prev_prob = self._get_probability_value(
                            prev_step, last_prob_idx
                        )

                        # Get new probability for meeting i at transition_step
                        # Only use transition steps that exist in the lookup
                        if transition_step in new_prob_lookup:
                            new_prob_list = new_prob_lookup[transition_step]
                            new_prob = (
                                new_prob_list[i] if i < len(new_prob_list) else 0.0
                            )
                        else:
                            new_prob = 0.0

                        # Accumulate: P_new(step_key) = Σ P_prev(step_key - x) ×
                        # P_new(x)[i]
                        p_i += prev_prob * new_prob

                    meeting_probabilities.append(p_i)

                meeting_probability["probabilities"].extend(meeting_probabilities)
        else:
            # Add probabilities directly without convolution (for debugging)
            n_meetings = len(meeting_dates)
            for meeting_probability in self.probability_matrix:
                step_key = meeting_probability["expected_rate_step"]
                # Get probabilities for this step key, or use zeros
                probabilities = new_prob_lookup.get(step_key, [0.0] * n_meetings)
                meeting_probability["probabilities"].extend(probabilities)

    def _process_initial_meeting(
        self,
        base_rate: float,
        future_price: float,
        future_implied_rate: float,
        accrual_start_date: date,
        accrual_end_date: date,
        accrual_days: int,
        meeting_dates: List[date],
        apply_convolution: bool = True,
    ):
        """Process initial meeting probabilities.

        Args:
            apply_convolution: Whether to apply convolution (for consistency).
        """
        if len(meeting_dates) == 1:
            if meeting_dates[0] is None:
                raise ValueError("First meeting date is required")
            self._calculate_initial_single_meeting_probabilities(
                base_rate,
                accrual_start_date,
                accrual_end_date,
                accrual_days,
                meeting_dates[0],
                future_implied_rate,
                apply_convolution=apply_convolution,
            )
        elif len(meeting_dates) >= 2:
            if any(meeting_date is None for meeting_date in meeting_dates):
                raise ValueError("All meeting dates are required")
            self._calculate_initial_n_meetings_probabilities(
                base_rate,
                future_price,
                accrual_start_date,
                accrual_end_date,
                accrual_days,
                meeting_dates,
                apply_convolution=apply_convolution,
            )

    def _process_subsequent_meeting(
        self,
        base_rate: float,
        future_price: float,
        future_implied_rate: float,
        accrual_start_date: date,
        accrual_end_date: date,
        accrual_days: int,
        meeting_dates: List[date],
        apply_convolution: bool = True,
    ):
        """Process subsequent meeting probabilities."""
        if len(meeting_dates) == 1:
            if meeting_dates[0] is None:
                raise ValueError("First meeting date is required")
            self._calculate_single_meeting_probabilities(
                base_rate,
                accrual_end_date,
                accrual_days,
                meeting_dates[0],
                future_implied_rate,
                apply_convolution=apply_convolution,
            )
        elif len(meeting_dates) >= 2:
            if any(meeting_date is None for meeting_date in meeting_dates):
                raise ValueError("All meeting dates are required")
            self._calculate_n_meetings_probabilities(
                base_rate,
                future_price,
                accrual_start_date,
                accrual_end_date,
                accrual_days,
                meeting_dates,
                apply_convolution=apply_convolution,
            )

    def generate_probability_matrix(
        self, apply_convolution: bool = True, format_probabilities: bool = True
    ):
        """Generate probability matrix for Three Month Futures interest rate changes.

        This function processes futures contracts and meeting dates to calculate
        probabilities of interest rate changes at each central bank meeting.

        Args:
            apply_convolution: If True, applies convolution with previous probabilities
                              for subsequent meetings. If False, probabilities are added
                              directly without convolution (useful for debugging).
        """
        logger.info("Generating probability matrix for Three Month Futures.")
        is_initial = True
        base_rate = self.initial_base_rate

        for meeting_by_future in self.meetings_by_futures:
            meeting_dates = meeting_by_future.get("meeting_dates")
            nb_meetings = meeting_by_future.get("nb_meetings")
            future_price = meeting_by_future.get("futures_price")
            future_implied_rate = meeting_by_future.get("futures_implied_rate")
            accrual_start_date = meeting_by_future.get("accrual_start_date")
            accrual_end_date = meeting_by_future.get("accrual_end_date")
            accrual_days = meeting_by_future.get("accrual_days")

            logger.info(
                f"Processing futures contract for meeting dates: {meeting_dates}."
            )
            if nb_meetings == 0:
                continue

            if is_initial:
                self._process_initial_meeting(
                    base_rate,
                    future_price,
                    future_implied_rate,
                    accrual_start_date,
                    accrual_end_date,
                    accrual_days,
                    meeting_dates,
                    apply_convolution=apply_convolution,
                )
                is_initial = False
            else:
                self._process_subsequent_meeting(
                    base_rate,
                    future_price,
                    future_implied_rate,
                    accrual_start_date,
                    accrual_end_date,
                    accrual_days,
                    meeting_dates,
                    apply_convolution=apply_convolution,
                )

            base_rate = future_implied_rate

        if format_probabilities:
            self._format_probabilities()


class FedFundsFuturesProbabilityMatrixService(ProbabilityMatrixBaseService):
    """Service for probability matrix calculation for Fed Funds Futures."""

    def __init__(
        self,
        initial_base_rate: float,
        future_prices: List[StirFuturesModel],
        meeting_dates: List[datetime],
    ):
        super().__init__(
            initial_base_rate,
            future_prices=future_prices,
            meeting_dates=meeting_dates[:MAX_MEETINGS_TO_COVER],
            remove_na=False,
        )
        self.meeting_rate_info: List[FedMeetingRateInfo] = []
        # Validate that all meetings are covered by futures
        self._validate_meetings_covered_by_futures()

    # __________________________________________________________
    # 0. VALIDATION
    # __________________________________________________________

    def _validate_meetings_covered_by_futures(self):
        """Validate that the all meeting dates are covered by futures contracts.

        Requirements:
        1. The all meetings date must fall within one future's accrual period
        2. The last meeting must have a future after it (on the next month)
        """
        if not self.meeting_dates:
            logger.warning("No meetings to validate.")
            return

        meeting_dates_as_dates = [md.date() for md in self.meeting_dates]
        sorted_meeting_dates = sorted(meeting_dates_as_dates)

        # Check that each meeting is covered by at least one future
        for meeting_date in sorted_meeting_dates:
            covered = False
            for future_price in self.future_prices:
                if (
                    future_price.first_accrual_date
                    <= meeting_date
                    < future_price.last_accrual_date
                ):
                    covered = True
                    break
            if not covered:
                raise ValueError(
                    f"Meeting date {meeting_date} is not covered by any future contract."
                )

        # Check that last meeting has a future after it
        last_meeting = sorted_meeting_dates[-1]
        has_future_after = False
        for future_price in self.future_prices:
            if future_price.first_accrual_date > last_meeting:
                has_future_after = True
                break
        if not has_future_after:
            raise ValueError(
                f"Last meeting date {last_meeting} requires a future contract after it to determine end_rate."
            )

    # __________________________________________________________
    # 1. IMPLIED RATE / PRICE CALCULATION
    # __________________________________________________________

    def _calculate_fedfunds_futures_rate(
        self,
        accrual_end_date: date,
        accrual_days: int,
        meeting_date: date,
        future_average_rate: float,
        period_rate: float,
        rate_type: FedFuturesRateType,
    ) -> float:
        """Calculate the rate for a given Fed Funds Futures contract.

        Calculates either the start rate (before meeting) or end rate (after meeting)
        given the future average rate and the period rate.
        Note: FF implied rates are average of daily FF rates during the period.
        """
        days_after_meeting = (accrual_end_date - meeting_date).days
        days_before_meeting = accrual_days - days_after_meeting

        if days_after_meeting <= 0 or days_before_meeting <= 0:
            raise ValueError(
                f"Meeting date must be within contract period. "
                f"Accrual days: {accrual_days}, Days after meeting: {days_after_meeting}"
            )

        prior_ratio = days_before_meeting / accrual_days
        after_ratio = days_after_meeting / accrual_days

        if rate_type == FedFuturesRateType.START:
            # Calculate start rate: (implied_rate - end_rate * after_ratio) / prior_ratio
            return (future_average_rate - period_rate * after_ratio) / prior_ratio
        elif rate_type == FedFuturesRateType.END:
            # Calculate end rate: (implied_rate - start_rate * prior_ratio) / after_ratio
            return (future_average_rate - period_rate * prior_ratio) / after_ratio

    # __________________________________________________________
    # 2. MEETING RATE CHANGE CALCULATION
    # __________________________________________________________

    def _infer_period_rates_from_period_without_meetings(self):
        """Infer period rates from period without meetings."""
        logger.info("Inferring period rates from period without meetings.")
        previous_rate: Optional[float] = None
        for idx, meeting_by_future in enumerate(self.meetings_by_futures):
            implied_rate = meeting_by_future["futures_implied_rate"]
            meeting_dates = meeting_by_future["meeting_dates"]
            assert len(meeting_dates) <= 1, "Only one meeting date is supported"
            meeting_date = meeting_dates[0] if meeting_dates else None
            has_meeting = meeting_date is not None

            if not has_meeting:
                # No meeting: propagate the implied rate
                previous_rate = implied_rate
                if (
                    self.meeting_rate_info
                    and self.meeting_rate_info[-1]["end_rate"] is None
                ):
                    self.meeting_rate_info[-1]["end_rate"] = implied_rate
            else:
                # Has meeting: start rate is previous rate (or initial if first)
                start_rate = (
                    previous_rate
                    if previous_rate is not None
                    else (self.initial_base_rate if idx == 0 else None)
                )
                self.meeting_rate_info.append(
                    FedMeetingRateInfo(
                        meeting_date=meeting_date,
                        start_rate=start_rate,
                        end_rate=None,  # end_rates are calculated within the loop
                        rate_diff=None,
                    )
                )
                previous_rate = None

    def _calculate_missing_rate(
        self,
        rate_info: FedMeetingRateInfo,
        meeting_by_future: MeetingsByFutures,
    ):
        """Calculate missing start_rate or end_rate using formulas."""
        accrual_end_date = meeting_by_future["accrual_end_date"]
        accrual_days = meeting_by_future["accrual_days"]
        future_implied_rate = meeting_by_future["futures_implied_rate"]
        meeting_date = rate_info["meeting_date"]

        if rate_info["start_rate"] is None and rate_info["end_rate"] is not None:
            # Calculate start_rate from end_rate
            rate_info["start_rate"] = self._calculate_fedfunds_futures_rate(
                accrual_end_date,
                accrual_days,
                meeting_date,
                future_implied_rate,
                rate_info["end_rate"],
                FedFuturesRateType.START,
            )
        elif rate_info["end_rate"] is None and rate_info["start_rate"] is not None:
            # Calculate end_rate from start_rate
            rate_info["end_rate"] = self._calculate_fedfunds_futures_rate(
                accrual_end_date,
                accrual_days,
                meeting_date,
                future_implied_rate,
                rate_info["start_rate"],
                FedFuturesRateType.END,
            )
        elif rate_info["end_rate"] and rate_info["start_rate"]:
            # Both rates available: recalculate start_rate from end_rate
            # This ensures start_rate is consistent with futures implied rate
            rate_info["start_rate"] = self._calculate_fedfunds_futures_rate(
                accrual_end_date,
                accrual_days,
                meeting_date,
                future_implied_rate,
                rate_info["end_rate"],
                FedFuturesRateType.START,
            )

    def _build_contract_to_meeting_mapping(
        self,
    ) -> Dict[int, int]:
        """Build mapping from contract index to meeting index."""
        contract_to_meeting_idx: Dict[int, int] = {}
        meeting_idx = 0
        for idx, meeting_by_future in enumerate(self.meetings_by_futures):
            meeting_dates = meeting_by_future["meeting_dates"]
            meeting_date = meeting_dates[0] if meeting_dates else None
            if meeting_date is not None:
                contract_to_meeting_idx[idx] = meeting_idx
                meeting_idx += 1
        return contract_to_meeting_idx

    def _has_non_fomc_anchor_between(
        self,
        contract_idx1: int,
        contract_idx2: int,
        contract_to_meeting_idx: Dict[int, int],
    ) -> bool:
        """Check if there's a non-FOMC anchor month between two contract indices."""
        for check_idx in range(contract_idx1 + 1, contract_idx2):
            if check_idx not in contract_to_meeting_idx:
                return True
        return False

    def _propagate_rate_backward(
        self,
        contract_to_meeting_idx: Dict[int, int],
        meeting_lookup: Dict[date, MeetingsByFutures],
    ):
        """Propagate calculated start_rate backward as end_rate until non-FOMC anchor."""
        for meeting_idx in range(len(self.meeting_rate_info) - 1, 0, -1):
            current_start_rate = self.meeting_rate_info[meeting_idx]["start_rate"]
            if current_start_rate is None:
                continue

            # Find contract index for this meeting
            current_contract_idx = None
            for contract_idx, mapped_meeting_idx in contract_to_meeting_idx.items():
                if mapped_meeting_idx == meeting_idx:
                    current_contract_idx = contract_idx
                    break

            if current_contract_idx is None:
                continue

            # Propagate backward until we hit a non-FOMC anchor
            for prev_contract_idx in range(current_contract_idx - 1, -1, -1):
                if prev_contract_idx not in contract_to_meeting_idx:
                    # Hit a non-FOMC anchor, stop
                    break

                prev_meeting_idx = contract_to_meeting_idx[prev_contract_idx]

                # Check if there's a non-FOMC anchor between contracts
                if self._has_non_fomc_anchor_between(
                    prev_contract_idx, current_contract_idx, contract_to_meeting_idx
                ):
                    break

                # Propagate start_rate as end_rate
                if self.meeting_rate_info[prev_meeting_idx]["end_rate"] is None:
                    self.meeting_rate_info[prev_meeting_idx][
                        "end_rate"
                    ] = current_start_rate

                    # Recalculate start_rate for previous meeting
                    prev_meeting_date = self.meeting_rate_info[prev_meeting_idx][
                        "meeting_date"
                    ]
                    prev_meeting_by_future = meeting_lookup.get(prev_meeting_date)
                    if prev_meeting_by_future:
                        self._calculate_missing_rate(
                            self.meeting_rate_info[prev_meeting_idx],
                            prev_meeting_by_future,
                        )

                current_contract_idx = prev_contract_idx

    def _calculate_meeting_rate_changes(self):
        """Calculate rate changes for each meeting from futures data."""
        logger.info("Calculating rate changes for each meeting from futures data.")
        self._infer_period_rates_from_period_without_meetings()

        # Build lookup: meeting_date -> meeting_by_future
        meeting_lookup: Dict[date, MeetingsByFutures] = {}
        for mbf in self.meetings_by_futures:
            for meeting_date in mbf.get("meeting_dates", []):
                if meeting_date is not None:
                    meeting_lookup[meeting_date] = mbf

        # Step 1: Calculate missing rates using formulas
        for rate_info in self.meeting_rate_info:
            meeting_by_future = meeting_lookup.get(rate_info["meeting_date"])
            if meeting_by_future:
                logger.info(
                    f"Calculating missing rates for: {rate_info['meeting_date']}."
                )
                self._calculate_missing_rate(rate_info, meeting_by_future)

        # Step 2: Backward propagation of calculated rates
        contract_to_meeting_idx = self._build_contract_to_meeting_mapping()
        self._propagate_rate_backward(contract_to_meeting_idx, meeting_lookup)

        # Step 3: Calculate rate differences
        for rate_info in self.meeting_rate_info:
            if rate_info["start_rate"] is None or rate_info["end_rate"] is None:
                raise ValueError(
                    f"Start rate or end rate is missing for {rate_info['meeting_date']}"
                )
            rate_info["rate_diff"] = rate_info["end_rate"] - rate_info["start_rate"]

    # __________________________________________________________
    # 3. FINAL PROBABILITY MATRIX CALCULATION
    # __________________________________________________________

    def generate_probability_matrix(
        self, apply_convolution: bool = True, format_probabilities: bool = True
    ):
        """Generate probability matrix for Fed interest rate changes from futures prices.

        This function processes futures contracts with rate changes to calculate
        probabilities of interest rate changes at each central bank meeting.

        Args:
            apply_convolution: If True, applies convolution with previous probabilities
                              for subsequent meetings. If False, probabilities are added
                              directly without convolution (useful for debugging).
            format_probabilities: If True, formats probabilities to 2 decimal places and
                              filters out entries below PROBABILITY_THRESHOLD.
                              This is useful for debugging.
        """
        logger.info(
            "Generating probability matrix for Fed interest rate changes from futures prices."
        )
        self._calculate_meeting_rate_changes()
        is_initial = True

        logger.info("Applying linear interpolation for probability calculation.")
        for rate_info in self.meeting_rate_info:
            if rate_info["rate_diff"] is None:
                raise ValueError(
                    f"Rate difference is missing for {rate_info['meeting_date']}"
                )
            rate_diff_bps = rate_info["rate_diff"] * 100
            self._apply_linear_interpolation(
                rate_diff_bps,
                is_initial=is_initial,
                apply_convolution=apply_convolution,
            )
            is_initial = False

        if format_probabilities:
            self._format_probabilities()


class EstrFuturesProbabilityMatrixService(ThreeMonthFuturesProbabilityMatrixService):
    """Service for probability matrix calculation for ESTR Futures.

    Based on Future price calculation on:
    https://www.ice.com/products/82908552/Three-Month-ESTR-Indexed-Future
    """

    def __init__(
        self,
        initial_base_rate: float,
        future_prices: List[StirFuturesModel],
        meeting_dates: List[datetime],
    ):
        config = FuturesCalculationConfig(days_per_year=360)
        super().__init__(initial_base_rate, future_prices, meeting_dates, config)


class MutanFuturesProbabilityMatrixService(ThreeMonthFuturesProbabilityMatrixService):
    """Service for probability matrix calculation for Mutan Futures.

    Based on Future price calculation on:
    https://www.tfx.co.jp/en/wholesale/products/tona.html
    """

    def __init__(
        self,
        initial_base_rate: float,
        future_prices: List[StirFuturesModel],
        meeting_dates: List[datetime],
    ):
        config = FuturesCalculationConfig(
            days_per_year=365, futures_days_compounding_convention=90
        )
        super().__init__(initial_base_rate, future_prices, meeting_dates, config)


def _initiate_central_bank_probability_matrix_calculation(
    central_bank: CentralBankChoices,
    initial_base_rate: float,
    future_prices: List[StirFuturesModel],
    meeting_dates: List[datetime],
) -> ProbabilityMatrixBaseService:
    """Initiate central bank probability matrix calculation."""
    match central_bank:
        case CentralBankChoices.FRB:
            calculation_service = FedFundsFuturesProbabilityMatrixService(
                initial_base_rate, future_prices, meeting_dates
            )
            calculation_service.generate_probability_matrix()
            return calculation_service
        case CentralBankChoices.ECB:
            calculation_service = EstrFuturesProbabilityMatrixService(
                initial_base_rate, future_prices, meeting_dates
            )
            calculation_service.generate_probability_matrix()
            return calculation_service
        case CentralBankChoices.BOJ:
            calculation_service = MutanFuturesProbabilityMatrixService(
                initial_base_rate, future_prices, meeting_dates
            )
            calculation_service.generate_probability_matrix()
            return calculation_service
        case _:
            raise ValueError(f"Invalid central bank: {central_bank}")


def get_central_bank_effective_rate(
    central_bank: CentralBankChoices,
    target_date: date,
) -> float:
    """Get effective rate for a central bank."""
    return MarketPriceModel.objects.get(
        date=target_date, asset__short_name=CENTRAL_BANK_TARGET_RATE_MAP[central_bank]
    ).price


def get_fall_back_rate(
    central_bank: CentralBankChoices,
    target_date: date,
) -> float:
    """Get fall back rate for a central bank (last non-None price)."""
    last_price = (
        MarketPriceModel.objects.filter(
            asset__short_name=CENTRAL_BANK_TARGET_RATE_MAP[central_bank],
            date__lte=target_date,
            price__isnull=False,
        )
        .order_by("-date")
        .first()
    )
    if not last_price:
        raise ValueError(f"No rates found before {target_date} for {central_bank}")
    return last_price.price


def get_central_bank_probability_matrices(
    target_date: date,
    central_banks: List[CentralBankChoices] = [],
    meeting_dates_override: Dict[CentralBankChoices, List[datetime]] = {},
) -> List[CentralBankProbabilityMatrix]:
    """Get probability matrices for specified central banks."""
    logger.info(f"Getting probability matrices for {central_banks} on {target_date}")
    central_banks_to_process = (
        central_banks if central_banks else list(CENTRAL_BANK_TARGET_RATE_MAP.keys())
    )

    all_meeting_dates = cb_meetings_services.get_central_bank_meeting_dates(
        central_banks_to_process
    )
    all_future_prices = stir_prices_services.get_futures_prices(
        target_date, central_banks_to_process
    )

    # Create lookup dictionaries for efficient access
    # Note: meeting_dates from cb_meetings_services are List[datetime]
    meeting_dates_lookup: Dict[CentralBankChoices, List[datetime]] = {
        meeting_data["central_bank"]: meeting_data["meeting_dates"]
        for meeting_data in all_meeting_dates
    }
    # Override meeting dates if provided (used for recalculating previous matrices)
    if meeting_dates_override:
        for cb, dates in meeting_dates_override.items():
            meeting_dates_lookup[cb] = dates
    future_prices_lookup = {
        cb: [fp for fp in all_future_prices if fp.central_bank == cb]
        for cb in central_banks_to_process
    }

    cb_probability_matrices: List[CentralBankProbabilityMatrix] = []
    for central_bank in central_banks_to_process:
        logger.info(f"Processing probability matrix for {central_bank}")

        # Get initial base rate
        initial_base_rate = get_central_bank_effective_rate(central_bank, target_date)
        if not initial_base_rate:
            logger.warning(
                f"No effective rate found for {central_bank} on {target_date}. Using fall back rate."
            )
            initial_base_rate = get_fall_back_rate(central_bank, target_date)

        # Get meeting dates
        meeting_dates = meeting_dates_lookup.get(central_bank)
        if not meeting_dates:
            raise ValueError(f"No meeting dates found for {central_bank}.")

        # Get future prices
        future_prices = future_prices_lookup.get(central_bank, [])
        if not future_prices:
            logger.warning(
                f"No future prices found for {central_bank} on {target_date}"
            )

        # Generate probability matrix
        try:
            calculation_service = _initiate_central_bank_probability_matrix_calculation(
                central_bank, initial_base_rate, future_prices, meeting_dates
            )
            cb_probability_matrices.append(
                CentralBankProbabilityMatrix(
                    central_bank=central_bank,
                    meeting_dates=calculation_service.meetings_in_period,
                    probability_matrix=calculation_service.probability_matrix,
                )
            )
            logger.info(f"Successfully generated probability matrix for {central_bank}")
        except Exception as e:
            logger.error(
                f"Error generating probability matrix for {central_bank}: {e}",
                exc_info=True,
            )
            raise

    return cb_probability_matrices


def calculate_probability_changes(
    probability_matrix: CentralBankProbabilityMatrix,
    previous_probability_matrix: CentralBankProbabilityMatrix,
) -> CentralBankProbabilityMatrix:
    """Calculate probability change matrix.

    Aligns probabilities by meeting dates to handle cases where meeting dates
    change between the current and previous matrices (e.g., after a meeting
    occurs).
    """
    current_meeting_dates = probability_matrix["meeting_dates"]
    previous_meeting_dates = previous_probability_matrix["meeting_dates"]

    # Build previous probabilities indexed by rate_step and meeting_date
    previous_by_step_and_date: Dict[int, Dict[date, float]] = {}
    for entry in previous_probability_matrix["probability_matrix"]:
        rate_step = entry["expected_rate_step"]
        previous_by_step_and_date[rate_step] = {}
        for meeting_idx, prob in enumerate(entry["probabilities"]):
            if meeting_idx < len(previous_meeting_dates):
                meeting_date = previous_meeting_dates[meeting_idx]
                meeting_date_as_date = (
                    meeting_date.date()
                    if isinstance(meeting_date, datetime)
                    else meeting_date
                )
                previous_by_step_and_date[rate_step][meeting_date_as_date] = prob

    probability_change_matrix: List[ProbabilitiesByStep] = []
    for current_entry in probability_matrix["probability_matrix"]:
        rate_step = current_entry["expected_rate_step"]
        current_probs = current_entry["probabilities"]
        previous_probs_map = previous_by_step_and_date.get(rate_step, {})

        differences = []
        for meeting_idx, current_prob in enumerate(current_probs):
            if meeting_idx < len(current_meeting_dates):
                meeting_date = current_meeting_dates[meeting_idx]
                # Convert to date for comparison (current_meeting_dates is List[date])
                meeting_date_as_date = (
                    meeting_date.date()
                    if isinstance(meeting_date, datetime)
                    else meeting_date
                )
                # Get previous probability for this meeting date, default to 0 if none
                previous_prob = previous_probs_map.get(meeting_date_as_date, 0.0)
                difference = round(current_prob - previous_prob, 8)
                differences.append(difference)

        probability_change_matrix.append(
            ProbabilitiesByStep(
                expected_rate_step=rate_step,
                probabilities=differences,
            )
        )

    return CentralBankProbabilityMatrix(
        central_bank=probability_matrix["central_bank"],
        meeting_dates=probability_matrix["meeting_dates"],
        probability_matrix=probability_change_matrix,
    )
