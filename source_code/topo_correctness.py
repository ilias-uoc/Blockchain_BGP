import networkx as nx
from networkx.drawing.nx_agraph import to_agraph
import csv, argparse
from bc_requests import get_chain, get_topos, get_by_txid


# This module parses data from the bgpstream file and forms the topology from scratch.
# Then it compares the topologies it has formed to the ones from the network.

Topos = {}


def parse_updates(filename):
    """
    Parses the bgpstream data from the file. Builds the topology for every prefix in the file.

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
                origin_asns = origin_as.split(",")
                path_asns = as_path.split(",")
                new_seq, loop = remove_prepending(path_asns)

                new_seq_rev = new_seq[::-1]
                try:
                    topo = Topos[prefix]
                except KeyError:
                    Topos[prefix] = nx.DiGraph()
                    topo = Topos[prefix]
                    topo.add_node(prefix)

                for oAS in origin_asns:
                    for i in range(len(new_seq_rev) - 1):
                        asn = new_seq_rev[i]
                        if oAS == asn:
                            topo.add_edge(oAS, prefix)
                        else:
                            topo.add_edge(asn, new_seq_rev[i-1])
                        topo.add_edge(new_seq_rev[i+1], asn)
    finally:
        f.close()


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


def compare_topos():
    """
    Compares the topologies this script formed with the ones from the network.

    :return: <Bool> True if the topologies are equal, False otherwise.
    """
    prefixes = Topos.keys()
    my_topos = {}
    bc_topos = get_topos() # get the BC topos

    for prefix in prefixes:
        my_topos[prefix] = []
        for edge in list(Topos[prefix].edges):
            my_topos[prefix].append([edge[0], edge[1]])
        graph_visualization(prefix)

    for prefix in prefixes:
        bc_edges = bc_topos[prefix]
        my_edges = my_topos[prefix]

        if len(bc_edges) != len(my_edges):
            return False

        if not all(k in my_edges for k in bc_edges):
            return False
    return True


def graph_visualization(prefix):
    """
    Creates an image of the graph of the prefix provided.
    """
    try:
        graph = Topos[prefix]
        graph.nodes[prefix].update(style='filled', fillcolor='pink')
        A = to_agraph(graph)
        A.layout('dot')
        cprefix = prefix.replace('/', '+')
        A.draw('correctness_graph_for_' + cprefix + '.png')
        print('Check your folder for a pic of the graph')
    except KeyError:
        print('The prefix does not exists')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', default='../bgpstream/forth_25_7_2018_9_to_10_am/P_139.91.0.0+16-S' +
                                                '_1532509200-E_1532512800.csv',
                        type=str, help='file with bgpstream updates')
    args = parser.parse_args()
    parse_updates(args.file)
    print("Topologies correct:", compare_topos())


if __name__ == '__main__':
    main()