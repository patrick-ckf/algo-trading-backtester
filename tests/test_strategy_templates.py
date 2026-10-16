"""Tests for strategy template presets."""

from backtester.strategy_templates import (
    CUSTOM_TEMPLATE_ID,
    STRATEGY_DONCHIAN,
    STRATEGY_RSI,
    STRATEGY_SMA,
    apply_template_params,
    default_template_id,
    get_strategy_template,
    template_label,
    template_select_options,
)


def test_default_template_is_dual_sma():
    assert default_template_id() == "dual_sma"
    tpl = get_strategy_template(default_template_id())
    assert tpl is not None
    assert tpl.strategy_type == STRATEGY_SMA
    assert tpl.params["fast_period"] == 20
    assert tpl.params["slow_period"] == 50


def test_all_presets_have_unique_ids():
    options = template_select_options()
    assert options[-1] == CUSTOM_TEMPLATE_ID
    assert len(options) == len(set(options))


def test_template_labels_are_bilingual():
    for tid in template_select_options():
        label = template_label(tid)
        assert "/" in label or tid == CUSTOM_TEMPLATE_ID


def test_apply_template_params_writes_session_fields():
    state = {}
    tpl = get_strategy_template("rsi_mean_reversion")
    apply_template_params(state, tpl)
    assert state["strategy_type"] == STRATEGY_RSI
    assert state["rsi_period"] == 14
    assert state["rsi_oversold"] == 30


def test_long_sma_and_donchian_presets():
    long_sma = get_strategy_template("long_sma")
    assert long_sma.params == {"fast_period": 50, "slow_period": 200}

    donchian = get_strategy_template("donchian_20")
    assert donchian.strategy_type == STRATEGY_DONCHIAN
    assert donchian.params["channel_period"] == 20
