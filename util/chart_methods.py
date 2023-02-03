import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def draw_line_chart_with_moving_average(x_series, y_series, sma_days_list=[5, 10, 20, 30]):
    f = plt.figure()
    f.set_figwidth(20)
    plt.plot(x_series, y_series, label='y')
    for days in sma_days_list:
        plt.plot(x_series, y_series.rolling(days).mean(), label='MA' + str(days))
    plt.legend(loc="upper left")
    plt.show()


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
    plt.show()


def draw_investment_log(df):
    x_series = pd.Series(df.date)
    f, ax = plt.subplots(1)
    f.set_figwidth(20)
    ax.plot(x_series, df.total / 10000)
    ax.plot(x_series, df.balance / 10000)
    ax.set_ylim(ymin=0)
    plt.show()
