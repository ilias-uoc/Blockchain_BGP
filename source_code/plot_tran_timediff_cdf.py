import numpy as np
import matplotlib.pyplot as plt
import statsmodels.api as sm
from bc_requests import get_chain


def get_time_diff():
    """
    Finds and returns all the (block timestamp - transaction timestamp) differences in the chain.

    :return: A list with all the time differences in the chain,
             A dict with the diffs per block (key: block #, val: a list with the time diffs of that block)
    """
    chain_len = get_chain()
    chain = chain_len['chain']
    length = chain_len['length']
    time_diffs_list = []
    perBlock_diffs = {}  # {block# : time_diffs_list}

    for i in range(length):
        per_block_time_diffs = []
        block = chain[i]
        block_time = block['timestamp']
        for tran in block['transactions']:
            if i == 0:
                tran_time = tran['timestamp']
            else:
                tran_time = tran['trans']['timestamp']
            time_diff = block_time - tran_time
            time_diffs_list.append(time_diff)
            per_block_time_diffs.append(time_diff)
            perBlock_diffs[i] = per_block_time_diffs
    return time_diffs_list, perBlock_diffs


def plot_cdf(results):
    # http://stackoverflow.com/questions/7799156/can-i-cycle-through-line-styles-in-matplotlib
    colors = ('k', 'g', 'b', 'r')
    linestyles = ('-', '--', '-.', ':')
    styles = ['{}{}'.format(color, linestyles[i]) for i, color in enumerate(colors)]

    cdf = sm.distributions.ECDF(results)

    x = set_x_axes(results)
    y = set_y_axes(cdf, x)

    fig, ax = plt.subplots()
    plt.subplots_adjust(bottom=0.15)
    plt.subplots_adjust(top=0.9)

    ax.plot(x, y, styles[0])

    # activate grid
    ax.grid(True, which='both')
    ax.xaxis.grid(linestyle=':')
    ax.yaxis.grid(linestyle=':')

    plt.savefig("cdf.png")
    plt.close()


def set_x_axes(results):
    # set x axes
    x_min = min(results)
    x_max = max(results)
    x= np.linspace(x_min, x_max, 1000)
    return x


def set_y_axes(cdf, x):
    # set y axes
    y = cdf(x)
    return y


def main():
    all_diffs, per_block_diffs = get_time_diff()
    # block index: time differences of all the transactions in this block
    plot_cdf(all_diffs)


if __name__ == '__main__':
    main()
