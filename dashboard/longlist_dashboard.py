import streamlit as st

st.set_page_config(page_title='Weekly Longlist Dashboard', layout='wide')

st.title('Weekly Longlist Dashboard (Deprecated)')
st.warning(
    'This dashboard is deprecated. Use `dashboard_python_output/app.py`, '
    'which reads `pwc reports/outputs/python_output_all.csv`.'
)
st.stop()
