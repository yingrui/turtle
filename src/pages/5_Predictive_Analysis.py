from datetime import date

import matplotlib.pyplot as plt
import streamlit as st
from statsmodels.tsa.arima.model import ARIMA

from configurer import load_yaml
from engine.StockRepository import StockRepository
from engine.StockTradeDataEngine import StockTradeDataEngine
from util.chart_methods import draw_line_chart_with_moving_average


# Function to display predictive analysis UI
def show_predictive_analysis_page():
    st.subheader("Predictive Analysis")
    options = ["portfolio", "test"]
    portfolio_name = st.selectbox('Enter portfolio name', options=options)
    config = load_yaml("{0}.{1}".format(portfolio_name, "yaml"))
    follow_stocks = config['follow_stocks']

    data_engine = StockTradeDataEngine()
    stock_repo = StockRepository()

    stocks = [stock_repo.find_stock(stock) for stock in follow_stocks]

    with st.form(key='analysis_policy_form'):
        name = 'Running stock analysis for: {0}, select stock'.format(portfolio_name)
        stock = st.selectbox(name, options=stocks, format_func=lambda s: "{0}, {1}".format(s.ts_code, s.name))
        start_button = st.form_submit_button(label='Analysis stock')

    if start_button:
        df = data_engine.get_trade_data_by_code(stock.ts_code, start_date=date(2020, 1, 1), end_date=date.today())
        st.pyplot(
            draw_line_chart_with_moving_average(x_series=df.trade_date, y_series=df.qfq, sma_days_list=[20, 70, 100],
                                                title='Double Moving Average System'))

        arima_model = ARIMA(df.qfq, order=(1, 1, 1))
        model = arima_model.fit()

        f = plt.figure()
        f.set_figwidth(20)
        plt.plot(df.trade_date, df.qfq, label='time series')
        plt.plot(df.trade_date, model.predict(dynamic=False), label='predict')
        st.pyplot(f)
        st.text(model.forecast(steps=10))
        st.text(model.summary())


st.set_page_config(layout="wide", page_title="Predictive Analysis") # Wide layout
show_predictive_analysis_page()