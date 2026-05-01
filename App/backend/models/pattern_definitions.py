from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal


Bias = Literal["Bullish", "Bearish", "Neutral", "Bilateral"]
Category = Literal["Reversal", "Continuation", "Bilateral", "Complex", "Candlestick"]


@dataclass(frozen=True)
class PatternDefinition:
    id: str
    name: str
    category: Category
    bias: Bias
    detector: str
    description: str

    def to_dict(self) -> dict:
        return asdict(self)


# The 55 names are encoded from Strike's "55 Trading Chart Patterns" article.
# The detector key maps each definition to a concrete rule family in pattern_detector.py.
PATTERN_DEFINITIONS: tuple[PatternDefinition, ...] = (
    PatternDefinition("head-and-shoulders", "Head and Shoulders Pattern", "Reversal", "Bearish", "head_shoulders", "Three-peak topping structure with a weaker right shoulder and neckline risk."),
    PatternDefinition("inverse-head-and-shoulders", "Inverse Head and Shoulders Pattern", "Reversal", "Bullish", "inverse_head_shoulders", "Three-trough basing structure with improving right shoulder strength."),
    PatternDefinition("double-top", "Double Top Pattern", "Reversal", "Bearish", "double_top", "Two similar highs after an advance with a neckline breakdown risk."),
    PatternDefinition("double-bottom", "Double Bottom Pattern", "Reversal", "Bullish", "double_bottom", "Two similar lows after a decline with a neckline breakout risk."),
    PatternDefinition("triple-top", "Triple Top Pattern", "Reversal", "Bearish", "triple_top", "Repeated failure at a resistance shelf across three highs."),
    PatternDefinition("triple-bottom", "Triple Bottom Pattern", "Reversal", "Bullish", "triple_bottom", "Repeated defense of a support shelf across three lows."),
    PatternDefinition("ascending-triangle", "Ascending Triangle Pattern", "Continuation", "Bullish", "ascending_triangle", "Flat resistance with rising lows showing accumulation."),
    PatternDefinition("descending-triangle", "Descending Triangle Pattern", "Continuation", "Bearish", "descending_triangle", "Flat support with falling highs showing distribution."),
    PatternDefinition("symmetrical-triangle", "Symmetrical Triangle Pattern", "Bilateral", "Bilateral", "symmetrical_triangle", "Converging highs and lows that wait for directional breakout."),
    PatternDefinition("rising-wedge", "Rising Wedge Pattern", "Reversal", "Bearish", "rising_wedge", "Rising but narrowing channel that often signals upside exhaustion."),
    PatternDefinition("falling-wedge", "Falling Wedge Pattern", "Reversal", "Bullish", "falling_wedge", "Falling but narrowing channel that often signals downside exhaustion."),
    PatternDefinition("bullish-flag", "Bullish Flag Pattern", "Continuation", "Bullish", "bullish_flag", "Sharp rally followed by a controlled downward-sloping pause."),
    PatternDefinition("bearish-flag", "Bearish Flag Pattern", "Continuation", "Bearish", "bearish_flag", "Sharp selloff followed by a controlled upward-sloping pause."),
    PatternDefinition("bullish-pennant", "Bullish Pennant Pattern", "Continuation", "Bullish", "bullish_pennant", "Impulse rally followed by a small converging pause."),
    PatternDefinition("bearish-pennant", "Bearish Pennant Pattern", "Continuation", "Bearish", "bearish_pennant", "Impulse selloff followed by a small converging pause."),
    PatternDefinition("bullish-rectangle", "Bullish Rectangle Pattern", "Continuation", "Bullish", "bullish_rectangle", "Uptrend consolidation inside horizontal support and resistance."),
    PatternDefinition("bearish-rectangle", "Bearish Rectangle Pattern", "Continuation", "Bearish", "bearish_rectangle", "Downtrend consolidation inside horizontal support and resistance."),
    PatternDefinition("cup-and-handle", "Cup & Handle Patterns", "Continuation", "Bullish", "cup_handle", "Rounded base followed by a small handle before a possible breakout."),
    PatternDefinition("rounding-top", "Rounding Top Pattern", "Reversal", "Bearish", "rounding_top", "Slow distribution arc after an advance."),
    PatternDefinition("rounding-bottom", "Rounding Bottom Pattern", "Reversal", "Bullish", "rounding_bottom", "Slow accumulation arc after a decline."),
    PatternDefinition("channel", "Channel Patterns", "Continuation", "Bilateral", "channel", "Parallel rising, falling, or sideways boundary behavior."),
    PatternDefinition("broadening-wedge", "Broadening Wedge Pattern", "Bilateral", "Bilateral", "broadening_wedge", "Diverging highs and lows with expanding volatility."),
    PatternDefinition("megaphone", "Megaphone Pattern", "Bilateral", "Bilateral", "megaphone", "Broadening swing structure with progressively wider pivots."),
    PatternDefinition("diamond-top", "Diamond Top Pattern", "Reversal", "Bearish", "diamond_top", "Expansion then contraction near a high, suggesting distribution."),
    PatternDefinition("diamond-bottom", "Diamond Bottom Pattern", "Reversal", "Bullish", "diamond_bottom", "Expansion then contraction near a low, suggesting accumulation."),
    PatternDefinition("bump-and-run", "Bump and Run Pattern", "Reversal", "Bearish", "bump_run", "Orderly trend accelerates into a steep bump and then loses support."),
    PatternDefinition("island-reversal", "Island Reversal Pattern", "Reversal", "Bilateral", "island_reversal", "Price gaps isolate a small trading island before reversing."),
    PatternDefinition("dead-cat-bounce", "Dead Cat Bounce Pattern", "Continuation", "Bearish", "dead_cat_bounce", "Weak rebound after a heavy fall that fails below resistance."),
    PatternDefinition("parabolic-curve", "Parabolic Curve Pattern", "Reversal", "Bearish", "parabolic_curve", "Accelerating advance with curvature that risks blow-off reversal."),
    PatternDefinition("v-pattern", "V Pattern", "Reversal", "Bullish", "v_pattern", "Sharp selloff and equally sharp recovery."),
    PatternDefinition("ascending-staircase", "Ascending Staircase Pattern", "Continuation", "Bullish", "ascending_staircase", "Series of higher highs and higher lows with shallow pauses."),
    PatternDefinition("descending-staircase", "Descending Staircase Pattern", "Continuation", "Bearish", "descending_staircase", "Series of lower highs and lower lows with shallow pauses."),
    PatternDefinition("tower-top", "Tower Top Pattern", "Reversal", "Bearish", "tower_top", "Tall bullish candle sequence followed by tall bearish rejection."),
    PatternDefinition("tower-bottom", "Tower Bottom Pattern", "Reversal", "Bullish", "tower_bottom", "Tall bearish candle sequence followed by tall bullish recovery."),
    PatternDefinition("pipe-top", "Pipe Top Pattern", "Reversal", "Bearish", "pipe_top", "Two large adjacent candles forming a sudden top reversal."),
    PatternDefinition("pipe-bottom", "Pipe Bottom Pattern", "Reversal", "Bullish", "pipe_bottom", "Two large adjacent candles forming a sudden bottom reversal."),
    PatternDefinition("scallop", "Scallop Pattern", "Continuation", "Bullish", "scallop", "Rounded pullback and recovery resembling a shallow bowl."),
    PatternDefinition("spikes", "Spikes Pattern", "Reversal", "Bilateral", "spikes", "Extreme candle range and wick displacement from the recent mean."),
    PatternDefinition("shakeout", "Shakeout Pattern", "Reversal", "Bullish", "shakeout", "False breakdown below support followed by quick recovery."),
    PatternDefinition("bull-trap", "Bull Trap Pattern", "Reversal", "Bearish", "bull_trap", "False breakout above resistance that quickly fails."),
    PatternDefinition("bear-trap", "Bear Trap Pattern", "Reversal", "Bullish", "bear_trap", "False breakdown below support that quickly reverses higher."),
    PatternDefinition("kicker", "Kicker Pattern", "Candlestick", "Bilateral", "kicker", "Abrupt sentiment shift with a gap and opposite-color candle."),
    PatternDefinition("morning-star", "Morning Star Pattern", "Candlestick", "Bullish", "morning_star", "Three-candle basing reversal after weakness."),
    PatternDefinition("evening-star", "Evening Star Pattern", "Candlestick", "Bearish", "evening_star", "Three-candle topping reversal after strength."),
    PatternDefinition("running-correction", "Running Correction Pattern", "Continuation", "Bilateral", "running_correction", "Corrective move that stays shallow relative to the dominant trend."),
    PatternDefinition("complex-double-top-bottom", "Complex Double top / Double bottom", "Complex", "Bilateral", "complex_double", "Clustered double-top or double-bottom behavior with extra retests."),
    PatternDefinition("complex-head-and-shoulder", "Complex Head and Shoulder pattern", "Complex", "Bilateral", "complex_head_shoulders", "Head-and-shoulders family structure with multiple shoulders."),
    PatternDefinition("harmonic", "Harmonic Pattern", "Complex", "Bilateral", "harmonic", "Five-point swing structure with Fibonacci-like retracements."),
    PatternDefinition("elliott-wave", "Elliott Wave Pattern", "Complex", "Bilateral", "elliott_wave", "Impulse and corrective swing count approximating five-wave behavior."),
    PatternDefinition("three-drives", "Three Drives Pattern", "Complex", "Bilateral", "three_drives", "Three measured pushes into exhaustion with rhythmic retracements."),
    PatternDefinition("bullish-wolfe-wave", "Bullish Wolfe Wave Pattern", "Complex", "Bullish", "bullish_wolfe", "Falling five-wave wedge with projected bullish mean reversion."),
    PatternDefinition("bearish-wolfe-wave", "Bearish Wolfe Wave Pattern", "Complex", "Bearish", "bearish_wolfe", "Rising five-wave wedge with projected bearish mean reversion."),
    PatternDefinition("gaps", "Gaps Pattern", "Continuation", "Bilateral", "gaps", "Opening displacement beyond the prior range."),
    PatternDefinition("triple-inside-out-reversal", "Triple Inside-Out Reversal", "Candlestick", "Bilateral", "triple_inside_out", "Compression inside prior candles followed by range expansion."),
    PatternDefinition("candlestick", "Candlestick Pattern", "Candlestick", "Bilateral", "candlestick", "Single or multi-candle reversal/continuation signal family."),
)


PATTERN_BY_ID = {pattern.id: pattern for pattern in PATTERN_DEFINITIONS}
PATTERN_BY_DETECTOR = {pattern.detector: pattern for pattern in PATTERN_DEFINITIONS}
KNOWN_PATTERN_NAMES = {pattern.name.lower() for pattern in PATTERN_DEFINITIONS}


def all_patterns() -> list[dict]:
    return [pattern.to_dict() for pattern in PATTERN_DEFINITIONS]
