"""Temporal train / calibration / test splits for modeling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import pandas as pd


@dataclass(frozen=True)
class SplitSpec:
    strategy: str
    train_years: Tuple[int, ...]
    test_years: Tuple[int, ...]
    train_rows: int
    test_rows: int
    calibration_years: Tuple[int, ...] = ()
    calibration_rows: int = 0


def _eligible_years(
    frame: pd.DataFrame,
    *,
    year_column: str,
    label_column: str,
    min_positive_rate: float,
) -> Tuple[int, ...]:
    years = sorted(int(year) for year in frame[year_column].dropna().unique())
    eligible = []
    for year in years:
        subset = frame.loc[frame[year_column] == year, label_column]
        if subset.empty:
            continue
        if float(subset.mean()) >= min_positive_rate:
            eligible.append(year)
    return tuple(eligible)


def _eligible_test_years(
    frame: pd.DataFrame,
    *,
    year_column: str,
    label_column: str,
    test_year_count: int,
    min_positive_rate: float,
) -> Tuple[int, ...]:
    eligible = list(
        _eligible_years(
            frame,
            year_column=year_column,
            label_column=label_column,
            min_positive_rate=min_positive_rate,
        )
    )
    years = sorted(int(year) for year in frame[year_column].dropna().unique())
    if len(eligible) < test_year_count:
        raise ValueError(
            "Not enough analytic years with informative labels for the requested test split."
        )
    if len(years) < test_year_count + 1:
        raise ValueError(
            f"Need at least {test_year_count + 1} analytic years for a time-based split."
        )
    return tuple(eligible[-test_year_count:])


def time_based_year_split(
    frame: pd.DataFrame,
    *,
    year_column: str = "analytic_year",
    label_column: Optional[str] = None,
    test_year_count: int = 2,
    min_positive_rate: float = 0.01,
    calibration_year_count: int = 0,
) -> Tuple[pd.DataFrame, pd.DataFrame, SplitSpec]:
    """Hold out recent analytic years that still have informative labels.

    When ``calibration_year_count`` > 0, the latest train years are carved into a
    temporal calibration set (strictly before test years).
    """
    years = sorted(int(year) for year in frame[year_column].dropna().unique())
    if label_column:
        test_years = _eligible_test_years(
            frame,
            year_column=year_column,
            label_column=label_column,
            test_year_count=test_year_count,
            min_positive_rate=min_positive_rate,
        )
        # Caller should pre-filter near-zero years; remaining non-test years form the train pool.
        candidate_train = [year for year in years if year not in test_years]
    else:
        if len(years) < test_year_count + 1:
            raise ValueError(
                f"Need at least {test_year_count + 1} analytic years for a time-based split."
            )
        test_years = tuple(years[-test_year_count:])
        candidate_train = [year for year in years if year not in test_years]

    calibration_years: Tuple[int, ...] = ()
    if calibration_year_count > 0:
        if len(candidate_train) <= calibration_year_count:
            raise ValueError(
                "Not enough informative train years to carve a temporal calibration set."
            )
        calibration_years = tuple(candidate_train[-calibration_year_count:])
        train_years = tuple(year for year in candidate_train if year not in calibration_years)
    else:
        train_years = tuple(candidate_train)

    train = frame[frame[year_column].isin(train_years)].copy()
    test = frame[frame[year_column].isin(test_years)].copy()
    calibration = frame[frame[year_column].isin(calibration_years)].copy() if calibration_years else frame.iloc[0:0]
    spec = SplitSpec(
        strategy="time_based_year_holdout",
        train_years=train_years,
        test_years=test_years,
        train_rows=len(train),
        test_rows=len(test),
        calibration_years=calibration_years,
        calibration_rows=len(calibration),
    )
    return train, test, spec


def calibration_frame(
    frame: pd.DataFrame,
    *,
    year_column: str,
    calibration_years: Tuple[int, ...],
) -> pd.DataFrame:
    if not calibration_years:
        return frame.iloc[0:0].copy()
    return frame[frame[year_column].isin(calibration_years)].copy()
