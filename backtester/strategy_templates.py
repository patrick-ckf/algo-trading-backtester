"""
Preset strategy templates for the Streamlit dashboard (bilingual labels).
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

STRATEGY_SMA = "SMA Crossover"
STRATEGY_RSI = "RSI Mean Reversion"
STRATEGY_DONCHIAN = "Donchian Breakout"

CUSTOM_TEMPLATE_ID = "custom"
CUSTOM_TEMPLATE_LABEL = "自訂 / Custom"


@dataclass(frozen=True)
class StrategyTemplate:
    """One-click preset: strategy kind + default parameters."""

    id: str
    label: str
    strategy_type: str
    params: Dict[str, Any]
    description: str = ""


STRATEGY_TEMPLATES: List[StrategyTemplate] = [
    StrategyTemplate(
        id="dual_sma",
        label="雙均線交叉 20/50 / Dual SMA Crossover 20/50",
        strategy_type=STRATEGY_SMA,
        params={"fast_period": 20, "slow_period": 50},
        description="預設短中期趨勢跟蹤 / Default short-to-medium trend following",
    ),
    StrategyTemplate(
        id="long_sma",
        label="長趨勢均線 50/200 / Long-Trend SMA 50/200",
        strategy_type=STRATEGY_SMA,
        params={"fast_period": 50, "slow_period": 200},
        description="經典長期趨勢 / Classic golden-cross style trend",
    ),
    StrategyTemplate(
        id="rsi_mean_reversion",
        label="RSI 均值回歸 / RSI Mean Reversion",
        strategy_type=STRATEGY_RSI,
        params={
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
        },
        description="超買超賣反轉 / Oversold-overbought reversals",
    ),
    StrategyTemplate(
        id="donchian_20",
        label="唐奇安突破 20 日 / Donchian Breakout 20-day",
        strategy_type=STRATEGY_DONCHIAN,
        params={"channel_period": 20},
        description="N 日高低突破 / Breakout on prior N-day high/low",
    ),
]

_TEMPLATE_BY_ID = {t.id: t for t in STRATEGY_TEMPLATES}


def template_select_options() -> List[str]:
    """Ordered template ids for selectbox options (custom last)."""
    return [t.id for t in STRATEGY_TEMPLATES] + [CUSTOM_TEMPLATE_ID]


def template_label(template_id: str) -> str:
    if template_id == CUSTOM_TEMPLATE_ID:
        return CUSTOM_TEMPLATE_LABEL
    tpl = _TEMPLATE_BY_ID.get(template_id)
    return tpl.label if tpl else CUSTOM_TEMPLATE_LABEL


def get_strategy_template(template_id: str) -> Optional[StrategyTemplate]:
    return _TEMPLATE_BY_ID.get(template_id)


def apply_template_params(target: Dict[str, Any], template: StrategyTemplate) -> None:
    """Write template strategy type and parameter defaults into a mapping (e.g. session_state)."""
    target["strategy_type"] = template.strategy_type
    for key, value in template.params.items():
        target[key] = value


def default_template_id() -> str:
    return "dual_sma"
