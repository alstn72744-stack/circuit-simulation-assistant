"""Review defaults and display-only helpers; no simulation or numeric analysis."""
import math
import re
from io import BytesIO

from ac_analysis import parse_request, FREQUENCY, normalize_frequency
from transient_analysis import parse_transient_request
from dc_analysis import parse_dc_request, VALUE, SIGNAL

GRAPH_WIDTH_FRACTION = .83
GRAPH_FIGURE_WIDTH = 8.0
GRAPH_DPI = 160
REUSABLE_FIELDS = {
    'AC': ('target', 'reference', 'start_frequency', 'stop_frequency', 'points', 'sweep_type'),
    'Transient': ('target', 'reference', 'stop_time', 'start_saving_time', 'maximum_timestep'),
    'DC Sweep': ('target', 'dc_comparison', 'sweep_source', 'dc_start', 'dc_stop', 'dc_step'),
}


def human_value(value, unit, digits=3):
    """Engineering units for display only. Never used as analysis/JSON input."""
    if value is None or not math.isfinite(float(value)):
        return 'Not available'
    number = float(value)
    prefix, scale = '', 1.
    if unit in ('Hz', 'V', 'A', 's', 'F', 'Ohm') and number != 0:
        for candidate, name in ((1e9,'G'), (1e6,'M'), (1e3,'k'), (1.,''),
                                (1e-3,'m'), (1e-6,'µ'), (1e-9,'n'), (1e-12,'p')):
            if abs(number) >= candidate:
                scale, prefix = candidate, name
                break
        else:
            return f'{number:.{digits}e} {unit}'
    scaled = number / scale
    # Avoid displaying 1000.000 mV at a rounding boundary.
    if abs(round(scaled, digits)) >= 1000 and unit in ('Hz','V','A','s','F','Ohm') and scale < 1e9:
        return human_value(round(scaled, digits)*scale, unit, digits)
    return f'{scaled:.{digits}f} {prefix}{unit}'


def style_graph(figure):
    width, height = figure.get_size_inches()
    figure.set_size_inches(GRAPH_FIGURE_WIDTH, GRAPH_FIGURE_WIDTH * height / width)
    for axis in figure.axes:
        axis.title.set_fontsize(max(12, axis.title.get_fontsize()))
        for text in [axis.xaxis.label, axis.yaxis.label, *axis.get_xticklabels(), *axis.get_yticklabels()]:
            text.set_fontsize(max(11, text.get_fontsize()))
        if axis.get_legend():
            for text in axis.get_legend().get_texts():
                text.set_fontsize(max(10.5, text.get_fontsize()))
    figure.tight_layout()
    return figure


def show_graph(figure):
    import streamlit as st
    side = (1 - GRAPH_WIDTH_FRACTION) / 2
    # On narrow screens Streamlit wraps columns; the image fits its container.
    with st.columns([side, GRAPH_WIDTH_FRACTION, side], gap=None)[1]:
        image = BytesIO()
        style_graph(figure).savefig(image, format='png', dpi=GRAPH_DPI, bbox_inches=None)
        st.image(image.getvalue(), width='stretch')


def asc_voltage_traces(data):
    """ASC FLAG labels only, not a complete netlist/RAW inventory. Read-only."""
    try:
        text = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    except UnicodeDecodeError:
        text = data.decode('latin-1')
    return list(dict.fromkeys(f'V({name})' for name in re.findall(
        r'^\s*FLAG\s+-?\d+\s+-?\d+\s+(\S+)\s*$', text, re.M) if name != '0'))


def trace_suggestion(requested, available):
    """Only unique case matches or a single leading 'v' in voltage node names.

    No fuzzy edit distance, node-number guessing or I(M1) -> Id(M1) substitution.
    Returns a suggestion, never an executable replacement.
    """
    requested = requested.strip()
    names = list(dict.fromkeys(available))
    if not requested or requested in names:
        return None
    folded = [name for name in names if name.casefold() == requested.casefold()]
    if folded:
        return folded[0] if len(folded) == 1 else None
    match = re.fullmatch(r'V\(([^(),]+)\)', requested, re.I)
    if not match:
        return None
    node = match[1].casefold()
    candidates = []
    for name in names:
        other = re.fullmatch(r'V\(([^(),]+)\)', name, re.I)
        if other and (other[1].casefold() == 'v'+node or node == 'v'+other[1].casefold()):
            candidates.append(name)
    return candidates[0] if len(candidates) == 1 else None


def requested_dc_point(text):
    match = re.search(rf'({VALUE})\s*에서', text, re.I)
    return match[1].strip() if match else ''


def review_defaults(text, analysis, previous=None):
    """Use existing parsers; distinguish omitted fields from their UI defaults.

    Small review adapters cover explicit AC labels/points. Measurement selection
    and previous requested DC points are not reused.
    """
    parser = {'AC': parse_request, 'Transient': parse_transient_request, 'DC Sweep': parse_dc_request}.get(analysis, parse_request)
    values = parser(text)
    explicit = {key for key, value in values.items() if value not in ('', None, [])}
    if analysis == 'AC':
        explicit -= {'target','points','sweep_type'}
        names = list(dict.fromkeys(re.findall(SIGNAL, text, re.I)))
        values['reference'] = names[1] if len(names)>1 else ''
        if names:
            explicit.add('target')
        if len(names)>1:
            explicit.add('reference')
        for field, label in [('start_frequency',r'start(?:\s+frequency)?|시작\s*주파수'),
                             ('stop_frequency',r'stop(?:\s+frequency)?|종료\s*주파수')]:
            match = re.search(rf'(?:{label})\s*[:=]?\s*({FREQUENCY})', text, re.I)
            if match:
                values[field] = normalize_frequency(match[1])
                explicit.add(field)
        points = re.search(r'(?:points?|포인트)\s*[:=]?\s*(\d+)|(\d+)\s*(?:points?|포인트)',text,re.I)
        if points:
            values['points'] = int(points[1] or points[2])
            explicit.add('points')
        for pattern, sweep in [(r'\b(?:decade|dec)\b','Decade'), (r'\b(?:octave|oct)\b','Octave'),
                               (r'\b(?:linear|lin)\b','Linear')]:
            if re.search(pattern,text,re.I):
                values['sweep_type'] = sweep
                explicit.add('sweep_type')
    # Explicit Target/Reference labels also support a reference-only new request.
    for field, label in [('target',r'target(?:\s+signal)?|측정\s*신호'),
                         ('dc_comparison' if analysis == 'DC Sweep' else 'reference',
                          r'reference(?:\s*/\s*input)?(?:\s+signal)?|input\s+signal|기준\s*신호')]:
        match = re.search(rf'(?:{label})\s*[:=]\s*({SIGNAL})',text,re.I)
        if match:
            values[field] = match[1]
            explicit.add(field)
            if field != 'target' and values.get('target') == match[1] and len(re.findall(SIGNAL,text,re.I)) == 1:
                values['target'] = 'V(out)' if analysis == 'AC' else ''
                explicit.discard('target')
    reused = []
    for field in REUSABLE_FIELDS.get(analysis, ()):
        if field not in explicit and previous and field in previous:
            values[field] = previous[field]
            reused.append(field)
    return values, reused


def compact_comparison_rows(rows):
    """Separate display records; deterministic comparison_table remains intact."""
    result = []
    for row in rows:
        display = {}
        for key, value in row.items():
            if key in ('RAW','LOG','Directive','Notes','Parameter Value'):
                continue
            match = re.search(r'\s*\[([^]]+)\]$',key)
            if match:
                display[key[:match.start()]] = human_value(value,match[1])
            else:
                display[key] = value
        result.append(display)
    return result


def compact_extrema_rows(rows):
    result = []
    for row in rows:
        display = dict(row)
        match = re.search(r'\[([^]]+)\]$',row['Measurement'])
        if match:
            for key in ('Minimum','Maximum','Delta last-first'):
                display[key] = human_value(row[key],match[1])
        result.append(display)
    return result


def show_point_evidence(summary):
    import streamlit as st
    if summary.get('analysis_type') != 'Parameter Sweep':
        return
    rows = summary['measured_facts'].get('points',[])
    evidence = summary.get('evidence',{}).get('points',[])
    with st.expander('Point Details / Evidence'):
        for row, files in zip(rows,evidence):
            st.write(f"{summary['simulation_conditions']['component']} = {row['parameter_label']} — {row['status']}")
            st.text('RAW: '+str(files.get('raw_file') or 'Not generated'))
            st.text('LOG: '+str(files.get('log_file') or 'Not generated'))
            st.text('Directive: '+str(files.get('applied_directive') or 'Not applied'))
            st.text('\n'.join(row.get('notes',[])))


def show_dc_requested_point(result):
    import streamlit as st
    if result.point is not None:
        unit = 'V' if result.sweep_source.upper().startswith('V') else 'A'
        st.metric(f'Value at {result.sweep_source} = {result.point:g} {unit}',
                  human_value(result.point_value,result.target_unit))
        st.caption(f'Target: {result.target_name}. Uses the existing DC interpolation; no extrapolation.')
