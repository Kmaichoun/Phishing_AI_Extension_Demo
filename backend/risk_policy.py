from __future__ import annotations

CONSENSUS_WARN_FUZZY_MIN = 0.50
CONSENSUS_WARN_ML_MIN = 0.90
CONSENSUS_WARN_FLOOR = 0.99

CONSENSUS_BLOCK_FUZZY_MIN = 0.85
CONSENSUS_BLOCK_ML_MIN = 0.95
CONSENSUS_BLOCK_FLOOR = 1.0

CONSENSUS_GUARDRAIL_VERSION = "two-layer-consensus-1.0"


def apply_consensus_guardrail(
    fuzzy_probability: float,
    ml_probability: float,
    learned_fusion_probability: float,
) -> tuple[float, str | None]:
    """Escalate only when independent rule and ML evidence strongly agree."""
    score = max(0.0, min(1.0, float(learned_fusion_probability)))
    trigger: str | None = None
    if (
        fuzzy_probability >= CONSENSUS_BLOCK_FUZZY_MIN
        and ml_probability >= CONSENSUS_BLOCK_ML_MIN
    ):
        score = max(score, CONSENSUS_BLOCK_FLOOR)
        trigger = "block_consensus"
    elif (
        fuzzy_probability >= CONSENSUS_WARN_FUZZY_MIN
        and ml_probability >= CONSENSUS_WARN_ML_MIN
    ):
        score = max(score, CONSENSUS_WARN_FLOOR)
        trigger = "warning_consensus"
    return score, trigger


def consensus_guardrail_config() -> dict[str, object]:
    return {
        "version": CONSENSUS_GUARDRAIL_VERSION,
        "warning": {
            "fuzzy_min": CONSENSUS_WARN_FUZZY_MIN,
            "ml_min": CONSENSUS_WARN_ML_MIN,
            "score_floor": CONSENSUS_WARN_FLOOR,
        },
        "blocking": {
            "fuzzy_min": CONSENSUS_BLOCK_FUZZY_MIN,
            "ml_min": CONSENSUS_BLOCK_ML_MIN,
            "score_floor": CONSENSUS_BLOCK_FLOOR,
        },
    }
