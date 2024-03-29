import streamlit as st
import pandas as pd

from datetime import date

from configurer import load_yaml
from engine.StockRepository import StockRepository
from util.chart_methods import draw_investment_log
from util.math_methods import round_down


def show_simulation_result_analysis_page():
    st.subheader("Simulation Result Analysis")
    options = ["portfolio", "test"]
    portfolio_name = st.selectbox('Enter portfolio name', options=options)
    config = load_yaml("{0}.{1}".format(portfolio_name, "yaml"))
    follow_stocks = config['follow_stocks']
    total_policies = len(config['policies'])

    with st.form(key='analysis_policy_form'):
        name = 'Running analysis for: {0}, select policy name'.format(portfolio_name)
        selected_policy_id = st.selectbox(name, options=["all", "0", "1", "2", "3", "4", "5"])
        start_button = st.form_submit_button(label='Analysis Policy')

    if start_button:
        if selected_policy_id == "all":
            analysis_all_policies(portfolio_name, total_policies, follow_stocks)
        else:
            df_list, df_trade_list, df_benefit = load_simulation_logs(portfolio_name, total_policies, follow_stocks)
            policy_id = int(selected_policy_id)
            st.text(calculate_cagr(policy_id, df_list[policy_id]))
            f = draw_investment_log(df_list[policy_id], xlabel='Trade Date', ylabel='Asset (unit: 10K)',
                                    title='Assets Changes Table of Policy ' + str(policy_id))
            st.pyplot(f)
            st.dataframe(df_benefit.sort_values(by=['sum_{0}'.format(policy_id)], ascending=False))
            st.dataframe(df_trade_list[policy_id].tail(60))


def analysis_all_policies(portfolio_name, total_policies, follow_stocks):
    df_list, df_trade_list, df_benefit = load_simulation_logs(portfolio_name, total_policies, follow_stocks)
    cagr_info = []
    for policy_id in range(0, total_policies):
        cagr_info.append(calculate_cagr(policy_id, df_list[policy_id]))
    st.text('\n'.join(cagr_info))

    for policy_id in range(0, total_policies):
        f = draw_investment_log(df_list[policy_id], xlabel='Trade Date', ylabel='Asset (unit: 10K)',
                                title='Assets Changes Table of Policy ' + str(policy_id))
        st.pyplot(f)

    df_win_loss = get_win_loss_dataframe(df_trade_list, total_policies)
    st.dataframe(df_win_loss.T)
    st.dataframe(df_benefit.sort_values(by=['sum_0'], ascending=False))


def get_win_loss_dataframe(df_trade_list, total_policies):
    df_win_loss = get_win_loss(0, df_trade_list)
    for policy_id in range(1, total_policies):
        df_win_loss = df_win_loss.join(get_win_loss(policy_id, df_trade_list))
    return df_win_loss


def get_win_loss(policy_id, df_trade_list):
    df_trade = df_trade_list[policy_id]
    return df_trade[['ts_code', 'status']].groupby(['status']).count().rename(
        columns={"ts_code": "policy_{0}".format(policy_id)})


def calculate_cagr(policy_id, df):
    start_date = date.fromtimestamp(df.date.values[0].astype(int) / 1e9)
    end_date = date.fromtimestamp(df.date.values[-1].astype(int) / 1e9)
    years = end_date.year - start_date.year if end_date.year > start_date.year else 1
    initial_total = df.total.values[0]
    total = df.total.values[-1]
    cagr = round_down((total / initial_total) ** (1 / years) - 1)
    return_rate = round_down(total / initial_total * 100)
    cagr_template = 'Policy-{0}: initial investment is {1}, after {2} years, now is {3}, return rate is {4}%, CAGR: {5}'
    cagr_information = cagr_template.format(policy_id, initial_total, years, total, return_rate, cagr)
    return cagr_information


def get_stock_benefit(policy_id, df_trade_list):
    df_trade = df_trade_list[policy_id]
    df_benefit = df_trade[['ts_code', 'benefit']].groupby(['ts_code']).sum(['benefit']).rename(
        columns={"benefit": "sum_{0}".format(policy_id)})
    df_win = df_trade[df_trade['status'] == 'win']
    df_win_sum = df_win[['ts_code', 'benefit']].groupby(['ts_code']).sum(['benefit']).rename(
        columns={"benefit": "win_{0}".format(policy_id)})
    df_win_count = df_win[['ts_code', 'benefit']].groupby(['ts_code']).count().rename(
        columns={"benefit": "w_cnt_{0}".format(policy_id)})
    df_loss = df_trade[df_trade['status'] == 'loss']
    df_loss_sum = df_loss[['ts_code', 'benefit']].groupby(['ts_code']).sum(['benefit']).rename(
        columns={"benefit": "loss_{0}".format(policy_id)})
    df_loss_count = df_loss[['ts_code', 'benefit']].groupby(['ts_code']).count().rename(
        columns={"benefit": "l_cnt_{0}".format(policy_id)})
    df_benefit = df_benefit.join(df_win_sum).join(df_loss_sum).join(df_win_count).join(df_loss_count)
    return df_benefit


def load_simulation_logs(portfolio_name, total_policies, follow_stocks):
    stock_repo = StockRepository()
    stocks = [stock_repo.find_stock(stock) for stock in follow_stocks]
    df_stocks = pd.DataFrame([{'ts_code': stock.ts_code, 'name': stock.name} for stock in stocks])

    df_list = []
    for id in range(0, total_policies):
        df = pd.read_csv('./logs/{0}-{1}.log'.format(portfolio_name, id), parse_dates=['date'],
                         date_parser=pd.to_datetime)
        df_list.append(df)

    df_trade_list = []
    for policy_id in range(0, total_policies):
        df_trade = pd.read_csv('./logs/trade_{0}-{1}.log'.format(portfolio_name, policy_id),
                               parse_dates=['date', 'hold_date'], date_parser=pd.to_datetime)
        df_trade = pd.merge(df_trade, df_stocks, on='ts_code', how='left')
        df_trade_list.append(df_trade)

    df_benefit = get_stock_benefit(0, df_trade_list)
    df_benefit = pd.merge(df_stocks, df_benefit, on='ts_code', how='left')
    for policy_id in range(1, total_policies):
        df_benefit = pd.merge(df_benefit, get_stock_benefit(policy_id, df_trade_list), on='ts_code', how='outer')

    return df_list, df_trade_list, df_benefit


st.set_page_config(layout="wide", page_title="Simulation Result Analysis")  # Wide layout
show_simulation_result_analysis_page()
