class Trend:
    __slots__ = ('ts_code', 'status', 'gradient', 'stationary')

    def __init__(self, ts_code, status,  gradient=0, stationary=0):
        self.ts_code = ts_code
        self.status = status
        self.gradient = gradient
        self.stationary = stationary

    def __str__(self):
        return '{0}: {1}, {2}, {3}'.format(self.ts_code, self.status, self.gradient, self.stationary)
