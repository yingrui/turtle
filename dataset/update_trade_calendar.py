import time

from configurer import get_ts_api, get_sql_connection

if __name__ == "__main__":
    ts_api = get_ts_api()
    sql_conn = get_sql_connection()
    # exchanges include: 上交所 SSE, 深交所 SZSE, 北交所 BSE
    for exchange in ['SSE', 'SZSE']:
        for year in range(1990, 2024):
            df = ts_api.query('trade_cal', exchange=exchange,
                              start_date='{0}0101'.format(year), end_date='{0}1231'.format(year),
                              fields='exchange,cal_date,is_open,pretrade_date')
            df.to_sql(con=sql_conn, name='trade_calendar', index=False, if_exists='append')
            time.sleep(1)
