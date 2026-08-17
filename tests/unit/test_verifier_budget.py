from opspilot.investigation.budget import BudgetState, ToolBudget
from opspilot.verifier.budget import can_followup, snapshot_budget


def test_shared_budget_allows_exactly_one_followup() -> None:
    budget = ToolBudget(max_tool_calls=8, max_steps=3)
    open_snap = snapshot_budget(
        BudgetState(tool_calls=3, steps=1),
        budget,
        followups_used=0,
        steps_used=1,
    )
    assert open_snap.remaining_tool_calls == 5
    assert open_snap.remaining_steps == 2
    assert can_followup(open_snap)

    used = snapshot_budget(
        BudgetState(tool_calls=3, steps=2),
        budget,
        followups_used=1,
        steps_used=2,
    )
    assert used.remaining_followups == 0
    assert can_followup(used) is False

    exhausted = snapshot_budget(
        BudgetState(tool_calls=8, steps=1),
        budget,
        followups_used=0,
        steps_used=1,
    )
    assert can_followup(exhausted) is False
