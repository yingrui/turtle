from datetime import date, datetime


class Stock:

    def __init__(self, ts_code, stock_info):
        self._ts_code = ts_code
        record = stock_info[stock_info['ts_code'] == ts_code]
        self._symbol = record['symbol'].values[0]
        self._name = record['name'].values[0]
        self._area = record['area'].values[0]
        self._market = record['market'].values[0]
        self._industry = record['industry'].values[0]
        self._list_date = self._parse_date(record['list_date'].values[0])
        self._delist_date = self._parse_date(record['delist_date'].values[0])
        self._list_status = record['list_status'].values[0]

    @staticmethod
    def _parse_date(value):
        if value is None or (isinstance(value, float) and str(value) == 'nan'):
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str) and len(value) == 8 and value.isdigit():
            return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
        return value

    @property
    def ts_code(self):
        return self._ts_code

    @property
    def symbol(self):
        return self._symbol

    @property
    def name(self):
        return self._name

    @property
    def area(self):
        return self._area

    @property
    def market(self):
        return self._market

    @property
    def industry(self):
        return self._industry

    @property
    def list_date(self):
        return self._list_date

    @property
    def status(self):
        if self._list_status == 'L':
            return 'Listed'
        elif self._list_status == 'D':
            return 'Delist'
        elif self._list_status == 'P':
            return 'Pause'
        else:
            return None

    def __str__(self) -> str:
        return "ts_code: {0}, name: {1}".format(self._ts_code, self._name)
