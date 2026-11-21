"""Plain-English explanation of a scheduling conflict.

If ANTHROPIC_API_KEY is configured the explanation is written by Claude, given
only the structured conflict (no personal data beyond first/last names already
shown on screen). Without a key — or on any API error — a deterministic
explanation built from the same data is returned, so the feature never blocks
the manager. Scheduling decisions are never delegated to the model: it explains,
the manager decides.
"""
from flask import current_app

SYSTEM_PROMPT = (
    "You are an operations assistant inside a roster-planning tool for a customer-experience team "
    "that supports D2C brands. Explain the scheduling conflict you are given to an operations manager "
    "in at most 4 short sentences: what is wrong, why it matters for the client, and the most practical "
    "fix using only the candidate covers or actions listed. Do not invent people, dates or rules."
)

TYPE_CONTEXT = {
    "COVERAGE_GAP": "A brand/process is below its contractual minimum staffing on an operating day.",
    "UNASSIGNED_REQUIREMENT": "A brand/process operates but has no assigned employee.",
    "MULTI_BRAND_IMPACT": "One person's absence leaves several client brands short on the same day.",
    "DOUBLE_BOOKING": "An employee is given more responsibilities than they can handle, or cover while off.",
    "INCOMPATIBLE_SHIFT": "An employee's duties span longer than the allowed shift length.",
    "LEAVE_CONFLICT": "An employee is rostered on a day of approved leave.",
    "RULE_VIOLATION": "A contractual (fixed) weekly off is being overridden.",
    "REST_VIOLATION": "An employee is not getting the mandatory weekly rest.",
    "PREFERENCE_VIOLATION": "A preferred weekly off was not granted because client coverage has priority.",
    "COMP_OFF_ELIGIBLE": "An employee works a public holiday and earns a comp-off.",
}


def _facts(conflict):
    lines = [
        f"Type: {conflict.conflict_type} ({TYPE_CONTEXT.get(conflict.conflict_type, '')})",
        f"Severity: {conflict.severity}",
        f"Date: {conflict.roster_date:%A %d %B %Y}",
    ]
    if conflict.brand:
        lines.append(f"Brand: {conflict.brand.name}")
    if conflict.process:
        lines.append(f"Process: {conflict.process.name}")
    if conflict.required_staff is not None:
        lines.append(f"Staff required: {conflict.required_staff}; staff available: {conflict.available_staff}")
    lines.append(f"Detected issue: {conflict.message}")
    if conflict.suggestion:
        lines.append(f"System suggestion: {conflict.suggestion}")
    for c in conflict.candidates:
        lines.append(f"Candidate cover: {c['name']} – {c['reason']}")
    return "\n".join(lines)


def fallback_explanation(conflict):
    parts = [TYPE_CONTEXT.get(conflict.conflict_type, "Scheduling issue."), conflict.message]
    if conflict.severity == "ERROR":
        parts.append("This is a mandatory constraint, so the roster should not be published until it is fixed "
                     "or explicitly acknowledged.")
    elif conflict.severity == "WARNING":
        parts.append("This is a soft constraint: the roster is still valid, but review it.")
    if conflict.candidates:
        best = conflict.candidates[0]
        parts.append(f"Quickest fix: assign {best['name']} ({best['reason']}) as cover.")
    elif conflict.suggestion:
        parts.append(conflict.suggestion)
    return " ".join(parts)


def explain(conflict):
    """Return (text, source) where source is 'claude' or 'rules'."""
    api_key = current_app.config.get("ANTHROPIC_API_KEY")
    if not api_key:
        return fallback_explanation(conflict), "rules"
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key, timeout=25.0, max_retries=1)
        response = client.beta.messages.create(
            model=current_app.config.get("AI_MODEL", "claude-opus-5-5"),
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": _facts(conflict)}],
        )
        if response.stop_reason == "refusal":
            return fallback_explanation(conflict), "rules"
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        return (text, "claude") if text else (fallback_explanation(conflict), "rules")
    except Exception as exc:  # network, auth, rate limit… never break the page
        current_app.logger.warning("AI explanation failed: %s", exc)
        return fallback_explanation(conflict), "rules"
