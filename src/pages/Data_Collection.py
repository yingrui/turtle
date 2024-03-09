import streamlit as st
import subprocess

from dataset.Dataset import Dataset


def get_latest_date():
    dataset = Dataset()
    return dataset.get_latest_date()


# Define functions to execute shell commands for data collection and backtesting
def run_data_collection(from_date):
    from_date_str = from_date.strftime('%Y-%m-%d')
    arguments = ['python3', 'src/dataset/update_stock_trade_daily.py', '--start', from_date_str]
    result = subprocess.run(arguments, capture_output=True, text=True)
    return result


# Function to display data collection UI
def show_data_collection_page():
    st.subheader("Data Collection")
    latest_date = get_latest_date()
    st.markdown('Latest Data: {0}'.format(latest_date))
    from_date = st.date_input('Collect data from: ', value=latest_date)
    if st.button('Collect Data'):
        with st.spinner('Collecting data...'):
            data_collection_result = run_data_collection(from_date)
        if data_collection_result.returncode == 0:
            st.success('Data collection successful!')
            st.text(data_collection_result.stdout)
        else:
            st.error('Data collection failed. Check logs for errors.')
            st.error(data_collection_result.stderr)


st.set_page_config(layout="wide", page_title="Data Collection") # Wide layout
st.title("Turtle Trading System")
show_data_collection_page()
