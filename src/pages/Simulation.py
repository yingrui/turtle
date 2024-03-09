import streamlit as st
import subprocess

from configurer import load_yaml


def run_simulation(config_file, start_date):
    start_date_str = start_date.strftime('%Y-%m-%d')
    arguments = ['python3', 'src/main.py', '--configure', config_file, '--start-date', start_date_str]
    result = subprocess.run(arguments, capture_output=True, text=True)
    return result


# Function to display simulation configuration UI
def show_simulation_page():
    st.subheader("Simulation Configuration")
    options = ["portfolio.yaml", "test.yaml"]
    config_file = st.selectbox('Enter configuration file name', options=options)
    with st.form(key='simulation_form'):
        config = load_yaml(config_file)
        start_date = st.date_input('Choose start date', value=(config.get('start_date', None)))
        submit_button = st.form_submit_button(label='Run Simulation')

    if submit_button:
        with st.spinner('Running simulation...'):
            simulation_result = run_simulation(config_file, start_date)
        if simulation_result.returncode == 0:
            st.success('Simulation completed successfully!')
            st.write("Results:")
            st.text(simulation_result.stdout)  # Placeholder for actual results
        else:
            st.error('Simulation failed. Check logs for errors.')
            st.text(simulation_result.stderr)


show_simulation_page()