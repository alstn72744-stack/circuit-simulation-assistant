"""Deterministic DC measurements on one ascending sweep, retaining signed traces."""
from dataclasses import dataclass, field
import re

import numpy as np
from matplotlib.figure import Figure
from PyLTSpice import RawRead

from ac_result_analysis import MissingTraceError
from dc_analysis import MEASUREMENTS, source_unit


@dataclass
class DCResult:
    sweep: np.ndarray
    target: np.ndarray
    comparison: np.ndarray | None
    metrics: dict = field(default_factory=dict)  # label -> (value, unit)
    curves: dict = field(default_factory=dict)  # label -> (array, unit)
    notes: list = field(default_factory=list)
    point: float | None = None
    point_value: float | None = None
    target_name: str = "Target"
    comparison_name: str = "Comparison"
    target_unit: str = "V"
    comparison_unit: str = "V"
    sweep_source: str = ""


def trace_unit(name):
    if re.fullmatch(r"v\([^()]+\)", name, re.I):
        return "V"
    if re.fullmatch(r"i[dgsb]?\([^()]+\)", name, re.I):
        return "A"
    raise ValueError(f"Select a voltage or current trace; unsupported trace: {name}")


def analyze_dc(sweep, target, comparison=None, measurements=(), point=None, *,
               target_unit="V", comparison_unit="V", denominator_floor=1e-12):
    arrays = [np.asarray(value) for value in (sweep, target) + ((comparison,) if comparison is not None else ())]
    if any(np.iscomplexobj(a) or a.ndim != 1 for a in arrays):
        raise ValueError("DC data must be real one-dimensional arrays.")
    arrays = [a.astype(float) for a in arrays]
    x, y = arrays[:2]
    other = arrays[2] if comparison is not None else None
    if len(x) < 2 or any(a.shape != x.shape or not np.all(np.isfinite(a)) for a in arrays):
        raise ValueError("DC data require matching finite arrays with at least two samples; invalid gaps are not interpolated.")
    if not np.all(np.diff(x) > 0):
        raise ValueError("Only one strictly increasing DC sweep is supported; descending/nested sweeps are not supported.")
    if set(measurements) - set(MEASUREMENTS):
        raise ValueError("Unknown DC measurement.")
    if not np.isfinite(denominator_floor) or denominator_floor < 0:
        raise ValueError("Denominator floor must be finite and non-negative.")
    paired = any(name in measurements for name in ("Difference", "Absolute Difference", "Matching Error"))
    if paired and (other is None or target_unit != comparison_unit):
        raise ValueError("Difference and Matching Error require a comparison trace with the same physical unit.")
    result = DCResult(x, y, other, target_unit=target_unit, comparison_unit=comparison_unit)
    if "Minimum" in measurements:
        result.metrics["Minimum"] = (float(np.min(y)), target_unit)
    if "Maximum" in measurements:
        result.metrics["Maximum"] = (float(np.max(y)), target_unit)
    if "Value at Sweep Point" in measurements:
        if point is None or not np.isfinite(point) or not x[0] <= point <= x[-1]:
            raise ValueError("Selected sweep point is outside the saved sweep range or missing; extrapolation is not performed.")
        result.point, result.point_value = float(point), float(np.interp(point, x, y))
        result.metrics["Value at Sweep Point"] = (result.point_value, target_unit)
        result.notes.append("Value at Sweep Point uses linear interpolation between adjacent saved samples.")
    if paired:
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            difference = y - other
            if "Difference" in measurements:
                result.curves["Difference"] = (difference.copy(), target_unit)
                result.notes.append("Difference = Target - Comparison, preserving LTspice current direction/sign.")
            if "Absolute Difference" in measurements:
                result.curves["Absolute Difference"] = (np.abs(difference), target_unit)
                result.notes.append("Absolute Difference = abs(Target - Comparison).")
            if "Matching Error" in measurements:
                # Default definition deliberately uses Target (first trace) as I1.
                floor = max(denominator_floor, float(np.max(np.abs(y))) * 1e-9)
                valid = np.abs(y) > floor
                error = np.full(y.shape, np.nan)
                np.divide(np.abs(difference), np.abs(y), out=error, where=valid)
                error *= 100
                result.curves["Matching Error"] = (error, "%")
                result.notes.append(f"Matching Error (%) = abs(Target - Comparison) / abs(Target) * 100. Denominator: Target (first trace); values <= {floor:.6g} {target_unit} are excluded.")
        for name, (values, unit) in result.curves.items():
            values[~np.isfinite(values)] = np.nan
            finite = values[np.isfinite(values)]
            if len(finite):
                result.metrics[f"{name} Minimum"] = (float(np.min(finite)), unit)
                result.metrics[f"{name} Maximum"] = (float(np.max(finite)), unit)
            if len(finite) != len(values):
                result.notes.append(f"{name}: {len(values) - len(finite)} invalid/near-zero sample(s) have no value (NaN); gaps are not interpolated.")
    return result


def read_dc_result(raw_path, target_name, comparison_name="", measurements=(), point=None, *, sweep_source):
    raw = RawRead(raw_path)
    if raw.get_raw_property("Plotname").casefold() != "dc transfer characteristic":
        raise ValueError("DC measurements require a DC transfer characteristic RAW file.")
    if "stepped" in raw.get_raw_property("Flags").casefold():
        raise ValueError("Parameter-stepped RAW files are not supported.")
    source_unit(sweep_source)
    available = raw.get_trace_names()
    names = {name.casefold(): name for name in available}
    requested = [target_name.strip()] + ([comparison_name.strip()] if comparison_name.strip() else [])
    missing = [name for name in requested if name.casefold() not in names]
    if missing:
        raise MissingTraceError(missing, available)
    selected = [names[name.casefold()] for name in requested]
    units = [trace_unit(name) for name in selected]
    result = analyze_dc(raw.get_trace(0).get_wave(), raw.get_trace(selected[0]).get_wave(),
                        raw.get_trace(selected[1]).get_wave() if len(selected) > 1 else None,
                        measurements, point, target_unit=units[0], comparison_unit=units[-1])
    result.target_name = selected[0]
    result.comparison_name = selected[1] if len(selected) > 1 else "Comparison"
    result.sweep_source = sweep_source
    return result


def dc_figure(result):
    mixed = result.comparison is not None and result.target_unit != result.comparison_unit
    count = 1 + int(mixed) + len(result.curves)
    figure = Figure(figsize=(9, 3.2 * count))
    axes = figure.subplots(count, 1, squeeze=False).ravel()
    axes[0].plot(result.sweep, result.target, label=result.target_name)
    axes[0].set(title="DC Sweep", ylabel=f"Signal [{result.target_unit}]")
    if result.comparison is not None:
        comparison_axis = axes[1] if mixed else axes[0]
        comparison_axis.plot(result.sweep, result.comparison, label=result.comparison_name)
        comparison_axis.set_ylabel(f"Signal [{result.comparison_unit}]")
    if result.point_value is not None:
        axes[0].plot(result.point, result.point_value, "o", label="Selected sweep point")
    for axis, (name, (values, unit)) in zip(axes[1 + int(mixed):], result.curves.items()):
        axis.plot(result.sweep, values, label=name)
        axis.set_ylabel(f"{name} [{unit}]")
    for axis in axes:
        axis.set_xlabel(f"{result.sweep_source} [{source_unit(result.sweep_source)}]")
        axis.legend()
        axis.grid(True, alpha=0.3)
    figure.tight_layout()
    return figure
