import streamlit as st
import subprocess
import pandas as pd
from datetime import date

from configurer import load_yaml
from engine.StockTradeDataEngine import StockTradeDataEngine
from engine.StockRepository import StockRepository
from util.chart_methods import draw_line_chart_with_moving_average
from util.chart_methods import draw_time_series_with_mean_and_std
from util.chart_methods import draw_line_chart_with_atr
from util.chart_methods import draw_line_chart_with_bolling
from util.chart_methods import draw_line_chart_with_max_min_window


# Function to display stock analysis UI
def show_stock_analysis_page():
    st.subheader("Stock Analysis")
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
        st.pyplot(draw_line_chart_with_max_min_window(trade_date=df.trade_date, close_price=df.qfq, ma_days=70, up=20,
                                                      down=10, title='Donchian System'))
        daily_range = df[['high', 'pre_close']].max(axis=1) - df[['low', 'pre_close']].min(axis=1)
        st.pyplot(
            draw_line_chart_with_atr(trade_date=df.trade_date, close_price=df.qfq, daily_range=daily_range, ma_days=30,
                                     up=3, down=1, title='ATR System'))
        st.pyplot(draw_line_chart_with_bolling(df.trade_date, df.qfq, ma_days=30, up=2, down=1.5,
                                               title='Bolling System'))
        st.pyplot(draw_time_series_with_mean_and_std(df.trade_date, df.pct_chg,
                                           title='Percentage change is a stable random variable', xlabel='date',
                                           ylabel='percentage changes'))


show_stock_analysis_page()