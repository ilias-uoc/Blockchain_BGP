import numpy as np
import matplotlib.pyplot as plt
from bc_requests import get_chain


def get_time_diff():
    """
    Finds and returns all the (block timestamp - transaction timestamp) differences in the chain.

    :return: A list with all the time differences, a dictionary with key the number of the block and value the list.
    """
    chain_len = get_chain()
    chain = chain_len['chain']
    length = chain_len['length']
    time_diffs_list = []
    time_diffs_dict = {}  # {block# : time_diffs_list}

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
            time_diffs_dict[i] = per_block_time_diffs
    return time_diffs_list, time_diffs_dict


def find_cdf(data):
    # Choose how many bins you want here
    num_bins = 20
    # Use the histogram function to bin the data
    counts, bin_edges = np.histogram(data, bins=num_bins, normed=True)
    # Now find the cdf
    cdf = np.cumsum(counts)
    # And finally plot the cdf
    plt.plot(bin_edges[1:], cdf)
    plt.savefig("cdf.png")

def main():
    l, d = get_time_diff()
    # block index: time differences of all the transactions in this block
    find_cdf(l)
    print(l)
    print(d)


if __name__ == '__main__':
    main()
