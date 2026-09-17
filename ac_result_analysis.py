"""Deterministic voltage-transfer analysis for a single low-pass AC sweep."""

from dataclasses import dataclass

import numpy as np
from PyLTSpice import RawRead
from matplotlib.figure import Figure


class MissingTraceError(ValueError):
    def __init__(self, missing, available):
        self.missing = missing
        self.available = available
        super().__init__("Trace not found: " + ", ".join(repr(name) for name in missing))


@dataclass
class ACResult:
    frequency: np.ndarray
    target: np.ndarray
    reference: np.ndarray
    transfer: np.ndarray
    gain_db: np.ndarray
    low_frequency_gain_db: float
    threshold_db: float
    bandwidth_hz: float | None
    bandwidth_status: str
    baseline_count: int
    baseline_stop_hz: float
    notes: list[str]
    target_name: str = "Target"
    reference_name: str = "Reference"


def analyze_ac(frequency, target, reference):
    """Use median dB gain in the first min(10, N) samples (at least 3 valid).

    Crossings use gain in dB vs log10(f), without bridging invalid samples.
    Reference amplitudes <= 1e-12 times their maximum are considered unusable.
    A sweep must start in the low-frequency passband for the estimate to be meaningful.
    """
    frequency = np.asarray(frequency, dtype=float)
    target = np.asarray(target, dtype=complex)
    reference = np.asarray(reference, dtype=complex)
    if any(data.ndim != 1 for data in (frequency, target, reference)):
        raise ValueError("AC data must be one-dimensional arrays.")
    if len(frequency) < 3 or target.shape != frequency.shape or reference.shape != frequency.shape:
        raise ValueError("AC data must have matching lengths and at least 3 samples.")
    if not np.all(np.isfinite(frequency) & (frequency > 0)) or not np.all(np.diff(frequency) > 0):
        raise ValueError("Frequency must be finite, positive and strictly increasing; stepped sweeps are not supported.")

    finite = np.isfinite(target) & np.isfinite(reference)
    with np.errstate(over="ignore", invalid="ignore"):
        ref_magnitude = np.abs(reference)
    usable_ref = np.isfinite(ref_magnitude)
    max_reference = np.max(ref_magnitude[usable_ref], initial=0.0)
    valid = finite & usable_ref & (ref_magnitude > max_reference * 1e-12)
    transfer = np.full(target.shape, complex(np.nan, np.nan))
    gain_db = np.full(frequency.shape, np.nan)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore", under="ignore"):
        np.divide(target, reference, out=transfer, where=valid)
        magnitude = np.abs(transfer)
        valid &= np.isfinite(transfer) & np.isfinite(magnitude) & (magnitude > 0)
        gain_db[valid] = 20 * np.log10(magnitude[valid])
    valid &= np.isfinite(gain_db)
    gain_db[~valid] = np.nan
    transfer[~valid] = complex(np.nan, np.nan)

    window = min(10, len(frequency))
    baseline = gain_db[:window][valid[:window]]
    if len(baseline) < 3:
        raise ValueError("Cannot estimate low-frequency gain: fewer than 3 valid samples in the initial frequency window. Check reference amplitude and trace data.")
    g0 = float(np.median(baseline))
    threshold = g0 - 3.0
    notes = []
    if not np.all(valid):
        notes.append(f"{int(np.sum(~valid))} invalid sample(s) excluded (zero/near-zero reference, zero target or non-finite data). Gaps are not interpolated.")
    if np.ptp(baseline) > 0.5:
        notes.append("Initial gain varies by more than 0.5 dB; the sweep may not start in a flat low-frequency passband.")
    if np.nanmax(gain_db) > g0 + 1.0:
        notes.append("Response peaks more than 1 dB above the initial gain. Bandwidth uses the first downward crossing relative to the low-frequency baseline.")

    bandwidth = None
    status = "Not found within sweep range"
    if valid[0] and gain_db[0] < threshold:
        status = "Cannot determine: response starts below the -3 dB level"
    else:
        for index in range(1, len(frequency)):
            if (valid[index - 1] and valid[index] and gain_db[index - 1] >= threshold
                    and gain_db[index] <= threshold and gain_db[index - 1] > gain_db[index]):
                if not np.all(valid[:index + 1]):
                    status = "Cannot determine first crossing: invalid samples before the crossing"
                    break
                fraction = (threshold - gain_db[index - 1]) / (gain_db[index] - gain_db[index - 1])
                log_f = np.log10(frequency[index - 1]) + fraction * (
                    np.log10(frequency[index]) - np.log10(frequency[index - 1]))
                bandwidth = float(10 ** log_f)
                status = "Found"
                break
        if bandwidth is None and status == "Not found within sweep range" and not np.all(valid):
            status = "Cannot determine: invalid samples within sweep range"

    return ACResult(frequency, target, reference, transfer, gain_db, g0, threshold,
                    bandwidth, status, len(baseline), float(frequency[window - 1]), notes)


def read_ac_result(raw_path, target_name, reference_name):
    raw = RawRead(raw_path)
    if raw.get_raw_property("Plotname").casefold() != "ac analysis":
        raise ValueError("Result analysis supports AC RAW files only.")
    if "stepped" in raw.get_raw_property("Flags").casefold():
        raise ValueError("Parameter-stepped AC RAW files are not supported in this version.")
    available = raw.get_trace_names()
    # SPICE names are case-insensitive; do not fuzzy-match or guess signal names.
    names = {name.casefold(): name for name in available}
    requested = [target_name.strip(), reference_name.strip()]
    missing = [name for name in requested if name.casefold() not in names]
    if missing:
        raise MissingTraceError(missing, available)
    target, reference = [names[name.casefold()] for name in requested]
    if not all(name.casefold().startswith("v(") for name in (target, reference)):
        raise ValueError("Voltage gain requires voltage traces for both Target and Reference.")
    # Explicitly load traces: RawRead may delay reading binary data until accessed.
    frequency = raw.get_trace("frequency").get_wave().real
    result = analyze_ac(frequency, raw.get_trace(target).get_wave(), raw.get_trace(reference).get_wave())
    result.target_name, result.reference_name = target, reference
    return result


def format_frequency(frequency):
    for scale, unit in ((1e9, "GHz"), (1e6, "MHz"), (1e3, "kHz")):
        if frequency >= scale:
            return f"{frequency / scale:.6g} {unit}"
    return f"{frequency:.6g} Hz"


def gain_figure(result):
    fig = Figure(figsize=(8, 4.5))
    ax = fig.subplots()
    ax.semilogx(result.frequency, result.gain_db,
                label=f"{result.target_name} / {result.reference_name}")
    ax.axhline(result.threshold_db, color="tab:orange", linestyle="--", label="Low-frequency gain - 3 dB")
    if result.bandwidth_hz is not None:
        ax.axvline(result.bandwidth_hz, color="tab:green", linestyle=":",
                   label=f"Bandwidth: {format_frequency(result.bandwidth_hz)}")
        ax.plot(result.bandwidth_hz, result.threshold_db, "o", color="tab:green")
    ax.set(title="AC Voltage Gain vs Frequency", xlabel="Frequency [Hz]", ylabel="Gain [dB]")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig
