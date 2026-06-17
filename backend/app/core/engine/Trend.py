class Trend:
    __slots__ = ('ts_code', 'status', 'gradient', 'stationary', 'reason')

    def __init__(self, ts_code, status, gradient=0, stationary=0, reason=''):
        self.ts_code = ts_code
        self.status = status
        self.gradient = gradient
        self.stationary = stationary
        self.reason = reason

    def __str__(self):
        return '{0}: {1} ({4}), {2}, {3}'.format(
            self.ts_code, self.status, self.gradient, self.stationary, self.reason,
        )
