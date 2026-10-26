"""JOV.si Application State Machine.

Pure Python, zero I/O. Defines the 19 states and exactly 28 legal transition classes
from Blueprint v2.0 Section 9.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class ApplicationState(str, Enum):
    DISCOVERED = "DISCOVERED"
    ELIGIBILITY_CHECKED = "ELIGIBILITY_CHECKED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    LINK_INVALID = "LINK_INVALID"
    AWAITING_USER_INPUT = "AWAITING_USER_INPUT"
    SHORTLISTED = "SHORTLISTED"
    BELOW_THRESHOLD = "BELOW_THRESHOLD"
    RESUME_GENERATED = "RESUME_GENERATED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    MANUAL_HANDOFF = "MANUAL_HANDOFF"
    DUPLICATE_BLOCKED = "DUPLICATE_BLOCKED"
    APPROVED = "APPROVED"
    SUBMISSION_IN_PROGRESS = "SUBMISSION_IN_PROGRESS"
    APPLIED_CONFIRMED = "APPLIED_CONFIRMED"
    SUBMISSION_UNCERTAIN = "SUBMISSION_UNCERTAIN"
    APPLICATION_FAILED = "APPLICATION_FAILED"
    PAUSED_AUTH = "PAUSED_AUTH"
    WITHDRAWN = "WITHDRAWN"


TERMINAL_STATES: Set[ApplicationState] = {
    ApplicationState.REJECTED,
    ApplicationState.EXPIRED,
    ApplicationState.LINK_INVALID,
    ApplicationState.MANUAL_HANDOFF,
    ApplicationState.DUPLICATE_BLOCKED,
    ApplicationState.APPLIED_CONFIRMED,
    ApplicationState.WITHDRAWN,
}

# BELOW_THRESHOLD is terminal unless user explicitly overrides
SEMI_TERMINAL_STATES: Set[ApplicationState] = {
    ApplicationState.BELOW_THRESHOLD,
}


class IllegalTransition(Exception):
    """Raised when an illegal state transition is attempted."""

    def __init__(self, from_state: Optional[ApplicationState], to_state: ApplicationState, reason: str = ""):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        super().__init__(f"Illegal transition from {from_state} to {to_state}: {reason}")


class GuardFailure(Exception):
    """Raised when a transition is structurally legal but its guard condition fails."""

    def __init__(self, transition_id: int, reason: str):
        self.transition_id = transition_id
        self.reason = reason
        super().__init__(f"Guard check failed for transition #{transition_id}: {reason}")


class TransitionContext(BaseModel):
    """Snapshot context passed to guard functions to evaluate transition eligibility without I/O."""
    application_id: str
    current_state: Optional[ApplicationState]
    target_state: ApplicationState
    canonical_job_key: Optional[str] = None
    hard_rules_failed: bool = False
    rules_uncertain: bool = False
    deadline_passed: bool = False
    url_invalid: bool = False
    score: Optional[float] = None
    suitability_floor: float = 65.0
    user_override_reason: Optional[str] = None
    resume_stored: bool = False
    pdf_stored: bool = False
    gate_outcome: Optional[str] = None  # PASS, NEEDS_USER, BLOCKED, WARN
    is_unsupported_portal: bool = False
    is_captcha_wall: bool = False
    is_duplicate: bool = False
    has_unresolved_fields: bool = False
    approval_valid: bool = False
    approval_expired: bool = False
    package_hash_matches: bool = False
    caps_available: bool = False
    clicked_at_set: bool = False
    evidence_level: Optional[str] = None  # E0, E1, E2, E3
    min_evidence_level: str = "E2"
    explicit_rejection: bool = False
    negative_evidence_confirmed: bool = False
    paused_from_state: Optional[ApplicationState] = None


class StateMachine:
    """Pure domain state machine enforcing Blueprint v2.0 Section 9."""

    # Explicit mapping of the 28 legal transition pairs (from_state -> list of legal to_states)
    # Transitions from None (new application creation) is transition #1
    @classmethod
    def get_legal_transitions(cls) -> Dict[Optional[ApplicationState], Set[ApplicationState]]:
        """Return full map of valid from_state -> to_states."""
        # Non-terminal states eligible for PAUSED_AUTH and WITHDRAWN
        pre_submission_non_terminals = {
            ApplicationState.DISCOVERED,
            ApplicationState.ELIGIBILITY_CHECKED,
            ApplicationState.AWAITING_USER_INPUT,
            ApplicationState.SHORTLISTED,
            ApplicationState.RESUME_GENERATED,
            ApplicationState.READY_FOR_REVIEW,
            ApplicationState.APPROVED,
            ApplicationState.SUBMISSION_UNCERTAIN,
            ApplicationState.APPLICATION_FAILED,
        }

        transitions: Dict[Optional[ApplicationState], Set[ApplicationState]] = {
            None: {ApplicationState.DISCOVERED},  # #1
            ApplicationState.DISCOVERED: {
                ApplicationState.ELIGIBILITY_CHECKED,  # #2
                ApplicationState.REJECTED,             # #3
                ApplicationState.EXPIRED,              # #4
                ApplicationState.LINK_INVALID,         # #5
            },
            ApplicationState.ELIGIBILITY_CHECKED: {
                ApplicationState.AWAITING_USER_INPUT,  # #6
                ApplicationState.SHORTLISTED,          # #7
                ApplicationState.BELOW_THRESHOLD,      # #8
            },
            ApplicationState.BELOW_THRESHOLD: {
                ApplicationState.SHORTLISTED,          # #9 (User override)
            },
            ApplicationState.SHORTLISTED: {
                ApplicationState.RESUME_GENERATED,     # #10
            },
            ApplicationState.RESUME_GENERATED: {
                ApplicationState.READY_FOR_REVIEW,     # #11
                ApplicationState.MANUAL_HANDOFF,       # #12
                ApplicationState.LINK_INVALID,         # #13
                ApplicationState.DUPLICATE_BLOCKED,    # #14
            },
            ApplicationState.READY_FOR_REVIEW: {
                ApplicationState.AWAITING_USER_INPUT,  # #15
                ApplicationState.APPROVED,             # #18
                ApplicationState.MANUAL_HANDOFF,       # #12b (Manual handoff from review)
            },
            ApplicationState.AWAITING_USER_INPUT: {
                ApplicationState.READY_FOR_REVIEW,     # #16
                ApplicationState.ELIGIBILITY_CHECKED,  # #17
            },
            ApplicationState.APPROVED: {
                ApplicationState.READY_FOR_REVIEW,         # #19
                ApplicationState.SUBMISSION_IN_PROGRESS,   # #20
            },
            ApplicationState.SUBMISSION_IN_PROGRESS: {
                ApplicationState.READY_FOR_REVIEW,         # #21 (failure before click)
                ApplicationState.APPLIED_CONFIRMED,        # #22 (verified evidence >= min)
                ApplicationState.SUBMISSION_UNCERTAIN,     # #23 (clicked, no/weak proof)
                ApplicationState.APPLICATION_FAILED,       # #24 (explicit portal rejection)
            },
            ApplicationState.SUBMISSION_UNCERTAIN: {
                ApplicationState.APPLIED_CONFIRMED,        # #25 (reconciliation success)
                ApplicationState.APPLICATION_FAILED,       # #26 (reconciliation confirmed fail)
            },
            ApplicationState.APPLICATION_FAILED: {
                ApplicationState.READY_FOR_REVIEW,         # #27 (user chooses retry with negative evidence)
            },
            ApplicationState.PAUSED_AUTH: set(),           # Will be populated with return states
            ApplicationState.REJECTED: set(),
            ApplicationState.EXPIRED: set(),
            ApplicationState.LINK_INVALID: set(),
            ApplicationState.MANUAL_HANDOFF: set(),
            ApplicationState.DUPLICATE_BLOCKED: set(),
            ApplicationState.APPLIED_CONFIRMED: set(),
            ApplicationState.WITHDRAWN: set(),
        }

        # #28: Any pre-submission non-terminal can transition to PAUSED_AUTH or WITHDRAWN
        for s in pre_submission_non_terminals:
            transitions[s].add(ApplicationState.PAUSED_AUTH)
            transitions[s].add(ApplicationState.WITHDRAWN)

        # PAUSED_AUTH can transition back to any pre-submission non-terminal state
        for s in pre_submission_non_terminals:
            transitions[ApplicationState.PAUSED_AUTH].add(s)

        return transitions

    @classmethod
    def validate_transition(cls, ctx: TransitionContext) -> None:
        """Validate whether the transition is structurally legal and satisfies its guard."""
        legal = cls.get_legal_transitions()
        valid_targets = legal.get(ctx.current_state, set())

        if ctx.target_state not in valid_targets:
            raise IllegalTransition(ctx.current_state, ctx.target_state, "Not a permitted transition path")

        # Evaluate Guards (Blueprint v2.0 Section 9)
        from_s = ctx.current_state
        to_s = ctx.target_state

        if from_s is None and to_s == ApplicationState.DISCOVERED:
            if not ctx.canonical_job_key:
                raise GuardFailure(1, "Canonical job key is required")

        elif from_s == ApplicationState.DISCOVERED:
            if to_s == ApplicationState.ELIGIBILITY_CHECKED:
                if ctx.hard_rules_failed:
                    raise GuardFailure(2, "Hard rules failed; cannot move to ELIGIBILITY_CHECKED")
            elif to_s == ApplicationState.REJECTED:
                if not ctx.hard_rules_failed:
                    raise GuardFailure(3, "Rejection requires hard rule failure")
            elif to_s == ApplicationState.EXPIRED:
                if not ctx.deadline_passed:
                    raise GuardFailure(4, "Cannot move to EXPIRED without passed deadline")
            elif to_s == ApplicationState.LINK_INVALID:
                if not ctx.url_invalid:
                    raise GuardFailure(5, "Cannot move to LINK_INVALID without 404/410 status")

        elif from_s == ApplicationState.ELIGIBILITY_CHECKED:
            if to_s == ApplicationState.AWAITING_USER_INPUT:
                if not ctx.rules_uncertain:
                    raise GuardFailure(6, "Requires uncertain rule or low confidence")
            elif to_s == ApplicationState.SHORTLISTED:
                if ctx.score is None or ctx.score < ctx.suitability_floor:
                    raise GuardFailure(7, f"Score must be >= floor ({ctx.suitability_floor})")
            elif to_s == ApplicationState.BELOW_THRESHOLD:
                if ctx.score is None or ctx.score >= ctx.suitability_floor:
                    raise GuardFailure(8, f"Score must be below floor ({ctx.suitability_floor})")

        elif from_s == ApplicationState.BELOW_THRESHOLD and to_s == ApplicationState.SHORTLISTED:
            if not ctx.user_override_reason:
                raise GuardFailure(9, "Explicit user override reason required")

        elif from_s == ApplicationState.SHORTLISTED and to_s == ApplicationState.RESUME_GENERATED:
            if not (ctx.resume_stored and ctx.pdf_stored):
                raise GuardFailure(10, "Validated resume and PDF must be stored")

        elif from_s in (ApplicationState.RESUME_GENERATED, ApplicationState.READY_FOR_REVIEW) and to_s == ApplicationState.MANUAL_HANDOFF:
            if not (ctx.is_unsupported_portal or ctx.is_captcha_wall or ctx.user_override_reason):
                raise GuardFailure(12, "Requires unsupported portal, captcha or login wall, or user handoff request")
            elif to_s == ApplicationState.LINK_INVALID:
                if not ctx.url_invalid:
                    raise GuardFailure(13, "Requires apply page 404")
            elif to_s == ApplicationState.DUPLICATE_BLOCKED:
                if not ctx.is_duplicate:
                    raise GuardFailure(14, "Requires duplicate detection")

        elif from_s == ApplicationState.READY_FOR_REVIEW:
            if to_s == ApplicationState.AWAITING_USER_INPUT:
                if not ctx.has_unresolved_fields:
                    raise GuardFailure(15, "Requires unresolved or sensitive fields")
            elif to_s == ApplicationState.APPROVED:
                if ctx.gate_outcome != "PASS":
                    raise GuardFailure(18, "Gate outcome must be PASS to approve")
                if not ctx.package_hash_matches:
                    raise GuardFailure(18, "Approval must match current package hash")

        elif from_s == ApplicationState.AWAITING_USER_INPUT:
            if to_s == ApplicationState.READY_FOR_REVIEW:
                if ctx.gate_outcome == "BLOCKED":
                    raise GuardFailure(16, "Cannot return to review while gate is BLOCKED")

        elif from_s == ApplicationState.APPROVED:
            if to_s == ApplicationState.SUBMISSION_IN_PROGRESS:
                if not ctx.approval_valid or ctx.approval_expired:
                    raise GuardFailure(20, "Valid unexpired approval required")
                if not ctx.package_hash_matches:
                    raise GuardFailure(20, "Package hash must match approval")
                if not ctx.caps_available:
                    raise GuardFailure(20, "Daily rate caps must be available")

        elif from_s == ApplicationState.SUBMISSION_IN_PROGRESS:
            if to_s == ApplicationState.READY_FOR_REVIEW:
                if ctx.clicked_at_set:
                    raise GuardFailure(21, "Cannot return to review if submit click was initiated")
            elif to_s == ApplicationState.APPLIED_CONFIRMED:
                min_levels = {"E2": 2, "E3": 3}
                cur_lvl = {"E0": 0, "E1": 1, "E2": 2, "E3": 3}.get(ctx.evidence_level or "E0", 0)
                req_lvl = min_levels.get(ctx.min_evidence_level, 2)
                if cur_lvl < req_lvl:
                    raise GuardFailure(22, f"Evidence level {ctx.evidence_level} below required {ctx.min_evidence_level}")
            elif to_s == ApplicationState.SUBMISSION_UNCERTAIN:
                if not ctx.clicked_at_set:
                    raise GuardFailure(23, "Cannot enter UNCERTAIN if click was never initiated")
            elif to_s == ApplicationState.APPLICATION_FAILED:
                if not ctx.explicit_rejection:
                    raise GuardFailure(24, "Requires explicit portal rejection evidence")

        elif from_s == ApplicationState.SUBMISSION_UNCERTAIN:
            if to_s == ApplicationState.APPLIED_CONFIRMED:
                cur_lvl = {"E0": 0, "E1": 1, "E2": 2, "E3": 3}.get(ctx.evidence_level or "E0", 0)
                if cur_lvl < 2:
                    raise GuardFailure(25, "Reconciliation requires E2/E3 evidence")
            elif to_s == ApplicationState.APPLICATION_FAILED:
                if not ctx.negative_evidence_confirmed:
                    raise GuardFailure(26, "Requires verified absence of application")

        elif from_s == ApplicationState.APPLICATION_FAILED and to_s == ApplicationState.READY_FOR_REVIEW:
            if not ctx.negative_evidence_confirmed:
                raise GuardFailure(27, "Retry requires negative evidence that no application exists")
