"""Test coverage for :py:module:`timedelta_isoformat`"""
import unittest

from timedelta_isoformat import Duration, Interval
from datetime import datetime, timedelta
import pytz

valid_durations = [
    # empty duration
    ("P0D", Duration(), timedelta()),
    ("P0Y", Duration(), timedelta()),
    ("PT0S", Duration(), timedelta()),
    # designator-format durations
    ("P3D", Duration(days=3), timedelta(days=3)),
    ("P3DT1H", Duration(days=3, hours=1), timedelta(days=3, hours=1)),
    ("P0DT1H20M", Duration(hours=1, minutes=20), timedelta(hours=1, minutes=20)),
    ("P0Y0DT1H20M", Duration(hours=1, minutes=20), timedelta(hours=1, minutes=20)),
    # week durations
    ("P1W", Duration(weeks=1), timedelta(days=7)),
    ("P3W", Duration(weeks=3), timedelta(days=21)),
    # decimal measurements
    ("PT1.5S", Duration(seconds=1.5), timedelta(seconds=1, microseconds=500000)),
    ("P2DT0.5H", Duration(days=2, hours=0.5), timedelta(days=2, minutes=30)),
    ("PT0,01S", Duration(seconds=0.01), timedelta(seconds=0.01)),
    ("PT01:01:01.01", Duration(hours=1, minutes=1, seconds=1.01), timedelta(hours=1, minutes=1, seconds=1, microseconds=10000)),
    ("PT131211.10", Duration(hours=13, minutes=12, seconds=11.1), timedelta(hours=13, minutes=12, seconds=11, microseconds=100000)),
    ("P1.5W", Duration(weeks=1.5), timedelta(days=10, hours=12)),
    ("P1.01D", Duration(days=1.01), timedelta(days=1, seconds=864)),
    ("P1.01DT1S", Duration(days=1.01, seconds=1), timedelta(days=1, seconds=865)),
    ("P10.0DT12H", Duration(days=10, hours=12), timedelta(days=10, hours=12)),
    # date-format durations
    ("P0000000", Duration(), timedelta()),
    ("P0000000T000000", Duration(), timedelta()),
    ("P0000360", Duration(days=360), timedelta(days=360)),
    ("P00000004", Duration(days=4), timedelta(days=4)),
    ("P0000-00-05", Duration(days=5), timedelta(days=5)),
    ("P0000-00-00T01:02:03", Duration(hours=1, minutes=2, seconds=3), timedelta(hours=1, minutes=2, seconds=3)),
    ("PT040506", Duration(hours=4, minutes=5, seconds=6), timedelta(hours=4, minutes=5, seconds=6)),
    ("PT04:05:06", Duration(hours=4, minutes=5, seconds=6), timedelta(hours=4, minutes=5, seconds=6)),
    ("PT00:00:00.001", Duration(seconds=0.001), timedelta(microseconds=1000)),
    # calendar edge cases
    ("P0000-366", Duration(days=366), timedelta(days=366)),
    ("PT23:59:59", Duration(hours=23, minutes=59, seconds=59), timedelta(hours=23, minutes=59, seconds=59)),
    ("PT23:59:59.9", Duration(hours=23, minutes=59, seconds=59.9), timedelta(hours=23, minutes=59, seconds=59.9)),
    # matching datetime.Duration day-to-microsecond carry precision
    ("P0.000001D", Duration(days=0.000001), timedelta(microseconds=86400)),
    ("PT0.000001S", Duration(seconds=0.000001), timedelta(microseconds=1)),
    # mixing week units with other units
    ("P1WT1H", Duration(weeks=1, hours=1), timedelta(days=7, hours=1)),
    ("P0Y1W", Duration(weeks=1), timedelta(days=7)),

]

invalid_durations = [
    # incomplete strings
    ("", "durations must begin with the character 'P'"),
    ("T", "durations must begin with the character 'P'"),
    ("P", "no measurements found"),
    ("PT", "no measurements found"),
    ("PPT", "unexpected character 'P'"),
    ("PTT", "unexpected character 'T'"),
    ("PTP", "unexpected character 'P'"),
    # incomplete measurements
    ("P0YD", "unable to parse '' as a positive decimal"),
    # repeated designators
    ("P1DT1H3H1M", "unexpected character 'H'"),
    ("P1D3D", "unexpected character 'D'"),
    ("P0MT1HP1D", "unexpected character 'P'"),
    # incorrectly-ordered designators
    ("PT5S1M", "unexpected character 'M'"),
    ("P0DT5M1H", "unexpected character 'H'"),
    # invalid units within segment
    ("PT1DS", "unexpected character 'D'"),
    ("P1HT0S", "unexpected character 'H'"),
    # incorrect quantities
    ("PT0.0.0S", "unable to parse '0.0.0' as a positive decimal"),
    ("P1.,0D", "unable to parse '1.,0' as a positive decimal"),
    # date-format durations exceeding calendar limits
    ("P0000-367", "days value of 367 exceeds range [0..366]"),
    ("P0000-400", "days value of 400 exceeds range [0..366]"),
    ("P0000-13-00", "months value of 13 exceeds range [0..12]"),
    ("PT12:60:00", "minutes value of 60 exceeds range [0..60)"),
    ("PT12:61:00", "minutes value of 61 exceeds range [0..60)"),
    ("PT15:25:60", "seconds value of 60 exceeds range [0..60)"),
    ("PT24:00:00", "hours value of 24 exceeds range [0..24)"),
    # invalid date-format style durations
    ("P0000-1-0", "unable to parse '1-0' as a positive decimal"),
    ("PT1:2:3", "unable to parse '1:2:3' into time components"),
    ("PT01:0203", "unable to parse '01:0203' into time components"),
    ("PT01", "unable to parse '01' into time components"),
    ("PT01:02:3.4", "unable to parse '01:02:3.4' into time components"),
    ("P0000y00m00", "unable to parse '0000y00m00' into date components"),
    # decimals must have a non-empty integer value before the separator
    ("PT.5S", "unable to parse '.5' as a positive decimal"),
    ("P1M.1D", "unable to parse '.1' as a positive decimal"),
    # segment repetition
    ("PT5MT5S", "unexpected character 'T'"),
    ("P1W2W", "unexpected character 'W'"),
    # segments out-of-order
    ("P1DT5S2W", "unexpected character 'W'"),
    # unexpected characters within date/time components
    ("PT01:-2:03", "unable to parse '-2' as a positive decimal"),
    ("P000000.1", "unable to parse '.1' as a positive decimal"),
    ("PT000000--", "unable to parse '000000--' into time components"),
    ("PT00:00:00,-", "unable to parse '00:00:00,-' into time components"),
    # negative designator-separated values
    ("P-1DT0S", "unexpected character '-'"),
    ("P0M-2D", "unexpected character '-'"),
    ("P0DT1M-3S", "unexpected character '-'"),
    # positive designator-separated values
    ("P+1DT0S", "unexpected character '+'"),
    ("P0M+2D", "unexpected character '+'"),
    ("P0DT1M+3S", "unexpected character '+'"),
    # scientific notation in designated values
    ("P1.0e+1D", "unexpected character 'e'"),
    ("P10.0E-1D", "unexpected character 'E'"),
    # attempt to cause the parser to confuse duration tokens and Duration arguments
    ("P1years1M", "unexpected character 'y'"),
    # components with missing designators
    ("PT1H2", "unable to parse '1H2' into time components"),
    ("P20D4T", "expected a unit designator after '4'"),
    ("P1D5T", "expected a unit designator after '5'"),
]

# ambiguous cases
_ = [
    # mixed segment formats
    ("P0000-00-01T5S", "date segment format differs from time segment"),
    ("P1DT00:00:00", "date segment format differs from time segment"),
]

format_expectations = [
    (Duration(seconds=1.0005), "PT1.0005S"),
    (Duration(seconds=10), "PT10S"),
    (Duration(minutes=10), "PT10M"),
    # (Duration(seconds=5400), "PT1H30M"),
    (Duration(seconds=5400), "PT5400S"),
    (Duration(hours=20, minutes=5), "PT20H5M"),
    # TODO: need a timedelta to Duration conversion to replace the functionality that this test covered
    # (Duration(days=1.5, minutes=4000), "P4DT6H40M"),
    (Duration(days=1.5, minutes=4000), "P1.5DT4000M"),
]

interval_expectations = [
    (
        "2000-01-01T00:00:00/2000-01-02T00:00:00",
        Interval(
            start=datetime(2000,1,1),
            end=datetime(2000,1,2),
            duration=Duration(days=1)
        )
    ),
    (
        "2000-01-01T00:00:00/P1D",
        Interval(
            start=datetime(2000,1,1),
            end=datetime(2000,1,2),
            duration=Duration(days=1)
        )
    ),
    (
        "2000-01-01T00:00:00/P1M",
        Interval(
            start=datetime(2000,1,1),
            end=datetime(2000,2,1),
            duration=Duration(months=1)
        )
    ),
    (
        "2000-01-01T00:00:00/P1MT1M",
        Interval(
            start=datetime(2000,1,1),
            end=datetime(2000,2,1,0,1),
            duration=Duration(months=1, minutes=1)
        )
    ),
    (
        "2000-01-31T00:00:00/P1M",
        ValueError("day is out of range for month")
    ),
    (
        "2000-01-31T00:00:00/P0.97M",
        ValueError("fractional months are not supported")
    ),
    (
        "2000-01-31T00:00:00/P2M",
        Interval(
            start=datetime(2000,1,31),
            end=datetime(2000,3,31),
            duration=Duration(months=2)
        )
    ),
    (
        "2000-04-30T00:00:00/P1M1D",
        Interval(
            start=datetime(2000,4,30),
            end=datetime(2000,5,31),
            duration=Duration(months=1, days=1)
        )
    ),
    (
        "1999-01-28T00:00:00/P1Y1M1DT1H1M1.0005S",
        Interval(
            start=datetime(1999,1,28),
            end=datetime(2000,2,29,1,1,1,500),
            duration=Duration(years=1, months=1, days=1, hours=1, minutes=1, seconds=1.0005)
        )
    ),
    (
        "2001-01-28T00:00:00/P1M1D",
        Interval(
            start=datetime(2001,1,28),
            end=datetime(2001,3,1),
            duration=Duration(months=1, days=1)
        )
    ),
    (
        "2000-01-01T00:00:00/P1W",
        Interval(
            start=datetime(2000,1,1),
            end=datetime(2000,1,8),
            duration=Duration(weeks=1)
        )
    ),
    (
        "2000-01-01T00:00:00/P1W1D",
        Interval(
            start=datetime(2000,1,1),
            end=datetime(2000,1,9),
            duration=Duration(weeks=1, days=1)
        )
    ),
    (
        "2000-02-28T00:00:00/PT24H",
        Interval(
            start=datetime(2000,2,28),
            end=datetime(2000,2,29),
            duration=Duration(hours=24)
        )
    ),
    (
        "2001-02-28T00:00:00/PT24H",
        Interval(
            start=datetime(2001,2,28),
            end=datetime(2001,3,1),
            duration=Duration(hours=24)
        )
    ),
    (
        # test that the month is applied before the day
        "2000-02-29T00:00:00/P1M1D",
        Interval(
            start=datetime(2000,2,29),
            end=datetime(2000,3,30),
            duration=Duration(months=1, days=1)
        )
    ),
    (
        # test that the year is applied before the month
        "1999-01-29T00:00:00/P1Y1M",
        Interval(
            start=datetime(1999,1,29),
            end=datetime(2000,2,29),
            duration=Duration(years=1, months=1)
        )
    )
]


class TimedeltaISOFormat(unittest.TestCase):
    """Functional testing for :class:`timedelta_isoformat.Duration`"""

    def test_fromisoformat_valid(self) -> None:
        """Parsing cases that should all succeed"""
        for duration_string, expected_duration, expected_timedelta in valid_durations:
            with self.subTest(duration_string=duration_string):
                parsed_duration = Duration.fromisoformat(duration_string)
                self.assertEqual(parsed_duration, expected_duration)
                start_date = datetime(2000, 1, 1)
                parsed_timedelta = (parsed_duration + start_date) - start_date

    def test_fromisoformat_invalid(self) -> None:
        """Parsing cases that should all fail"""
        for duration_string, expected_reason in invalid_durations:
            with self.subTest(duration_string=duration_string):
                with self.assertRaises(ValueError) as context:
                    Duration.fromisoformat(duration_string)
                self.assertIn(expected_reason, str(context.exception))

    def test_roundtrip_valid(self) -> None:
        """Round-trip from valid duration to string and back maintains the same value"""
        for _, valid_duration, valid_timedelta in valid_durations:
            with self.subTest(valid_duration=valid_duration):
                duration_string = valid_duration.isoformat()
                parsed_duration = Duration.fromisoformat(duration_string)
                self.assertEqual(parsed_duration, valid_duration)

    def test_year_month_formatting(self) -> None:
        """Formatting of Duration objects with year-or-month attributes"""
        year_month_timedelta = Duration(hours=4, months=6, years=1)
        self.assertEqual("P1Y6MT4H", year_month_timedelta.isoformat())
        self.assertEqual(
            "Duration(years=1.0, months=6.0, hours=4.0)",
            repr(year_month_timedelta),
        )

    def test_year_month_support_handling(self) -> None:
        """Parsing of duration strings containing non-zero year-or-month components"""
        with self.assertRaises(ValueError):
            Duration.fromisoformat("P1Y0D").to_timedelta()

    def test_minimal_precision(self) -> None:
        """Ensure that the smallest py3.9 datetime.timedelta is formatted correctly"""
        microsecond = Duration.fromisoformat("PT0.000001S")
        self.assertEqual("PT0.000001S", microsecond.isoformat())

    def test_formatting_precision(self) -> None:
        """Formatting for decimal fields"""
        for sample_timedelta, expected_format in format_expectations:
            with self.subTest(sample_timedelta=sample_timedelta):
                self.assertEqual(expected_format, sample_timedelta.isoformat())

    def test_interval_parsing(self) -> None:
        """Parsing of interval strings"""
        for interval_string, expected_interval in interval_expectations:
            with self.subTest(interval_string=interval_string):
                if isinstance(expected_interval, Exception):
                    with self.assertRaises(type(expected_interval)) as context:
                        Interval.fromisoformat(interval_string)
                    self.assertIn(str(expected_interval), str(context.exception))
                else:
                    parsed_interval = Interval.fromisoformat(interval_string)
                    self.assertEqual(parsed_interval, expected_interval)
    
    def test_crossing_dst_boundary(self) -> None:
        """Test that a Duration in hours is taken as actual elapsed time, not just difference in local time"""
        eastern = pytz.timezone('US/Eastern')

        # Test that a duration of 23 hours is exactly one day when starting DST
        start = eastern.localize(datetime(2020, 3, 7, 12, 0, 0))
        end = start + Duration(hours=23)
        self.assertEqual(end, eastern.localize(datetime(2020, 3, 8, 12, 0, 0)))

        # Test that a duration of 25 hours is exactly one day when ending DST
        start = eastern.localize(datetime(2020, 10, 31, 12, 0, 0))
        end = start + Duration(hours=25)
        self.assertEqual(end, eastern.localize(datetime(2020, 11, 1, 12, 0, 0)))

        # Test that a duration of 1 day is treated as 1 day when starting DST
        start = eastern.localize(datetime(2020, 3, 7, 12, 0, 0))
        end = start + Duration(days=1)
        self.assertEqual(end, eastern.localize(datetime(2020, 3, 8, 12, 0, 0)))

        # Test that a duration of 1 day is treated as 1 day when ending DST
        start = eastern.localize(datetime(2020, 10, 31, 12, 0, 0))
        end = start + Duration(days=1)
        self.assertEqual(end, eastern.localize(datetime(2020, 11, 1, 12, 0, 0)))
        