from pathlib import Path
from uuid import uuid4
from ac_analysis import build_ac_directive, apply_analysis_directive
from transient_analysis import build_transient_directive
from dc_analysis import build_dc_directive, validate_sweep_source

PROJECT_DIR = Path(__file__).resolve().parent


def run_ltspice(uploaded_file, ac_conditions=None, *, transient_conditions=None, dc_conditions=None,
                component_update=None, approved=False):
    if not approved:
        raise ValueError("Review the circuit and approve execution before running.")
    if uploaded_file is None:
        raise ValueError("Please upload an LTspice .asc file first.")
    from PyLTSpice import SimRunner, SpiceEditor, AscEditor, LTspice
    if component_update is not None:
        from parameter_sweep import validate_asc_component, component_value
        component, value = component_update
        component = validate_asc_component(uploaded_file.getvalue(), component)
        if component[0].upper() not in 'RC':
            raise ValueError("Parameter execution currently supports resistors and capacitors only.")
        value = str(component_value(str(value)))

    if sum(condition is not None for condition in (ac_conditions, transient_conditions, dc_conditions)) > 1:
        raise ValueError("Select one analysis per simulation.")
    directive = (build_dc_directive(**dc_conditions) if dc_conditions is not None
                 else build_transient_directive(**transient_conditions) if transient_conditions is not None
                 else build_ac_directive(**ac_conditions) if ac_conditions is not None else None)

    filename = Path(uploaded_file.name).name
    if Path(filename).suffix.lower() != ".asc":
        raise ValueError("The uploaded circuit must be an .asc file.")

    # 실행별 폴더로 동명 업로드 및 이전 결과와의 충돌을 방지한다.
    run_id = uuid4().hex
    input_folder = PROJECT_DIR / "simulation_input" / run_id
    output_folder = PROJECT_DIR / "simulation_output" / run_id
    input_folder.mkdir(parents=True)
    output_folder.mkdir(parents=True)

    # Streamlit에 업로드된 .asc 파일을 실제 파일로 저장
    asc_path = input_folder / Path(filename).with_suffix(".asc")
    asc_path.write_bytes(uploaded_file.getbuffer())

    # LTspice simulation 준비
    runner = SimRunner(
        output_folder=str(output_folder),
        simulator=LTspice,
        verbose=True
    )

    if directive is not None or component_update is not None:
        schematic = AscEditor(str(asc_path))
        if component_update is not None:
            edit_component_value(schematic, component, value)
        if directive is not None:
            apply_analysis_directive(schematic, directive)
        schematic.save_netlist(asc_path)

    # test_ltspice.py와 동일하게 실행용 복사본에서 netlist를 생성한다.
    circuit = SpiceEditor(str(asc_path))
    if dc_conditions is not None:
        validate_sweep_source(circuit, dc_conditions["sweep_source"])

    # 실제 LTspice 실행
    raw_file, log_file = runner.run_now(circuit)

    # run_now는 실패해도 경로를 반환할 수 있으므로 성공 여부를 확인한다.
    if runner.okSim != 1:
        task = runner.completed_tasks[-1]
        detail = task.exception_text or f"LTspice exit code: {task.retcode}"
        if log_file and Path(log_file).is_file():
            log_path = Path(log_file)
            log_bytes = log_path.read_bytes()
            encoding = "utf-16" if log_bytes.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
            detail += f"\nLOG: {log_path}\n{log_bytes.decode(encoding, errors='replace')[-4000:]}"
        error = RuntimeError(detail)
        error.raw_file, error.log_file = raw_file, log_file
        raise error

    for label, file in (("RAW", raw_file), ("LOG", log_file)):
        if not file or not Path(file).is_file() or Path(file).stat().st_size == 0:
            raise RuntimeError(f"LTspice did not generate a non-empty {label} file. Results: {output_folder}")

    return Path(raw_file).resolve(), Path(log_file).resolve(), directive


def edit_component_value(editor, component, value):
    """Use the official editor on a run copy; no text substitution."""
    names = {name.casefold(): name for name in editor.get_components('RC')}
    if component.casefold() not in names:
        raise ValueError(f"Resistor/capacitor not found: {component}")
    editor.set_component_value(names[component.casefold()], value)

