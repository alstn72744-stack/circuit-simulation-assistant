"""Transient-only request parsing and validated LTspice .tran generation."""

from decimal import Decimal, DecimalException
import math
import re

from ac_analysis import NUMBER, decimal_text, apply_analysis_directive


MEASUREMENTS = ["Voltage Gain", "Output Swing", "Rise Time", "Fall Time", "Overshoot", "Settling Time"]
TIME_UNIT = r"(?:nanoseconds?|microseconds?|milliseconds?|seconds?|나노초|마이크로초|밀리초|ns|us|µs|μs|ms|s|초)"
TIME_VALUE = rf"{NUMBER}\s*{TIME_UNIT}"


def is_transient_request(text):
    return bool(re.search(r"(?<![a-z])(?:transient|\.?tran)(?![a-z])|과도\s*(?:해석|분석)", text, re.I))


def parse_transient_request(text):
    optional = {}
    remaining = text
    for field, label in (
        ("start_saving_time", r"start\s+saving(?:\s+time)?|save\s+from|저장\s*시작(?:\s*시간)?"),
        ("maximum_timestep", r"max(?:imum)?\s*time\s*step|최대\s*(?:시간\s*간격|타임스텝|timestep)"),
    ):
        match = re.search(rf"(?:{label})\s*[:=]?\s*({TIME_VALUE})", remaining, re.I)
        optional[field] = match[1].strip() if match else ""
        if match:
            remaining = remaining[:match.start()] + " " + remaining[match.end():]
    duration = re.search(rf"({TIME_VALUE})\s*(?:동안|간|까지)", remaining, re.I)
    if not duration:
        duration = re.search(rf"(?:for|stop(?:\s+time)?\s*[:=]?|until)\s+({TIME_VALUE})", remaining, re.I)
    if not duration:
        values = list(re.finditer(TIME_VALUE, remaining, re.I))
        duration_value = values[0][0] if len(values) == 1 else ""
    else:
        duration_value = duration[1]
    signals = re.findall(r"(?<![a-z])([vi])\(\s*([^()\r\n]+?)\s*\)", text, re.I)
    names = list(dict.fromkeys(f"{kind.upper()}({name.strip()})" for kind, name in signals))
    patterns = [r"(?:voltage\s*)?gain|전압\s*이득|이득", r"output\s*swing|출력\s*(?:스윙|범위)",
                r"rise\s*time|상승\s*시간", r"fall\s*time|하강\s*시간", r"overshoot|오버슈트",
                r"settling\s*time|정착\s*시간|안정화\s*시간"]
    return {"analysis_type": "Transient", "stop_time": duration_value.strip(), **optional,
            "target": names[0] if names else "", "reference": names[1] if len(names) > 1 else "",
            "transient_measurements": [name for name, pattern in zip(MEASUREMENTS, patterns) if re.search(pattern, text, re.I)]}


def time_seconds(text):
    match = re.fullmatch(rf"\s*({NUMBER})\s*({TIME_UNIT}|[num])?\s*", text, re.I)
    if not match:
        raise ValueError("Enter a time in ns, us, µs, ms or s.")
    unit = (match[2] or "s").casefold()
    if unit.startswith(("nano", "나노", "n")):
        scale = "1e-9"
    elif unit.startswith(("micro", "마이크로", "u", "µ", "μ")):
        scale = "1e-6"
    elif unit.startswith(("milli", "밀리", "m")):
        scale = "1e-3"
    else:
        scale = "1"
    try:
        value = Decimal(match[1]) * Decimal(scale)
        if not value.is_finite() or not math.isfinite(float(value)) or value < 0:
            raise ValueError("Times must be finite and non-negative.")
    except DecimalException as error:
        raise ValueError("Time is outside the supported numeric range.") from error
    return value


def spice_time(value):
    for scale, suffix in ((Decimal(1), ""), (Decimal("1e-3"), "m"), (Decimal("1e-6"), "u"), (Decimal("1e-9"), "n")):
        if value >= scale:
            return decimal_text(value / scale) + suffix
    return decimal_text(value)


def build_transient_directive(stop_time, start_saving_time="", maximum_timestep=""):
    stop = time_seconds(stop_time)
    if stop <= 0:
        raise ValueError("Stop Time must be positive.")
    start = time_seconds(start_saving_time) if start_saving_time.strip() else None
    maximum = time_seconds(maximum_timestep) if maximum_timestep.strip() else None
    if start is not None and start >= stop:
        raise ValueError("Start Saving Time must be less than Stop Time.")
    if maximum is not None and (maximum <= 0 or maximum > stop):
        raise ValueError("Maximum Timestep must be positive and no greater than Stop Time.")
    if start is None and maximum is None:
        return f".tran {spice_time(stop)}"
    # Tstep=0 lets LTspice use adaptive steps; Tstart=0 is a positional placeholder
    # only when dTmax was supplied without an explicit saving start.
    directive = f".tran 0 {spice_time(stop)} {spice_time(start or Decimal(0))}"
    return directive + (f" {spice_time(maximum)}" if maximum is not None else "")


def apply_transient_directive(editor, directive):
    apply_analysis_directive(editor, directive)
