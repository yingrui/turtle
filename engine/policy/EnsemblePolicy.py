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

    def analysis(self) -> Signal:
        signals = []
        for policy in self._policies:
            signals.append(policy.analysis())

        if signals[0].status == signals[1].status:
            return signals[0]
        elif signals[0].status == 'stay':
            return signals[1]
        elif signals[1].status == 'stay':
            return signals[0]
        else:
            return Signal(self._ts_code, 'sell')
