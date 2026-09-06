"""ApprovalPolicy tests."""

from blheli32proxy.approval.models import ActivationRequest
from blheli32proxy.approval.policy import AllowAllPolicy, CountedLicensePolicy


def test_allow_all_always_approves():
    policy = AllowAllPolicy()
    result = policy.evaluate(ActivationRequest(esc_type="ARM", uuid="abc123"))
    assert result.approved
    assert result.remaining is None


def test_counted_policy_decrements_on_new_uuid(tmp_path):
    policy = CountedLicensePolicy(tmp_path / "state.json", initial_count=2)
    r1 = policy.evaluate(ActivationRequest(esc_type="ARM", uuid="uuid-1"))
    assert r1.approved and r1.remaining == 1

    r2 = policy.evaluate(ActivationRequest(esc_type="ARM", uuid="uuid-2"))
    assert r2.approved and r2.remaining == 0

    r3 = policy.evaluate(ActivationRequest(esc_type="ARM", uuid="uuid-3"))
    assert not r3.approved and r3.remaining == 0


def test_counted_policy_reactivating_same_uuid_does_not_decrement_again(tmp_path):
    policy = CountedLicensePolicy(tmp_path / "state.json", initial_count=1)
    first = policy.evaluate(ActivationRequest(esc_type="ARM", uuid="uuid-1"))
    assert first.approved and first.remaining == 0

    second = policy.evaluate(ActivationRequest(esc_type="ARM", uuid="uuid-1"))
    assert second.approved and second.remaining == 0
    assert second.message == "already activated"


def test_counted_policy_rejects_missing_uuid(tmp_path):
    policy = CountedLicensePolicy(tmp_path / "state.json", initial_count=5)
    result = policy.evaluate(ActivationRequest(esc_type="ARM", uuid=None))
    assert not result.approved


def test_counted_policy_persists_state_across_instances(tmp_path):
    state_path = tmp_path / "state.json"
    policy1 = CountedLicensePolicy(state_path, initial_count=3)
    policy1.evaluate(ActivationRequest(esc_type="ARM", uuid="uuid-1"))

    policy2 = CountedLicensePolicy(state_path, initial_count=3)  # should reuse existing state
    result = policy2.evaluate(ActivationRequest(esc_type="ARM", uuid="uuid-2"))
    assert result.remaining == 1  # 3 - 1 (uuid-1) - 1 (uuid-2)
