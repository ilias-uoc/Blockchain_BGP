import json
from bc_requests import get_chain
from argparse import ArgumentParser
from pprint import pprint


def calc_mining_times(filename):
    # Calculate the time difference between block mining time - block creation time,
    # i.e. how long it took to find the PoW
    # Returns a dictionary with the per block differences
    if filename is None:
        # get chain from the network
        chain_len = get_chain()
    else:
        with open(filename) as f:
            chain_len = json.load(f)
        f.close()
    chain = chain_len['chain']
    length = chain_len['length']
    timediffs = {} # { block index : time_diff }
    for i in range(length):
        if i == 0:
            # don't care about Genesis block, since it was not mined.
            continue
        block = chain[i]
        block_time = block['timestamp']
        block_mined_time = block['mined_timestamp']
        diff = block_mined_time - block_time
        timediffs[i] = diff
    return timediffs


def main(filename):
    timediffs = calc_mining_times(filename)
    pprint(timediffs)
    print(" -------- ")
    print("Min:", min(timediffs.values()))
    print("Max:", max(timediffs.values()))
    print("Average time: ", sum(timediffs.values())/len(timediffs.values()))


if __name__=="__main__":
    parser = ArgumentParser()
    parser.add_argument('-f', '--file', default=None,  help='JSON file that contains a chain')
    args = parser.parse_args()
    filename = args.file
    main(filename)