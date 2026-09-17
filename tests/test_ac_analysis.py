from pathlib import Path
import tempfile
import unittest

from PyLTSpice import AscEditor

from ac_analysis import parse_request, build_ac_directive, apply_ac_directive


class ACAnalysisTests(unittest.TestCase):
    def test_requested_korean_example(self):
        parsed = parse_request("V(out)을 10 Hz부터 1 MHz까지 AC simulation하고\ngain과 -3 dB bandwidth를 구해줘")
        self.assertEqual(parsed["analysis_type"], "AC")
        self.assertEqual(parsed["start_frequency"], "10 Hz")
        self.assertEqual(parsed["stop_frequency"], "1 MHz")
        self.assertEqual(parsed["target"], "V(out)")
        self.assertEqual(parsed["measurements"], ["Gain", "-3 dB Bandwidth"])

    def test_english_and_compact_range(self):
        for request in ("AC from 10Hz to 1MHz I(R1) gain", "AC 10 Hz ~ 1 MHz I(R1) gain"):
            with self.subTest(request=request):
                parsed = parse_request(request)
                self.assertEqual(parsed["stop_frequency"], "1 MHz")
                self.assertEqual(parsed["target"], "I(R1)")
                self.assertEqual(parsed["measurements"], ["Gain"])

    def test_missing_range_is_not_silently_defaulted(self):
        parsed = parse_request("AC gain for V(out)")
        self.assertEqual(parsed["start_frequency"], "")
        self.assertEqual(parsed["stop_frequency"], "")
        with self.assertRaises(ValueError):
            build_ac_directive("Decade", 100, "", "")

    def test_directive_units(self):
        self.assertEqual(build_ac_directive("Decade", 100, "10 Hz", "1 MHz"), ".ac dec 100 10 1Meg")
        self.assertEqual(build_ac_directive("Octave", 20, "1.5 kHz", "2.5 MHz"), ".ac oct 20 1.5k 2.5Meg")
        self.assertEqual(build_ac_directive("Linear", 50, "1e1", "1e6"), ".ac lin 50 10 1Meg")

    def test_invalid_conditions(self):
        for start, stop in (("0", "1 MHz"), ("-1 Hz", "1 MHz"), ("2 MHz", "1 MHz"),
                            ("10", "10"), ("nan", "1 MHz"), ("10 Hz\n.tran 1", "1 MHz"), ("10", "1 M")):
            with self.subTest(start=start, stop=stop), self.assertRaises(ValueError):
                build_ac_directive("Decade", 100, start, stop)
        for points in (0, -1, 1.5, True):
            with self.subTest(points=points), self.assertRaises(ValueError):
                build_ac_directive("Decade", points, "10", "1 MHz")

    def test_schematic_analysis_replacement_preserves_other_instructions(self):
        # Includes multiple analyses and a grouped .param block, plus a comment.
        source = (
            "Version 4\nSHEET 1 880 680\n"
            "TEXT 0 0 Left 2 !.tran 1m\n"
            "TEXT 0 40 Left 2 !.ac dec 10 1 100Meg\n"
            "TEXT 0 80 Left 2 !.dc V1 0 1 0.1\n"
            "TEXT 0 120 Left 2 !.op\n"
            "TEXT 0 160 Left 2 !.param R=1000\\n.tran 2m\n"
            "TEXT 0 200 Left 2 ;.tran comment must remain\n"
        )
        with tempfile.TemporaryDirectory() as folder:
            original, copy = Path(folder) / "source.asc", Path(folder) / "copy.asc"
            original.write_text(source, encoding="utf-8")
            editor = AscEditor(original)
            apply_ac_directive(editor, ".ac dec 100 10 1Meg")
            editor.save_netlist(copy)
            self.assertEqual(original.read_text(encoding="utf-8"), source)
            result = copy.read_text(encoding="utf-8")
            self.assertEqual(result.count("!.ac dec 100 10 1Meg"), 1)
            self.assertNotIn("!.tran", result)
            self.assertNotIn("!.dc", result)
            self.assertNotIn("!.op", result)
            self.assertIn("!.param R=1000", result)
            self.assertIn(";.tran comment must remain", result)
            self.assertNotIn(r"\n.tran", result)


if __name__ == "__main__":
    unittest.main()
