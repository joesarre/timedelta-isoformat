"""Supplemental ISO8601 duration format support for :py:class:`datetime.timedelta`"""
import datetime
import pytz
from enum import StrEnum
from functools import total_ordering
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

@total_ordering
class Duration(object):
    """
    ISO8601 duration format support
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
        date_context = {"D": "days", "W": "weeks", "M": "months", "Y": "years"}
        time_context = {"S": "seconds", "M": "minutes", "H": "hours"}

        context, value, values_found = date_context, "", False
        for char in duration:
            if char in _DECIMAL_CHARACTERS:
                value += char
                continue

            if char == "T" and context is not time_context:
                assert not value, f"expected a unit designator after '{value}'"
                context = time_context
                continue

            while context:
                designator, unit = context.popitem()
                if designator == char:
                    break
            else:
                raise ValueError(f"unexpected character '{char}'")

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

    @classmethod
    def from_timedelta(cls, td: datetime.timedelta) -> "Duration":
        return cls(days=td.days, seconds=td.seconds + (td.microseconds / 1000000.0))

    def __bool__(self) -> bool:
        return bool(self.years or self.months or self.weeks or self.days or self.hours or self.minutes or self.seconds)


    def isoformat(self) -> str:
        """Produce an ISO8601-style representation of this :py:class:`timedelta`"""
        if not self:
            return "P0D"

        result = "P"
        result += f"{_format_as_integer_if_possible(self.years)}Y" if self.years else ""
        result += f"{_format_as_integer_if_possible(self.months)}M" if self.months else ""
        result += f"{_format_as_integer_if_possible(self.weeks)}W" if self.weeks else ""
        result += f"{_format_as_integer_if_possible(self.days)}D" if self.days else ""
        
        if self.hours or self.minutes or self.seconds:
            result += "T"
            result += f"{_format_as_integer_if_possible(self.hours)}H" if self.hours else ""
            result += f"{_format_as_integer_if_possible(self.minutes)}M" if self.minutes else ""
            result += f"{_format_as_integer_if_possible(self.seconds)}S" if self.seconds else ""
        return result
    
    def __add__(self, other: Union[datetime.datetime, datetime.timedelta, "Duration"]) -> Union[datetime.datetime, "Duration"]:
        # I couldn't find anything in ISO 8601 wikipedia page about whether to apply right to left or left to right.
        # Feb 28 + P1M1D differs on this distinction. If we apply the month first, then it's March 29th. If we apply the day first then it's April 1st
        # In this case we choose to apply the month first, because it's more intuitive to me.
        if isinstance(other, datetime.datetime):
            end_time = other

            # fractional months are not supported, because the behaviour is not well defined
            if self.months % 1 != 0:
                raise ValueError("fractional months are not supported")
            
            # we add the integer and fractional components of months separately
            new_zero_indexed_month = end_time.month - 1 + round(self.months)
            new_year = end_time.year + round(self.years) + (new_zero_indexed_month // 12)
            end_time = end_time.replace(
                year = new_year,
            )

            end_time = end_time.replace(
                month = (new_zero_indexed_month % 12) + 1,
            )
            

            # we add days ignoring time
            naive_time = end_time.replace(tzinfo=None)
            naive_time += datetime.timedelta(
                days=self.days + (7.0 * self.weeks),
            )
            end_time = end_time.tzinfo.localize(naive_time) if end_time.tzinfo else naive_time

            # if the datetime is timezone aware, then we add hours in UTC, because the specification says that
            # a day is not necessarily 24 hours around a DST boundary (https://en.wikipedia.org/wiki/ISO_8601#Durations)
            utc_time = end_time.astimezone(pytz.utc) if end_time.tzinfo else end_time
            utc_time += datetime.timedelta(
                hours=self.hours,
                minutes=self.minutes,
                seconds=self.seconds
            )
            end_time = utc_time.astimezone(end_time.tzinfo) if end_time.tzinfo else utc_time

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
    
    def __radd__(self, other):
        return self.__add__(other)

    def __eq__(self, other):
        return (
            self.years == other.years and
            self.months == other.months and
            self.weeks == other.weeks and
            self.days == other.days and
            self.hours == other.hours and
            self.minutes == other.minutes and
            self.seconds == other.seconds
        )

    def __lt__(self, other):
        return (
            self.years < other.years or
            self.months < other.months or
            self.weeks < other.weeks or
            self.days < other.days or
            self.hours < other.hours or
            self.minutes < other.minutes or
            self.seconds < other.seconds
        )

    def to_timedelta(self, start_date: datetime.datetime = None) -> datetime.timedelta:
        if not (self.years or self.months):
            start_date = datetime(1970, 1, 1) # doesn't matter what the start_date is if there are no years or months
        if start_date is None:
            raise ValueError(f"Cannot convert a Duration with years or months to a timedelta without a start date")
        return (start_date + self) - start_date


@total_ordering
class Interval(object):
    def __init__(
        self,
        start: datetime.datetime | None,
        end: datetime.datetime | None,
        duration: Duration | None,
    ):
        if start is not None and duration is None and end is not None:
            self.start = start
            self.end = end
            self.duration = Duration.from_timedelta(end - start)

        elif start is None and duration is not None and end is not None:
            self.end = end
            self.duration = duration
            self.start = end - duration

        elif start is not None and duration is not None and end is None:
            self.start = start
            self.duration = duration
            self.end = start + duration

        elif start is not None and duration is not None and end is not None:
            self.start = start
            self.duration = duration
            self.end = end

        else:
            raise ValueError(f"Interval takes at least two of start, duration and end")
        
        if self.start + self.duration != self.end:
            raise ValueError(f"Start, duration and end do not match up: {self.start} + {self.duration} = {self.start + self.duration} not {self.end}")
    
    @classmethod
    def to_timedelta(self):
        return self.end - self.start

    @classmethod
    def fromisoformat(cls, interval: str) -> "Interval":
        """Parses an ISO8601 interval input string and returns a :py:class:`Interval` result

        :raises: `ValueError` with an explanatory message when parsing fails

        There are four ways to express a time interval:

            Start and end, such as "2007-03-01T13:00:00Z/2008-05-11T15:30:00Z"
            Start and duration, such as "2007-03-01T13:00:00Z/P1Y2M10DT2H30M"
            Duration and end, such as "P1Y2M10DT2H30M/2008-05-11T15:30:00Z"
            Duration only, such as "P1Y2M10DT2H30M", with additional context information
        """
        if "/" not in interval:
            raise ValueError(f"Interval must contain a slash")
        start, end = interval.split("/")
        if start.startswith("P") and end.startswith("P"):
            raise ValueError(f"Interval cannot have two durations")
        if start.startswith("P"):
            duration = Duration.fromisoformat(start)
            end = datetime.datetime.fromisoformat(end)
            return cls(None, end, duration)
        if end.startswith("P"):
            duration = Duration.fromisoformat(end)
            start = datetime.datetime.fromisoformat(start)
            return cls(start, None, duration)
        start = datetime.datetime.fromisoformat(start)
        end = datetime.datetime.fromisoformat(end)
        return cls(start, end, None)

    def __str__(self):
        return self.isoformat()
    
    def __repr__(self):
        return f"Interval({repr(self.start)}/{repr(self.end)})"

    def __eq__(self, other: "Interval") -> bool:
        return (
            self.start == other.start and
            self.end == other.end and
            self.duration == other.duration
        )
    
    def __lt__(self, other: "Interval") -> bool:
        return self.to_timedelta() < other.to_timedelta()
    
    def isoformat(self):
        return f"{self.start.isoformat()}/{self.end.isoformat()}"


def _format_as_integer_if_possible(number: float) -> str:
    return f"{number:.6f}".rstrip("0").rstrip(".")
