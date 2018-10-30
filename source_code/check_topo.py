from bc_requests import get_chain, get_topos, get_by_txid
import networkx as nx


# This module parses data from the blockchain and forms the topology from scratch.
# Then it compares the topologies it has formed to the ones from the network.

Topos = {}


def parse_transactions():
    """
    Parses the transactions in the chain. Calls the appropriate functions for every transaction type.

    """
    chain_len = get_chain()
    chain = chain_len['chain']
    length = chain_len['length']

    if chain is None:
        return

    for i in range(length):
        block = chain[i]
        for tran in block['transactions']:
            if i == 0:
                genesis_topo(tran)
                continue
            transaction = tran['trans']

            if transaction['type'] == 'Assign':
                update_topo_assign(transaction)
            elif transaction['type'] == 'Revoke':
                update_topo_revoke(transaction)
            elif transaction['type'] == 'BGP Announce':
                update_topo_announce(transaction)
            elif transaction['type'] == 'BGP Withdraw':
                update_topo_withdraw(transaction)


def genesis_topo(genesis_tran):
    """
    Forms the initial topologies from the genesis transaction.

    :param genesis_tran: The genesis transaction of the blockchain.
    """
    output = genesis_tran['output']
    for i in range(len(output)):
        prefix = output[i][0]
        AS = output[i][1]
        try:
            topo = Topos[prefix]
            topo.add_edge(AS, prefix)
        except KeyError:
            Topos[prefix] = nx.DiGraph()
            topo = Topos[prefix]
            topo.add_edge(AS, prefix)


def update_topo_announce(transaction):
    """
    Updates the topology of this prefix based on the announce transaction.

    :param transaction: An Announce transaction.
    """
    prefix = transaction['input'][0]
    sub_paths = transaction['output']
    topo = Topos[prefix]

    for path in sub_paths:
        if path[1] == '0':
            topo.add_edges_from([(path[2], prefix), (path[3], path[2])])  # don't add the 0 node in the graph
        else:
            topo.add_edges_from([(path[2], path[1]), (path[3], path[2])])


def update_topo_withdraw(transaction):
    """
    Updates the topology of this prefix based on the withdraw transaction.

    :param transaction: A bgp withdraw transaction.
    """
    redundant_nodes = set()
    prefix = transaction['input'][0]
    as_source = transaction['input'][1]
    topo = Topos[prefix]
    topo.remove_node(as_source)  # remove the withdrawing node.
    # find all the other nodes that cannot reach the prefix.
    for node in topo.nodes:
        paths = nx.all_simple_paths(topo, node, prefix)
        if len(list(paths)) == 0 and node != prefix:
            redundant_nodes.add(node)  # these nodes cannot reach the prefix.
    topo.remove_nodes_from(redundant_nodes)


def update_topo_assign(transaction):
    """
    Updates the topology of this prefix based on an IP assign transaction.

    :param transaction: An IP Assign transaction
    """
    prefix = transaction['input'][0]
    as_source = transaction['input'][1]
    asn_list = transaction['input'][2]

    # reject the previous topo for this prefix and start a new one.
    topo = Topos[prefix]
    clear_topo(topo, prefix, as_source)

    for AS in asn_list:
        topo.add_edge(AS, prefix)


def update_topo_revoke(transaction):
    """
    Updates the topology of this prefix based on an IP Revoke transaction.

    :param transaction: An IP Revoke transaction.
    """
    as_source = transaction['input'][0]
    assign_tran_id = transaction['input'][1]
    assign_tran = get_by_txid(assign_tran_id)['transaction']

    if assign_tran is not None:
        tran = assign_tran['trans']
        prefix = tran['input'][0]
        as_dest_list = tran['input'][2]

        topo = Topos[prefix]
        for AS in as_dest_list:
            clear_topo(topo, prefix, AS)  # remove the ASes that no longer own the prefix
        topo.add_edge(as_source, prefix)  # add the AS that did the revocation and now owns the prefix.


def clear_topo(topo, prefix, source):
    """
    Removes the edges from the topology after a new IP Assignment.

    :param topo: The topology of this prefix
    :param prefix: The prefix
    :param source: The AS that made the Assign transaction.
    """
    try:
        topo.remove_edge(source, prefix)
    except nx.NetworkXError:
        return
    edges_to_source = set()
    edges_to_prefix = set()
    my_nodes = set()

    # find all the edges from all the paths that lead to the source AS
    for node in topo.nodes:
        for path in nx.all_simple_paths(topo, node, source):
            for i in range(len(path) - 1):
                my_nodes.add(path[i])
                my_nodes.add(path[i + 1])
                edges_to_source.add((path[i], path[i + 1]))

    # find all the edges from the paths that lead to the prefix from the previous nodes
    for node in my_nodes:
        for path in nx.all_simple_paths(topo, node, prefix):
            for i in range(len(path) - 1):
                edges_to_prefix.add((path[i], path[i + 1]))

    diff = edges_to_source.difference(edges_to_prefix)
    topo.remove_edges_from(diff)  # remove the edges that can't reach the prefix.


def compare_topos():
    """
    Compares the topologies this script formed with the ones from the network.

    :return: <Bool> True if the topologies are equal, False otherwise.
    """
    my_topos = {}
    bc_topos = get_topos()

    for prefix in Topos.keys():
        my_topos[prefix] = []
        for edge in list(Topos[prefix].edges):
            my_topos[prefix].append([edge[0], edge[1]])

    for prefix in bc_topos.keys():
        bc_edges = bc_topos[prefix]
        my_edges = my_topos[prefix]

        if len(bc_edges) != len(my_edges):
            return False

        if prefix not in my_topos.keys():
            return False

        if not all(k in my_edges for k in bc_edges):
            return False
    return True


def main():
    parse_transactions()
    print(compare_topos())


if __name__ == '__main__':
    main()