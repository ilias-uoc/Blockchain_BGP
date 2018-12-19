import hashlib
import json
import requests
import threading
from urllib.parse import urlparse
from networkx.drawing.nx_agraph import to_agraph
from time import time
from flask import Flask, jsonify, request
from argparse import ArgumentParser
from Crypto.PublicKey import RSA
from config import state, txid_to_block, ASN_nodes, pending_transactions, as2pref, pref2as_pyt
from config import node_key, my_IP, my_ASN, my_Port, my_assignments, update_sum, assign_sum
from config import bgp_txid_announced, mutex, AS_topo, pt_mutex, bgpa_mutex, assigned_prefixes, assign_txids
from config import as_to_announced_txids, topo_mutex, AN_mutex, alive_neighbors, invalid_transactions
from Blockchain import blockchain
from Transaction import AssignTransaction, RevokeTransaction, UpdateTransaction
from BGP_Transaction import BGP_Announce, BGP_Withdraw
from Block import Block

"""
The main functionality is here.
"""

app = Flask(__name__)

""" --------------------------------------Routes and functions for the network-------------------------------------- """


def register_nodes():
    """
    Registers the other nodes of the network.
    The node running the script enters the BC network.
    """
    # first register the bootstrap nodes
    for asn in ASN_nodes:
        if my_IP in asn and my_Port == asn[1]:
            continue
        else:
            ip = "http://" + asn[0] + ":" + str(asn[1])
            blockchain.register_node(ip, asn[2])

    # then find out about the rest of the network
    neighbors = blockchain.nodes
    network = []
    for node in neighbors:
        try:
            response = requests.get('{}/neighbors'.format(node[0]))

            if response.status_code == 200:
                n = response.json()
                for v in n.values():
                    network.append(v)
        except:
            print("Could not contact node {}. Moving on...".format(node[0]))
            continue

    for node in network:
        parsed_url = urlparse(node[0])
        ip_port_list = parsed_url.netloc.split(":")
        ip_addr = ip_port_list[0]
        port = int(ip_port_list[1])

        if my_IP == ip_addr and my_Port == port:
            continue
        blockchain.register_node(node[0], node[1])


@app.route('/neighbors', methods=['GET'])
def send_neighbors():
    """
    The node sends its neighbors to the requesting node.

    :return: <json> This node's neighbors.
    """
    neighbors = blockchain.nodes
    neighbors_dict = {}

    for i, node in enumerate(neighbors):
        neighbors_dict[i] = node

    return jsonify(neighbors_dict), 200


@app.route('/public_key/send', methods=['GET'])
def send_public_key():
    """
    A node sends its public key upon request.

    :return: <str> This node's public key.
    """
    public_key = node_key.publickey()
    public_key_string = public_key.exportKey()
    return public_key_string, 200


def broadcast_public_key():
    """
    A node broadcasts its own Public Key, IP, Port and ASN to all the other nodes
    in the blockchain network.

    """
    headers = {
        "Content-Type": "application/json"
    }

    my_info = {
        'public_key': node_key.publickey().exportKey().decode(),
        'IPAddress': my_IP,
        'Port': my_Port,
        'ASN': my_ASN
    }
    my_data = json.dumps(my_info)

    print("Broadcasting my public key to the network...")

    for node in blockchain.nodes:
        try:
            requests.post('{}/public_key/incoming'.format(node[0]), data=my_data, headers=headers)
        except:
            print("Could not contact node {}. Moving on...".format(node[0]))
            continue


def update_nodes_publicKey(externKey, IPAddress, port):
    """
    Updates the public key entry of a node.
    """
    for i in range(len(ASN_nodes)):
        if ASN_nodes[i][0] == IPAddress and ASN_nodes[i][1] == port:
            ASN_nodes[i][-1] = RSA.importKey(externKey)


def request_public_key():
    """
    A node requests all public keys from the nodes in the blockchain network.
    Updates the ASN Nodes list.
    """
    print("Requesting my neighbors' public keys...")
    neighbors = blockchain.nodes
    for node in neighbors:
        try:
            response = requests.get('{}/public_key/send'.format(node[0]))
            key = response.content
            node_list = node[0].split("/")
            ip_port = node_list[2].split(":")

            node_IP = ip_port[0]
            node_Port = int(ip_port[1])
            update_nodes_publicKey(key, node_IP, node_Port)
        except:
            print("Could not contact node {}. Moving on...".format(node[0]))
            continue


@app.route('/public_key/incoming', methods=['POST'])
def receive_incoming_public_key():
    """
    A node receives a public key, the IP Address and Port from another node.
    Updates the ASN Nodes list.
    """
    values = request.get_json()
    # Check that required fields are in the posted data
    required = ['public_key', 'IPAddress', 'Port', 'ASN']
    if not all(k in values for k in required):
        return 'Missing values', 400

    ip = values['IPAddress']
    port = values['Port']
    asn = values['ASN']
    public_key = values['public_key']

    found = 0
    for AS in ASN_nodes:
        if ip in AS and int(port) == AS[1]:
            found = 1
            break

    if found == 0:
        ASN_nodes.append([ip, int(port), asn, None])
        addr = "http://" + ip + ":" + str(port)
        blockchain.register_node(addr, asn)

    update_nodes_publicKey(public_key, ip, port)
    return "Received a public key.", 200


@app.route('/alive', methods=['POST'])
def neighbor_is_alive():
    """
    It updates the alive neighbors dictionary every time
    a neighbor sends an alive message.
    """
    values = request.get_json()
    required = ['ip', 'port']
    if not all(k in values for k in required):
        return 'Missing values', 400
    ip = values['ip']
    port = values['port']
    url = "http://" + str(ip) + ":" + str(port)
    time_received = time()
    AN_mutex.acquire()
    alive_neighbors[url] = time_received
    AN_mutex.release()
    return "ok", 200


def send_alive():
    """
    Send an alive message to all the neighbors.
    This function is being called every 20 seconds.
    """
    headers = {
        "Content-Type": "application/json"
    }
    my_info = {
        'ip':  my_IP,
        'port': my_Port,
    }
    my_data = json.dumps(my_info)

    for node in blockchain.nodes:
        try:
            requests.post('{}/alive'.format(node[0]), data=my_data, headers=headers)  # send alive to every neighbor
        except:
            print("Could not contact node {}. Moving on...".format(node[0]))
            continue
    # start a timer that calls this function every 20 seconds.
    threading.Timer(20.0, send_alive).start()


def check_alive():
    """
    Checks if the neighbors are still here.
    Removes the dead neighbors from the neighbors set.
    """
    neighbors = blockchain.nodes
    dead_neighbors = []
    for node in neighbors:
        try:
            url = node[0]
            AN_mutex.acquire()
            last_alive = alive_neighbors[url]
            AN_mutex.release()
            time_now = time()
            if time_now - last_alive > 60:
                dead_neighbors.append(node)
        except KeyError:
            # node was already removed, do nothing
            AN_mutex.release()
    for node in dead_neighbors:
        # I also need mutexes for blockchain.nodes and ASN_nodes this is a TODO.
        neighbors.remove(node)
        AN_mutex.acquire()
        alive_neighbors.pop(node[0])
        remove_from_ASN_Nodes(node[0])
        AN_mutex.release()
    # start a timer that calls this function every 60 seconds.
    threading.Timer(60.0, check_alive).start()


def remove_from_ASN_Nodes(url):
    """
    Removes dead neighbors from the ASN Nodes list,
    so that we can register them again if they rejoin the network.
    that contain offline information about a neighbor i.e. its public key.
    :param url: the url address of the neighbor
    """
    parsed_url = urlparse(url)
    ip_port_list = parsed_url.netloc.split(":")
    ip_addr = ip_port_list[0]
    port = int(ip_port_list[1])
    node = None
    for asn in ASN_nodes:
        if ip_addr in asn and port == asn[1]:
            node = asn
            break
    if node is not None:
        ASN_nodes.remove(node)


@app.route('/', methods=['GET'])
def start():
    """
    Start. This is the first request a node has to make
    in order to enter the BC network.
    """
    # register nodes
    register_nodes()
    # broadcast your public key
    broadcast_public_key()
    # request all public keys in the network
    request_public_key()
    # send alive to all the neighbors
    send_alive()
    # start timer to check your neighbors
    check_alive()
    return "Successfully entered the BC network.", 200


""" ---------------------------------------------------------------------------------------------------------------  """


""" -------------------------------Routes and functions for all the transaction types------------------------------- """


@app.route('/transactions/assign/new', methods=['POST'])
def new_assign_transaction():
    """
    Create a new transaction.
    The AS node that makes the transaction signs it using its private key.
    """
    values = request.get_json()
    # Check that required fields are in the posted data
    required = ['prefix', 'as_source', 'as_dest', 'source_lease', 'leaseDuration', 'transferTag', 'last_assign']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new transaction
    prefix = values['prefix']
    as_source = values['as_source']
    as_dest = values['as_dest']
    source_lease = values['source_lease']
    leaseDuration = values['leaseDuration']
    transferTag = values['transferTag']
    last_assign = values['last_assign']

    tran_time = time()   # Transaction creation time

    new_trans = AssignTransaction(prefix, as_source, as_dest, source_lease, leaseDuration, transferTag, tran_time,
                                  last_assign)

    trans_hash = new_trans.calculate_hash()
    signature = node_key.sign(trans_hash.encode(), '')

    new_trans.sign(signature)

    test_str = '{}{}{}'.format(as_source, as_dest.sort(), last_assign).encode()
    test_hash = hashlib.sha256(test_str).hexdigest()
    if test_hash in assign_txids:
        return 'Transaction was already made', 500  # don't include the same transaction multiple times in the chain

    # Broadcast it to the rest of the network (to be mined later)
    blockchain.broadcast_transaction(new_trans)

    new_trans_dict = new_trans.return_transaction()  # also validates the transaction

    if new_trans_dict is not None:
        pending_transactions.append(new_trans_dict)  # to be mined later
        my_assignments.add(trans_hash)
        assigned_prefixes.add(prefix)
        assign_txids.add(test_hash)
    return 'New Assign transaction created. It was also broadcasted to the network', 200


@app.route('/transactions/assign/incoming', methods=['POST'])
def receive_incoming_assign_transaction():
    """
    Receive an incoming transaction sent by an AS.
    """
    values = request.get_json()

    # Check that the required fields are in the posted data
    required = ['prefix', 'as_source', 'as_dest', 'source_lease', 'leaseDuration', 'transferTag', 'signature', 'time',
                'last_assign']
    if not all(k in values for k in required):
        return 'Missing values', 400

    prefix = values['prefix']
    as_source = values['as_source']
    as_dest = values['as_dest']
    source_lease = values['source_lease']
    leaseDuration = values['leaseDuration']
    transferTag = values['transferTag']
    last_assign = values['last_assign']
    signature = values['signature']
    time = values['time']

    # Create a new transaction
    new_trans = AssignTransaction(prefix, as_source, as_dest, source_lease, leaseDuration, transferTag, time,
                                  last_assign)

    new_trans.signature = signature

    new_trans_dict = new_trans.return_transaction()  # also validates the transaction

    if new_trans_dict is not None:
        pending_transactions.append(new_trans_dict)  # to be mined later
        assigned_prefixes.add(prefix)
        return "Incoming Assign transaction received", 200
    else:
        # store the hash of this invalid transaction to the list
        tran_hash = new_trans.calculate_hash()
        invalid_transactions.append(tran_hash)
        return "Incoming Assign transaction invalid. Transaction is not accepted", 500


@app.route('/transactions/revoke/new', methods=['POST'])
def new_revoke_transaction():
    """
    Create a new Revoke transaction.
    The AS node that makes the transaction signs it using its private key.
    """
    values = request.get_json()
    # Check that required fields are in the posted data
    required = ['as_source', 'assign_tran']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new transaction
    as_source = values['as_source']
    assign_tran = values['assign_tran']

    tran_time = time()   # Transaction creation time

    new_trans = RevokeTransaction(as_source, assign_tran, tran_time)

    trans_hash = new_trans.calculate_hash()
    signature = node_key.sign(trans_hash.encode(), '')

    new_trans.sign(signature)

    # Broadcast it to the rest of the network (to be mined later)

    blockchain.broadcast_transaction(new_trans)

    new_trans_dict = new_trans.return_transaction()  # also validates the transaction

    if new_trans_dict is not None:
        pending_transactions.append(new_trans_dict)  # to be mined later

    return 'New Revoke transaction created. It was also broadcasted to the network', 200


@app.route('/transactions/revoke/incoming', methods=['POST'])
def receive_incoming_revoke_transaction():
    """
    Receive an incoming Revoke transaction sent by an AS.
    """
    values = request.get_json()

    # Check that the required fields are in the posted data
    required = ['as_source', 'assign_tran_id', 'time', 'signature']
    if not all(k in values for k in required):
        return 'Missing values', 400

    as_source = values['as_source']
    assign_tran_id = values['assign_tran_id']
    signature = values['signature']
    time = values['time']

    # Create a new transaction
    new_trans = RevokeTransaction(as_source, assign_tran_id, time)

    new_trans.signature = signature

    new_trans_dict = new_trans.return_transaction()  # also validates the transaction

    if new_trans_dict is not None:
        pending_transactions.append(new_trans_dict)  # to be mined later
        return "Incoming Revoke transaction received", 200
    else:
        # store the hash of this invalid transaction to the list
        tran_hash = new_trans.calculate_hash()
        invalid_transactions.append(tran_hash)
        return "Incoming Revoke transaction invalid. Transaction is not accepted", 500


@app.route('/transactions/update/new', methods=['POST'])
def new_update_transaction():
    """
    Create a new Update transaction.
    The AS node that makes the transaction signs it using its private key.
    """
    values = request.get_json()
    # Check that required fields are in the posted data
    required = ['as_source', 'assign_tran', 'new_lease']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new transaction
    as_source = values['as_source']
    assign_tran = values['assign_tran']
    new_lease = values['new_lease']

    tran_time = time()   # Transaction creation time

    new_trans = UpdateTransaction(as_source, assign_tran, tran_time, new_lease)

    trans_hash = new_trans.calculate_hash()
    signature = node_key.sign(trans_hash.encode(), '')

    new_trans.sign(signature)

    # Broadcast it to the rest of the network (to be mined later)

    blockchain.broadcast_transaction(new_trans)

    new_trans_dict = new_trans.return_transaction()  # also validates the transaction

    if new_trans_dict is not None:
        pending_transactions.append(new_trans_dict)  # to be mined later

    return 'New Update transaction created. It was also broadcasted to the network', 200


@app.route('/transactions/update/incoming', methods=['POST'])
def receive_incoming_update_transaction():
    """
    Receive an incoming Update transaction sent by an AS.
    """
    values = request.get_json()

    # Check that the required fields are in the posted data
    required = ['as_source', 'assign_tran_id', 'time', 'signature', 'new_lease']
    if not all(k in values for k in required):
        return 'Missing values', 400

    as_source = values['as_source']
    assign_tran_id = values['assign_tran_id']
    signature = values['signature']
    time = values['time']
    new_lease = values['new_lease']

    # Create a new transaction
    new_trans = UpdateTransaction(as_source, assign_tran_id, time, new_lease)

    new_trans.signature = signature

    new_trans_dict = new_trans.return_transaction()  # also validates the transaction

    if new_trans_dict is not None:
        pending_transactions.append(new_trans_dict)  # to be mined later
        return "Incoming Update transaction received", 200
    else:
        # store the hash of this invalid transaction to the list
        tran_hash = new_trans.calculate_hash()
        invalid_transactions.append(tran_hash)
        return "Incoming Update transaction invalid. Transaction is not accepted", 500


@app.route('/transactions/bgp_announce/new', methods=['POST'])
def new_bgp_announce():
    """
    Create a new BGP Announce transaction.
    The AS node that makes the transaction signs it using its private key.
    """
    values = request.get_json()
    # Check that required fields are in the posted data
    required = ['prefix', 'bgp_timestamp', 'as_source', 'as_source_list', 'as_dest_list', 'project', 'collector',
                'asn_peer']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new transaction
    prefix = values['prefix']
    bgp_timestamp = values['bgp_timestamp']
    as_source = values['as_source']
    as_source_list = values['as_source_list']
    as_dest_list = values['as_dest_list']
    project = values['project']
    collector = values['collector']
    asn_peer = values['asn_peer']

    tran_time = time()   # Transaction creation time

    new_trans = BGP_Announce(prefix, bgp_timestamp, as_source, as_source_list, as_dest_list, tran_time, project,
                             collector, asn_peer)

    trans_hash = new_trans.calculate_hash()
    signature = node_key.sign(trans_hash.encode(), '')

    new_trans.sign(signature)

    # Broadcast it to the rest of the network (to be mined later)
    blockchain.broadcast_transaction(new_trans)

    new_trans_dict = new_trans.return_transaction()  # also validates the transaction

    if new_trans_dict is not None and not check_announce(as_source, prefix, as_source_list, as_dest_list, bgp_timestamp):
        pending_transactions.append(new_trans_dict)  # to be mined later

    return 'New BGP Announce transaction created. It was also broadcasted to the network', 200


@app.route('/transactions/bgp_announce/incoming', methods=['POST'])
def bgp_announce_incoming():
    """
    Receive an incoming BGP Announce transaction sent by an AS.
    """
    values = request.get_json()

    # Check that the required fields are in the posted data
    required = ['prefix', 'bgp_timestamp', 'as_source', 'as_source_list', 'as_dest_list', 'signature', 'time',
                'project', 'collector', 'asn_peer']
    if not all(k in values for k in required):
        return 'Missing values', 400

    prefix = values['prefix']
    bgp_timestamp = values['bgp_timestamp']
    as_source = values['as_source']
    as_source_list = values['as_source_list']
    as_dest_list = values['as_dest_list']
    signature = values['signature']
    time = values['time']
    project = values['project']
    collector = values['collector']
    asn_peer = values['asn_peer']

    # Create a new transaction
    new_trans = BGP_Announce(prefix, bgp_timestamp, as_source, as_source_list, as_dest_list, time, project, collector,
                             asn_peer)
    new_trans.sign(signature)

    new_trans_dict = new_trans.return_transaction()  # also validates the transaction

    if new_trans_dict is not None and not check_announce(as_source, prefix, as_source_list, as_dest_list, bgp_timestamp):
        pending_transactions.append(new_trans_dict)  # to be mined later
        return "Incoming BGP Announce transaction received", 200
    else:
        # store the hash of this invalid transaction to the list
        tran_hash = new_trans.calculate_hash()
        invalid_transactions.append(tran_hash)
        return "Incoming BGP Announce transaction invalid. Transaction is not accepted", 500


@app.route('/transactions/bgp_withdraw/new', methods=['POST'])
def new_bgp_withdraw():
    """
    Create a new BGP Withdraw transaction.
    The AS node that makes the transaction signs it using its private key.
    """
    values = request.get_json()
    # Check that required fields are in the posted data
    required = ['prefix', 'as_source']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new transaction
    prefix = values['prefix']
    as_source = values['as_source']

    tran_time = time()   # Transaction creation time

    new_trans = BGP_Withdraw(prefix, as_source, tran_time)

    trans_hash = new_trans.calculate_hash()
    signature = node_key.sign(trans_hash.encode(), '')

    new_trans.sign(signature)

    # Broadcast it to the rest of the network (to be mined later)
    blockchain.broadcast_transaction(new_trans)

    new_trans_dict = new_trans.return_transaction()  # also validates the transaction

    if new_trans_dict is not None and check_withdraw(prefix, as_source):
        update_bgp_txids(as_source)
        pending_transactions.append(new_trans_dict)  # to be mined later

    return 'New BGP Withdraw transaction created. It was also broadcasted to the network', 200


@app.route('/transactions/bgp_withdraw/incoming', methods=['POST'])
def bgp_withdraw_incoming():
    """
    Receive an incoming BGP Withdraw transaction sent by an AS.
    """
    values = request.get_json()

    # Check that the required fields are in the posted data
    required = ['prefix', 'as_source', 'signature', 'time']
    if not all(k in values for k in required):
        return 'Missing values', 400

    prefix = values['prefix']
    as_source = values['as_source']
    signature = values['signature']
    time = values['time']

    # Create a new transaction
    new_trans = BGP_Withdraw(prefix, as_source, time)
    new_trans.sign(signature)

    new_trans_dict = new_trans.return_transaction()  # also validates the transaction

    if new_trans_dict is not None and check_withdraw(prefix, as_source):
        update_bgp_txids(as_source)
        pending_transactions.append(new_trans_dict)  # to be mined later
        return "Incoming BGP Withdraw transaction received", 200
    else:
        # store the hash of this invalid transaction to the list
        tran_hash = new_trans.calculate_hash()
        invalid_transactions.append(tran_hash)
        return "Incoming BGP Withdraw transaction invalid. Transaction is not accepted", 500


def check_lease():
    """
    Goes through every transaction in pending transactions and removes all the assign/update
    transactions that violate the lease duration

    (This is mostly for multiple assign/updates that have yet to be included in the blockchain)
    """
    pt_mutex.acquire()
    current_update_lease = -2000
    i = 0
    while i < len(pending_transactions):
        trans = pending_transactions[i]['trans']

        if trans['type'] == "Assign":
            as_assign_source = trans['input'][1]
            original_lease = trans['input'][3]
            lease = trans['input'][4]

            if not check_assign(as_assign_source, original_lease, lease):
                pending_transactions.remove(pending_transactions[i])  # this transaction is invalid
                i -= 1

        elif trans['type'] == "Update":
            as_assign_source = trans['input'][0]
            txid = trans['input'][1]
            lease = trans['input'][2]
            assign_tran = blockchain.find_by_txid(txid)
            original_lease = assign_tran['trans']['input'][3]

            if lease > current_update_lease:
                current_update_lease = lease

                if assign_tran is not None:
                    if not check_update(as_assign_source, original_lease, lease):
                        pending_transactions.remove(pending_transactions[i])  # this transaction is invalid
                        i -= 1
            else:
                pending_transactions.remove(pending_transactions[i])  # this transaction is invalid
                i -= 1
        i += 1
    pt_mutex.release()


def check_assign(as_assign_source, original_lease, lease):
    """
    Checks the sum of all assign transactions made by as_assign_source. If the current sum + lease is greater than
    the original lease this transaction is invalid so it should be removed from the pending transactions.
    """
    try:
        if assign_sum[as_assign_source] + lease > original_lease:
            return False
        else:
            assign_sum[as_assign_source] += lease
    except KeyError:
        assign_sum[as_assign_source] = lease
    return True


def check_update(as_assign_source, original_lease, lease):
    """
    Checks the sum of all update transactions made by as_assign_source. If the current sum + lease is greater than
    the original lease this transaction is invalid so it should be removed from the pending transactions.
    """
    try:
        if update_sum[as_assign_source] + lease > original_lease:
            return False
        else:
            update_sum[as_assign_source] += lease
    except KeyError:
        update_sum[as_assign_source] = lease
    return True


def check_announce(as_source, prefix, as_source_list, as_dest_list, bgp_timestamp):
    """
    Checks whether a BGP Announce transaction was made more than once before it was withdrawn.

    :param as_source: The advertising AS.
    :param prefix: The prefix.
    :param as_source_list: The ASes from which as_source learns the prefix.
    :param as_dest_list: The ASes as_source advertises the prefix.

    :return: <Bool> True if the transaction was made before. False otherwise.
    """
    as_source_list.sort()
    as_dest_list.sort()
    bgpa_mutex.acquire()
    txid = '{}{}{}{}'.format(as_source, prefix, as_source_list, as_dest_list, bgp_timestamp).encode()
    txid_hash = hashlib.sha256(txid).hexdigest()
    try:
        as_set = as_to_announced_txids[as_source]
    except KeyError:
        as_to_announced_txids[as_source] = set()
    try:
        x = bgp_txid_announced[txid_hash]
        if x is False:
            bgp_txid_announced[txid_hash] = True
            as_to_announced_txids[as_source].add(txid_hash)
        bgpa_mutex.release()
        return x
    except KeyError:
        bgp_txid_announced[txid_hash] = True
        as_to_announced_txids[as_source].add(txid_hash)
        bgpa_mutex.release()
        return False


def check_withdraw(prefix, as_source):
    """
    Checks if the same withdraw transaction has already been made in the same block before mining.

    :param as_source: The withdrawing AS
    :param prefix: The prefix
    :return: <Bool> True if the withdraw transaction has not been already made in the same block, False otherwise.
    """
    for i in range (len(pending_transactions)):
        trans = pending_transactions[i]['trans']
        if trans['type'] == "BGP Withdraw":
            w_prefix = trans['input'][0]
            w_as_source = trans['input'][1]
            if w_prefix == prefix and w_as_source == as_source:
                return False
    return True


def update_bgp_txids(as_source):
    """
    Marks all the txids made by as_source as False after a withdraw transaction made by as_source.

    :param as_source: The withdrawing AS.
    """
    try:
        bgpa_mutex.acquire()
        txids_list = as_to_announced_txids[as_source]
        for txid in txids_list:
            bgp_txid_announced[txid] = False
        as_to_announced_txids[as_source].clear()
        bgpa_mutex.release()
    except KeyError:
        print("Error: Key not found.")
        bgpa_mutex.release()


""" ---------------------------------------------------------------------------------------------------------------  """


""" --------------------------------------Routes and functions for the mining--------------------------------------  """


@app.route('/chain', methods=['GET'])
def full_chain():
    """
    A node sends its own copy of the blockchain upon request.

    :return: <dict> Containing the chain and its length.
    """
    dict_chain = []

    for block in blockchain.chain:
        dict_chain.append(block.__dict__)  # convert Block objects to dictionaries for json export

    response = {
        'chain': dict_chain,
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200


@app.route('/resolve', methods=['GET'])
def resolve():
    """
    Every node resolves any conflicts with other nodes in the network.
    """
    blockchain.resolve_conflicts()
    return "OK", 200


def broadcast_resolve_message():
    """
    Send a message to every other node in the blockchain network to check for any conflicts
    """
    neighbors = blockchain.nodes
    for node in neighbors:
        try:
            requests.get('{}/resolve'.format(node[0]))
        except:
            print("Could not contact node {}. Moving on...".format(node[0]))
            continue


def remove_pending_transactions():
    """
    Removes every pending transaction that is already in the chain.
    """
    pt_mutex.acquire()

    i = 0
    while i < len(pending_transactions):
        trans = pending_transactions[i]['trans']
        if trans['txid'] in txid_to_block.keys():
            pending_transactions.remove(pending_transactions[i])
            i -= 1
        i += 1

    pt_mutex.release()


def check_prefixes():
    """
    Checks if a prefix in a BGP Announce transaction has also been in an IP Assignment
    and if so, it rejects the BGP Announce transaction.
    """
    pt_mutex.acquire()

    i = 0
    while i < len(pending_transactions):
        trans = pending_transactions[i]['trans']
        if trans['type'] == "BGP Announce" and trans['input'][0] in assigned_prefixes:
            pending_transactions.remove(pending_transactions[i])
            i -= 1
        i += 1

    pt_mutex.release()


@app.route('/mine', methods=['GET'])
def mine():
    """
    Mines a new block.
    Adds a new block that include all the valid transactions to the chain if the mining was successful.
    """
    blockchain.resolve_conflicts()  # check the network before mining a new block

    check_prefixes()

    mutex.acquire()  # lock

    if blockchain.check_before_mining:
        remove_pending_transactions()

    if len(pending_transactions) > 0:
        last_block = blockchain.get_last_block()  # check critical region
        last_block_hash = last_block.hash

        check_lease()

        for i in range(len(pending_transactions)):
            # update txid_to_block with all the txids that are about to be mined
            tran = pending_transactions[i]['trans']
            txid = tran['txid']
            txid_to_block[txid] = len(blockchain.chain)

        block = Block(len(blockchain.chain), time(), pending_transactions, last_block_hash)

        print("Mining...")
        block.proof_of_work()

        block_hash = block.calculate_hash()
        signature = node_key.sign(block_hash.encode(), '')
        block.sign(signature)
        block.mined_by(my_ASN)

        blockchain.add_block(block)

        blockchain.state_update()
        blockchain.check_before_mining = False
        update_sum.clear()
        assign_sum.clear()
        assigned_prefixes.clear()
        assign_txids.clear()
        remove_pending_transactions()

    mutex.release()  # unlock
    broadcast_resolve_message()  # let everyone know that the chain has changed
    return "Mined one block", 200


""" ---------------------------------------------------------------------------------------------------------------  """


""" ---------------------------------------------------Misc/Debug--------------------------------------------------- """


@app.route('/debug', methods=['GET'])
def print_for_debugging():
    print("\nAS NODES:")
    print(ASN_nodes)
    print("\nTXID_TO_BLOCK:")
    print(txid_to_block)
    print("\nSTATE:")
    print(state)
    print("\nPENDING TRANSACTIONS:")
    print(pending_transactions)
    print("\nBC NEIGHBORS:")
    print(blockchain.nodes)
    print("\nBGP TXID ANNOUNCED:")
    print(bgp_txid_announced)
    print("\nAS TO BGP ANNOUNCED:")
    print(as_to_announced_txids)
    print("\nALIVE NEIGHBORS TIMES:")
    print(alive_neighbors)
    return "OK", 200


@app.route('/topos', methods=['GET'])
def return_topos():
    """
    Returns all the topologies of all the prefixes.
    """
    topos = {}
    topo_mutex.acquire()
    for prefix in AS_topo.keys():
        topos[prefix] = list(AS_topo[prefix].edges)
    topo_mutex.release()
    return jsonify(topos), 200


@app.route('/gv', methods=['POST'])
def graph_visualization():
    """
    Creates an image of the graph of the prefix requested.
    """
    values = request.get_json()
    required = ['prefix']
    if not all(k in values for k in required):
        return 'Missing Values', 400

    prefix = values['prefix']
    topo_mutex.acquire()
    try:
        graph = AS_topo[prefix]
        graph.nodes[prefix].update(style='filled', fillcolor='lightblue')
        A = to_agraph(graph)
        A.layout('dot')
        prefix = prefix.replace('/', '+')
        A.draw('graph_for_' + prefix + '.png')
        topo_mutex.release()
    except KeyError:
        topo_mutex.release()
        return 'The prefix does not exists', 400
    return 'Check your folder for a pic of the graph', 200


@app.route('/transactions/find_by_txid', methods=['POST'])
def find_transaction_by_txid():
    """
    Finds a transaction given a transaction id (txid)
    Returns all the information about this transaction

    :return: <dict>, <status code> The transaction if found in the blockchain
    """
    values = request.get_json()

    required = ['txid']
    if not all(k in values for k in required):
        return 'Missing values', 400

    txid = values['txid']

    try:
        index = txid_to_block[txid]
    except KeyError:
        return "Transaction does not exist", 500

    if index == 0:  # this is the genesis transaction
        block = blockchain.chain[0]
        requested_tran = block.transactions
        response = {
            'transaction': requested_tran
        }
        return jsonify(response), 200

    if index > 0:  # every other valid transaction
        chain = blockchain.chain
        block = chain[index]
        for i in range(len(block.transactions)):
            if txid == block.transactions[i]['trans']['txid']:
                requested_tran = block.transactions[i]
                response = {
                    'transaction': requested_tran
                }
                return jsonify(response), 200


""" ---------------------------------------------------------------------------------------------------------------- """


""" ------------------------------------------------------Main------------------------------------------------------ """


def update_my_publicKey(myIP, myPort):
    """
    Updates the node's public key entry in the ASN list.
    """
    for asn in ASN_nodes:
        if myIP in asn:
            if myPort == asn[1]:
                asn[-1] = node_key.publickey()
                break


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    parser.add_argument('-a', '--asn', help='the as number of the node')
    parser.add_argument('-i', '--ip', default='localhost', type=str, help='node\'s ip')
    args = parser.parse_args()

    my_Port = args.port
    my_IP = args.ip
    my_ASN = args.asn

    found = 0

    for asn in ASN_nodes:
        if my_IP in asn and my_Port == asn[1]:
            found = 1
            break

    if found == 0:
        ASN_nodes.append([my_IP, my_Port, my_ASN, node_key.publickey()])
    else:
        update_my_publicKey(my_IP, my_Port)

    app.run(host=my_IP, port=my_Port, threaded=True)


""" ---------------------------------------------------------------------------------------------------------------- """
