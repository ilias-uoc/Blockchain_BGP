import requests
import json, csv
import argparse


headers = {
    "Content-Type": "application/json"
}


def parse_bgpstream(filename):
    """
    Parses the bgpstream data from the file.

    :param filename: <str> The path of the .csv file.
    """
    f = open(filename, 'r')

    try:
        reader = csv.reader(f, delimiter='|')
        for row in reader:
            prefix, origin_as, as_path, project, collector, type, timestamp, peer_asn = row
            if prefix == '' or origin_as == '' or as_path == '':
                break
            if type == 'A':  # make the Announcements.
                make_announce_transaction(row)
            elif type == 'W':
                # future work
                pass
    finally:
        f.close()


def make_announce_transaction(data):
    """
    Makes a new announce transaction.

    :param data: the data for the request
    """
    prefix, origin_as, as_path, project, \
    collector, type, timestamp, peer_asn = data

    origin_asns = origin_as.split(",")
    path_asns = as_path.split(",")
    new_seq, loop = remove_prepending(path_asns)

    new_seq_rev = new_seq[::-1]

    for orAS in origin_asns:
        for i in range(len(new_seq_rev) - 1):
            as_source_list = []
            as_dest_list= []
            asn = new_seq_rev[i]

            if orAS == asn:
                as_source_list.append('0')
            else:
                as_source_list.append(new_seq_rev[i-1])
            as_dest_list.append(new_seq_rev[i+1])

            announce = {'prefix': prefix, 'bgp_timestamp': timestamp, 'as_source': asn,
                        'as_source_list': as_source_list, 'as_dest_list': as_dest_list, 'project': project,
                        'collector': collector, 'asn_peer': peer_asn}
            # make the request
            announce_data = json.dumps(announce)
            ip, port = find_AS_ip_port(asn)
            requests.post('http://' + str(ip) + ':' + str(port) + '/transactions/bgp_announce/new', data=announce_data,
                      headers=headers)


def remove_prepending(seq):
    """
    Method to remove prepending ASs from AS path.
    """
    last_add = None
    new_seq = []
    for x in seq:
        if last_add != x:
            last_add = x
            new_seq.append(x)

    is_loopy = False
    if len(set(seq)) != len(new_seq):
        is_loopy = True
        # raise Exception('Routing Loop: {}'.format(seq))
    return new_seq, is_loopy


def find_AS_ip_port(AS):
    """
    Returns the ip and port of the AS found in the new_nodes.csv file.

    :param AS: the AS number
    :return: the ip and port of the BC node
    """
    f = open('new_nodes.csv')
    try:
        reader = csv.reader(f)
        for row in reader:
            ip, port, ASN = row
            if AS == ASN:
                return ip, port
    finally:
        f.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', default='../bgpstream/forth_25_7_2018_9_to_10_am/P_139.91.0.0+16-S' +
                                                '_1532509200-E_1532512800.csv',
                        type=str, help='file with bgpstream data')
    args = parser.parse_args()
    parse_bgpstream(args.file)


if __name__ == '__main__':
    main()
