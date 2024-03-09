import streamlit as st


st.set_page_config(layout="wide", page_title="Turtle Trading System") # Wide layout

# Documentation/Help Section at the bottom or in another sidebar menu item
st.markdown(
"""
# 个人海龟交易系统 Turtle Trading System

本项目期望能为个人提供一个基于《海龟交易法则》的简单交易系统，帮助大家能够针对中国股票市场进行分析。

## 数据收集 Data Collection
每天收盘后，点击Data Collection开始收集数据，更新当日的数据。

## 回测 Simulation
选择投资组合，点击运行开始进行模拟回测。可以指定不同的投资组合和开始时间并进行回测。
"""
)

# Run this script using `streamlit run your_script.py` in your command line.
