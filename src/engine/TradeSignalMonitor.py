from engine.policy.PolicyFactory import PolicyFactory


class TradeSignalMonitor:

    def __init__(self, data_engine, follow_stocks=None, parameters={}):
        self._data_engine = data_engine
        self._follow_stocks = [] if follow_stocks is None else follow_stocks
        self._parameters = parameters
        self._policy_factory = PolicyFactory()

    def detect_signals(self, day):
        signals = []
        for ts_code in self._follow_stocks:
            if self._data_engine.is_open(ts_code, day):
                trade_data = self._data_engine.get_trade_data_by_date(ts_code, end_date=day, qfq=True)
                signal = self._analysis(ts_code, trade_data)
                if signal is not None:
                    signals.append(signal)
        return signals

    def _analysis(self, ts_code, trade_data):
        policy = self._policy_factory.create(ts_code, trade_data, self._parameters)
        return policy.analysis()
