"""Unit tests for the 19-state, 28-transition State Machine.

Tests the full 19x19 state transition matrix according to Blueprint v2.0 Section 9 & 16.
"""

import pytest
from jovsi.domain.state_machine import (
    ApplicationState,
    IllegalTransition,
    GuardFailure,
    StateMachine,
    TransitionContext,
)


ALL_STATES = list(ApplicationState)


def test_state_machine_matrix_completeness() -> None:
    """Verify that every legal pair is permitted and all illegal pairs raise IllegalTransition."""
    legal_map = StateMachine.get_legal_transitions()

    # Total 19 states
    assert len(ALL_STATES) == 19

    illegal_count = 0
    legal_count = 0

    for from_state in ALL_STATES:
        allowed_targets = legal_map.get(from_state, set())
        for to_state in ALL_STATES:
            ctx = TransitionContext(
                application_id="app-123",
                current_state=from_state,
                target_state=to_state,
            )

            if to_state in allowed_targets:
                legal_count += 1
                # Must either pass or fail guard, but never raise IllegalTransition
                try:
                    StateMachine.validate_transition(ctx)
                except GuardFailure:
                    pass  # Expected when dummy ctx doesn't meet guards
                except IllegalTransition:
                    pytest.fail(f"Legally registered transition {from_state} -> {to_state} raised IllegalTransition!")
            else:
                illegal_count += 1
                with pytest.raises(IllegalTransition):
                    StateMachine.validate_transition(ctx)

    assert legal_count > 0
    assert illegal_count > 0
    assert legal_count + illegal_count == 19 * 19


def test_transition_none_to_discovered() -> None:
    """Transition #1: (none) -> DISCOVERED requires canonical key."""
    # Without canonical key
    ctx_no_key = TransitionContext(
        application_id="app-1",
        current_state=None,
        target_state=ApplicationState.DISCOVERED,
        canonical_job_key=None,
    )
    with pytest.raises(GuardFailure):
        StateMachine.validate_transition(ctx_no_key)

    # With canonical key
    ctx_with_key = TransitionContext(
        application_id="app-1",
        current_state=None,
        target_state=ApplicationState.DISCOVERED,
        canonical_job_key="sha256-key",
    )
    StateMachine.validate_transition(ctx_with_key)


def test_transition_discovered_branches() -> None:
    """Transitions #2, #3, #4, #5 from DISCOVERED."""
    # #2 to ELIGIBILITY_CHECKED
    ctx_pass = TransitionContext(
        application_id="app-1",
        current_state=ApplicationState.DISCOVERED,
        target_state=ApplicationState.ELIGIBILITY_CHECKED,
        hard_rules_failed=False,
    )
    StateMachine.validate_transition(ctx_pass)

    ctx_fail_guard = TransitionContext(
        application_id="app-1",
        current_state=ApplicationState.DISCOVERED,
        target_state=ApplicationState.ELIGIBILITY_CHECKED,
        hard_rules_failed=True,
    )
    with pytest.raises(GuardFailure):
        StateMachine.validate_transition(ctx_fail_guard)

    # #3 to REJECTED
    ctx_rej = TransitionContext(
        application_id="app-1",
        current_state=ApplicationState.DISCOVERED,
        target_state=ApplicationState.REJECTED,
        hard_rules_failed=True,
    )
    StateMachine.validate_transition(ctx_rej)

    # #4 to EXPIRED
    ctx_exp = TransitionContext(
        application_id="app-1",
        current_state=ApplicationState.DISCOVERED,
        target_state=ApplicationState.EXPIRED,
        deadline_passed=True,
    )
    StateMachine.validate_transition(ctx_exp)


def test_submission_to_applied_confirmed_guard() -> None:
    """Transition #22 requires evidence >= MIN_EVIDENCE_LEVEL."""
    # E1 is not enough for default E2
    ctx_e1 = TransitionContext(
        application_id="app-1",
        current_state=ApplicationState.SUBMISSION_IN_PROGRESS,
        target_state=ApplicationState.APPLIED_CONFIRMED,
        evidence_level="E1",
        min_evidence_level="E2",
    )
    with pytest.raises(GuardFailure):
        StateMachine.validate_transition(ctx_e1)

    # E2 is enough
    ctx_e2 = TransitionContext(
        application_id="app-1",
        current_state=ApplicationState.SUBMISSION_IN_PROGRESS,
        target_state=ApplicationState.APPLIED_CONFIRMED,
        evidence_level="E2",
        min_evidence_level="E2",
    )
    StateMachine.validate_transition(ctx_e2)


def test_submission_uncertain_requires_click() -> None:
    """Transition #23 requires click_started_at set."""
    ctx_unclicked = TransitionContext(
        application_id="app-1",
        current_state=ApplicationState.SUBMISSION_IN_PROGRESS,
        target_state=ApplicationState.SUBMISSION_UNCERTAIN,
        clicked_at_set=False,
    )
    with pytest.raises(GuardFailure):
        StateMachine.validate_transition(ctx_unclicked)

    ctx_clicked = TransitionContext(
        application_id="app-1",
        current_state=ApplicationState.SUBMISSION_IN_PROGRESS,
        target_state=ApplicationState.SUBMISSION_UNCERTAIN,
        clicked_at_set=True,
    )
    StateMachine.validate_transition(ctx_clicked)
