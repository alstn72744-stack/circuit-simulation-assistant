import unittest
from unittest.mock import patch, Mock

import numpy as np

from ac_result_analysis import analyze_ac, read_ac_result, MissingTraceError, gain_figure


class ACResultTests(unittest.TestCase):
    def test_synthetic_low_pass_nonunity_complex_reference(self):
        frequency = np.logspace(-2, 6, 801)
        gain, pole = 4.0, 1000.0
        expected_h = gain / (1 + 1j * frequency / pole)
        reference = (0.2 + frequency / 1e7) * np.exp(0.4j * np.log10(frequency))
        result = analyze_ac(frequency, expected_h * reference, reference)
        np.testing.assert_allclose(result.transfer, expected_h, rtol=1e-12)
        self.assertAlmostEqual(result.low_frequency_gain_db, 20 * np.log10(gain), places=7)
        # Exactly -3 dB is slightly below the pole's -3.0103 dB frequency.
        expected_bw = pole * np.sqrt(10 ** (3 / 10) - 1)
        self.assertLess(abs(result.bandwidth_hz / expected_bw - 1), 0.0002)

    def test_median_rejects_first_sample_outlier(self):
        frequency = np.logspace(-2, 6, 801)
        target = 4 / (1 + 1j * frequency / 1000)
        target[0] *= 100
        result = analyze_ac(frequency, target, np.ones(len(target)))
        self.assertAlmostEqual(result.low_frequency_gain_db, 20 * np.log10(4), places=7)
        self.assertEqual(result.baseline_count, 10)

    def test_no_crossing(self):
        frequency = np.logspace(0, 2, 101)
        result = analyze_ac(frequency, 2 / (1 + 1j * frequency / 1e6), np.ones(101))
        self.assertIsNone(result.bandwidth_hz)
        self.assertEqual(result.bandwidth_status, "Not found within sweep range")

    def test_log_interpolation_and_peaking_first_crossing(self):
        frequency = np.logspace(0, 6, 14)
        db = np.array([6.] * 10 + [10., 4., 2., 5.])
        result = analyze_ac(frequency, 10 ** (db / 20), np.ones(14))
        self.assertAlmostEqual(result.bandwidth_hz, np.sqrt(frequency[11] * frequency[12]), places=6)
        self.assertTrue(any("peaks" in note for note in result.notes))

    def test_invalid_samples_do_not_create_crossings(self):
        frequency = np.logspace(0, 5, 14)
        target = 10 ** (np.array([6.] * 10 + [4., 3., 2., 1.]) / 20)
        for invalid in (0, 1e-20, np.nan, np.inf):
            with self.subTest(reference=invalid):
                reference = np.ones(14)
                reference[11] = invalid
                result = analyze_ac(frequency, target, reference)
                self.assertIsNone(result.bandwidth_hz)
                self.assertTrue(np.isnan(result.gain_db[11]))
                self.assertIn("Cannot determine", result.bandwidth_status)
        with self.assertRaises(ValueError):
            analyze_ac(frequency, target, np.zeros(14))
        with self.assertRaises(ValueError):
            analyze_ac(frequency, np.zeros(14), np.ones(14))

    def test_invalid_frequency_and_too_few_samples(self):
        for frequency in ([1, 1, 2], [2, 1, 3], [0, 1, 2], [1, 2]):
            with self.subTest(frequency=frequency), self.assertRaises(ValueError):
                analyze_ac(frequency, np.ones(len(frequency)), np.ones(len(frequency)))

    def test_missing_trace_reports_both_names_without_guessing(self):
        raw = Mock()
        raw.get_raw_property.side_effect = lambda key: {"Plotname": "AC Analysis", "Flags": "complex"}[key]
        raw.get_trace_names.return_value = ["frequency", "V(output)", "V(input)"]
        with patch("ac_result_analysis.RawRead", return_value=raw):
            with self.assertRaises(MissingTraceError) as caught:
                read_ac_result("unused.raw", "V(out)", "V(in)")
        self.assertEqual(caught.exception.missing, ["V(out)", "V(in)"])
        self.assertEqual(caught.exception.available, raw.get_trace_names.return_value)
        raw.get_trace.assert_not_called()

    def test_graph_axes_and_threshold(self):
        frequency = np.logspace(0, 5, 101)
        result = analyze_ac(frequency, 4 / (1 + 1j * frequency / 1000), np.ones(101))
        fig = gain_figure(result)
        axis = fig.axes[0]
        self.assertEqual(axis.get_xscale(), "log")
        self.assertEqual(axis.get_ylabel(), "Gain [dB]")
        self.assertEqual(axis.lines[1].get_ydata()[0], result.threshold_db)
        self.assertEqual(axis.lines[2].get_xdata()[0], result.bandwidth_hz)


if __name__ == "__main__":
    unittest.main()
