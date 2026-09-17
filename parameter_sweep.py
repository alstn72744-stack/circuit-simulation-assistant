"""Parse and validate component-value sweep requests, without any execution."""
from decimal import Decimal, DecimalException
import math
import re

from ac_analysis import NUMBER, parse_request
from transient_analysis import parse_transient_request, MEASUREMENTS as TRANSIENT_MEASUREMENTS
from dc_analysis import parse_dc_request, MEASUREMENTS as DC_MEASUREMENTS

COMPONENT = r"(?<![A-Za-z0-9_(])([RCL][A-Za-z0-9_]+)(?![A-Za-z0-9_])(?=\s*(?:을|를|은|는|from\b|values?\b|=|[+\-.\d]))"
ANALYSES = ["Not specified", "AC", "Transient", "DC Sweep"]
MEASUREMENTS = list(dict.fromkeys(["Gain", "-3 dB Bandwidth", "Phase", "Peak Gain"]
                                 + TRANSIENT_MEASUREMENTS + DC_MEASUREMENTS))
EXECUTION_NOTICE = "Parameter Sweep execution will be implemented in the next step."


class ComponentNotFoundError(ValueError):
    def __init__(self, component, available):
        self.available = available
        message = f"Component not found: {component}" if component else "Enter a component name (input is empty)."
        super().__init__(message)


def validate_asc_component(asc_data, component):
    """Read top-level SYMBOL/InstName records from upload bytes; never write/run.

    UTF-16 BOM and UTF-8 are decoded directly. Legacy ANSI files retain their
    ASCII record/component names via Latin-1; no symbol files are loaded.
    """
    try:
        text = asc_data.decode("utf-16" if asc_data.startswith((b'\xff\xfe', b'\xfe\xff')) else "utf-8-sig")
    except UnicodeDecodeError:
        text = asc_data.decode("latin-1")
    if not re.match(r"\s*Version\s+\d+\b", text, re.I):
        raise ValueError("Cannot read component names: invalid ASC header.")
    names = {}
    in_symbol = False
    for line in text.splitlines():
        if re.match(r"\s*SYMBOL\s+", line, re.I):
            in_symbol = True
        elif re.match(r"\s*TEXT\s+", line, re.I):
            in_symbol = False
        elif in_symbol:
            match = re.fullmatch(r"\s*SYMATTR\s+InstName\s+(\S+)\s*", line, re.I)
            if match:
                names.setdefault(match[1].casefold(), match[1])
                in_symbol = False
    requested = component.strip()
    if not requested or requested.casefold() not in names:
        raise ComponentNotFoundError(requested, list(names.values()))
    return names[requested.casefold()]


def is_parameter_sweep_request(text):
    explicit = re.search(r"parameter\s*sweep|파라미터\s*(?:sweep|스윕)", text, re.I)
    component = re.search(COMPONENT, text, re.I)
    action = re.search(r"sweep|스윕|바꿔가며|바꾸어가며|변경하며|\bvary\b", text, re.I)
    return bool(explicit or (component and action))


def parse_parameter_sweep(text):
    component = re.search(COMPONENT, text, re.I)
    tail = text[component.end():] if component else ""
    tail = re.sub(r"^\s*(?:을|를|은|는|values?\s*[:=]?|=)?\s*", "", tail, flags=re.I)
    interval = re.search(r"([^\s,]+?)\s*부터\s*([^\s,]+?)\s*까지\s*([^\s,]+?)\s*간격", tail)
    if not interval:
        interval = re.search(r"from\s+(\S+)\s+to\s+(\S+)\s+(?:step|increment)\s+(\S+)", tail, re.I)
    range_requested = bool(interval or re.search(r"부터|\bfrom\b", tail, re.I))
    values = []
    if not range_requested and "," in tail:
        # Keep every token, including malformed ones, for visible validation.
        value_text = re.split(r"(?:으로|로)\s*(?:바꿔|바꾸|변경)|\b(?:for|and)\b", tail, maxsplit=1, flags=re.I)[0]
        values = [value.strip() for value in value_text.strip().split(",")]
    analysis = "Not specified"
    measurements = []
    if re.search(r"(?<![a-z])\.?ac(?![a-z])|교류", text, re.I):
        analysis, measurements = "AC", parse_request(text)["measurements"]
    elif re.search(r"(?<![a-z])(?:transient|\.?tran)(?![a-z])|과도", text, re.I):
        analysis, measurements = "Transient", parse_transient_request(text)["transient_measurements"]
    elif re.search(r"(?<![a-z])\.?dc(?![a-z])|직류", text, re.I):
        analysis, measurements = "DC Sweep", parse_dc_request(text)["dc_measurements"]
    return {"sweep_type": "Component Value", "component": component[1].upper() if component else "",
            "value_mode": "Start / Stop / Step" if range_requested else "Explicit Values",
            "values": values, "start": interval[1] if interval else "",
            "stop": interval[2] if interval else "", "step": interval[3] if interval else "",
            "analysis_type": analysis, "measurements": measurements}


def component_value(text):
    """Positive numeric R/C/L values with SPICE suffixes; M means milli, Meg mega."""
    match = re.fullmatch(rf"\s*({NUMBER})\s*(meg|[fpnuµμmkgt])?\s*", text, re.I)
    if not match:
        raise ValueError(f"Invalid component value: {text!r}. Use values such as 1k, 10n or 1Meg.")
    scales = {"": "1", "f": "1e-15", "p": "1e-12", "n": "1e-9", "u": "1e-6", "µ": "1e-6",
              "μ": "1e-6", "m": "1e-3", "k": "1e3", "meg": "1e6", "g": "1e9", "t": "1e12"}
    try:
        value = Decimal(match[1]) * Decimal(scales[(match[2] or "").lower()])
        if value <= 0 or not math.isfinite(float(value)) or float(value) == 0:
            raise ValueError("Component values must be positive and finite.")
    except (DecimalException, OverflowError) as error:
        raise ValueError("Component value is outside the supported numeric range.") from error
    return value


def validate_parameter_sweep(conditions):
    if conditions["sweep_type"] != "Component Value":
        raise ValueError("Only Component Value requests are supported.")
    if not re.fullmatch(r"[RCL][A-Za-z0-9_]+", conditions["component"].strip(), re.I):
        raise ValueError("Enter one R/C/L component name, e.g. R1, CL or L3.")
    if conditions["value_mode"] == "Explicit Values":
        values = conditions["values"]
        if len(values) < 2:
            raise ValueError("Enter at least two comma-separated values.")
        for value in values:
            component_value(value)
    elif conditions["value_mode"] == "Start / Stop / Step":
        start, stop, step = (component_value(conditions[key]) for key in ("start", "stop", "step"))
        if start >= stop or step > stop - start:
            raise ValueError("Require Start < Stop and a positive Step no larger than the range.")
    else:
        raise ValueError("Select Explicit Values or Start / Stop / Step.")
    if conditions["analysis_type"] not in ANALYSES[1:]:
        raise ValueError("Select the analysis type; it was not specified in the request.")
    if set(conditions["measurements"]) - set(MEASUREMENTS):
        raise ValueError("Unknown measurement.")


def generate_sweep_values(conditions, max_points=100):
    """Decimal arithmetic, inclusive reachable stop; never force an off-grid stop."""
    validate_parameter_sweep(conditions)
    if conditions['value_mode'] == 'Explicit Values':
        if len(conditions['values']) > max_points:
            raise ValueError(f"At most {max_points} sweep points are supported.")
        return [component_value(value) for value in conditions['values']]
    start, stop, step = (component_value(conditions[key]) for key in ('start', 'stop', 'step'))
    if start + step <= start:
        raise ValueError("Step is too small to resolve at this start value.")
    intervals = (stop - start) / step
    if intervals >= max_points:
        raise ValueError(f"At most {max_points} sweep points are supported.")
    count = int(intervals) + 1
    return [start + index * step for index in range(count)]
