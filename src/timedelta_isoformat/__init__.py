"""Supplemental ISO8601 duration format support for :py:class:`datetime.timedelta`"""
import datetime
from enum import StrEnum
from typing import Iterable, Tuple, TypeAlias, Union
from dataclasses import dataclass

_DECIMAL_CHARACTERS = frozenset("0123456789" + ",.")


class DateUnit(StrEnum):
    Y = YEARS = "years"
    M = MONTHS = "months"
    D = DAYS = "days"


class TimeUnit(StrEnum):
    H = HOURS = "hours"
    M = MINUTES = "minutes"
    S = SECONDS = "seconds"


class WeekUnit(StrEnum):
    W = WEEKS = "weeks"


RawValue: TypeAlias = str
Unit: TypeAlias = DateUnit | TimeUnit | WeekUnit
MeasurementLimit: TypeAlias = int | None
MeasuredValue: TypeAlias = float

Components: TypeAlias = Iterable[Tuple[RawValue, Unit, MeasurementLimit]]
Measurements: TypeAlias = Iterable[Tuple[Unit, MeasuredValue]]


class Duration(object):
    # TODO: update
    """Subclass of :py:class:`datetime.timedelta` with additional methods to implement
    ISO8601-style parsing and formatting.
    """
    def __init__(
        self,
        years: int | float = 0.0,
        months: int | float = 0.0,
        weeks: int | float = 0.0,
        days: int | float = 0.0,
        hours: int | float = 0.0,
        minutes: int | float = 0.0,
        seconds: int | float = 0.0,
    ):
        self.years = float(years)
        self.months = float(months)
        self.weeks = float(weeks)
        self.days = float(days)
        self.hours = float(hours)
        self.minutes = float(minutes)
        self.seconds = float(seconds)

    def __repr__(self) -> str:
        return "Duration(" + ', '.join([
            attr + '=' + str(getattr(self, attr))
            for attr
            in (
                "years", "months", "weeks", "days", "hours", "minutes", "seconds"
            )
            if getattr(self, attr)
        ]) + ")"

    @staticmethod
    def _from_date(segment: str) -> Components:
        match tuple(segment):
            # YYYY-DDD
            case _, _, _, _, "-", _, _, _:
                yield segment[0:4], DateUnit.YEARS, None
                yield segment[5:8], DateUnit.DAYS, 366
            # YYYY-MM-DD
            case _, _, _, _, "-", _, _, "-", _, _:
                yield segment[0:4], DateUnit.YEARS, None
                yield segment[5:7], DateUnit.MONTHS, 12
                yield segment[8:10], DateUnit.DAYS, 31
            # YYYYDDD
            case _, _, _, _, _, _, _:
                yield segment[0:4], DateUnit.YEARS, None
                yield segment[4:7], DateUnit.DAYS, 366
            # YYYYMMDD
            case _, _, _, _, _, _, _, _:
                yield segment[0:4], DateUnit.YEARS, None
                yield segment[4:6], DateUnit.MONTHS, 12
                yield segment[6:8], DateUnit.DAYS, 31
            case _:
                raise ValueError(f"unable to parse '{segment}' into date components")

    @staticmethod
    def _from_time(segment: str) -> Components:
        match tuple(segment):
            # HH:MM:SS[.ssssss]
            case _, _, ":", _, _, ":", _, _, ".", *_:
                yield segment[0:2], TimeUnit.HOURS, 24
                yield segment[3:5], TimeUnit.MINUTES, 60
                yield segment[6:15], TimeUnit.SECONDS, 60
            # HH:MM:SS
            case _, _, ":", _, _, ":", _, _:
                yield segment[0:2], TimeUnit.HOURS, 24
                yield segment[3:5], TimeUnit.MINUTES, 60
                yield segment[6:8], TimeUnit.SECONDS, 60
            # HHMMSS[.ssssss]
            case _, _, _, _, _, _, ".", *_:
                yield segment[0:2], TimeUnit.HOURS, 24
                yield segment[2:4], TimeUnit.MINUTES, 60
                yield segment[4:13], TimeUnit.SECONDS, 60
            # HHMMSS
            case _, _, _, _, _, _:
                yield segment[0:2], TimeUnit.HOURS, 24
                yield segment[2:4], TimeUnit.MINUTES, 60
                yield segment[4:6], TimeUnit.SECONDS, 60
            case _:
                raise ValueError(f"unable to parse '{segment}' into time components")

    @staticmethod
    def _from_designators(duration: str) -> Components:
        """Parser for designator-separated ISO-8601 duration strings

        The code sweeps through the input exactly once, expecting to find measurements
        in order of largest-to-smallest unit from left-to-right (with the exception of
        week measurements, which must be the only measurement in the string if present).
        """
        date_context = {"D": "days", "M": "months", "Y": "years"}
        time_context = {"S": "seconds", "M": "minutes", "H": "hours"}
        week_context = {"W": "weeks"}

        context, value, values_found = date_context, "", False
        for char in duration:
            if char in _DECIMAL_CHARACTERS:
                value += char
                continue

            if char == "T" and context is not time_context:
                assert not value, f"expected a unit designator after '{value}'"
                context = time_context
                continue

            if char == "W" and context is date_context:
                context = week_context
                pass

            while context:
                designator, unit = context.popitem()
                if designator == char:
                    break
            else:
                raise ValueError(f"unexpected character '{char}'")

            assert len(week_context) or not values_found, "cannot mix weeks with other units"
            yield value, unit, None
            value, values_found = "", True

        assert values_found, "no measurements found"

    @classmethod
    def _from_duration(cls, duration: str) -> Measurements:
        """Selects and runs an appropriate parser for ISO-8601 duration strings

        The format of these strings is composed of two segments; date measurements
        are situated between the 'P' and 'T' characters, and time measurements are
        situated between the 'T' character and the end-of-string.

        If no unit designator is found at the end of the duration string, then
        an attempt is made to parse the segment as a fixed-length date or time.
        """
        assert duration.startswith("P"), "durations must begin with the character 'P'"

        if duration[-1].isupper():
            components = cls._from_designators(duration[1:])
            yield from cls._to_measurements(components, inclusive_limit=True)
            return

        date_segment, _, time_segment = duration[1:].partition("T")
        if date_segment:
            components = cls._from_date(date_segment)
            yield from cls._to_measurements(components, inclusive_limit=True)
        if time_segment:
            components = cls._from_time(time_segment)
            yield from cls._to_measurements(components, inclusive_limit=False)

    @staticmethod
    def _to_measurements(components: Components, inclusive_limit: bool) -> Measurements:
        for value, unit, limit in components:
            try:
                assert value[0].isdigit()
                quantity = float("+" + value.replace(",", "."))
            except (AssertionError, IndexError, ValueError) as exc:
                msg = f"unable to parse '{value}' as a positive decimal"
                raise ValueError(msg) from exc
            if quantity:
                yield unit, quantity
            if limit and (quantity > limit if inclusive_limit else quantity >= limit):
                bounds = f"[0..{limit}" + ("]" if inclusive_limit else ")")
                raise ValueError(f"{unit} value of {value} exceeds range {bounds}")

    @classmethod
    def fromisoformat(cls, duration: str) -> "Duration":
        """Parses an input string and returns a :py:class:`Duration` result

        :raises: `ValueError` with an explanatory message when parsing fails
        """
        try:
            return cls(**dict(cls._from_duration(duration)))
        except (AssertionError, ValueError) as exc:
            raise ValueError(f"could not parse  duration '{duration}': {exc}") from exc

    def __bool__(self) -> bool:
        return bool(self.years or self.months or self.days or self.hours or self.minutes or self.seconds)


    def isoformat(self) -> str:
        """Produce an ISO8601-style representation of this :py:class:`timedelta`"""
        # TODO: years, months
        if not self:
            return "P0D"

        result = "P"
        # TODO: move function out
        def _format_as_integer_if_possible(number: float) -> str:
            return f"{number:.6f}".rstrip("0").rstrip(".") # TODO: on the one hand this number of decimal places feels arbitrary, but on the other hand I don't want the iso format durations to be full of extremely long floats to the 20th decimal place
        result += f"{_format_as_integer_if_possible(self.years)}Y" if self.years else ""
        result += f"{_format_as_integer_if_possible(self.months)}M" if self.months else ""
        result += f"{_format_as_integer_if_possible(self.days)}D" if self.days else ""
        
        if self.hours or self.minutes or self.seconds:
            result += "T"
            result += f"{_format_as_integer_if_possible(self.hours)}H" if self.hours else ""
            result += f"{_format_as_integer_if_possible(self.minutes)}M" if self.minutes else ""
            result += f"{_format_as_integer_if_possible(self.seconds)}S" if self.seconds else ""
        return result
    
    # TODO: template type
    def __add__(self, other: Union[datetime.datetime, datetime.timedelta, "Duration"]):
        # TODO: I couldn't find anything in ISO 8601 wikipedia page about whether to apply right to left or left to right.
        # TODO: come up with a test case that differs on this distinction. Feb 28 + P1M1D. If we apply the month first, then it's March 29th. If we apply the day first then it's April 1st
        if isinstance(other, datetime.datetime):            
            end_time = other
            
            # we add seconds and days separately in case there are leap seconds
            # TODO: seconds > 86400 added to a day before a leap second
            
            # Leap seconds are ignored. Reasons: https://stackoverflow.com/questions/39686553/what-does-python-return-on-the-leap-second
            end_time += datetime.timedelta(
                days=self.days + (7.0 * self.weeks),
                hours=self.hours,
                minutes=self.minutes,
                seconds=self.seconds
            )

            # TODO: fractional months, e.g. P0.5M. Does that end up with a fractional day in an odd numbered month? :vomit:
            # for now, months are rounded, but that it definitely wrong
            new_zero_indexed_month = end_time.month - 1 + round(self.months)
            end_time = end_time.replace(
                month = (new_zero_indexed_month % 12) + 1,
            )

            new_year = end_time.year + round(self.years) + (new_zero_indexed_month // 12)
            end_time = end_time.replace(
                year = new_year,
            )

            return end_time
        elif isinstance(other, datetime.timedelta):
            return Duration(
                years = self.years,
                months = self.months,
                days = self.days + other.days,
                hours = self.hours,
                minutes = self.minutes,
                seconds = self.seconds + other.seconds,
            )
        elif isinstance(other, Duration):
            return Duration(
                years = self.years + other.years,
                months = self.months + other.months,
                days = self.days + other.days,
                hours = self.hours + other.hours,
                minutes = self.minutes + other.minutes,
                seconds = self.seconds + other.seconds,
            )
        raise TypeError(f"Cannot add Duration and {type(other).__name__}")
    
    # TODO: either implement all rich comparison methods or use functools.total_ordering
    def __eq__(self, other):
        return (
            self.years == other.years and
            self.months == other.months and
            self.days == other.days and
            self.hours == other.hours and
            self.minutes == other.minutes and
            self.seconds == other.seconds
        )

# TODO: test crossing DST