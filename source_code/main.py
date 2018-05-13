import hashlib
import json
import requests
from requests_futures.sessions import FuturesSession
from time import time, sleep
from random import seed, randrange
from flask import Flask, jsonify, request
from argparse import ArgumentParser
from Crypto.PublicKey import RSA
from config import state, txid_to_block, ASN_nodes, pending_transactions, as2pref, pref2as_pyt
from config import node_key, my_IP, my_ASN, my_Port, my_assignments, update_sum, assign_sum
from Blockchain import blockchain
from Transaction import AssignTransaction, RevokeTransaction, UpdateTransaction
from Block import Block
from config import myIPPort

"""
The main functionality is here
"""

app = Flask(__name__)


def broadcast_resolve_message():
    """
    Send a message to every other node in the blockchain network to check for any conflicts
    """
    headers = {
        "Content-Type": "application/json"
    }

    info = {
        "IP": my_IP,
        "PORT": my_Port
    }
    info_str = json.dumps(info)

    session = FuturesSession(max_workers=10)
    neighbors = blockchain.nodes

    for node in neighbors:
        session.post('{}/resolve/after_mine'.format(node[0]), data=info_str, headers=headers)
        # to-do : Cancel queued requests ??


@app.route('/resolve/after_mine', methods=['POST'])
def resolve_after_mine():
    values = request.get_json()

    required = ['IP', 'PORT']
    if not all(k in values for k in required):
        return 'Missing values', 400

    IP = values['IP']
    port = values['PORT']

    blockchain.resolve_after_mine(IP, port)   # possible deadlock here
    return "OK", 200


@app.route('/resolve', methods=['GET'])
def resolve():
    """
    Every node resolves any conflicts with other nodes in the network
    """
    resolved = blockchain.resolve_conflicts()
    if resolved:
        response = "Resolved conflicts"
    else:
        response = "Chain is up to date"

    return response, 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node[0], node[1])

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes)
    }
    return jsonify(response), 201


@app.route('/transactions/assign/new', methods=['POST'])
def new_assign_transaction():
    """
    Create a new transaction. The AS node that makes the transaction signs it using its private key.
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

    new_trans = AssignTransaction(prefix, as_source, as_dest, source_lease, leaseDuration, transferTag, tran_time, last_assign)

    trans_hash = new_trans.calculate_hash()
    signature = node_key.sign(trans_hash.encode(), '')

    new_trans.sign(signature)

    # Broadcast it to the rest of the network (to be mined later)
    blockchain.broadcast_transaction(new_trans)

    new_trans_dict = new_trans.return_transaction()  # also validates the transaction

    if new_trans_dict is not None:
        pending_transactions.append(new_trans_dict)  # to be mined later
        my_assignments.add(trans_hash)

    return 'New Assign transaction created. It was also broadcasted to the network', 200


@app.route('/transactions/assign/incoming', methods=['POST'])
def receive_incoming_assign_transaction():
    """
    Receive an incoming transaction sent by an AS.
    """
    values = request.get_json()

    # Check that the required fields are in the posted data
    required = ['prefix', 'as_source', 'as_dest', 'source_lease', 'leaseDuration', 'transferTag', 'signature', 'time', 'last_assign']
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
    new_trans = AssignTransaction(prefix, as_source, as_dest, source_lease, leaseDuration, transferTag, time, last_assign)

    new_trans.signature = signature

    new_trans_dict = new_trans.return_transaction()  # also validates the transaction

    if new_trans_dict is not None:
        pending_transactions.append(new_trans_dict)  # to be mined later
        return "Incoming Assign transaction received", 200
    else:
        return "Incoming Assign transaction invalid. Transaction is not accepted", 500


@app.route('/transactions/revoke/new', methods=['POST'])
def new_revoke_transaction():
    """
    Create a new Revoke transaction. The AS node that makes the transaction signs it using its private key.
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
        return "Incoming Revoke transaction invalid. Transaction is not accepted", 500


@app.route('/transactions/update/new', methods=['POST'])
def new_update_transaction():
    """
    Create a new Update transaction. The AS node that makes the transaction signs it using its private key.
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
    Receive an incoming Revoke transaction sent by an AS.
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
        return "Incoming Update transaction invalid. Transaction is not accepted", 500


def remove_pending_transactions():
    """
    Removes every pending transaction that is already in the chain
    """
    i = 0
    while i < len(pending_transactions):
        trans = pending_transactions[i]['trans']
        if trans['txid'] in txid_to_block.keys():
            pending_transactions.remove(pending_transactions[i])
            i -= 1
        i += 1


def check_lease():
    """
    Goes through every transaction in pending transactions and removes all the assign/update
    transactions that violate the lease duration

    (This is mostly for multiple assign/updates that have yet to be included in the blockchain)
    """
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


def check_assign(as_assign_source, original_lease, lease):
    """
    Checks the sum of all assign transactions made by as_assign_source. If the current sum + lease is greater than
    the original lease this transaction is invalid so it should be removed from the pending transactions
    """
    try:
        if assign_sum[as_assign_source] + lease > original_lease:
            return False
        else:
            assign_sum[as_assign_source] += lease
    except:
        assign_sum[as_assign_source] = lease
    return True


def check_update(as_assign_source, original_lease, lease):
    """
    Checks the sum of all update transactions made by as_assign_source. If the current sum + lease is greater than
    the original lease this transaction is invalid so it should be removed from the pending transactions
    """
    try:
        if update_sum[as_assign_source] + lease > original_lease:
            return False
        else:
            update_sum[as_assign_source] += lease
    except:
        update_sum[as_assign_source] = lease
    return True


@app.route('/mine', methods=['GET'])
def mine():
    """
    Mine a block to be added to the chain.
    """
    # possible deadlock here
    blockchain.resolve_conflicts()  # check the network before mining a new block

    if blockchain.check_before_mining:
        print("Resolved my chain so I'm removing the mined pending transactions")
        remove_pending_transactions()

    if len(pending_transactions) > 0:
        last_block = blockchain.get_last_block()
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
        remove_pending_transactions()

        broadcast_resolve_message()  # let everyone know that the chain has changed

    return "Mined one block", 200


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


def update_nodes_publicKey(externKey, IPAddress, port):
    """
    Updates the public key entry of a node.
    """
    for i in range(len(ASN_nodes)):
        if ASN_nodes[i][0] == IPAddress and ASN_nodes[i][1] == port:
            ASN_nodes[i][-1] = RSA.importKey(externKey)


@app.route('/public_key/send', methods=['GET'])
def send_public_key():
    """
    A node sends its public key upon request

    :return: <string> Node's public key
    """
    public_key = node_key.publickey()
    public_key_string = public_key.exportKey()
    return public_key_string, 200


@app.route('/public_key/incoming', methods=['POST'])
def receive_incoming_public_key():
    """
    A node receives a public key, the IP Address and Port from another node.
    Updates the ASN Nodes list.
    """
    values = request.get_json()
    # Check that required fields are in the posted data
    required = ['public_key', 'IPAddress', 'Port']
    if not all(k in values for k in required):
        return 'Missing values', 400

    update_nodes_publicKey(values['public_key'], values['IPAddress'], values['Port'])
    return "Received public key", 200


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


def broadcast_public_key():
    """
    A node broadcasts its own public key, IP and Port to all the other nodes in the blockchain network
    """
    headers = {
        "Content-Type": "application/json"
    }

    my_info = {
        'public_key': node_key.publickey().exportKey().decode(),
        'IPAddress': my_IP,
        'Port': my_Port
    }
    my_data = json.dumps(my_info)
    print("Broadcasting my public key to the network...")
    for node in blockchain.nodes:
        try:
            response = requests.post('{}/public_key/incoming'.format(node[0]), data=my_data, headers=headers)
        except:
            print("Could not contact node {}. Moving on...".format(node[0]))
            continue


@app.route('/command', methods=['GET'])
def command():
    """
    Start
    """
    # register nodes
    for asn in ASN_nodes:
        if my_IP in asn:
            if my_Port != asn[1]:
                ip = "http://" + asn[0] + ":" + str(asn[1])
                blockchain.register_node(ip, asn[2])

    # broadcast your public key
    broadcast_public_key()
    # request all public keys in the network
    request_public_key()
    return "OK", 200


@app.route('/print', methods=['GET'])
def print_for_debugging():
    print(ASN_nodes)
    print(txid_to_block)
    print(state)
    print(pending_transactions)
    return "OK", 200


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


def find_my_asn(myIP, myPort):
    """
    Returns the node's AS number
    """
    for asn in ASN_nodes:
        if myIP == asn[0]:
            if myPort == asn[1]:
                return asn[2]


def update_my_publicKey(myIP, myPort):
    """
    Updates the node's public key entry in the ASN list
    """
    for asn in ASN_nodes:
        if myIP in asn:
            if myPort in asn:
                asn[-1] = node_key.publickey()
                break


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port
    host = 'localhost'
    my_IP = host
    my_Port = port

    update_my_publicKey(my_IP, my_Port)

    my_ASN = find_my_asn(my_IP, my_Port)

    myIPPort[my_IP] = my_Port

    app.run(host=my_IP, port=my_Port)
