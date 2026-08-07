from __future__ import annotations

FUZZY_SCHEMA_VERSION = "rule-score-fuzzy-membership-1.0"


def _falling(value: float, full_until: float, zero_at: float) -> float:
    if value <= full_until:
        return 1.0
    if value >= zero_at:
        return 0.0
    return (zero_at - value) / (zero_at - full_until)


def _rising(value: float, zero_until: float, full_at: float) -> float:
    if value <= zero_until:
        return 0.0
    if value >= full_at:
        return 1.0
    return (value - zero_until) / (full_at - zero_until)


def _triangle(value: float, left: float, peak: float, right: float) -> float:
    if value <= left or value >= right:
        return 0.0
    if value == peak:
        return 1.0
    if value < peak:
        return (value - left) / (peak - left)
    return (right - value) / (right - peak)


def fuzzy_memberships(rule_score: float) -> dict[str, float]:
    """Return explainable fuzzy memberships for a RuleScore on a 0-100 scale."""
    value = max(0.0, min(100.0, float(rule_score)))
    return {
        "safe": _falling(value, full_until=20.0, zero_at=45.0),
        "suspicious": _triangle(value, left=20.0, peak=50.0, right=80.0),
        "dangerous": _rising(value, zero_until=55.0, full_at=85.0),
    }


def fuzzy_score(rule_score: float) -> float:
    """Defuzzify safe/suspicious/dangerous evidence to a stable 0-100 score."""
    memberships = fuzzy_memberships(rule_score)
    denominator = sum(memberships.values())
    if denominator <= 0:
        return max(0.0, min(100.0, float(rule_score)))
    score = (
        memberships["safe"] * 0.0
        + memberships["suspicious"] * 50.0
        + memberships["dangerous"] * 100.0
    ) / denominator
    return max(0.0, min(100.0, score))


def fuzzy_audit(rule_score: float) -> dict[str, object]:
    memberships = fuzzy_memberships(rule_score)
    return {
        "schema_version": FUZZY_SCHEMA_VERSION,
        "input_rule_score": round(max(0.0, min(100.0, float(rule_score))), 4),
        "memberships": {key: round(value, 6) for key, value in memberships.items()},
        "fuzzy_score": round(fuzzy_score(rule_score), 4),
    }
