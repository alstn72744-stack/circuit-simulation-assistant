"""Rule-based AC request parsing and deterministic directive generation."""

from decimal import Decimal
import re


NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
FREQUENCY = rf"{NUMBER}\s*(?:GHz|MHz|kHz|Hz)"
RANGE = re.compile(
    rf"(?P<start>{FREQUENCY})\s*(?:부터|to|through|[~〜–—-])\s*(?P<stop>{FREQUENCY})",
    re.IGNORECASE,
)
ANALYSIS_DIRECTIVE = re.compile(r"^\s*\.(?:ac|dc|tran|op|noise|tf|four)\b", re.IGNORECASE)


def detect_analysis_type(text):
    patterns = (
        (r"(?<![a-z])\.?ac(?![a-z])|교류", "AC"),
        (r"transfer\s+function|\.tf\b", "Transfer Function"),
        (r"(?<![a-z])(?:transient|\.?tran)(?![a-z])", "Transient"),
        (r"(?<![a-z])\.?dc(?![a-z])", "DC Sweep"),
        (r"operating\s+point|\.op\b", "Operating Point"),
        (r"noise", "Noise"),
        (r"fourier", "Fourier"),
    )
    for pattern, analysis in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return analysis
    return "AC"


def parse_request(text):
    """Extract explicit Hz ranges, V()/I() targets, and requested measurements.

    Missing frequencies stay empty so an unparsed request cannot silently run
    with a default 100 MHz stop frequency.
    """
    match = RANGE.search(text)
    target = re.search(r"(?<![a-z])([vi])\(\s*([^()\r\n]+?)\s*\)", text, re.IGNORECASE)
    measurements = []
    if re.search(r"gain|이득", text, re.IGNORECASE):
        measurements.append("Gain")
    if re.search(r"bandwidth|대역폭", text, re.IGNORECASE):
        measurements.append("-3 dB Bandwidth")
    if re.search(r"phase|위상", text, re.IGNORECASE):
        measurements.append("Phase")
    return {
        "analysis_type": detect_analysis_type(text),
        "target": f"{target[1].upper()}({target[2].strip()})" if target else "V(out)",
        "start_frequency": normalize_frequency(match["start"]) if match else "",
        "stop_frequency": normalize_frequency(match["stop"]) if match else "",
        "sweep_type": "Decade",
        "points": 100,
        "measurements": measurements,
    }


def normalize_frequency(text):
    match = re.fullmatch(rf"({NUMBER})\s*(GHz|MHz|kHz|Hz)", text, re.IGNORECASE)
    units = {"ghz": "GHz", "mhz": "MHz", "khz": "kHz", "hz": "Hz"}
    return f"{match[1]} {units[match[2].lower()]}"


def frequency_hz(text):
    match = re.fullmatch(rf"\s*({NUMBER})\s*(GHz|MHz|kHz|Hz|Meg|k|g)?\s*", text, re.IGNORECASE)
    if not match:
        raise ValueError("Enter a frequency in Hz, kHz, MHz or GHz (for example, 1 MHz).")
    scales = {"": "1", "hz": "1", "khz": "1e3", "k": "1e3", "mhz": "1e6",
              "meg": "1e6", "ghz": "1e9", "g": "1e9"}
    value = Decimal(match[1]) * Decimal(scales[(match[2] or "").lower()])
    if not value.is_finite() or value <= 0:
        raise ValueError("AC frequencies must be positive finite values.")
    return value


def spice_frequency(value):
    # LTspice interprets M as milli; always spell mega as Meg.
    for scale, suffix in ((Decimal("1e9"), "G"), (Decimal("1e6"), "Meg"), (Decimal("1e3"), "k")):
        if value >= scale:
            return decimal_text(value / scale) + suffix
    return decimal_text(value)


def decimal_text(value):
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def build_ac_directive(sweep_type, points, start_frequency, stop_frequency):
    sweep = {"Decade": "dec", "Octave": "oct", "Linear": "lin"}.get(sweep_type)
    if sweep is None:
        raise ValueError("Select a valid AC sweep type.")
    if isinstance(points, bool) or not isinstance(points, int) or points < 1:
        raise ValueError("Points must be a positive integer.")
    if sweep == "lin" and points < 2:
        raise ValueError("Linear sweeps require at least 2 points.")
    start, stop = frequency_hz(start_frequency), frequency_hz(stop_frequency)
    if start >= stop:
        raise ValueError("Stop Frequency must be greater than Start Frequency.")
    return f".ac {sweep} {points} {spice_frequency(start)} {spice_frequency(stop)}"


def apply_ac_directive(editor, directive):
    apply_analysis_directive(editor, directive)


def apply_analysis_directive(editor, directive):
    """Edit parsed schematic directives, preserving unrelated text and components."""
    for block in list(editor.directives):
        if block.type.name != "DIRECTIVE":
            continue
        # LTspice stores grouped instructions as literal backslash-n separators.
        lines = block.text.split(r"\n")
        retained = [line for line in lines if not ANALYSIS_DIRECTIVE.match(line)]
        if len(retained) == len(lines):
            continue
        if any(line.strip() for line in retained):
            # Keep .param/.model/etc. sharing the same schematic text block.
            block.text = r"\n".join(retained)
            editor.canvas_updated = True
        else:
            editor.remove_Xinstruction("^" + re.escape(block.text) + "$")
    editor.add_instruction(directive)
