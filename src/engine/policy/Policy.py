from engine.policy.Signal import Signal


class Policy:

    def __init__(self, ts_code, trade_data):
        self._ts_code = ts_code
        self._trade_data = trade_data

    def analysis(self) -> Signal:
        pass


