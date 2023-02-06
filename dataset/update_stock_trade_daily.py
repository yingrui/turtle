import argparse
import time
from datetime import date

import pandas as pd

from configurer import get_ts_api, get_sql_connection
from util.sql_methods import insert_or_update


def download_stock_trade_data(ts_api, sql_conn, day):
    df = ts_api.query('daily', ts_code='', start_date=day.strftime('%Y%m%d'), end_date=day.strftime('%Y%m%d'))
    count = df.to_sql(con=sql_conn, name='stock_trade_daily', index=False, if_exists='append',
                      method=insert_or_update)
    print('{0}, {1}'.format(day.strftime('%Y-%m-%d'), count))
    time.sleep(1)


def download_stock_adj_data(ts_api, sql_conn, day):
    df = ts_api.query('adj_factor', ts_code='', trade_date=day.strftime('%Y%m%d'))
    count = df.to_sql(con=sql_conn, name='stock_adj_daily', index=False, if_exists='append',
                      method=insert_or_update)
    print('{0}, {1}'.format(day.strftime('%Y-%m-%d'), count))
    time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=str, default=date.today().strftime('%Y-%m-%d'), help='start date')
    parser.add_argument('--end', type=str, default=date.today().strftime('%Y-%m-%d'), help='end date')
    parser.add_argument('--adj-data', type=bool, default=True, help='whether download adj data, default is False')
    parser.add_argument('--trade-data', type=bool, default=True, help='whether download trade data, default is False')
    opt = parser.parse_args()

    ts_api = get_ts_api()
    sql_conn = get_sql_connection()
    # exchanges include: 上交所 SSE, 深交所 SZSE, 北交所 BSE
    for day in pd.date_range(start=opt.start, end=opt.end):
        if day.day_of_week < 5:
            if opt.trade_data:
                download_stock_trade_data(ts_api, sql_conn, day)
            if opt.adj_data:
                download_stock_adj_data(ts_api, sql_conn, day)
