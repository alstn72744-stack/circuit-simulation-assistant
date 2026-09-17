"""Manual UI-only graph layout fixture: streamlit run tests/ux_preview.py."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import streamlit as st
from ac_result_analysis import analyze_ac, gain_figure
from transient_result_analysis import analyze_transient, waveform_figure
from dc_result_analysis import analyze_dc, dc_figure
from parameter_sweep_execution import SweepPoint, comparison_figures, overlay_figure
from ui_helpers import show_graph

st.set_page_config(layout='wide')
st.title('Core UX graph rendering verification')
frequency=np.logspace(1,6,501)
ac=analyze_ac(frequency,10/(1+1j*frequency/10000),np.ones(501))
ac.target_name,ac.reference_name='V(vout)','V(vin)'
time=np.linspace(0,.01,1001)
transient=analyze_transient(time,2*np.sin(2*np.pi*1000*time),np.sin(2*np.pi*1000*time))
dc=analyze_dc(np.linspace(0,5,101),np.linspace(0,2.5,101),measurements=['Minimum','Maximum'])
dc.sweep_source='V2'
points=[SweepPoint('1k',1000,'OK',{'Gain [dB]':20.},result=ac),
        SweepPoint('2k',2000,'OK',{'Gain [dB]':20.},result=ac)]
for name,figure in [('AC',gain_figure(ac)),('Transient',waveform_figure(transient)),
                    ('DC',dc_figure(dc)),('Parameter metric',next(iter(comparison_figures(points,'R1').values()))),
                    ('AC overlay',overlay_figure(points,'R1','AC'))]:
    st.subheader(name)
    show_graph(figure)
st.text('Layout fixture ready')
