import csv, requests, json

"""
This module provides functions that request data from the blockchain.
"""


def get_network():
    """
    Finds the ip and port of the nodes in the bc network.

    :return: A list with all the nodes' info eg [[IP, port],...]
    """
    f = open('bgp_network.csv', 'r')
    nodes = []
    try:
        reader = csv.reader(f)
        for row in reader:
            if reader.line_num != 1:
                IP, port, AS  = row
                nodes.append([IP, port])
    finally:
        f.close()
    return nodes


def get_chain():
    """
    Asks the BC network for the chain.

    :return: <dict> {chain:the chain, length:the number of block in the chain}, None if the nodes can't be reached
    """
    net_list = get_network()
    for node in net_list:
        try:
            response = requests.get('http://{}:{}/chain'.format(node[0], node[1]))
            chain = response.json()
            return chain
        except:
            print("Could not contact node {}:{}. Moving on...".format(node[0], node[1]))
            continue
    return None


def get_topos():
    """
    Asks the BC network for the topologies of all the prefixes.

    :return: <dict> {prefix : the graph}, None if nodes can't be reached.
    """
    net_list = get_network()
    for node in net_list:
        try:
            response = requests.get('http://{}:{}/topos'.format(node[0], node[1]))
            topos = response.json()
            return topos
        except:
            print("Could not contact node {}:{}. Moving on...".format(node[0], node[1]))
            continue
    return None


def get_by_txid(txid):
    """
    Returns a transaction based on a txid.

    :return: <dict> the requested transaction, None if a transaction is not found.
    """
    headers = {
        "Content-Type": "application/json"
    }

    net_list = get_network()
    req = {
        "txid": txid,
    }
    req_data = json.dumps(req)

    for node in net_list:
        try:
            response = requests.post('http://{}:{}/transactions/find_by_txid'.format(node[0], node[1]), data=req_data,
                                     headers=headers)
            tran = response.json()
            return tran
        except:
            print("Could not contact node {}:{}. Moving on...".format(node[0], node[1]))
            continue
    return None