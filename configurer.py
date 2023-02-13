import os

import tushare as ts
from dotenv import load_dotenv
from sqlalchemy import create_engine


def get_sql_connection():
    load_dotenv()
    engine = create_engine(os.getenv('DB_URL'), encoding="utf8")
    return engine.connect()


def get_ts_api():
    load_dotenv()
    return ts.pro_api(token=os.getenv('TUSHARE_TOKEN'))


def follow_stocks():
    return [
        # 汽车
        '002594.SZ',  # 比亚迪
        '000625.SZ',  # 长安汽车
        '600733.SH',  # 北汽蓝谷
        '601127.SH',  # 赛力斯
        '601238.SH',  # 广汽集团
        '600418.SH',  # 江淮汽车
        # 新能源
        '300750.SZ',  # 宁德时代
        '002460.SZ',  # 赣锋锂业
        # 白酒
        '600519.SH',  # 贵州茅台
        '600809.SH',  # 山西汾酒
        '000858.SZ',  # 五粮液
        # 医美
        '300896.SZ',  # 爱美客
        # 其它

    ]
