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
            if type == 'A':  # only parse the Announcements.
                make_announce_transaction(row)
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

    for orAS in origin_asns:
        as_source_set = set()
        as_dest_set = set()
        for destAS in path_asns:
            if orAS == destAS:
                as_source_set.add('0')
            else:
                as_dest_set.add(destAS)
        as_source_list = list(as_source_set)
        as_dest_list = list(as_dest_set)

        announce = {'prefix': prefix, 'bgp_timestamp': timestamp, 'as_source': orAS,
                    'as_source_list': as_source_list, 'as_dest_list': as_dest_list, 'project': project,
                    'collector': collector, 'asn_peer': peer_asn}
        # make the request
        announce_data = json.dumps(announce)
        ip, port = find_AS_ip_port(orAS)
        requests.post('http://' + ip + ':' + str(port) + '/transactions/bgp_announce/new', data=announce_data,
                      headers=headers)


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
