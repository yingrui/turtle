class Signal:
    __slots__ = ('ts_code', 'status')

    def __init__(self, ts_code, status):
        self.ts_code = ts_code
        self.status = status

    def __str__(self):
        if self.status == 'stay':
            return 'do nothing {0}'.format(self.ts_code)
        else:
            return '{0} {1}'.format(self.status, self.ts_code)
