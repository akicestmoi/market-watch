import math
from datetime import date, datetime
from enum import Enum
from typing import List, Optional, TypedDict

import pandas as pd

import central_banks_overview.services.cb_meetings_services as cb_meetings_services
import central_banks_overview.services.stir_prices_ingestion_services as stir_prices_services
from central_banks_overview.models import CentralBankChoices, StirFuturesModel
from core.services import logger
from market_overview.models import MarketPriceModel

# Day count convention: ACT/365
DAYS_PER_YEAR = 365
MUTAN_FUTURES_AVERAGE_DAYS = 90

# Step size for probability calculations
STEP_SIZE = 25
STANDARD_STEP_SCENARIOS = [-2 * STEP_SIZE, -STEP_SIZE, 0, STEP_SIZE, 2 * STEP_SIZE]
# Number of steps to extend probability support in each direction
PROBABILITY_EXTENSION_STEPS = 5
# Threshold for probability removal
PROBABILITY_THRESHOLD = 1.0


CENTRAL_BANK_TARGET_RATE_MAP = {
    CentralBankChoices.FRB: "FEDFUNDS",
    CentralBankChoices.BOJ: "MUTAN",
}


class RateChangePerStep(TypedDict):
    """Rate change per step."""

    nb_steps: int
    proportion: float
    sign: float


class MeetingsByFutures(TypedDict):
    """Meetings information for a futures contract."""

    futures_contract_start_date: date
    futures_contract_end_date: date
    futures_contract_days: int
    futures_price: float
    futures_implied_rate: float
    nb_meetings: int
    first_meeting_date: Optional[date]
    second_meeting_date: Optional[date]


class ProbabilitiesByStep(TypedDict):
    """Probabilities for a step."""

    expected_rate_step: int
    probabilities: List[float]


class CentralBankProbabilityMatrix(TypedDict):
    """Central bank probability matrix."""

    central_bank: CentralBankChoices
    meeting_dates: List[date]
    probability_matrix: List[ProbabilitiesByStep]


class TwoMeetingsTotalProbabilitiesByStep(TypedDict):
    """Total probabilities for each step."""

    step: int
    first_meeting_prob: float
    second_meeting_prob: float


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


class RateChangePerMeeting(TypedDict):
    """Rate change information for a meeting."""

    rate_diff: float
    meeting_date: date


class ProbabilityMatrixBaseService:
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
            period_start = future_price.reference_start_date
            period_end = future_price.reference_end_date

            meetings_in_period = [
                meeting_date.date()
                for meeting_date in self.meeting_dates
                if period_start <= meeting_date.date() < period_end
            ]
            if len(meetings_in_period) > 2:
                raise ValueError(
                    f"Too many meetings ({len(meetings_in_period)}) within period "
                    f"{period_start} to {period_end}"
                )

            if (remove_na and len(meetings_in_period) != 0) or not remove_na:
                meetings_by_futures.append(
                    MeetingsByFutures(
                        futures_contract_start_date=period_start,
                        futures_contract_end_date=period_end,
                        futures_contract_days=(period_end - period_start).days + 1,
                        futures_price=future_price.price,
                        futures_implied_rate=100 - future_price.price,
                        nb_meetings=len(meetings_in_period),
                        first_meeting_date=(
                            meetings_in_period[0]
                            if len(meetings_in_period) > 0
                            else None
                        ),
                        second_meeting_date=(
                            meetings_in_period[1]
                            if len(meetings_in_period) > 1
                            else None
                        ),
                    )
                )

        return meetings_by_futures

    def _get_meetings_in_period(self) -> List[date]:
        """Get meetings in period."""
        all_meeting_dates: set[date] = set()

        for meeting_by_future in self.meetings_by_futures:
            first_meeting = meeting_by_future.get("first_meeting_date")
            if first_meeting is not None:
                all_meeting_dates.add(first_meeting)
            second_meeting = meeting_by_future.get("second_meeting_date")
            if second_meeting is not None:
                all_meeting_dates.add(second_meeting)

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
    ):
        """Apply linear interpolation for probability calculation."""
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
            self._extend_probability_support()
            last_prob_idx = self._get_last_probability_index()

            for meeting_probability in self.probability_matrix:
                step_key = meeting_probability["expected_rate_step"]

                prev_step_key = step_key - nb_steps * STEP_SIZE
                next_step_key = step_key - int((nb_steps + sign) * STEP_SIZE)

                prev_prob = self._get_probability_value(prev_step_key, last_prob_idx)
                next_prob = self._get_probability_value(next_step_key, last_prob_idx)

                p_x = (1 - proportion) * prev_prob + proportion * next_prob
                meeting_probability["probabilities"].append(p_x)

    def generate_probability_matrix(self):
        """Generate probability matrix for the futures contracts."""
        raise NotImplementedError("This method is not implemented for the base class.")

    def restructure_probability_matrix_by_meeting_date(self):
        """Restructure probability matrix to have probabilities for each meeting date."""


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
            meeting_dates=meeting_dates,
            remove_na=False,
        )

    # __________________________________________________________
    # 1. IMPLIED RATE / PRICE CALCULATION
    # __________________________________________________________

    def _calculate_fedfunds_futures_rate(
        self,
        future_settlement_date: date,
        contract_days: int,
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
        days_after_meeting = (future_settlement_date - meeting_date).days
        days_before_meeting = contract_days - days_after_meeting

        if days_after_meeting <= 0 or days_before_meeting <= 0:
            raise ValueError(
                f"Meeting date must be within contract period. "
                f"Contract days: {contract_days}, Days after meeting: {days_after_meeting}"
            )

        prior_ratio = days_before_meeting / contract_days
        after_ratio = days_after_meeting / contract_days

        if rate_type == FedFuturesRateType.START:
            # Calculate start rate: (implied_rate - end_rate * after_ratio) / prior_ratio
            return (future_average_rate - period_rate * after_ratio) / prior_ratio
        elif rate_type == FedFuturesRateType.END:
            # Calculate end rate: (implied_rate - start_rate * prior_ratio) / after_ratio
            return (future_average_rate - period_rate * prior_ratio) / after_ratio

    # __________________________________________________________
    # 2. MEETING RATE CHANGE CALCULATION
    # __________________________________________________________

    def _infer_period_rates_from_period_without_meetings(
        self,
    ) -> List[FedMeetingRateInfo]:
        """Infer period rates from period without meetings."""
        logger.info("Inferring period rates from period without meetings.")
        meeting_rate_info: List[FedMeetingRateInfo] = []
        previous_rate: Optional[float] = None
        for idx, meeting_by_future in enumerate(self.meetings_by_futures):
            implied_rate = meeting_by_future["futures_implied_rate"]
            first_meeting_date = meeting_by_future.get("first_meeting_date")
            has_meeting = first_meeting_date is not None

            if not has_meeting:
                # No meeting: propagate the implied rate
                if idx == 0:
                    # First contract without meeting: use initial base rate
                    previous_rate = self.initial_base_rate
                else:
                    # Update previous meeting's end rate if exists,
                    # then set new previous_rate
                    if meeting_rate_info:
                        meeting_rate_info[-1]["end_rate"] = implied_rate
                    previous_rate = implied_rate

                # For last contract, also update end rate
                if idx == len(self.meetings_by_futures) - 1:
                    if meeting_rate_info:
                        meeting_rate_info[-1]["end_rate"] = implied_rate
            else:
                # Has meeting: start rate is previous rate (or initial if first)
                start_rate = (
                    previous_rate
                    if previous_rate is not None
                    else (self.initial_base_rate if idx == 0 else None)
                )
                meeting_rate_info.append(
                    FedMeetingRateInfo(
                        meeting_date=first_meeting_date,
                        start_rate=start_rate,
                        end_rate=None,
                        rate_diff=None,
                    )
                )
                previous_rate = None

        return meeting_rate_info

    def _calculate_meeting_rate_changes(self) -> List[RateChangePerMeeting]:
        """Calculate rate changes for each meeting from futures data."""
        logger.info("Calculating rate changes for each meeting from futures data.")
        rate_changes: List[RateChangePerMeeting] = []
        meeting_rate_info = self._infer_period_rates_from_period_without_meetings()

        # Create lookup for faster access
        meeting_lookup = {
            mbf.get("first_meeting_date"): mbf
            for mbf in self.meetings_by_futures
            if mbf.get("first_meeting_date") is not None
        }

        for rate_info in meeting_rate_info:
            meeting_by_future = meeting_lookup.get(rate_info["meeting_date"])

            if meeting_by_future is None:
                continue

            settlement_date = meeting_by_future["futures_contract_end_date"]
            contract_days = meeting_by_future["futures_contract_days"]
            future_implied_rate = meeting_by_future["futures_implied_rate"]
            meeting_date = rate_info["meeting_date"]

            logger.info(f"Calculating missing rates for: {meeting_date}.")
            # Calculate missing rates
            if rate_info["start_rate"] is None and rate_info["end_rate"] is not None:
                calculated_rate = self._calculate_fedfunds_futures_rate(
                    settlement_date,
                    contract_days,
                    meeting_date,
                    future_implied_rate,
                    rate_info["end_rate"],
                    FedFuturesRateType.START,
                )
                rate_info["start_rate"] = calculated_rate
            elif rate_info["end_rate"] is None and rate_info["start_rate"] is not None:
                calculated_rate = self._calculate_fedfunds_futures_rate(
                    settlement_date,
                    contract_days,
                    meeting_date,
                    future_implied_rate,
                    rate_info["start_rate"],
                    FedFuturesRateType.END,
                )
                rate_info["end_rate"] = calculated_rate

            # Calculate rate difference
            if (
                rate_info["start_rate"] is not None
                and rate_info["end_rate"] is not None
            ):
                rate_diff = rate_info["end_rate"] - rate_info["start_rate"]
                rate_changes.append(
                    RateChangePerMeeting(rate_diff=rate_diff, meeting_date=meeting_date)
                )
        return rate_changes

    # __________________________________________________________
    # 3. FINAL PROBABILITY MATRIX CALCULATION
    # __________________________________________________________

    def generate_probability_matrix(self):
        """Generate probability matrix for Fed interest rate changes from futures prices.

        This function processes futures contracts with rate changes to calculate
        probabilities of interest rate changes at each central bank meeting.
        """
        logger.info(
            "Generating probability matrix for Fed interest rate changes from futures prices."
        )
        rate_changes = self._calculate_meeting_rate_changes()
        is_initial = True

        logger.info("Applying linear interpolation for probability calculation.")
        for rate_change in rate_changes:
            rate_diff_bps = rate_change["rate_diff"] * 100
            self._apply_linear_interpolation(rate_diff_bps, is_initial=is_initial)
            is_initial = False

        logger.info("Formatting probabilities.")
        self._format_probabilities()


class MutanFuturesProbabilityMatrixService(ProbabilityMatrixBaseService):
    """Service for probability matrix calculation for Mutan Futures."""

    def __init__(
        self,
        initial_base_rate: float,
        future_prices: List[StirFuturesModel],
        meeting_dates: List[datetime],
    ):
        super().__init__(initial_base_rate, future_prices, meeting_dates)

    # __________________________________________________________
    # 1. IMPLIED RATE / PRICE CALCULATION
    # __________________________________________________________

    def _calculate_mutan_futures_average_rate(
        self,
        future_settlement_date: date,
        contract_days: int,
        meeting_date: date,
        future_rate: float,
        base_rate: float,
    ) -> float:
        """Calculate the average rate for a given Mutan Futures.

        Based on Future price calculation on:
        https://www.tfx.co.jp/en/wholesale/products/tona.html
        """
        days_after_meeting = (future_settlement_date - meeting_date).days
        days_before_meeting = contract_days - days_after_meeting

        if days_after_meeting <= 0:
            raise ValueError("Meeting date must be before settlement date")

        daily_rate_factor = 1 + (base_rate / 100) / DAYS_PER_YEAR
        discounted_base_rate = daily_rate_factor ** (-days_before_meeting)

        future_rate_factor = 1 + (contract_days / DAYS_PER_YEAR) * (future_rate / 100)
        compound_factor = (future_rate_factor * discounted_base_rate) ** (
            1 / days_after_meeting
        )

        return (compound_factor - 1) * DAYS_PER_YEAR * 100

    def _calculate_mutan_futures_price_with_two_period(
        self,
        base_rate: float,
        first_rate: float,
        second_rate: float,
        first_meeting_date: date,
        second_meeting_date: date,
        future_settlement_date: date,
        contract_days: int,
    ) -> float:
        """Calculate the price for a given Mutan Futures with two meeting dates."""
        days_after_second = (future_settlement_date - second_meeting_date).days
        days_between_meetings = (second_meeting_date - first_meeting_date).days
        days_before_first = contract_days - (days_after_second + days_between_meetings)

        if days_before_first < 0 or days_between_meetings < 0 or days_after_second < 0:
            raise ValueError("Invalid date sequence for meetings and settlement")

        daily_rate_factor = 1 / (100 * DAYS_PER_YEAR)
        compounded_base = (1 + base_rate * daily_rate_factor) ** days_before_first
        compounded_first = (1 + first_rate * daily_rate_factor) ** days_between_meetings
        compounded_second = (1 + second_rate * daily_rate_factor) ** days_after_second

        par_rate = compounded_base * compounded_first * compounded_second - 1
        annualized_par_rate = (
            par_rate * 100 * DAYS_PER_YEAR / MUTAN_FUTURES_AVERAGE_DAYS
        )

        return 100 - annualized_par_rate

    # __________________________________________________________
    # 2. ONE PERIOD PROBABILITY CALCULATION
    # __________________________________________________________

    def _calculate_probability_distribution_for_mutan_futures_with_two_period(
        self,
        base_rate: float,
        future_price: float,
        settlement_date: date,
        contract_days: int,
        first_meeting_date: date,
        second_meeting_date: date,
    ) -> pd.DataFrame:
        """Calculate probability distribution for Mutan Futures with two meetings.

        Creates a dataframe with different rate scenarios and their probabilities
        based on inverse distance weighting from the actual future price.

        Final dataframe columns:
        - first_rate_step: Rate step change for first meeting
        - second_rate_step: Rate step change for second meeting
        - total_step: Cumulative rate step change (first_rate_step + second_rate_step)
        - first_rate: Rate after first meeting
        - second_rate: Rate after second meeting
        - price: Futures price based on rates of scenario
        - distance: Absolute distance between market future price and price of scenario.
            The closer the distance, the more likely the scenario is reflecting
            the market price.
        - reverse_distance: Reverse distance to allocate heavier weight to scenarios
            closer to the market price
        - probability: Probability for each scenario based on inverse distance weighting.
        """
        # Generate all possible outcomes of rate changes
        rate_combinations = [
            (-STEP_SIZE, -STEP_SIZE),
            (-STEP_SIZE, 0),
            (0, -STEP_SIZE),
            (0, 0),
            (0, STEP_SIZE),
            (STEP_SIZE, 0),
            (STEP_SIZE, STEP_SIZE),
        ]

        df_prob = pd.DataFrame(
            {
                "first_rate_step": [fc[0] for fc in rate_combinations],
                "second_rate_step": [fc[1] for fc in rate_combinations],
            }
        )

        # Calculate rates and prices for each scenario
        df_prob["total_step"] = df_prob["first_rate_step"] + df_prob["second_rate_step"]
        df_prob["first_rate"] = base_rate + df_prob["first_rate_step"] / 100
        df_prob["second_rate"] = base_rate + df_prob["second_rate_step"] / 100

        # Vectorized price calculation
        df_prob["price"] = df_prob.apply(
            lambda row: self._calculate_mutan_futures_price_with_two_period(
                base_rate,
                row["first_rate"],
                row["second_rate"],
                first_meeting_date,
                second_meeting_date,
                settlement_date,
                contract_days,
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
        self, prob_df: pd.DataFrame, step_keys: List[int]
    ) -> List[TwoMeetingsTotalProbabilitiesByStep]:
        """Calculate total probabilities for each step from probability dataframe
        for each meeting date.

        For each step value X in step_keys:
        - First meeting probability: Sum of all probabilities where first_rate_step == X
        (i.e., aggregate all scenarios where the first meeting results in step X)
        - Second meeting probability: Sum of all probabilities where total_step == X
        (i.e., aggregate all scenarios where the cumulative rate change after both
        meetings equals step X)
        """
        total_probabilities: List[TwoMeetingsTotalProbabilitiesByStep] = []
        for step_key in step_keys:
            # Aggregate probabilities for first meeting: sum where first_rate_step matches
            first_meeting_mask = prob_df["first_rate_step"] == step_key
            p_1 = (
                float(prob_df.loc[first_meeting_mask, "probability"].sum())
                if first_meeting_mask.any()
                else 0.0
            )

            # Aggregate probabilities for second meeting: sum where total_step matches
            second_meeting_mask = prob_df["total_step"] == step_key
            p_2 = (
                float(prob_df.loc[second_meeting_mask, "probability"].sum())
                if second_meeting_mask.any()
                else 0.0
            )

            total_probabilities.append(
                TwoMeetingsTotalProbabilitiesByStep(
                    step=step_key, first_meeting_prob=p_1, second_meeting_prob=p_2
                )
            )
        return total_probabilities

    def _calculate_initial_single_meeting_probabilities(
        self,
        base_rate: float,
        settlement_date: date,
        contract_days: int,
        meeting_date: date,
        future_implied_rate: float,
    ):
        """Calculate initial probabilities for single meeting case."""
        logger.info("Calculating initial probabilities for single meeting case.")
        meeting_implied_rate = self._calculate_mutan_futures_average_rate(
            settlement_date,
            contract_days,
            meeting_date,
            future_implied_rate,
            base_rate,
        )

        # Calculate rate change in basis points
        rate_change_bps = (meeting_implied_rate - base_rate) * 100
        self._apply_linear_interpolation(rate_change_bps, is_initial=True)

    def _calculate_initial_two_meetings_probabilities(
        self,
        base_rate: float,
        future_price: float,
        settlement_date: date,
        contract_days: int,
        first_meeting_date: date,
        second_meeting_date: date,
    ):
        """Calculate initial probabilities for two meetings case."""
        logger.info("Calculating initial probabilities for two meetings case.")
        prob_df = (
            self._calculate_probability_distribution_for_mutan_futures_with_two_period(
                base_rate,
                future_price,
                settlement_date,
                contract_days,
                first_meeting_date,
                second_meeting_date,
            )
        )

        step_keys = [
            meeting_probability["expected_rate_step"]
            for meeting_probability in self.probability_matrix
        ]
        total_probabilities = self._get_total_probabilities_from_dataframe(
            prob_df, step_keys
        )

        # Create a lookup dict for faster access
        prob_lookup = {prob["step"]: prob for prob in total_probabilities}

        # Update meeting_probabilities with the calculated probabilities
        default_prob_pair = TwoMeetingsTotalProbabilitiesByStep(
            step=0,
            first_meeting_prob=0.0,
            second_meeting_prob=0.0,
        )
        for meeting_probability in self.probability_matrix:
            step_key = meeting_probability["expected_rate_step"]
            prob_pair = prob_lookup.get(step_key, default_prob_pair)
            meeting_probability["probabilities"].extend(
                [prob_pair["first_meeting_prob"], prob_pair["second_meeting_prob"]]
            )

    def _calculate_single_meeting_probabilities(
        self,
        base_rate: float,
        settlement_date: date,
        contract_days: int,
        first_meeting_date: date,
        future_implied_rate: float,
    ):
        """Calculate probabilities for subsequent single meeting."""
        logger.info("Calculating probabilities for subsequent single meeting.")
        meeting_implied_rate = self._calculate_mutan_futures_average_rate(
            settlement_date,
            contract_days,
            first_meeting_date,
            future_implied_rate,
            base_rate,
        )
        # Calculate rate change in basis points
        rate_change_bps = (meeting_implied_rate - base_rate) * 100
        self._apply_linear_interpolation(rate_change_bps, is_initial=False)

    def _calculate_two_meetings_probabilities(
        self,
        base_rate: float,
        future_price: float,
        settlement_date: date,
        contract_days: int,
        first_meeting_date: date,
        second_meeting_date: date,
    ):
        """Calculate probabilities for subsequent two meetings case."""
        logger.info("Calculating probabilities for subsequent two meetings case.")
        if not self.probability_matrix:
            return

        # Extend support
        self._extend_probability_support()

        # Calculate new probabilities
        prob_df = (
            self._calculate_probability_distribution_for_mutan_futures_with_two_period(
                base_rate,
                future_price,
                settlement_date,
                contract_days,
                first_meeting_date,
                second_meeting_date,
            )
        )

        # Extract probabilities for standard step keys
        new_total_probabilities = self._get_total_probabilities_from_dataframe(
            prob_df, STANDARD_STEP_SCENARIOS
        )

        # Create lookup for new probabilities from dataframe
        new_prob_lookup = {prob["step"]: prob for prob in new_total_probabilities}
        last_prob_idx = self._get_last_probability_index()

        # Default probability pair
        default_prob_pair: TwoMeetingsTotalProbabilitiesByStep = {
            "step": 0,
            "first_meeting_prob": 0.0,
            "second_meeting_prob": 0.0,
        }

        # Get probability pairs for standard steps, defaulting to zero if not found
        prob_unchanged = new_prob_lookup.get(0, default_prob_pair)
        prob_positive_step = new_prob_lookup.get(STEP_SIZE, default_prob_pair)
        prob_negative_step = new_prob_lookup.get(-STEP_SIZE, default_prob_pair)
        prob_positive_two_steps = new_prob_lookup.get(2 * STEP_SIZE, default_prob_pair)
        prob_negative_two_steps = new_prob_lookup.get(-2 * STEP_SIZE, default_prob_pair)

        # Update probabilities for each step
        for meeting_probability in self.probability_matrix:
            step_key = meeting_probability["expected_rate_step"]

            # Get previous probabilities for adjacent steps
            prev_prob_unchanged = self._get_probability_value(step_key, last_prob_idx)
            prev_prob_negative_step = self._get_probability_value(
                step_key - STEP_SIZE, last_prob_idx
            )
            prev_prob_positive_step = self._get_probability_value(
                step_key + STEP_SIZE, last_prob_idx
            )
            prev_prob_negative_two_steps = self._get_probability_value(
                step_key - 2 * STEP_SIZE, last_prob_idx
            )
            prev_prob_positive_two_steps = self._get_probability_value(
                step_key + 2 * STEP_SIZE, last_prob_idx
            )

            # Calculate probability for first meeting
            p_1 = (
                prev_prob_unchanged * prob_unchanged["first_meeting_prob"]
                + prev_prob_negative_step * prob_positive_step["first_meeting_prob"]
                + prev_prob_positive_step * prob_negative_step["first_meeting_prob"]
            )

            # Calculate probability for second meeting
            p_2 = (
                prev_prob_unchanged * prob_unchanged["second_meeting_prob"]
                + prev_prob_negative_step * prob_positive_step["second_meeting_prob"]
                + prev_prob_positive_step * prob_negative_step["second_meeting_prob"]
                + prev_prob_negative_two_steps
                * prob_positive_two_steps["second_meeting_prob"]
                + prev_prob_positive_two_steps
                * prob_negative_two_steps["second_meeting_prob"]
            )

            meeting_probability["probabilities"].extend([p_1, p_2])

    def generate_probability_matrix(self):
        """Generate probability matrix for BOJ interest rate changes from futures prices.

        This function processes futures contracts and meeting dates to calculate
        probabilities of interest rate changes at each central bank meeting.
        """
        logger.info(
            "Generating probability matrix for BOJ interest rate changes from futures prices."
        )
        is_initial = True
        base_rate = self.initial_base_rate

        for meeting_by_future in self.meetings_by_futures:
            first_meeting_date = meeting_by_future.get("first_meeting_date")
            second_meeting_date = meeting_by_future.get("second_meeting_date")
            nb_meetings = meeting_by_future.get("nb_meetings")
            future_price = meeting_by_future.get("futures_price")
            future_implied_rate = meeting_by_future.get("futures_implied_rate")
            settlement_date = meeting_by_future.get("futures_contract_end_date")
            contract_days = meeting_by_future.get("futures_contract_days")

            logger.info(
                f"Getting probabilities for: {first_meeting_date} and {second_meeting_date}."
            )
            if nb_meetings == 0:
                continue

            # Validate that we have the required meeting dates
            if nb_meetings == 1 and first_meeting_date is None:
                raise ValueError("First meeting date is required for single meeting")
            if nb_meetings == 2 and (
                first_meeting_date is None or second_meeting_date is None
            ):
                raise ValueError(
                    "First meeting and second meeting date are required for two meetings"
                )

            if is_initial:
                if nb_meetings == 1:
                    assert first_meeting_date is not None
                    self._calculate_initial_single_meeting_probabilities(
                        base_rate,
                        settlement_date,
                        contract_days,
                        first_meeting_date,
                        future_implied_rate,
                    )

                elif nb_meetings == 2:
                    assert (
                        first_meeting_date is not None
                        and second_meeting_date is not None
                    )
                    self._calculate_initial_two_meetings_probabilities(
                        base_rate,
                        future_price,
                        settlement_date,
                        contract_days,
                        first_meeting_date,
                        second_meeting_date,
                    )

                is_initial = False

            else:
                if nb_meetings == 1:
                    assert first_meeting_date is not None
                    self._calculate_single_meeting_probabilities(
                        base_rate,
                        settlement_date,
                        contract_days,
                        first_meeting_date,
                        future_implied_rate,
                    )

                elif nb_meetings == 2:
                    assert (
                        first_meeting_date is not None
                        and second_meeting_date is not None
                    )
                    self._calculate_two_meetings_probabilities(
                        base_rate,
                        future_price,
                        settlement_date,
                        contract_days,
                        first_meeting_date,
                        second_meeting_date,
                    )

            base_rate = future_implied_rate

        self._format_probabilities()


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
    match central_bank:
        case CentralBankChoices.FRB:
            return 3.875
        case CentralBankChoices.BOJ:
            base_rate_obj = MarketPriceModel.objects.get(
                date=target_date,
                asset__short_name=CENTRAL_BANK_TARGET_RATE_MAP[central_bank],
            )
            return base_rate_obj.price
        case CentralBankChoices.ECB:
            return 2.15
        case _:
            raise ValueError(f"Invalid central bank: {central_bank}")


def get_central_bank_probability_matrices(
    target_date: date,
    central_banks: List[CentralBankChoices] = [],
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
    meeting_dates_lookup = {
        meeting_data["central_bank"]: meeting_data["meeting_dates"]
        for meeting_data in all_meeting_dates
    }
    future_prices_lookup = {
        cb: [fp for fp in all_future_prices if fp.central_bank == cb]
        for cb in central_banks_to_process
    }

    cb_probability_matrices: List[CentralBankProbabilityMatrix] = []
    for central_bank in central_banks_to_process:
        logger.info(f"Processing probability matrix for {central_bank}")

        # Get initial base rate
        initial_base_rate = get_central_bank_effective_rate(central_bank, target_date)

        # Get meeting dates
        meeting_dates = meeting_dates_lookup.get(central_bank)
        if not meeting_dates:
            raise ValueError(f"No meeting dates found for {central_bank}. ")

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
    """Calculate probability change matrix."""
    previous_by_step = {
        entry["expected_rate_step"]: entry["probabilities"]
        for entry in previous_probability_matrix["probability_matrix"]
    }

    probability_change_matrix: List[ProbabilitiesByStep] = []
    for current_entry in probability_matrix["probability_matrix"]:
        rate_step = current_entry["expected_rate_step"]
        current_probs = current_entry["probabilities"]
        previous_probs = previous_by_step.get(rate_step, [])

        differences = []
        for meeting_idx, current_prob in enumerate(current_probs):
            previous_prob = previous_probs[meeting_idx]
            difference = current_prob - previous_prob
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
