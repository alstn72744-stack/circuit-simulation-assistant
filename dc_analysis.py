"""Single-source, ascending linear DC sweeps; no LLM or parameter sweeps."""
from decimal import Decimal, DecimalException
import math
import re

from ac_analysis import NUMBER, decimal_text

MEASUREMENTS = ["Minimum", "Maximum", "Value at Sweep Point", "Difference", "Absolute Difference", "Matching Error"]
VALUE = rf"{NUMBER}\s*(?:Meg|[pnuµμmkMG])?[VA]"
SOURCE = r"[VI][A-Za-z0-9_]+"
SIGNAL = r"(?<![a-z])((?:V|I[dgsb]?)\([^()\r\n]+\))"


def is_dc_request(text):
    if re.search(r"(?<![a-z])\.?dc(?![a-z])|직류", text, re.I):
        return True
    if re.search(r"(?<![a-z])\.?ac(?![a-z])|교류", text, re.I):
        return False
    return bool((re.search(r"sweep|스윕", text, re.I)
                    and re.search(rf"(?<![a-z0-9_(]){SOURCE}(?![a-z0-9_(])", text, re.I))
                or re.search(rf"{SOURCE}\s*=\s*{VALUE}", text, re.I))


def parse_dc_request(text):
    # A node inside V(vout) is not an independent source named vout.
    source = re.search(rf"(?<![a-z0-9_(])({SOURCE})(?![a-z0-9_(])", text, re.I)
    sweep = re.search(rf"({VALUE})\s*(?:부터|to|through|[~–—])\s*({VALUE})", text, re.I)
    # Prefer "step 10 uA": in "to 1 mA step 10 uA", the stop is not a step.
    step = re.search(rf"(?:step(?:\s+size)?|increment)\s*[:=]?\s*({VALUE})", text, re.I)
    if not step:
        step = re.search(rf"({VALUE})\s*(?:간격|씩|steps?)", text, re.I)
    point = re.search(rf"{SOURCE}\s*=\s*({VALUE})", text, re.I)
    if not point:
        point = re.search(rf"({VALUE})\s*에서", text, re.I)
    signals = list(dict.fromkeys(match.strip() for match in re.findall(SIGNAL, text, re.I)))
    measurements = []
    if re.search(r"minimum|\bmin\b|최소", text, re.I):
        measurements.append("Minimum")
    if re.search(r"maximum|\bmax\b|최대", text, re.I):
        measurements.append("Maximum")
    if point:
        measurements.append("Value at Sweep Point")
    if re.search(r"absolute\s+difference|절대\s*차", text, re.I):
        measurements.append("Absolute Difference")
    elif re.search(r"difference|차이", text, re.I):
        measurements.append("Difference")
    if re.search(r"matching\s*error|매칭\s*(?:오차|에러)|정합\s*오차", text, re.I):
        measurements.append("Matching Error")
    return {"analysis_type": "DC Sweep", "sweep_source": source[1] if source else "",
            "dc_start": sweep[1].strip() if sweep else "", "dc_stop": sweep[2].strip() if sweep else "",
            "dc_step": step[1].strip() if step else "", "target": signals[0] if signals else "",
            "dc_comparison": signals[1] if len(signals) > 1 else "",
            "dc_point": point[1].strip() if point else "",
            "dc_measurements": measurements or ["Minimum", "Maximum"]}


def source_unit(source):
    if not re.fullmatch(SOURCE, source, re.I):
        raise ValueError("Sweep Source must name one independent voltage/current source, e.g. V1 or I1.")
    return "V" if source[0].upper() == "V" else "A"


def dc_value(text, unit):
    match = re.fullmatch(rf"\s*({NUMBER})\s*(Meg|[pnuµμmkMG])?\s*([VAva])?\s*", text)
    if not match or (match[3] and match[3].upper() != unit):
        raise ValueError(f"Enter a finite value in {unit}, e.g. 0, 5 {unit}, or 10 m{unit}.")
    scales = {None: "1", "p": "1e-12", "n": "1e-9", "u": "1e-6", "µ": "1e-6", "μ": "1e-6",
              "m": "1e-3", "k": "1e3", "M": "1e6", "Meg": "1e6", "G": "1e9"}
    try:
        value = Decimal(match[1]) * Decimal(scales[match[2]])
        if not value.is_finite() or not math.isfinite(float(value)) or (value != 0 and float(value) == 0):
            raise ValueError("DC value is outside the finite numeric range.")
    except (DecimalException, OverflowError) as error:
        raise ValueError("DC value is outside the finite numeric range.") from error
    return value


def spice_value(value):
    for scale, suffix in ((Decimal('1e9'), 'G'), (Decimal('1e6'), 'Meg'), (Decimal('1e3'), 'k'),
                          (Decimal(1), ''), (Decimal('1e-3'), 'm'), (Decimal('1e-6'), 'u'),
                          (Decimal('1e-9'), 'n'), (Decimal('1e-12'), 'p')):
        if abs(value) >= scale:
            return decimal_text(value / scale) + suffix
    return str(value) if value else '0'


def build_dc_directive(sweep_source, start_value, stop_value, step_value):
    source = sweep_source.strip()
    unit = source_unit(source)
    start, stop, step = (dc_value(value, unit) for value in (start_value, stop_value, step_value))
    if start >= stop:
        raise ValueError("This version requires Start Value < Stop Value (ascending sweep).")
    if step <= 0 or step > stop - start or float(start) + float(step) <= float(start):
        raise ValueError("Step Value must be positive, resolvable, and no larger than the sweep range.")
    return f".dc {source} {spice_value(start)} {spice_value(stop)} {spice_value(step)}"


def validate_sweep_source(editor, source):
    available = editor.get_components("VI")
    if source.strip().casefold() not in {name.casefold() for name in available}:
        raise ValueError(f"Sweep source not found: {source}. Available independent sources: {', '.join(available)}")
