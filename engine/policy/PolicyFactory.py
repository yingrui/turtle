from engine.policy.DonchianPolicy import DonchianPolicy
from engine.policy.EnsemblePolicy import EnsemblePolicy
from engine.policy.Policy import Policy
from engine.policy.SimpleMovingAveragePolicy import SimpleMovingAveragePolicy


class PolicyFactory:

    @staticmethod
    def create(ts_code, trade_data, parameters={}) -> Policy:
        policy = parameters.get('trade_policy.name', 'moving_average')
        if policy == 'moving_average':
            return SimpleMovingAveragePolicy(ts_code, trade_data, parameters)

        if policy == 'donchian':
            return DonchianPolicy(ts_code, trade_data, parameters)

        if policy == 'ensemble':
            return EnsemblePolicy(ts_code, trade_data, parameters)

        raise Exception('Cannot create policy')
