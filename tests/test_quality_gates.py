import pytest
from app.orchestration.gates import GateFailed, GateStatus, evaluate, require


def test_fail_stops_next_stage():
    report = evaluate("topology", {"mesh_exists": True, "has_volume": False})
    assert report.status is GateStatus.FAIL
    with pytest.raises(GateFailed):
        require(report)


def test_warning_can_continue():
    assert require(evaluate("image", {"readable": True}, ["low resolution"])).status is GateStatus.WARNING
