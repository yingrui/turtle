import time

from configurer import get_sql_connection, get_ts_api
from util.sql_methods import insert_or_update

if __name__ == "__main__":
    fields = 'ts_code,symbol,name,area,industry,market,exchange,curr_type,list_status,list_date,delist_date,is_hs'
    ts_api = get_ts_api()
    sql_conn = get_sql_connection()

    # exchanges include: 上交所 SSE, 深交所 SZSE, 北交所 BSE
    df = ts_api.query('stock_basic', exchange='', fields=fields)
    count = df.to_sql(con=sql_conn, name='stock', index=False, if_exists='append', method=insert_or_update)
    print('update count: {0}'.format(count))
    time.sleep(1)
