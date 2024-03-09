import streamlit as st

from page.data_collection_page import show_data_collection_page
from page.simulation_page import show_simulation_page
from page.simulation_result_analysis_page import show_simulation_result_analysis_page
from page.stock_analysis_page import show_stock_analysis_page
from page.predictive_analysis_page import show_predictive_analysis_page


st.set_page_config(layout="wide") # Wide layout
st.title("Turtle Trading System") # Main title of the page

# Sidebar navigation with hyperlink-style links
st.sidebar.title("Navigation")
if st.sidebar.button("Dataset"):
    st.session_state['page'] = 'dataset'

if st.sidebar.button("Simulation"):
    st.session_state['page'] = 'simulation'

if st.sidebar.button("Simulation Result Analysis"):
    st.session_state['page'] = 'simulation_result_analysis'

if st.sidebar.button("Stock Analysis"):
    st.session_state['page'] = 'stock_analysis'

if st.sidebar.button("Predictive Analysis"):
    st.session_state['page'] = 'predictive_analysis'

# Initialize page selection
if 'page' not in st.session_state:
    st.session_state['page'] = 'dataset'

# Conditional rendering of pages based on navigation selection
if st.session_state['page'] == 'dataset':
    show_data_collection_page()
elif st.session_state['page'] == 'simulation':
    show_simulation_page()
elif st.session_state['page'] == 'simulation_result_analysis':
    show_simulation_result_analysis_page()
elif st.session_state['page'] == 'stock_analysis':
    show_stock_analysis_page()
elif st.session_state['page'] == 'predictive_analysis':
    show_predictive_analysis_page()

# Documentation/Help Section at the bottom or in another sidebar menu item
st.sidebar.title("Help")
if st.sidebar.button("Documentation"):
    st.subheader("Documentation")
    st.write("Learn more about how to use the page and how to configure your trading strategies.")

# Run this script using `streamlit run your_script.py` in your command line.
