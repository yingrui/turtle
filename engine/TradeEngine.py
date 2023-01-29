from random import randint


class Signal:
    __slots__ = ('ts_code', 'status')

    def __init__(self, ts_code, status):
        self.ts_code = ts_code
        self.status = status

    def __str__(self):
        if self.status == 2:
            return 'buy {0}'.format(self.ts_code)
        elif self.status == 1:
            return 'do nothing {0}'.format(self.ts_code)
        else:
            return 'sell {0}'.format(self.ts_code)


class TradeEngine:

    def __init__(self, follow_stocks=None):
        self._follow_stocks = [] if follow_stocks is None else follow_stocks

    def get_signals(self):
        signals = []
        for ts_code in self._follow_stocks:
            signals.append(Signal(ts_code, randint(0, 2)))
        return signals
