import datetime

import monitor

MON = datetime.date(2026, 9, 14)
SAT = datetime.date(2026, 9, 19)
SUN = datetime.date(2026, 9, 20)
HOUR = 60 * 60

SETTINGS = {"DAILY_LIMIT_SECONDS": HOUR, "DAILY_LIMIT_OVERRIDES": {"sat": 2 * HOUR, "sun": 0}}


def data(spent=0, carryover=0, granted=0):
    return {"time_spent_sec": spent, "carryover_sec": carryover, "granted_sec": granted}


def test_a_weekday_without_an_override_gets_the_general_limit():
    assert monitor.daily_limit_seconds(MON, SETTINGS) == HOUR


def test_a_weekday_with_an_override_gets_it_even_when_it_is_zero():
    assert monitor.daily_limit_seconds(SAT, SETTINGS) == 2 * HOUR
    assert monitor.daily_limit_seconds(SUN, SETTINGS) == 0


def test_remaining_adds_carryover_and_grants_and_subtracts_time_spent():
    assert monitor.remaining_seconds(data(), SETTINGS, MON) == HOUR
    assert monitor.remaining_seconds(data(spent=900, carryover=300, granted=600), SETTINGS, MON) == HOUR
    assert monitor.remaining_seconds(data(spent=900), SETTINGS, SAT) == 2 * HOUR - 900
    assert monitor.remaining_seconds(data(carryover=1800), SETTINGS, MON) == HOUR + 1800
    assert monitor.remaining_seconds(data(granted=600), SETTINGS, MON) == HOUR + 600
    assert monitor.remaining_seconds(data(spent=HOUR, carryover=1800, granted=600), SETTINGS, MON) == 2400
    assert monitor.remaining_seconds(data(spent=1200, granted=600), SETTINGS, SUN) == -600


def test_remaining_goes_negative_during_the_grace_period():
    assert monitor.remaining_seconds(data(spent=HOUR + 120), SETTINGS, MON) == -120
