"""Conservative measurements on a single, finite, nonuniform transient waveform."""

from dataclasses import dataclass, field

import numpy as np
from matplotlib.figure import Figure
from PyLTSpice import RawRead

from ac_result_analysis import MissingTraceError
from transient_analysis import MEASUREMENTS


@dataclass
class Measurement:
    values: dict = field(default_factory=dict)  # label -> (value, unit)
    reason: str = ""


@dataclass
class TransientResult:
    time: np.ndarray
    target: np.ndarray
    reference: np.ndarray | None
    measurements: dict
    kind: str
    notes: list = field(default_factory=list)
    markers: list = field(default_factory=list)  # (time, voltage, label)
    settling_band: tuple | None = None
    target_name: str = "Target"
    reference_name: str = "Reference"


def _floor(signal):
    return max(1e-12, float(np.max(np.abs(signal))) * 1e-9)


def _crossings(time, signal, level, rising=True):
    if rising:
        indices = np.flatnonzero((signal[:-1] <= level) & (signal[1:] > level))
    else:
        indices = np.flatnonzero((signal[:-1] >= level) & (signal[1:] < level))
    return time[indices] + (level - signal[indices]) / (signal[indices + 1] - signal[indices]) * (time[indices + 1] - time[indices])


def _window(time, signal, start, stop):
    mask = (time > start) & (time < stop)
    return np.concatenate(([np.interp(start, time, signal)], signal[mask], [np.interp(stop, time, signal)]))


def _periodic(time, signal):
    """Require three recent complete cycles with stable period and phase shape."""
    if np.ptp(signal) <= _floor(signal):
        return None
    grid = np.linspace(time[0], time[-1], min(8192, max(256, 4 * len(time))))
    sampled = np.interp(grid, time, signal)
    middle = (np.percentile(sampled, 5) + np.percentile(sampled, 95)) / 2
    crossings = _crossings(time, signal, middle)
    if len(crossings) < 4:
        return None
    boundaries = crossings[-4:]
    periods = np.diff(boundaries)
    if np.ptp(periods) > 0.05 * np.mean(periods):
        return None
    if any(np.count_nonzero((time >= a) & (time <= b)) < 12 for a, b in zip(boundaries[:-1], boundaries[1:])):
        return None
    cycles = np.array([np.interp(np.linspace(a, b, 128), time, signal)
                       for a, b in zip(boundaries[:-1], boundaries[1:])])
    amplitude = float(np.ptp(cycles))
    if amplitude <= _floor(signal) or np.max(np.abs(cycles - np.median(cycles, axis=0))) > amplitude * 0.08:
        return None
    return boundaries[0], boundaries[-1], float(np.mean(periods))


def _step(time, signal):
    """Accept one sustained transition between stable endpoint plateaus only."""
    grid = np.linspace(time[0], time[-1], 1001)
    sampled = np.interp(grid, time, signal)
    initial, final = float(np.median(sampled[:51])), float(np.median(sampled[-101:]))
    delta = final - initial
    span = float(np.ptp(sampled))
    if abs(delta) <= _floor(signal) or abs(delta) < 0.5 * span:
        return None
    if np.ptp(sampled[:51]) > 0.02 * abs(delta) or np.ptp(sampled[-101:]) > 0.02 * abs(delta):
        return None
    progress = (signal - initial) / delta
    first = _crossings(time, progress, 0.01)
    ten, ninety = _crossings(time, progress, 0.1), _crossings(time, progress, 0.9)
    if not len(first) or len(ten) != 1 or not len(ninety):
        return None
    if not first[0] <= ten[0] < ninety[0] or np.any(progress[time >= ninety[0]] < 0.1):
        return None
    return initial, final, delta, progress, first[0], ten[0], ninety[0]


def _pulse_levels(time, signal):
    sampled = np.interp(np.linspace(time[0], time[-1], 2001), time, signal)
    low, high = np.percentile(sampled, [5, 95])
    span = high - low
    if span <= _floor(signal):
        return None
    low_fraction = np.mean(np.abs(sampled - low) <= 0.02 * span)
    high_fraction = np.mean(np.abs(sampled - high) <= 0.02 * span)
    if min(low_fraction, high_fraction) < 0.15 or low_fraction + high_fraction < 0.75:
        return None
    if not len(_crossings(time, signal, low + 0.5 * span)) or not len(_crossings(time, signal, low + 0.5 * span, False)):
        return None
    return float(low), float(high)


def analyze_transient(time, target, reference=None, measurements=(), settling_tolerance=0.02):
    time, target = np.asarray(time, dtype=float), np.asarray(target, dtype=float)
    reference = np.asarray(reference, dtype=float) if reference is not None else None
    if time.ndim != 1 or target.shape != time.shape or len(time) < 5:
        raise ValueError("Transient data require matching one-dimensional arrays with at least 5 samples.")
    if not np.all(np.isfinite(time)) or np.any(time < 0) or not np.all(np.diff(time) > 0):
        raise ValueError("Time must be finite, non-negative and strictly increasing.")
    if not np.all(np.isfinite(target)) or (reference is not None and (reference.shape != time.shape or not np.all(np.isfinite(reference)))):
        raise ValueError("Waveform data must have matching lengths and finite values; invalid gaps are not interpolated.")
    if not 0 < settling_tolerance < 1:
        raise ValueError("Settling tolerance must be between 0 and 1.")
    unknown = set(measurements) - set(MEASUREMENTS)
    if unknown:
        raise ValueError(f"Unknown measurements: {sorted(unknown)}")
    periodic = _periodic(time, target)
    step = None if periodic else _step(time, target)
    pulse = None if step else _pulse_levels(time, target)
    kind = "single step" if step else "pulse" if pulse else "periodic" if periodic else "undetermined / flat"
    result = TransientResult(time, target, reference, {}, kind)
    for name in dict.fromkeys(measurements):
        measurement = Measurement()
        result.measurements[name] = measurement
        if name == "Output Swing":
            measurement.values = {"Maximum": (float(np.max(target)), "V"), "Minimum": (float(np.min(target)), "V"),
                                  "Peak-to-Peak": (float(np.ptp(target)), "V")}
            result.notes.append("Output Swing uses the entire saved time interval.")
        elif name == "Voltage Gain":
            input_periodic = _periodic(time, reference) if reference is not None else None
            if reference is None or np.ptp(reference) <= _floor(reference):
                measurement.reason = "Reference is missing or Input Vpp is zero/near zero."
            elif not periodic or not input_periodic or abs(periodic[2] / input_periodic[2] - 1) > 0.05:
                measurement.reason = "Input/output do not show at least three complete, stable cycles with matching periods."
            else:
                start, stop, _ = input_periodic
                # Reject an output still changing in the common measurement window.
                if start < periodic[0] - periodic[2] or stop > periodic[1] + periodic[2]:
                    measurement.reason = "Stable input/output cycle windows do not overlap reliably."
                    continue
                vin = float(np.ptp(_window(time, reference, start, stop)))
                vout = float(np.ptp(_window(time, target, start, stop)))
                with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
                    gain = float(np.divide(vout, vin))
                if vin <= _floor(reference) or gain <= 0 or not np.isfinite(gain):
                    measurement.reason = "Finite voltage gain could not be determined."
                else:
                    measurement.values = {"Input Vpp": (vin, "V"), "Output Vpp": (vout, "V"),
                                          "Voltage Gain": (gain, "V/V"), "Voltage Gain (dB)": (float(20 * np.log10(gain)), "dB")}
                    result.notes.append(f"Vpp gain uses the last three complete input cycles: {start:.9g}–{stop:.9g} s. Magnitude only; inversion is not measured.")
        elif name in ("Rise Time", "Fall Time"):
            rising = name == "Rise Time"
            if step and (step[2] > 0) == rising:
                initial, final, delta, _, _, t10, t90 = step
                measurement.values[name] = (float(t90 - t10), "s")
                result.markers.extend([(t10, initial + 0.1 * delta, "10% transition"), (t90, initial + 0.9 * delta, "90% transition")])
            elif pulse:
                low, high = pulse
                progress = (target - low) / (high - low)
                progress = progress if rising else 1 - progress
                tens, nineties = _crossings(time, progress, 0.1), _crossings(time, progress, 0.9)
                returns = _crossings(time, progress, 0.1, False)
                for t10 in tens:
                    later = nineties[nineties > t10]
                    if len(later) and not np.any((returns > t10) & (returns < later[0])):
                        t90 = later[0]
                        measurement.values[name] = (float(t90 - t10), "s")
                        result.markers.extend([(t10, float(np.interp(t10, time, target)), "Edge start threshold"),
                                               (t90, float(np.interp(t90, time, target)), "Edge end threshold")])
                        break
                if not measurement.values:
                    measurement.reason = "A complete pulse edge could not be determined."
            else:
                measurement.reason = "A stable step/pulse with the requested edge direction was not identified."
        elif name in ("Overshoot", "Settling Time"):
            if not step:
                measurement.reason = "A single step with stable initial and final plateaus was not identified."
                continue
            initial, final, delta, progress, onset, _, _ = step
            if name == "Overshoot":
                peak_index = int(np.argmax(progress))
                overshoot = max(0., float(progress[peak_index] - 1))
                measurement.values = {"Peak excursion": (overshoot * abs(delta), "V"), "Overshoot": (100 * overshoot, "%")}
                result.markers.append((float(time[peak_index]), float(target[peak_index]), "Peak"))
            else:
                outside = np.flatnonzero((time >= onset) & (np.abs(progress - 1) > settling_tolerance))
                if not len(outside) or outside[-1] == len(time) - 1:
                    measurement.reason = "The waveform does not remain inside the final-value tolerance band."
                    continue
                index = outside[-1]
                boundary = 1 + settling_tolerance if progress[index] > 1 else 1 - settling_tolerance
                entry = time[index] + (boundary - progress[index]) / (progress[index + 1] - progress[index]) * (time[index + 1] - time[index])
                if time[-1] - entry < 0.1 * (time[-1] - time[0]):
                    measurement.reason = "Insufficient observation time after the last tolerance-band entry."
                    continue
                measurement.values[name] = (float(entry - onset), "s")
                result.settling_band = (final - settling_tolerance * abs(delta), final + settling_tolerance * abs(delta))
                result.markers.append((float(entry), float(np.interp(entry, time, target)), "Settled"))
                result.notes.append(f"Settling uses ±{100 * settling_tolerance:g}% of the step amplitude around the final level, measured from the interpolated 1% transition onset ({onset:.9g} s).")
    return result


def read_transient_result(raw_path, target_name, reference_name="", measurements=(), settling_tolerance=0.02):
    raw = RawRead(raw_path)
    if raw.get_raw_property("Plotname").casefold() != "transient analysis":
        raise ValueError("Transient measurements require a Transient Analysis RAW file.")
    if "stepped" in raw.get_raw_property("Flags").casefold():
        raise ValueError("Parameter-stepped RAW files are not supported.")
    available = raw.get_trace_names()
    names = {name.casefold(): name for name in available}
    requested = [target_name.strip()] + ([reference_name.strip()] if reference_name.strip() else [])
    missing = [name for name in requested if name.casefold() not in names]
    if missing:
        raise MissingTraceError(missing, available)
    selected = [names[name.casefold()] for name in requested]
    if not all(name.casefold().startswith("v(") for name in selected):
        raise ValueError("This version measures voltage waveforms only.")
    # LTspice stores time relative to the RAW header's saving-time Offset.
    # PyLTSpice corrects compression signs but does not add this header value.
    offset = float(raw.get_raw_property().get("Offset", 0))
    if not np.isfinite(offset) or offset < 0:
        raise ValueError("RAW time Offset must be finite and non-negative.")
    time = np.asarray(raw.get_trace("time").get_wave(), dtype=float) + offset
    result = analyze_transient(time, raw.get_trace(selected[0]).get_wave(),
                               raw.get_trace(selected[1]).get_wave() if len(selected) > 1 else None,
                               measurements, settling_tolerance)
    result.target_name = selected[0]
    result.reference_name = selected[1] if len(selected) > 1 else "Reference"
    return result


def format_value(value, unit):
    if unit == "s" and value != 0:
        for scale, label in ((1, "s"), (1e-3, "ms"), (1e-6, "µs"), (1e-9, "ns")):
            if abs(value) >= scale:
                return f"{value / scale:.6g} {label}"
    return f"{value:.6g} {unit}"


def waveform_figure(result):
    fig = Figure(figsize=(9, 4.5))
    ax = fig.subplots()
    ax.plot(result.time, result.target, label=result.target_name)
    if result.reference is not None:
        ax.plot(result.time, result.reference, label=result.reference_name, alpha=0.8)
    if result.settling_band:
        ax.axhspan(*result.settling_band, alpha=0.15, color="tab:green", label="Settling band")
    for time, value, label in result.markers:
        ax.plot(time, value, "o", label=label)
    ax.set(title="Transient Voltage Waveforms", xlabel="Time [s]", ylabel="Voltage [V]")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig
