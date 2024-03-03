import datetime

from datetime import date


def tomorrow():
    return date.today() + datetime.timedelta(days=1)
