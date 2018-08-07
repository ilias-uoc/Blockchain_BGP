import requests
import json, csv
import argparse
import networkx as nx


headers = {
    "Content-Type": "application/json"
}

AS_topo = {}


def run_file(filename):
    """
    Makes BGP Announce transactions based on real data.

    :param filename: <str> The path of the .csv file.
    """
    f = open(filename or '../bgpstream/forth_25_7_2018_9_to_10_am/P_139.91.0.0+16-S_1532509200-E_1532512800.csv', 'r')

    my_ASN = '8522'  # TODO: Ignore for now.

    try:
        reader = csv.reader(f, delimiter='|')
        for row in reader:
            prefix, origin_as, as_path, project, collector, type, timestamp, peer_asn = row

            if type == 'A':  # only parse the Announcements.

                origin_asns = origin_as.split(",")
                path_asns = as_path.split(",")
                as_source_set = set()
                as_dest_set = set()

                for AS in origin_asns:
                    if my_ASN == AS:
                        as_source_set.add('0')
                    else:
                        as_source_set.add(AS)

                for AS in path_asns:
                    if my_ASN == AS:
                        pass
                    else:
                        as_dest_set.add(AS)

                as_source_list = list(as_source_set)
                as_dest_list = list(as_dest_set)

                announce = {'prefix': prefix, 'bgp_timestamp': timestamp, 'as_source': my_ASN,
                            'as_source_list': as_source_list, 'as_dest_list': as_dest_list, 'project': project,
                            'collector': collector, 'asn_peer': peer_asn}

                # make the request
                announce_data = json.dumps(announce)
                response = requests.post("http://localhost:(enter 8522's port here)/transactions/bgp_announce/new", data=announce_data,
                                         headers=headers)
                '''
                # form the topology
                try:
                    topo = AS_topo[prefix]
                except KeyError:
                    AS_topo[prefix] = nx.DiGraph()
                    topo = AS_topo[prefix]

                for AS in as_source_list:
                    if AS == '0':
                        topo.add_edge(my_ASN, prefix)  # don't add the 0 node in the graph
                    else:
                        topo.add_edge(AS, prefix)

                    for as_s in as_source_list:
                        for as_d in as_dest_list:
                            if as_s == '0':
                                topo.add_edge(as_d, my_ASN)  # don't add the 0 node in the graph
                            else:
                                topo.add_edge(as_d, as_s)
                '''
    finally:
        f.close()


def main():
    # TODO: Ignore for now.
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', type=str, help='the path of the file')
    parser.add_argument('-a', '--asn', help='the as number of the node')
    args = parser.parse_args()
    run_file(None)
    pass


if __name__ == '__main__':
    main()
