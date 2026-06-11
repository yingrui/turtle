from app.core.engine.policy.AtrPolicy import AtrPolicy
from app.core.engine.policy.BollingPolicy import BollingPolicy
from app.core.engine.policy.DonchianPolicy import DonchianPolicy
from app.core.engine.policy.EnsemblePolicy import EnsemblePolicy
from app.core.engine.policy.Policy import Policy
from app.core.engine.policy.SimpleMovingAveragePolicy import SimpleMovingAveragePolicy


class PolicyFactory:

    @staticmethod
    def create(ts_code, trade_data, parameters={}) -> Policy:
        policy = parameters.get('trade_policy.name', 'moving_average')
        if policy == 'moving_average':
            return SimpleMovingAveragePolicy(ts_code, trade_data, parameters)

        if policy == 'donchian':
            return DonchianPolicy(ts_code, trade_data, parameters)

        if policy == 'atr':
            return AtrPolicy(ts_code, trade_data, parameters)

        if policy == 'bolling':
            return BollingPolicy(ts_code, trade_data, parameters)

        if policy == 'ensemble':
            return EnsemblePolicy(ts_code, trade_data, parameters)

        raise Exception('Cannot create policy')
