from engine.policy.AtrPolicy import AtrPolicy
from engine.policy.BollingPolicy import BollingPolicy
from engine.policy.DonchianPolicy import DonchianPolicy
from engine.policy.Policy import Policy
from engine.policy.Signal import Signal
from engine.policy.SimpleMovingAveragePolicy import SimpleMovingAveragePolicy


class EnsemblePolicy(Policy):

    def __init__(self, ts_code, trade_data, parameters={}):
        Policy.__init__(self, ts_code, trade_data)
        self._policies = [
            SimpleMovingAveragePolicy(ts_code, trade_data, parameters),
            DonchianPolicy(ts_code, trade_data, parameters)
        ]

    def _all_status_are_same(self, signals):
        # if all status of signals are same, return True
        status = signals[0].status
        for signal in signals:
            if signal.status != status:
                return False
        return True

    def _vote_buy(self, signals):
        # if buy signals are more than sell signal, return True
        buy_count = 0
        sell_count = 0
        for signal in signals:
            if signal.status == 'buy':
                buy_count += 1
            if signal.status == 'sell':
                sell_count += 1
        return buy_count > sell_count

    def analysis(self) -> Signal:
        signals = []
        for policy in self._policies:
            signals.append(policy.analysis())

        if self._all_status_are_same(signals):
            return signals[0]
        elif self._vote_buy(signals):
            return Signal(self._ts_code, 'buy')
        else:
            return Signal(self._ts_code, 'sell')
