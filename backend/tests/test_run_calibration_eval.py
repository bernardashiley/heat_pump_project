import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "run_calibration_eval.py"
SPEC = importlib.util.spec_from_file_location("run_calibration_eval", SCRIPT_PATH)
assert SPEC is not None
run_calibration_eval = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_calibration_eval)

RUN_ORDER = run_calibration_eval.RUN_ORDER
_run_applies = run_calibration_eval._run_applies


def _case(
    *,
    t_internal_c_source: str = "fallback",
    measured: bool = True,
) -> dict:
    measured_hlc = 5000.0 if measured else None
    measured_indoor = 21.5 if measured else None
    return {
        "t_internal_c_source": t_internal_c_source,
        "best_info_overrides": {
            "heat_loss_design_w_measured": measured_hlc,
            "t_internal_c_measured": measured_indoor,
        },
    }


def test_required_indoor_temperature_false_preserves_v1_run_eligibility() -> None:
    case = _case(t_internal_c_source="fallback", measured=True)

    applies = {
        run_name: _run_applies(case, run_name)
        for run_name in RUN_ORDER
    }

    assert applies == {
        "A-full": True,
        "A-subset": True,
        "B": True,
        "C": True,
        "D": True,
        "E": True,
        "F": True,
    }


def test_required_indoor_temperature_excludes_fallback_from_full_set_runs() -> None:
    fallback_case = _case(t_internal_c_source="fallback", measured=True)
    declared_case = _case(t_internal_c_source="declared", measured=False)
    measured_case = _case(t_internal_c_source="measured", measured=True)

    fallback_applies = {
        run_name: _run_applies(
            fallback_case,
            run_name,
            require_measured_indoor_temperature=True,
        )
        for run_name in RUN_ORDER
    }

    assert fallback_applies["A-full"] is False
    assert fallback_applies["F"] is False
    assert fallback_applies["B"] is True
    assert fallback_applies["C"] is True
    assert fallback_applies["D"] is True
    assert fallback_applies["E"] is True

    assert _run_applies(
        declared_case,
        "A-full",
        require_measured_indoor_temperature=True,
    )
    assert _run_applies(
        declared_case,
        "F",
        require_measured_indoor_temperature=True,
    )
    assert _run_applies(
        measured_case,
        "A-full",
        require_measured_indoor_temperature=True,
    )
    assert _run_applies(
        measured_case,
        "F",
        require_measured_indoor_temperature=True,
    )
