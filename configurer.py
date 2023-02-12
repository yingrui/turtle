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
        '000625.SZ',  # 长安汽车
        '600733.SH',  # 北汽蓝谷
        '601127.SH',  # 赛力斯
        '601238.SH',  # 广汽集团
        '600418.SH',  # 江淮汽车
        '300750.SZ',  # 宁德时代
        '002460.SZ',  # 赣锋锂业
        # 白酒
        '600519.SH',  # 贵州茅台
        '600809.SZ',  # 山西汾酒
        # 地产
        # '000002.SZ',  # 万科
        # 银行
        # '600036.SH',  # 招商银行
        # 其它
        # '300568.SZ',  # 星源材质
        '002895.SZ',  # 川恒股份
        # '300565.SZ',  # 科信技术
        '000758.SZ',  # 中色股份
        '601226.SH',  # 华电重工
        '600787.SH',  # 中储股份
        '600313.SH',  # 农发种业
        # '000798.SZ',  # 中水渔业
        '603392.SZ',  # 万泰生物
        '601012.SZ',  # 隆基绿能
        '300628.SZ',  # 亿联网络
        # '002714.SZ',  # 牧原股份
        '600276.SH', # 恒瑞医药
    ]
