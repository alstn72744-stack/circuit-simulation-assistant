import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PyLTSpice import AscEditor

from transient_analysis import parse_transient_request, build_transient_directive, apply_transient_directive
from transient_result_analysis import analyze_transient, read_transient_result, waveform_figure
from ac_result_analysis import MissingTraceError


class TransientParsingTests(unittest.TestCase):
    def test_requested_examples(self):
        parsed = parse_transient_request("V(out)을 1 ms 동안 transient simulation하고 V(in)과 비교해서 voltage gain과 output swing을 구해줘.")
        self.assertEqual(parsed["analysis_type"], "Transient")
        self.assertEqual(parsed["stop_time"], "1 ms")
        self.assertEqual(parsed["target"], "V(out)")
        self.assertEqual(parsed["reference"], "V(in)")
        self.assertEqual(parsed["transient_measurements"], ["Voltage Gain", "Output Swing"])
        self.assertEqual(parsed["start_saving_time"], "")
        self.assertEqual(parsed["maximum_timestep"], "")
        second = parse_transient_request("10 us 동안 transient 돌리고 V(out)의 rise time과 overshoot를 구해줘.")
        self.assertEqual(second["stop_time"], "10 us")
        self.assertEqual(second["reference"], "")
        self.assertEqual(second["transient_measurements"], ["Rise Time", "Overshoot"])

    def test_units_optional_fields_and_validation(self):
        for unit in ("us", "µs", "μs", "microseconds", "마이크로초"):
            self.assertEqual(build_transient_directive("10 " + unit), ".tran 10u")
        self.assertEqual(build_transient_directive("1 ms"), ".tran 1m")
        self.assertEqual(build_transient_directive("1 밀리초", "100 us", "10 ns"), ".tran 0 1m 100u 10n")
        self.assertEqual(build_transient_directive("1 ms", maximum_timestep="1 us"), ".tran 0 1m 0 1u")
        parsed = parse_transient_request("Run V(out) transient for 1 ms, start saving time: 100 us, maximum timestep=10 ns")
        self.assertEqual(parsed["stop_time"], "1 ms")
        self.assertEqual(parsed["start_saving_time"], "100 us")
        self.assertEqual(parsed["maximum_timestep"], "10 ns")
        for args in (("0",), ("-1 ms",), ("NaN",), ("1 ms", "2 ms"), ("1 ms", "", "0"), ("1 ms\n.ac dec 1 1 2",)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                build_transient_directive(*args)

    def test_transient_editor_preserves_original(self):
        source = "Version 4\nSHEET 1 880 680\nTEXT 0 0 Left 2 !.ac dec 100 10 1Meg\nTEXT 0 40 Left 2 !.tran 2m\nTEXT 0 80 Left 2 !.param R=1k\\n.dc V1 0 1 0.1\n"
        with tempfile.TemporaryDirectory() as directory:
            original, copy = Path(directory) / "source.asc", Path(directory) / "copy.asc"
            original.write_text(source)
            editor = AscEditor(original)
            apply_transient_directive(editor, ".tran 1m")
            editor.save_netlist(copy)
            self.assertEqual(original.read_text(), source)
            result = copy.read_text()
            self.assertEqual(result.count("!.tran 1m"), 1)
            self.assertNotIn(".ac ", result)
            self.assertNotIn(".dc ", result)
            self.assertIn(".param R=1k", result)


class TransientMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.time = np.linspace(0, 1, 10001)
        self.tau = 0.04
        self.step = np.where(self.time >= 0.1, 1 - np.exp(-np.maximum(self.time - 0.1, 0) / self.tau), 0.)

    def value(self, result, group, name):
        self.assertFalse(result.measurements[group].reason)
        return result.measurements[group].values[name][0]

    def test_known_rise_and_fall_with_interpolation(self):
        rise = analyze_transient(self.time, 2 + 3 * self.step, measurements=["Rise Time", "Fall Time"])
        fall = analyze_transient(self.time, 5 - 3 * self.step, measurements=["Fall Time"])
        expected = self.tau * np.log(9)
        self.assertAlmostEqual(self.value(rise, "Rise Time", "Rise Time"), expected, delta=1e-6)
        self.assertAlmostEqual(self.value(fall, "Fall Time", "Fall Time"), expected, delta=1e-6)
        self.assertFalse(rise.measurements["Fall Time"].values)

    def test_known_overshoot(self):
        damping, natural = 0.25, 80.
        elapsed = np.maximum(self.time - 0.1, 0)
        wd = natural * np.sqrt(1 - damping ** 2)
        response = 1 - np.exp(-damping * natural * elapsed) * (np.cos(wd * elapsed) + damping / np.sqrt(1 - damping ** 2) * np.sin(wd * elapsed))
        result = analyze_transient(self.time, 2 + 3 * response, measurements=["Overshoot"])
        expected = 100 * np.exp(-np.pi * damping / np.sqrt(1 - damping ** 2))
        self.assertAlmostEqual(self.value(result, "Overshoot", "Overshoot"), expected, delta=0.001)

    def test_known_settling_and_configurable_tolerance(self):
        for tolerance in (0.02, 0.05):
            result = analyze_transient(self.time, self.step, measurements=["Settling Time"], settling_tolerance=tolerance)
            expected = self.tau * np.log(0.99 / tolerance)  # from the 1% onset, explicitly defined
            self.assertAlmostEqual(self.value(result, "Settling Time", "Settling Time"), expected, delta=2e-6)

    def test_periodic_gain_and_inapplicable_step_metrics(self):
        reference = 2 + 0.2 * np.sin(2 * np.pi * 10 * self.time)
        target = 5 - 3 * (reference - 2)
        result = analyze_transient(self.time, target, reference, ["Voltage Gain", "Output Swing", "Rise Time", "Fall Time", "Overshoot", "Settling Time"])
        self.assertAlmostEqual(self.value(result, "Voltage Gain", "Input Vpp"), 0.4)
        self.assertAlmostEqual(self.value(result, "Voltage Gain", "Output Vpp"), 1.2)
        self.assertAlmostEqual(self.value(result, "Voltage Gain", "Voltage Gain"), 3.)
        self.assertAlmostEqual(self.value(result, "Voltage Gain", "Voltage Gain (dB)"), 20 * np.log10(3))
        for name in ("Rise Time", "Fall Time", "Overshoot", "Settling Time"):
            self.assertFalse(result.measurements[name].values)
            self.assertTrue(result.measurements[name].reason)

    def test_single_pulse_rise_and_fall(self):
        pulse = np.interp(self.time, [0, 0.1, 0.12, 0.5, 0.52, 1], [0, 0, 1, 1, 0, 0])
        result = analyze_transient(self.time, pulse, measurements=["Rise Time", "Fall Time", "Overshoot"])
        self.assertEqual(result.kind, "pulse")
        self.assertAlmostEqual(self.value(result, "Rise Time", "Rise Time"), 0.016)
        self.assertAlmostEqual(self.value(result, "Fall Time", "Fall Time"), 0.016)
        self.assertFalse(result.measurements["Overshoot"].values)

    def test_flat_input_invalid_and_ambiguous_responses(self):
        target = np.sin(2 * np.pi * 10 * self.time)
        for reference in (None, np.zeros(len(self.time)), np.full(len(self.time), 3.)):
            result = analyze_transient(self.time, target, reference, ["Voltage Gain", "Output Swing"])
            self.assertFalse(result.measurements["Voltage Gain"].values)
            self.assertAlmostEqual(self.value(result, "Output Swing", "Peak-to-Peak"), 2.)
        for ambiguous in (self.time, np.zeros(len(self.time)), np.sin(np.pi * self.time)):
            result = analyze_transient(self.time, ambiguous, measurements=["Rise Time", "Settling Time", "Overshoot"])
            self.assertTrue(all(not item.values for item in result.measurements.values()))
        target[50] = np.nan
        with self.assertRaises(ValueError):
            analyze_transient(self.time, target)

    def test_raw_saving_time_offset(self):
        raw = Mock()
        raw.get_trace_names.return_value = ["time", "V(output)"]
        raw.get_trace.side_effect = lambda name: Mock(get_wave=Mock(return_value=self.time if name == "time" else self.step))
        for offset in (None, "0.001"):
            properties = {"Plotname": "Transient Analysis", "Flags": "real"}
            if offset is not None:
                properties["Offset"] = offset
            raw.get_raw_property.side_effect = lambda key=None: properties if key is None else properties[key]
            with patch("transient_result_analysis.RawRead", return_value=raw):
                result = read_transient_result("unused.raw", "V(output)", measurements=["Rise Time"])
            np.testing.assert_allclose(result.time, self.time + float(offset or 0))
            self.assertAlmostEqual(self.value(result, "Rise Time", "Rise Time"), self.tau * np.log(9), delta=1e-6)
        for offset in ("nan", "-0.001"):
            properties["Offset"] = offset
            with patch("transient_result_analysis.RawRead", return_value=raw), self.assertRaisesRegex(ValueError, "Offset"):
                read_transient_result("unused.raw", "V(output)")

    def test_missing_trace_and_graph(self):
        raw = Mock()
        raw.get_raw_property.side_effect = lambda key: {"Plotname": "Transient Analysis", "Flags": "real"}[key]
        raw.get_trace_names.return_value = ["time", "V(output)"]
        with patch("transient_result_analysis.RawRead", return_value=raw), self.assertRaises(MissingTraceError) as caught:
            read_transient_result("unused.raw", "V(out)", "V(in)")
        self.assertEqual(caught.exception.missing, ["V(out)", "V(in)"])
        raw.get_trace.assert_not_called()
        result = analyze_transient(self.time, self.step, measurements=["Rise Time", "Settling Time"])
        figure = waveform_figure(result)
        self.assertEqual(figure.axes[0].get_xlabel(), "Time [s]")
        self.assertTrue(figure.axes[0].patches)


if __name__ == "__main__":
    unittest.main()
