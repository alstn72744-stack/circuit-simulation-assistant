"""JSON summaries of existing deterministic results; no simulator or LLM calls.

Trend v1: sort by parameter; never bridge missing/failed samples. A large trend
reversal requires two preceding same-direction changes and an opposite change
larger than 3 * their median absolute change. This is a descriptive heuristic,
not a physical diagnosis or a statistically established outlier test.
"""
from dataclasses import replace
from decimal import Decimal
import math
from pathlib import Path
from statistics import median

import numpy as np

from ac_result_analysis import MissingTraceError
from parameter_sweep_execution import comparison_summary


def warning(code, message, **context):
    return dict(code=code, message=message, **context)


def json_native(value, warnings=None, path='$'):
    """Strict JSON conversion: NaN/Inf become null with their location recorded."""
    warnings = warnings if warnings is not None else []
    if isinstance(value, np.ndarray):
        return json_native(value.tolist(), warnings, path)
    if isinstance(value, np.generic):
        return json_native(value.item(), warnings, path)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Decimal):
        value = float(value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        warnings.append(warning('non_finite_result', 'Non-finite value replaced with null.', path=path))
        return None
    if isinstance(value, dict):
        return {str(k): json_native(v, warnings, f'{path}.{k}') for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_native(v, warnings, f'{path}[{i}]') for i, v in enumerate(value)]
    raise TypeError(f'Unsupported summary value at {path}: {type(value).__name__}')


def _finish(summary):
    extra = []
    summary = json_native(summary, extra)
    summary['warnings'].extend(extra)
    return summary


def _base(analysis_type, conditions, evidence):
    return dict(schema_version='1.0', analysis_type=analysis_type,
                simulation_conditions=dict(conditions or {}), measured_facts={}, derived_facts={},
                warnings=[], comparison_results={}, evidence=dict(evidence or {}))


def error_warning(error, status='Analysis Failed'):
    if isinstance(error, MissingTraceError):
        return warning('trace_missing', str(error), missing_traces=error.missing, available_traces=error.available)
    return warning('simulation_failed' if status == 'Simulation Failed' else 'analysis_failed',
                   f'{type(error).__name__}: {error}')


def _measurement(value, unit, warnings, name, reason=''):
    clean = json_native(value, warnings, f'measured_facts.{name}')
    status = 'available' if clean is not None else 'unavailable'
    if value is None:
        warnings.append(warning('measurement_missing', reason or 'No verified value available.', measurement=name))
    return dict(value=clean, unit=unit, status=status)


def build_analysis_summary(analysis_type, result=None, *, conditions=None, evidence=None,
                           error=None, status=None):
    """Adapt ACResult/TransientResult/DCResult without recalculating measurements."""
    summary = _base(analysis_type, conditions, evidence)
    notes = summary['warnings']
    summary['status'] = status or ('Analysis Failed' if error is not None else 'OK')
    if error is not None:
        notes.append(error_warning(error, summary['status']))
        return _finish(summary)
    if result is None:
        summary['status'] = 'Analysis Failed'
        notes.append(warning('measurement_missing', 'No analysis result is available.'))
        return _finish(summary)
    facts = summary['measured_facts']
    context = summary['simulation_conditions']
    context['target_signal'] = result.target_name
    if analysis_type == 'AC':
        context.update(reference_signal=result.reference_name, saved_frequency_range_hz=[result.frequency[0], result.frequency[-1]],
                       low_frequency_method=dict(method='initial_sample_median_db', valid_samples=result.baseline_count,
                                                 window_stop_hz=result.baseline_stop_hz),
                       bandwidth_method='First downward G0-3 dB crossing; dB vs log10(f) interpolation; low-pass assumption')
        for name, value, unit in [('Low-Frequency Gain', result.low_frequency_gain_db, 'dB'),
                                  ('-3 dB Level', result.threshold_db, 'dB'), ('-3 dB Bandwidth', result.bandwidth_hz, 'Hz')]:
            facts[name] = _measurement(value, unit, notes, name, result.bandwidth_status)
        if result.bandwidth_hz is None:
            code = 'bandwidth_not_found' if result.bandwidth_status == 'Not found within sweep range' else 'bandwidth_undetermined'
            notes.append(warning(code, result.bandwidth_status, measurement='-3 dB Bandwidth'))
    elif analysis_type == 'Transient':
        context.update(reference_signal=result.reference_name if result.reference is not None else None,
                       saved_time_range_s=[result.time[0], result.time[-1]], waveform_assessment=result.kind)
        for group, measurement in result.measurements.items():
            facts[group] = {name: _measurement(value, unit, notes, f'{group}.{name}')
                            for name, (value, unit) in measurement.values.items()}
            if measurement.reason or not measurement.values:
                notes.append(warning('measurement_not_applicable', measurement.reason or 'No reliable measurement.', measurement=group))
    elif analysis_type == 'DC Sweep':
        context.update(comparison_signal=result.comparison_name if result.comparison is not None else None,
                       sweep_source=result.sweep_source, saved_sweep_range=[result.sweep[0], result.sweep[-1]], selected_point=result.point)
        facts.update({name: _measurement(value, unit, notes, name) for name, (value, unit) in result.metrics.items()})
        for name in context.get('measurements', []):
            if not any(key == name or key.startswith(name + ' ') for key in facts):
                notes.append(warning('measurement_missing', 'Requested measurement has no valid value.', measurement=name))
    else:
        raise ValueError(f'Unsupported analysis summary: {analysis_type}')
    context['calculation_notes'] = list(result.notes)
    # Preserve upstream cautions verbatim; do not infer a cause from free text.
    for note in result.notes:
        if analysis_type == 'AC' or any(word in note.lower() for word in ('invalid', 'nan', 'non-finite', 'no value')):
            notes.append(warning('analysis_caution', note))
    if not facts:
        notes.append(warning('measurement_missing', 'No measured facts were produced.'))
    if any(w['code'] != 'analysis_caution' for w in notes):
        summary['status'] = 'Partial Measurements'
    return _finish(summary)


def _direction(a, b):
    tolerance = max(1e-15, max(abs(a), abs(b)) * 1e-9)
    return 0 if abs(b-a) <= tolerance else 1 if b > a else -1


def _segment(points, values, start, end, direction, metric):
    first, last = values[start], values[end]
    # Percent changes of dB values are intentionally not reported.
    relative = 100 * ((last-first) / abs(first)) if first != 0 and not metric.endswith('[dB]') else None
    return dict(direction={1: 'increasing', -1: 'decreasing', 0: 'constant'}[direction],
                start_parameter=points[start].value, stop_parameter=points[end].value,
                start_value=first, stop_value=last, delta=last-first, relative_change_percent=relative,
                point_count=end-start+1)


def _trend(points, metric, warnings):
    values = [p.metrics.get(metric) for p in points]
    signs = [None if a is None or b is None else _direction(a, b) for a, b in zip(values, values[1:])]
    segments = []
    index = 0
    while index < len(signs):
        sign = signs[index]
        if sign is None:
            index += 1
            continue
        end = index + 1
        while end < len(signs) and signs[end] == sign:
            end += 1
        segments.append(_segment(points, values, index, end, sign, metric))
        index = end
    valid = sum(v is not None for v in values)
    if valid < 2:
        overall = 'insufficient_data'
    elif None in values:
        overall = 'incomplete'
    elif all(sign == 0 for sign in signs):
        overall = 'constant'
    elif all(sign >= 0 for sign in signs):
        overall = 'nondecreasing' if 0 in signs else 'increasing'
    elif all(sign <= 0 for sign in signs):
        overall = 'nonincreasing' if 0 in signs else 'decreasing'
    else:
        overall = 'non_monotonic'
    for i in range(3, len(points)):
        previous = signs[i-3:i-1]
        if previous[0] not in (1, -1) or previous[0] != previous[1] or signs[i-1] != -previous[0]:
            continue
        baseline = median([abs(values[i-2]-values[i-3]), abs(values[i-1]-values[i-2])])
        change = values[i]-values[i-1]
        if abs(change) > 3 * baseline:
            warnings.append(warning('large_trend_reversal', 'Observed reversal exceeds 3 times the preceding two median absolute changes; cause not inferred.',
                                    measurement=metric, point_index=points[i]._summary_index,
                                    parameter_value=points[i].value, preceding_parameters=[p.value for p in points[i-3:i]],
                                    previous_direction='increasing' if previous[0] == 1 else 'decreasing',
                                    observed_change=change, baseline_absolute_change=baseline, factor=3))
    return dict(monotonic=overall, valid_points=valid, total_points=len(points), segments=segments)


def build_sweep_summary(points, component, analysis_type, *, conditions=None, graph_paths=()):
    summary = _base('Parameter Sweep', dict(conditions or {}, component=component, analysis_type=analysis_type),
                    dict(graph_paths=list(graph_paths), points=[]))
    summary['simulation_conditions']['parameter_unit'] = {'R': 'Ohm', 'C': 'F'}.get(component[:1].upper())
    warnings = summary['warnings']
    rows, clean_points = [], []
    columns = list(dict.fromkeys(key for p in points for key in p.metrics))
    for index, point in enumerate(points):
        context = dict(point_index=index, parameter_value=point.value)
        analysis_context = {}
        failed = point.status not in ('OK', 'Partial Measurements')
        metrics = {} if failed else json_native(point.metrics, warnings, f'points[{index}].measurements')
        # Missing/non-finite measurements never contribute to trends/extrema.
        if failed:
            warnings.append(warning('simulation_failed' if point.status == 'Simulation Failed' else 'analysis_failed',
                                    '\n'.join(point.notes) or point.status, **context))
        if getattr(point, 'failure', None):
            info = point.failure
            if info.get('missing_traces'):
                warnings.append(warning('trace_missing', info['message'], missing_traces=info['missing_traces'],
                                        available_traces=info.get('available_traces', []), **context))
        if point.result is not None and not failed:
            child = build_analysis_summary(analysis_type, point.result,
                                           conditions={'measurements': (conditions or {}).get('measurements', [])})
            analysis_context = child['simulation_conditions']
            warnings.extend(dict(w, **context) for w in child['warnings'])
        for name in columns:
            if not failed and metrics.get(name) is None:
                warnings.append(warning('measurement_missing', 'No verified value available for this point.', measurement=name, **context))
        rows.append(dict(point_index=index, parameter_value=point.value, parameter_label=point.label,
                         status=point.status, measurements=metrics, notes=list(point.notes), analysis_context=analysis_context))
        summary['evidence']['points'].append(dict(**context, raw_file=point.raw or None, log_file=point.log or None,
                                                  applied_directive=point.directive or None))
        clean = replace(point, metrics=metrics)
        clean._summary_index = index
        clean_points.append(clean)
    summary['measured_facts']['points'] = rows
    summary['comparison_results']['extrema_and_changes'] = comparison_summary(clean_points)
    summary['comparison_results']['order'] = 'requested order; valid measurements only; ties use first point'
    parameters = [p.value for p in clean_points]
    summary['derived_facts']['trend_method'] = dict(version=1, order='ascending parameter value',
        relative_tolerance=1e-9, absolute_tolerance=1e-15, missing_policy='no bridging',
        anomaly_rule='opposite change > 3 * median of preceding two same-direction absolute changes',
        percent_change='100 * (last-first) / abs(first); omitted for zero baseline or dB')
    if any(not math.isfinite(v) for v in parameters) or len(set(parameters)) != len(parameters):
        warnings.append(warning('trend_not_evaluated', 'Parameter values must be finite and unique.'))
        summary['derived_facts']['trends'] = {}
    else:
        ordered = sorted(clean_points, key=lambda p: p.value)
        summary['derived_facts']['trends'] = {name: _trend(ordered, name, warnings) for name in columns}
    summary['status'] = 'Completed' if all(p.status == 'OK' for p in points) else 'Completed with warnings'
    if not points:
        summary['status'] = 'No Results'
        warnings.append(warning('measurement_missing', 'No sweep points are available.'))
    return _finish(summary)


def summary_lines(summary):
    """Plain deterministic display; no generated interpretation or file writes."""
    lines = [f"{summary['analysis_type']} — {summary.get('status', '')}"]
    def values(facts, prefix=''):
        for name, item in facts.items():
            if isinstance(item, dict) and 'value' in item and 'unit' in item:
                value = 'unavailable' if item['value'] is None else f"{item['value']:.6g}"
                lines.append(f"{prefix}{name}: {value} {item['unit']}")
            elif isinstance(item, dict):
                values(item, prefix + name + ' / ')
    values(summary['measured_facts'])
    for row in summary['measured_facts'].get('points', []):
        lines.append(f"{summary['simulation_conditions']['component']}={row['parameter_label']}: {row['status']}; "
                     + ', '.join(f'{k}: {v:.6g}' if v is not None else f'{k}: unavailable' for k, v in row['measurements'].items()))
    for name, trend in summary['derived_facts'].get('trends', {}).items():
        lines.append(f"{name}: {trend['monotonic']} ({trend['valid_points']}/{trend['total_points']} valid points)")
        for segment in trend['segments']:
            lines.append(f"  {segment['start_parameter']:.6g} → {segment['stop_parameter']:.6g}: {segment['direction']}; delta={segment['delta']:.6g}")
    for item in summary['warnings']:
        location = f" at parameter={item['parameter_value']}" if 'parameter_value' in item else ''
        lines.append(f"Warning [{item['code']}]{location}: {item['message']}")
    return lines
