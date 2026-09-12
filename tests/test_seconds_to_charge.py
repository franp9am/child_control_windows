import datetime

import monitor
from config import CHECK_INTERVAL_SECONDS

NOW = datetime.datetime(2026, 9, 11, 10, 0, 0)


def data_with_last_tick(seconds_before_now):
    previous = NOW - datetime.timedelta(seconds=seconds_before_now)
    return {"last_tick": previous.strftime(monitor.TIMESTAMP_FORMAT)}


def test_no_previous_tick_charges_the_interval():
    assert monitor.seconds_to_charge({"last_tick": None}, NOW) == CHECK_INTERVAL_SECONDS
    assert monitor.seconds_to_charge({}, NOW) == CHECK_INTERVAL_SECONDS


def test_ordinary_gap_charges_the_real_elapsed_seconds():
    data = data_with_last_tick(CHECK_INTERVAL_SECONDS + 3)
    assert monitor.seconds_to_charge(data, NOW) == CHECK_INTERVAL_SECONDS + 3


def test_long_gap_means_the_machine_slept_so_only_the_interval_is_charged():
    data = data_with_last_tick(10 * CHECK_INTERVAL_SECONDS + 1)
    assert monitor.seconds_to_charge(data, NOW) == CHECK_INTERVAL_SECONDS


def test_clock_moved_backwards_charges_the_interval():
    data = data_with_last_tick(-3600)  # last tick is an hour in the future
    assert monitor.seconds_to_charge(data, NOW) == CHECK_INTERVAL_SECONDS
