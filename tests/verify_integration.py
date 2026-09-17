"""Check the Streamlit workflow; --real-ltspice also runs the existing test circuit.

Run from the project folder with .venv/Scripts/python.exe.
The original circuit referenced by test_ltspice.py is only read, never executed in place.
"""

import argparse
from summary_assertions import check_summary
import ast
import math
import statistics
import sys
from pathlib import Path
from unittest.mock import patch

import streamlit as st
from PyLTSpice import RawRead
from streamlit.testing.v1 import AppTest


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
from ac_result_analysis import read_ac_result, gain_figure

AC_REQUEST = "V(out)을 10 Hz부터 1 MHz까지 AC simulation하고 gain과 -3 dB bandwidth를 구해줘"


def run_button(app):
    return next(button for button in app.button if button.label == "Run Simulation")


def check_app(app):
    check_summary(app, required=any(item.value == 'Simulation completed' for item in app.success))
    assert not app.exception, [error.message for error in app.exception]


def review(app, name, data, request=AC_REQUEST):
    app.file_uploader[0].set_value((name, data, "application/octet-stream")).run()
    app.text_area[0].set_value(request).run()
    app.button[0].click().run()
    if app.selectbox[0].value == "AC":
        app.text_input(key="review_reference").set_value("V(vin)").run()
    check_app(app)
    assert run_button(app).disabled


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-ltspice", action="store_true")
    args = parser.parse_args()
    app = AppTest.from_file(str(PROJECT_DIR / "app.py"), default_timeout=60)

    # Both constructing SpiceEditor(.asc) and calling the runner can start LTspice.
    before_files = set((PROJECT_DIR / "simulation_input").glob("**/*"))
    with patch("PyLTSpice.SpiceEditor") as editor, patch("PyLTSpice.AscEditor") as schematic, patch("PyLTSpice.SimRunner") as runner:
        app.run()
        check_app(app)
        assert app.title[0].value == "Circuit Simulation Assistant"
        app.button[0].click().run()
        assert "upload" in app.warning[0].value.lower()
        review(app, "approval.asc", b"Version 4\n")
        assert app.text_input(key="review_start_frequency").value == "10 Hz"
        assert app.text_input(key="review_stop_frequency").value == "1 MHz"
        assert app.text_input(key="review_target").value == "V(out)"
        assert app.multiselect[0].value == ["Gain", "-3 dB Bandwidth"]
        assert app.number_input[0].value == 100
        assert app.code[0].value == ".ac dec 100 10 1Meg"
        # AppTest correctly rejects disabled clicks; inject a button event to
        # separately verify the server-side guard against unapproved execution.
        real_button = st.button
        with patch("streamlit.button", side_effect=lambda label, **kwargs:
                   True if label == "Run Simulation" else real_button(label, **kwargs)):
            app.run()
        assert "approve execution" in app.error[1].value
        app.run()
        check_app(app)
        app.checkbox[0].check().run()
        assert not run_button(app).disabled
        app.text_input(key="review_reference").set_value("V(other_input)").run()
        assert not app.checkbox[0].value and run_button(app).disabled
        app.checkbox[0].check().run()
        app.text_input[0].set_value("V(changed)").run()
        assert not app.checkbox[0].value and run_button(app).disabled
        app.checkbox[0].check().run()
        app.text_area[0].set_value("AC from 20 Hz to 2 MHz").run()
        assert len(app.checkbox) == 0
        app.button[0].click().run()
        assert not app.checkbox[0].value and run_button(app).disabled
        assert app.text_input(key="review_stop_frequency").value == "2 MHz"
        assert app.checkbox[0].disabled  # Reference must be reviewed again for the new request.
        app.text_input(key="review_reference").set_value("V(vin)").run()
        app.checkbox[0].check().run()
        app.file_uploader[0].set_value(("other.asc", b"Version 4\n", "text/plain")).run()
        assert len(app.checkbox) == 0
        app.button[0].click().run()
        assert not app.checkbox[0].value and run_button(app).disabled
        app.text_input(key="review_reference").set_value("V(vin)").run()
        app.checkbox[0].check().run()
        app.number_input[0].set_value(50).run()
        assert not app.checkbox[0].value and run_button(app).disabled
        assert app.code[0].value == ".ac dec 50 20 2Meg"
        app.text_input(key="review_stop_frequency").set_value("1 Hz").run()
        assert run_button(app).disabled and app.checkbox[0].disabled
        check_app(app)
        editor.assert_not_called()
        schematic.assert_not_called()
        runner.assert_not_called()
        assert set((PROJECT_DIR / "simulation_input").glob("**/*")) == before_files
    print("PASS: startup, approval guard, and approval reset on condition/request/upload changes")

    if not args.real_ltspice:
        return

    # Read the known successful circuit path without executing test_ltspice.py.
    tree = ast.parse((PROJECT_DIR / "test_ltspice.py").read_text(encoding="utf-8"))
    source = Path(next(
        ast.literal_eval(node.value)
        for node in tree.body if isinstance(node, ast.Assign)
        if any(isinstance(target, ast.Name) and target.id == "ASC_FILE" for target in node.targets)
    ))
    original = source.read_bytes()
    before_inputs = set((PROJECT_DIR / "simulation_input").glob("*/*.asc"))
    before_raw = set((PROJECT_DIR / "simulation_output").glob("*/*.raw"))
    review(app, source.name, original)
    app.text_input(key="review_target").set_value("V(vout)").run()
    app.checkbox[0].check().run()
    run_button(app).click().run(timeout=60)
    check_app(app)
    assert not app.error, [error.value for error in app.error]
    assert app.success[0].value == "Simulation completed"
    new_inputs = set((PROJECT_DIR / "simulation_input").glob("*/*.asc")) - before_inputs
    assert len(new_inputs) == 1
    saved = new_inputs.pop()
    assert source.read_bytes() == original
    saved_text = saved.read_text(encoding="utf-8", errors="replace")
    assert ".ac dec 100 10 1Meg" in saved_text and ".tran " not in saved_text.lower()
    new_raw = set((PROJECT_DIR / "simulation_output").glob("*/*.raw")) - before_raw
    raw = next(path for path in new_raw if not path.name.endswith(".op.raw"))
    log = raw.with_suffix(".log")
    assert raw.stat().st_size > 0 and log.stat().st_size > 0
    netlist = raw.with_suffix(".net").read_text(encoding="utf-8", errors="replace")
    assert ".ac dec 100 10 1Meg" in netlist and ".tran " not in netlist.lower()
    data = RawRead(raw)
    assert data.get_raw_property("Plotname") == "AC Analysis"
    axis = data.get_trace("frequency").get_wave().real
    assert abs(float(axis[0]) - 10) < 1e-6
    assert abs(float(axis[-1]) - 1_000_000) < 1e-3
    assert len(axis) == 501
    assert app.code[-1].value == ".ac dec 100 10 1Meg"
    assert any(str(raw) in item.value for item in app.markdown)
    assert any(str(log) in item.value for item in app.markdown)
    print(f"PASS: real Streamlit -> PyLTSpice -> LTspice AC; original unchanged, copy edited\nCOPY: {saved}")
    print(f"RAW: {raw} ({raw.stat().st_size} bytes)\nLOG: {log} ({log.stat().st_size} bytes)")
    print(f"PASS: .ac dec 100 10 1Meg; RAW frequency {axis[0]} to {axis[-1]} Hz, {len(axis)} points")

    result = read_ac_result(raw, "V(vout)", "V(vin)")
    assert len(app.metric) == 3
    assert app.metric[0].value == f"{result.low_frequency_gain_db:.3f} dB"
    assert result.bandwidth_hz is not None
    # Independent scalar math check, not a second call to the production algorithm.
    target_wave = data.get_trace("V(vout)").get_wave()
    reference_wave = data.get_trace("V(vin)").get_wave()
    scalar_db = [20 * math.log10(abs(complex(t) / complex(r))) for t, r in zip(target_wave, reference_wave)]
    scalar_g0 = statistics.median(scalar_db[:10])
    assert abs(result.low_frequency_gain_db - scalar_g0) < 1e-10
    for i in range(1, len(axis)):
        if scalar_db[i - 1] >= scalar_g0 - 3 > scalar_db[i]:
            weight = (scalar_g0 - 3 - scalar_db[i - 1]) / (scalar_db[i] - scalar_db[i - 1])
            scalar_bw = math.exp(math.log(axis[i - 1]) * (1 - weight) + math.log(axis[i]) * weight)
            break
    assert abs(result.bandwidth_hz / scalar_bw - 1) < 1e-10
    figure_path = raw.parent / "gain_frequency.png"
    gain_figure(result).savefig(figure_path, dpi=140)
    print(f"PASS: real RAW analysis G0={result.low_frequency_gain_db:.9f} dB, threshold={result.threshold_db:.9f} dB, BW={result.bandwidth_hz:.9f} Hz")
    print(f"PASS: independent scalar calculation agrees; GRAPH: {figure_path}")

    # Real missing-trace requests must report exact missing names and available traces.
    app.text_input(key="review_target").set_value("V(missing_target)").run()
    app.text_input(key="review_reference").set_value("V(missing_reference)").run()
    app.checkbox[0].check().run()
    run_button(app).click().run(timeout=60)
    check_app(app)
    assert app.success[0].value == "Simulation completed" and not app.metric
    assert "V(missing_target)" in app.error[0].value and "V(missing_reference)" in app.error[0].value
    assert "V(vout)" in app.code[-1].value and "V(vin)" in app.code[-1].value
    assert not any("simulation failed" in error.value.lower() for error in app.error)
    print("PASS: missing Target/Reference displayed with available RAW traces; no app crash")
    app.text_input(key="review_target").set_value("V(vout)").run()
    app.text_input(key="review_reference").set_value("V(vin)").run()

    # Verify user edits reach the real simulator rather than reusing parsed values.
    app.text_input(key="review_stop_frequency").set_value("2 MHz").run()
    app.number_input[0].set_value(20).run()
    assert run_button(app).disabled
    assert app.code[0].value == ".ac dec 20 10 2Meg"
    app.checkbox[0].check().run()
    before_edited = set((PROJECT_DIR / "simulation_output").glob("*/*.raw"))
    run_button(app).click().run(timeout=60)
    check_app(app)
    assert not app.error
    edited_raw = next(path for path in set((PROJECT_DIR / "simulation_output").glob("*/*.raw")) - before_edited
                      if not path.name.endswith(".op.raw"))
    edited_axis = RawRead(edited_raw).get_trace("frequency").get_wave().real
    assert abs(float(edited_axis[-1]) - 2_000_000) < 1e-3
    assert app.code[-1].value == ".ac dec 20 10 2Meg"
    print(f"PASS: edited .ac dec 20 10 2Meg executed; RAW: {edited_raw}")

    # A reviewed transient request preserves the previous .tran 1m behavior.
    review(app, source.name, original, "V(vout) transient simulation for 1 ms")
    before_legacy = set((PROJECT_DIR / "simulation_output").glob("*/*.raw"))
    app.checkbox[0].check().run()
    run_button(app).click().run(timeout=60)
    check_app(app)
    assert not app.error
    legacy_raw = next(path for path in set((PROJECT_DIR / "simulation_output").glob("*/*.raw")) - before_legacy
                      if not path.name.endswith(".op.raw"))
    assert RawRead(legacy_raw).get_raw_property("Plotname") == "Transient Analysis"
    assert source.read_bytes() == original
    print(f"PASS: existing saved-directive execution preserved; RAW: {legacy_raw}")

    # A missing model produces a real simulator failure, using only uploaded bytes.
    assert b"FQB55N10" in original
    invalid = original.replace(b"FQB55N10", b"MODEL_MISSING_FOR_VERIFICATION")
    review(app, "missing_model.asc", invalid)
    app.checkbox[0].check().run()
    run_button(app).click().run(timeout=60)
    check_app(app)
    assert len(app.error) >= 2 and not app.success
    assert "MODEL_MISSING_FOR_VERIFICATION" in app.error[1].value
    assert source.read_bytes() == original
    print("PASS: real LTspice failure displayed without an app crash")
    print(app.error[1].value)


if __name__ == "__main__":
    main()
