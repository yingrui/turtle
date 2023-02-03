import datetime
from datetime import date

from engine.Portfolio import Portfolio
from engine.StockTradeDataEngine import StockTradeDataEngine
from engine.TradeEngine import TradeEngine
from simulation.Simulator import Simulator

if __name__ == "__main__":
    initial_investment = 400000
    # 贵州茅台 600519.SH, 北汽蓝谷 600733.SH, 长安汽车 000625.SZ, 赛力斯 601127.SH, 广汽集团 601238.SH, 宁德时代 300750.SZ, 赣锋锂业 002460.SZ
    follow_stocks = ['600519.SH', '600733.SH', '000625.SZ', '601127.SH', '601238.SH', '300750.SZ', '002460.SZ',
                     '300568.SZ', '002895.SZ', '300565.SZ', '600418.SH']

    parameters = {
        'window_1': 20,
        'window_2': 70
    }

    data_engine = StockTradeDataEngine()
    portfolio = Portfolio('test', [], initial_investment, 0, initial_investment, data_engine)
    trade_engine = TradeEngine(data_engine, follow_stocks=follow_stocks, parameters=parameters)

    simulator = Simulator(portfolio, trade_engine, data_engine)

    simulator.run(start_date=date(2016, 1, 1), end_date=date.today() + datetime.timedelta(days=1))
