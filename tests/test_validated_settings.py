import config

HOUR = 60 * 60

# what a machine already runs with; deliberately not the defaults, so a test can
# tell "kept the fallback" from "reset to defaults"
IN_FORCE = {
    "DAILY_LIMIT_SECONDS": 2 * HOUR,
    "CARRYOVER": False,
    "MAX_CARRYOVER_SECONDS": 3 * HOUR,
    "EARLIEST_HOUR_INCLUDED": 8,
    "LATEST_HOUR_INCLUDED": 19,
    "DAILY_LIMIT_OVERRIDES": {"sat": 3 * HOUR},
}


def validated(change):
    return config.validated_settings(change, IN_FORCE)


def test_a_full_valid_change_is_taken_as_is():
    change = {**IN_FORCE, "DAILY_LIMIT_SECONDS": HOUR, "CARRYOVER": True}
    assert validated(change) == change


def test_a_partial_change_is_filled_from_what_is_in_force_not_the_defaults():
    assert validated({"DAILY_LIMIT_SECONDS": HOUR}) == {**IN_FORCE, "DAILY_LIMIT_SECONDS": HOUR}


def test_without_a_fallback_the_defaults_fill_the_gaps():
    assert config.validated_settings({"CARRYOVER": False}) == {
        **config.default_settings(),
        "CARRYOVER": False,
    }


def test_one_bad_value_rejects_the_whole_change():
    change = {"DAILY_LIMIT_SECONDS": HOUR, "EARLIEST_HOUR_INCLUDED": 24}
    assert validated(change) == IN_FORCE


def test_an_unknown_setting_rejects_the_whole_change():
    assert validated({"DAILY_LIMIT_SECONDS": HOUR, "BEDTIME": 21}) == IN_FORCE


def test_a_window_that_ends_before_it_starts_is_rejected():
    assert validated({"EARLIEST_HOUR_INCLUDED": 20, "LATEST_HOUR_INCLUDED": 6}) == IN_FORCE
    same_hour = validated({"EARLIEST_HOUR_INCLUDED": 12, "LATEST_HOUR_INCLUDED": 12})
    assert same_hour["EARLIEST_HOUR_INCLUDED"] == same_hour["LATEST_HOUR_INCLUDED"] == 12


def test_none_is_accepted_only_where_nullable():
    assert validated({"MAX_CARRYOVER_SECONDS": None})["MAX_CARRYOVER_SECONDS"] is None
    assert validated({"DAILY_LIMIT_SECONDS": None}) == IN_FORCE


def test_a_bool_is_not_an_int_and_an_int_is_not_a_bool():
    assert validated({"DAILY_LIMIT_SECONDS": True}) == IN_FORCE
    assert validated({"CARRYOVER": 1}) == IN_FORCE


def test_limits_outside_a_day_are_rejected():
    assert validated({"DAILY_LIMIT_SECONDS": 0})["DAILY_LIMIT_SECONDS"] == 0  # no screen time
    assert validated({"DAILY_LIMIT_SECONDS": 24 * HOUR})["DAILY_LIMIT_SECONDS"] == 24 * HOUR
    assert validated({"DAILY_LIMIT_SECONDS": 24 * HOUR + 1}) == IN_FORCE
    assert validated({"DAILY_LIMIT_SECONDS": -1}) == IN_FORCE


def test_valid_overrides_replace_the_ones_in_force():
    change = {"DAILY_LIMIT_OVERRIDES": {"mon": 0, "sun": 24 * HOUR}}
    assert validated(change) == {**IN_FORCE, **change}
    assert validated({"DAILY_LIMIT_OVERRIDES": {}}) == {**IN_FORCE, "DAILY_LIMIT_OVERRIDES": {}}


def test_overrides_need_real_weekdays_and_int_seconds():
    assert validated({"DAILY_LIMIT_OVERRIDES": {"monday": HOUR}}) == IN_FORCE
    assert validated({"DAILY_LIMIT_OVERRIDES": {"mon": "3600"}}) == IN_FORCE
    assert validated({"DAILY_LIMIT_OVERRIDES": {"mon": None}}) == IN_FORCE
    assert validated({"DAILY_LIMIT_OVERRIDES": [("mon", HOUR)]}) == IN_FORCE


def test_the_result_is_a_copy_and_the_fallback_stays_untouched():
    before = dict(IN_FORCE)
    result = validated({"DAILY_LIMIT_SECONDS": HOUR})
    result["CARRYOVER"] = True
    rejected = validated({"BEDTIME": 21})
    rejected["CARRYOVER"] = True
    assert IN_FORCE == before
