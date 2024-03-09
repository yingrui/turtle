import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def draw_line_chart_with_moving_average(x_series, y_series, sma_days_list=[5, 10, 20, 30],
                                        xlabel='Trade Date', ylabel='Close Price', title=''):
    f = plt.figure()
    f.set_figwidth(20)
    plt.plot(x_series, y_series, label='y')
    for days in sma_days_list:
        plt.plot(x_series, y_series.rolling(days).mean(), label='MA' + str(days))
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend(loc="upper left")
    return f


def draw_line_chart_with_atr(trade_date, close_price, daily_range,
                             ma_days=350, atr_days=20, up=7, down=3,
                             xlabel='Trade Date', ylabel='Close Price', title=''):
    sma = close_price.rolling(ma_days).mean()
    average_true_range = daily_range.rolling(atr_days).mean()

    f = plt.figure()
    f.set_figwidth(20)
    plt.plot(trade_date, close_price, label=ylabel)
    plt.plot(trade_date, sma + average_true_range * up, label='High')
    plt.plot(trade_date, sma - average_true_range * down, label='Low')
    plt.plot(trade_date, sma, label='MA' + str(ma_days))
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend(loc="upper left")
    return f


def draw_line_chart_with_bolling(trade_date, close_price, ma_days=350, up=2, down=1.5, xlabel='Trade Date',
                                 ylabel='Close Price', title=''):
    sma = close_price.rolling(ma_days).mean()
    std = close_price.rolling(ma_days).std()
    f = plt.figure()
    f.set_figwidth(20)
    plt.plot(trade_date, close_price, label='Close Price')
    plt.plot(trade_date, sma, label='MA' + str(ma_days))
    plt.plot(trade_date, sma + std * up, label='Up: ' + str(up) + ' * std')
    plt.plot(trade_date, sma - std * down, label='Lower: -' + str(down) + ' * std')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend(loc="upper left")
    return f


def draw_time_series_with_mean_and_std(x_series, y_series, xlabel='x', ylabel='y', title=''):
    desc = y_series.describe()
    mean = desc['mean']
    std = desc['std']

    mean_series = np.full(y_series.shape, mean)

    f = plt.figure()
    f.set_figwidth(20)
    plt.plot(x_series, mean_series, color="black", label='mean: ' + str(round(mean, 3)))
    plt.plot(x_series, mean_series + std, color="grey", label='+σ: ' + str(round(mean + std, 3)))
    plt.plot(x_series, mean_series - std, color="grey", label='-σ: ' + str(round(mean - std, 3)))
    plt.plot(x_series, mean_series + 2 * std, color="black", label='+2σ: ' + str(round(mean + 2 * std, 3)))
    plt.plot(x_series, mean_series - 2 * std, color="black", label='-2σ: ' + str(round(mean - 2 * std, 3)))
    plt.plot(x_series, y_series, label=ylabel)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend(loc="lower center", ncol=6)
    return f


def draw_line_chart_with_max_min_window(trade_date, close_price,
                                        ma_days=150, up=20, down=10,
                                        xlabel='Trade Date', ylabel='Close Price', title=''):
    sma = close_price.rolling(ma_days).mean()
    max_in_previous_days = close_price.rolling(up).max()
    min_in_previous_days = close_price.rolling(down).min()

    f = plt.figure()
    f.set_figwidth(20)
    plt.plot(trade_date, close_price, label=ylabel)
    plt.plot(trade_date, max_in_previous_days, label='Max' + str(up))
    plt.plot(trade_date, min_in_previous_days, label='Min' + str(down))
    plt.plot(trade_date, sma, label='MA' + str(ma_days))
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend(loc="upper left")
    return f


def draw_investment_log(df, xlabel='x', ylabel='y', title=''):
    x_series = pd.Series(df.date)
    f = plt.figure()
    f.set_figwidth(20)
    plt.plot(x_series, df.total / 10000, label='Total')
    plt.plot(x_series, (df.total - df.balance) / 10000, label='Position')
    plt.legend(loc='upper left')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    return f
