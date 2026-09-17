"""Run transient workflow checks; --real-ltspice runs the existing MOSFET circuit."""
import argparse
from summary_assertions import check_summary
import ast
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import streamlit as st
from PyLTSpice import RawRead
from streamlit.testing.v1 import AppTest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from transient_result_analysis import read_transient_result, waveform_figure

REQUEST = "V(out)을 1 ms 동안 transient simulation하고 V(in)과 비교해서 voltage gain과 output swing을 구해줘."


def run_button(app):
    return next(button for button in app.button if button.label == "Run Simulation")


def check(app):
    check_summary(app, required=any(item.value == 'Simulation completed' for item in app.success))
    assert not app.exception, [error.message for error in app.exception]


def prepare(app, name, data):
    app.file_uploader[0].set_value((name, data, "text/plain")).run()
    app.text_area[0].set_value(REQUEST).run()
    app.button[0].click().run()
    check(app)
    assert app.text_input(key="review_stop_time").value == "1 ms"
    assert app.text_input(key="review_target").value == "V(out)"
    assert app.text_input(key="review_reference").value == "V(in)"
    assert app.text_input(key="review_start_saving_time").value == ""
    assert app.text_input(key="review_maximum_timestep").value == ""
    assert app.code[0].value == ".tran 1m"
    assert run_button(app).disabled


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-ltspice", action="store_true")
    args = parser.parse_args()
    app = AppTest.from_file(str(PROJECT / "app.py"), default_timeout=60)
    before = set((PROJECT / "simulation_input").glob("**/*"))
    with patch("PyLTSpice.AscEditor") as editor, patch("PyLTSpice.SpiceEditor") as netlist, patch("PyLTSpice.SimRunner") as runner:
        app.run()
        prepare(app, "approval.asc", b"Version 4\n")
        original_button = st.button
        with patch("streamlit.button", side_effect=lambda label, **kwargs: True if label == "Run Simulation" else original_button(label, **kwargs)):
            app.run()
        check(app)
        app.run()
        app.checkbox[0].check().run()
        app.text_input(key="review_maximum_timestep").set_value("1 us").run()
        assert not app.checkbox[0].value and run_button(app).disabled
        assert app.code[0].value == ".tran 0 1m 0 1u"
        app.text_input(key="review_start_saving_time").set_value("2 ms").run()
        assert run_button(app).disabled and app.checkbox[0].disabled
        editor.assert_not_called()
        netlist.assert_not_called()
        runner.assert_not_called()
        assert set((PROJECT / "simulation_input").glob("**/*")) == before
    print("PASS: transient parsing, optional fields, preview, validation, approval guard; no files or simulator calls before approval")
    if not args.real_ltspice:
        return
    tree = ast.parse((PROJECT / "test_ltspice.py").read_text(encoding="utf-8"))
    source = Path(next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(name, ast.Name) and name.id == "ASC_FILE" for name in node.targets)))
    original = source.read_bytes()
    prepare(app, source.name, original)
    app.text_input(key="review_target").set_value("V(vout)").run()
    app.text_input(key="review_reference").set_value("V(vin)").run()
    before_raw = set((PROJECT / "simulation_output").glob("*/*.raw"))
    app.checkbox[0].check().run()
    run_button(app).click().run(timeout=60)
    check(app)
    assert not app.error, [error.value for error in app.error]
    assert app.success[0].value == "Simulation completed" and app.code[-1].value == ".tran 1m"
    raw = next(path for path in set((PROJECT / "simulation_output").glob("*/*.raw")) - before_raw if not path.name.endswith(".op.raw"))
    assert raw.stat().st_size > 0 and raw.with_suffix(".log").stat().st_size > 0
    assert source.read_bytes() == original
    saved = PROJECT / "simulation_input" / raw.parent.name / source.name
    assert ".tran 1m" in saved.read_text(encoding="utf-8")
    result = read_transient_result(raw, "V(vout)", "V(vin)", ["Voltage Gain", "Output Swing"])
    assert result.kind == "periodic" and len(app.metric) == 7
    gain = result.measurements["Voltage Gain"].values
    assert gain and not result.measurements["Voltage Gain"].reason
    # Independent extrema check over the last 0.3 ms (three known 10 kHz cycles).
    window = result.time >= 0.0007
    scalar_input = max(result.reference[window]) - min(result.reference[window])
    scalar_output = max(result.target[window]) - min(result.target[window])
    assert abs(gain["Voltage Gain"][0] / (scalar_output / scalar_input) - 1) < 0.001
    # Keep the app's evidence image intact; render verification separately.
    assert (raw.parent / "transient_waveform.png").stat().st_size > 0
    figure = raw.parent / "transient_waveform_verification.png"
    waveform_figure(result).savefig(figure, dpi=140)
    print(f"PASS: real transient .tran 1m; RAW: {raw}; LOG: {raw.with_suffix('.log')}")
    print(f"GAIN: {gain}\nSWING: {result.measurements['Output Swing'].values}\nNOTES: {result.notes}\nGRAPH: {figure}")

    app.text_input(key="review_stop_time").set_value("2 ms").run()
    app.text_input(key="review_start_saving_time").set_value("1 ms").run()
    app.text_input(key="review_maximum_timestep").set_value("1 us").run()
    app.multiselect[0].set_value(["Voltage Gain", "Output Swing", "Rise Time", "Fall Time", "Overshoot", "Settling Time"]).run()
    assert app.code[0].value == ".tran 0 2m 1m 1u" and run_button(app).disabled
    before_raw = set((PROJECT / "simulation_output").glob("*/*.raw"))
    app.checkbox[0].check().run()
    run_button(app).click().run(timeout=60)
    check(app)
    assert not app.error
    second = next(path for path in set((PROJECT / "simulation_output").glob("*/*.raw")) - before_raw if not path.name.endswith(".op.raw"))
    second_result = read_transient_result(second, "V(vout)", "V(vin)", ["Voltage Gain"])
    time = second_result.time
    assert abs(time[-1] - 0.002) < 1e-9 and time[0] >= 0.001 - 1e-9
    relative_time = RawRead(second).get_trace("time").get_wave()
    np.testing.assert_allclose(time, relative_time + 0.001, rtol=0, atol=1e-12)
    assert second_result.measurements["Voltage Gain"].values
    for measurement in ("Rise Time", "Fall Time", "Overshoot", "Settling Time"):
        assert any(measurement in item.value and "not applicable" in item.value for item in app.info)
    print(f"PASS: optional .tran 0 2m 1m 1u; saved interval {time[0]}–{time[-1]} s; sine step metrics rejected; RAW: {second}")

    app.text_input(key="review_target").set_value("V(missing)").run()
    app.checkbox[0].check().run()
    run_button(app).click().run(timeout=60)
    check(app)
    assert app.success and "V(missing)" in app.error[0].value
    assert "V(vout)" in app.code[-1].value
    assert source.read_bytes() == original
    print("PASS: missing transient trace reported with available traces; original preserved; no app crash")


if __name__ == "__main__":
    main()
