"""Sequential independent runs and comparison using existing analysis pipelines."""
from dataclasses import dataclass, field
import math

import numpy as np
from matplotlib.figure import Figure

from parameter_sweep import generate_sweep_values, validate_asc_component
from simulation_runner import run_ltspice
from ac_analysis import build_ac_directive
from transient_analysis import build_transient_directive, MEASUREMENTS as TRANSIENT_MEASUREMENTS
from dc_analysis import build_dc_directive, spice_value, MEASUREMENTS as DC_MEASUREMENTS
from ac_result_analysis import read_ac_result, MissingTraceError
from transient_result_analysis import read_transient_result
from dc_result_analysis import read_dc_result

SUPPORTED = {'AC': ['Gain', '-3 dB Bandwidth'], 'Transient': TRANSIENT_MEASUREMENTS, 'DC Sweep': DC_MEASUREMENTS}


@dataclass
class SweepPoint:
    label: str
    value: float
    status: str = 'Simulation Failed'
    metrics: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    raw: str = ''
    log: str = ''
    directive: str = ''
    result: object = None
    failure: dict = field(default_factory=dict)


def validate_sweep_analysis(analysis, settings, target, reference, measurements, point=None):
    if analysis not in SUPPORTED:
        raise ValueError('Select AC, Transient or DC Sweep.')
    if set(measurements) - set(SUPPORTED[analysis]):
        raise ValueError(f'Unsupported {analysis} measurements: {sorted(set(measurements)-set(SUPPORTED[analysis]))}')
    if not target.strip():
        raise ValueError('Enter Target Signal.')
    if analysis == 'AC' or (analysis == 'Transient' and 'Voltage Gain' in measurements):
        if not reference.strip():
            raise ValueError('Enter Reference / Input Signal.')
    if analysis == 'DC Sweep':
        if any(m in measurements for m in ('Difference', 'Absolute Difference', 'Matching Error')) and not reference.strip():
            raise ValueError('Enter Comparison Signal.')
        if 'Value at Sweep Point' in measurements and (point is None or not math.isfinite(point)):
            raise ValueError('Enter Selected Sweep Point.')
    return {'AC': build_ac_directive, 'Transient': build_transient_directive, 'DC Sweep': build_dc_directive}[analysis](**settings)


def measure_point(raw, analysis, target, reference, measurements, settings, point=None):
    metrics, notes = {}, []
    if analysis == 'AC':
        result = read_ac_result(raw, target, reference)
        if 'Gain' in measurements:
            metrics['Low-Frequency Gain [dB]'] = result.low_frequency_gain_db
        if '-3 dB Bandwidth' in measurements:
            metrics['-3 dB Bandwidth [Hz]'] = result.bandwidth_hz
            if result.bandwidth_hz is None:
                notes.append(result.bandwidth_status)
        notes.extend(result.notes)
    elif analysis == 'Transient':
        result = read_transient_result(raw, target, reference, measurements)
        for group, measurement in result.measurements.items():
            if measurement.reason:
                notes.append(f'{group}: {measurement.reason}')
            for name, (value, unit) in measurement.values.items():
                metrics[f'{group}: {name} [{unit}]'] = value
        notes.extend(result.notes)
    else:
        result = read_dc_result(raw, target, reference, measurements, point, sweep_source=settings['sweep_source'])
        metrics = {f'{name} [{unit}]': value for name, (value, unit) in result.metrics.items()}
        notes.extend(result.notes)
    return result, metrics, notes


def run_parameter_sweep(uploaded_file, conditions, settings, target, reference='', point=None, *, approved=False,
                        runner=None, progress=None):
    if not approved:
        raise ValueError('Review and approve Parameter Sweep before execution.')
    values = generate_sweep_values(conditions)
    component = validate_asc_component(uploaded_file.getvalue(), conditions['component'])
    if component[0].upper() not in 'RC':
        raise ValueError('Parameter execution currently supports resistors and capacitors only.')
    analysis, measurements = conditions['analysis_type'], conditions['measurements']
    directive = validate_sweep_analysis(analysis, settings, target, reference, measurements, point)
    runner = runner or run_ltspice
    keyword = {'AC': 'ac_conditions', 'Transient': 'transient_conditions', 'DC Sweep': 'dc_conditions'}[analysis]
    points = []
    for index, value in enumerate(values):
        entry = SweepPoint(spice_value(value), float(value), directive=directive)
        points.append(entry)
        try:
            raw, log, entry.directive = runner(uploaded_file, **{keyword: settings},
                                               component_update=(component, str(value)), approved=True)
            entry.raw, entry.log = str(raw), str(log)
        except Exception as error:
            entry.failure = {'message': str(error)}
            entry.notes.append(f'{type(error).__name__}: {error}')
            entry.raw = str(getattr(error, 'raw_file', '') or '')
            entry.log = str(getattr(error, 'log_file', '') or '')
        else:
            try:
                entry.result, entry.metrics, entry.notes = measure_point(raw, analysis, target, reference, measurements, settings, point)
                entry.status = 'OK'
                if any(value is None for value in entry.metrics.values()) or (measurements and not entry.metrics):
                    entry.status = 'Partial Measurements'
                if analysis == 'Transient' and any(item.reason for item in entry.result.measurements.values()):
                    entry.status = 'Partial Measurements'
            except Exception as error:
                entry.status = 'Analysis Failed'
                entry.failure = {'message': str(error)}
                entry.notes.append(f'{type(error).__name__}: {error}')
                if isinstance(error, MissingTraceError):
                    entry.failure.update(missing_traces=error.missing, available_traces=error.available)
                    entry.notes.append('Available traces: ' + ', '.join(error.available))
        if progress:
            progress(index + 1, len(values))
    return points


def comparison_table(points, component):
    columns = list(dict.fromkeys(key for entry in points for key in entry.metrics))
    return [{component: entry.label, 'Parameter Value': entry.value,
             **{key: entry.metrics.get(key) for key in columns}, 'Status': entry.status,
             'RAW': entry.raw, 'LOG': entry.log, 'Directive': entry.directive, 'Notes': '\n'.join(entry.notes)}
            for entry in points]


def comparison_summary(points):
    """Extrema and last-minus-first in requested order, using valid values only."""
    columns = list(dict.fromkeys(key for entry in points for key in entry.metrics))
    summaries = []
    for key in columns:
        valid = [(entry, entry.metrics.get(key)) for entry in points
                 if entry.metrics.get(key) is not None and math.isfinite(entry.metrics[key])]
        if not valid:
            continue
        low, high = min(valid, key=lambda pair: pair[1]), max(valid, key=lambda pair: pair[1])
        summaries.append({'Measurement': key, 'Minimum': low[1], 'Minimum at': low[0].label,
                          'Maximum': high[1], 'Maximum at': high[0].label,
                          'Delta last-first': valid[-1][1]-valid[0][1] if len(valid)>1 else None,
                          'First valid': valid[0][0].label, 'Last valid': valid[-1][0].label,
                          'Valid points': len(valid)})
    return summaries


def comparison_figures(points, component):
    figures = {}
    ordered = sorted(points, key=lambda entry: entry.value)
    for row in comparison_summary(points):
        name = row['Measurement']
        figure = Figure(figsize=(7, 3.5))
        axis = figure.subplots()
        axis.plot([entry.value for entry in ordered],
                  [entry.metrics.get(name) if entry.metrics.get(name) is not None else np.nan for entry in ordered], 'o-')
        axis.set(title=f'{component} vs {name}', xlabel=f"{component} [{'Ohm' if component[0].upper() == 'R' else 'F'}]", ylabel=name)
        axis.grid(True, alpha=.3)
        figure.tight_layout()
        figures[name] = figure
    return figures


def overlay_figure(points, component, analysis, limit=8):
    successful = [entry for entry in points if entry.result is not None][:limit]
    if not successful:
        return None
    figure = Figure(figsize=(8, 4))
    axis = figure.subplots()
    for entry in successful:
        result, label = entry.result, f'{component}={entry.label}'
        if analysis == 'AC':
            axis.semilogx(result.frequency, result.gain_db, label=label)
            axis.set(xlabel='Frequency [Hz]', ylabel='Gain [dB]')
        elif analysis == 'Transient':
            axis.plot(result.time, result.target, label=label)
            axis.set(xlabel='Time [s]', ylabel=f'{result.target_name} [V]')
        else:
            axis.plot(result.sweep, result.target, label=label)
            axis.set(xlabel=f'{result.sweep_source} sweep', ylabel=f'{result.target_name} [{result.target_unit}]')
    axis.set_title(f'{analysis} overlay (first {len(successful)} available curves)')
    axis.legend()
    axis.grid(True, alpha=.3)
    figure.tight_layout()
    return figure
