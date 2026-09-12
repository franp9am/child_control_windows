import datetime

import monitor

SETTINGS = {"EARLIEST_HOUR_INCLUDED": 6, "LATEST_HOUR_INCLUDED": 20}


def at(hour, minute=0):
    return datetime.datetime(2026, 9, 14, hour, minute)


def test_the_whole_earliest_hour_is_day():
    assert not monitor.is_night_time(at(6, 0), SETTINGS)
    assert not monitor.is_night_time(at(6, 59), SETTINGS)


def test_the_whole_latest_hour_is_still_day():
    assert not monitor.is_night_time(at(20, 0), SETTINGS)
    assert not monitor.is_night_time(at(20, 59), SETTINGS)


def test_just_outside_the_window_is_night():
    assert monitor.is_night_time(at(5, 59), SETTINGS)
    assert monitor.is_night_time(at(21, 0), SETTINGS)


def test_midnight_is_night():
    assert monitor.is_night_time(at(0, 0), SETTINGS)
