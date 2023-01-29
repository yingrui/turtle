import time
import pandas as pd
from configurer import get_ts_api, get_sql_connection
from util.sql_methods import insert_or_update

if __name__ == "__main__":
    ts_api = get_ts_api()
    sql_conn = get_sql_connection()
    # exchanges include: 上交所 SSE, 深交所 SZSE, 北交所 BSE
    for day in pd.date_range(start='2015-01-01', end='2020-12-31'):
        df = ts_api.query('daily', ts_code='', start_date=day.strftime('%Y%m%d'), end_date=day.strftime('%Y%m%d'))
        count = df.to_sql(con=sql_conn, name='stock_trade_daily', index=False, if_exists='append', method=insert_or_update)
        print('{0}, {1}'.format(day.strftime('%Y-%m-%d'), count))
        time.sleep(1)
