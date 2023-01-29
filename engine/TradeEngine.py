from engine.Policy import SimpleMovingAveragePolicy


class TradeEngine:

    def __init__(self, data_engine, follow_stocks=None):
        self._data_engine = data_engine
        self._follow_stocks = [] if follow_stocks is None else follow_stocks

    def get_signals(self, day):
        signals = []
        for ts_code in self._follow_stocks:
            time_series = self._data_engine.get_trade_data_by_date(ts_code, day, 200)
            signals.append(self.analysis(ts_code, time_series))
        return signals

    @staticmethod
    def analysis(ts_code, trade_data):
        policy = SimpleMovingAveragePolicy(ts_code, trade_data)
        return policy.analysis()
