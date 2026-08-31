"""StillDot: smartphone dead reckoning. Networks estimate speed; the filter estimates position."""

from stilldot.engine import run_scenario
from stilldot.types import Frame, RunResult, ScenarioSpec

__all__ = ["Frame", "RunResult", "ScenarioSpec", "run_scenario"]
__version__ = "0.1.0"
