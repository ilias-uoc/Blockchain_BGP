import sys
import hashlib
import json
import requests
from textwrap import dedent
from time import time
from uuid import uuid4
from urllib.parse import urlparse
from flask import Flask, jsonify, request
from argparse import ArgumentParser
from  parse_utils import get_as_prefs
from Crypto.PublicKey import RSA
from Crypto import Random
import random


state = {} # state: {'prefix' : ([AS1,...,ASN], lease duration(in months), transfer tag, txid) }
txid_to_block = {} # {'txid' : block index}

ASN_nodes = [] # ASN nodes = [ [IP Address, Port, AS Number, ASN Public Key] ]
pending_transactions = []

as2pref, pref2as_pyt = get_as_prefs()


class Blockchain():
    def __init__(self):
        self.chain = []
        self.nodes = set()
        self.check_before_mining = False

        # Create the genesis block
        self.create_genesis_block()

    def create_genesis_block(self):
        """
        Creates and adds the first block in the Blockchain. (Genesis Block)
        """
        input = []
        output = []

        for AS in as2pref.keys():
            for pref in as2pref[AS]:
                input.append((pref, AS))
                output.append((pref, AS))
                state[pref] = (pref2as_pyt[pref], 1000, True, -1)

        txid_to_block[-1] = len(self.chain)

        genesis_transaction = {
            'input': input,
            'output': output,
            'txid': -1,
            'timestamp': time(),
        }

        genesis_block = Block(len(self.chain), time(), genesis_transaction, -1)
        self.chain.append(genesis_block)

    def add_block(self, block):
        self.chain.append(block)

    def get_last_block(self):
        """
        Returns Blockchain's last block
        :return: <Block> the last block of the chain
        """
        return self.chain[-1]

    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid

        :param chain: <list> A blockchain
        :return: <bool> True if valid, False if not
        """
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]

            # Check that the hash of the block is correct
            if block.previousHash != last_block.calculate_hash():
                return False

            # Check that the Proof of Work is correct
            if not block.valid_proof(block.nonce):
                return False

            last_block = block
            current_index += 1
        return True

    def resolve_conflicts(self):
        """
        This is our Consensus Algorithm, it resolves conflicts
        by replacing our chain with the longest one in the network.

        :return: <bool> True if our chain was replaced, False if not
        """

        neighbors = self.nodes
        new_chain = None

        # We are looking for chains longer than ours
        max_length = len(self.chain)

        # Get and verify the chains from all the nodes in the network
        print("Resolving the conflicts between the chains in the network...")
        for node in neighbors:
            try:
                response = requests.get('{}/chain'.format(node[0]))
            except:
                print("Could not contact node {}. Moving on...".format(node[0]))
                continue

            if response.status_code == 200:
                length = response.json()['length']
                chain_received = response.json()['chain']
                chain = self.dict_to_block_chain(chain_received)
                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our own chain if we have discovered a new valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            return True

        return False

    def dict_to_block_chain(self, chain):
        """
        Converts a chain of dictionaries that was received from a node
        to a chain of Block objects.

        :return: <list> A chain of Block objects
        """
        bc = []
        for block in chain:
            timestamp = block['timestamp']
            transactions = block['transactions']
            previousHash = block['previousHash']
            nonce = block['nonce']
            index = block['index']
            hash = block['hash']

            new_block = Block(index, timestamp, transactions, previousHash)
            new_block.hash = hash
            new_block.nonce = nonce

            bc.append(new_block)
        return bc

    def register_node(self, address, ASN):
        """
        Add a new node to the list of nodes
        Update the ASN Nodes list

        :param address: <str> Address of node. E.g., 'http://192.168.0.5:5000'
        :param ASN: <str> AS number of the node
        :return: None
        """
        parsed_url = urlparse(address)
        self.nodes.add((parsed_url.scheme + "://" + parsed_url.netloc, ASN))

        ip_port_list = parsed_url.netloc.split(":")
        ip_addr = ip_port_list[0]
        port = int(ip_port_list[1])

        found_it = 0
        for asn in ASN_nodes:
            if ip_addr in asn:
                if port != asn[1]:
                    found_it = 1

        if found_it == 0:
            ASN_nodes.append([ip_addr, port, ASN, None])

    def broadcast_transaction(self, transaction):
        """
        Broadcast a newly created transaction to the rest of the network

        :param transaction: : <Transaction> Transaction
        """
        neighbors = self.nodes
        transaction_data = json.dumps(transaction.__dict__)
        headers = {
            "Content-Type": "application/json"
        }

        print("Broadcasting the transaction to the rest of the network...")

        for node in neighbors:
            try:
                response = requests.post('{}/transactions/incoming'.format(node[0]), data=transaction_data, headers=headers)
            except:
                print("Could not contact node {}. Moving on...".format(node[0]))
                continue


class Block():
    def __init__(self, index, timestamp, transactions, previousHash):
        self.timestamp = timestamp
        self.transactions = transactions
        self.previousHash = previousHash
        self.nonce = 0
        self.index = index
        self.hash = self.calculate_hash()

    def proof_of_work(self):
        """
        Simple Proof of Work Algorithm:
            - Find a number, nonce, such that the hash of the block contains 4 leading zeros

        :param nonce: <int>
        """
        while not self.valid_proof(self.nonce):
            self.nonce += 1
        self.hash = self.calculate_hash() # update the hash of the block with the new nonce value

    def calculate_hash(self, nonce=None):
        """
        Create a SHA-256 hash of a Block

        :return: <str> The hash of the block
        """
        block_str = '{}{}{}{}'.format(self.timestamp, self.previousHash, json.dumps(self.transactions, sort_keys=True),
                                      nonce or self.nonce).encode()
        block_hash = hashlib.sha256(block_str).hexdigest()
        return block_hash

    def valid_proof(self, nonce):
        """
        Validates the Proof: Does the hash of the block contain 4 leading zeroes?

        :param nonce: <int>
        :return: <bool> True if correct, False if not.
        """
        block_hash = self.calculate_hash(nonce)
        if block_hash[:4] == "0000":
            return True
        else:
            return False


blockchain = Blockchain()


class Transaction():
    def __init__(self, prefix, as_source, as_dest, leaseDuration, transferTag, signature, txid):
        self.prefix = prefix
        self.as_source = as_source
        self.as_dest = as_dest
        self.leaseDuration = leaseDuration
        self.transferTag = transferTag # can the ASes in the AS destination list further transfer the prefix?
        self.last_assign = txid
        self.signature = signature
        self.__input = []
        self.__output = []

        if not isinstance(as_dest, list):
            raise TypeError("AS destination must be set to a list")

        if not isinstance(as_source, str):
            raise TypeError("AS source must be set to a string")

        for i in as_dest:
            if not isinstance(i, str):
                raise TypeError("AS destination list element must be set to a string")

    def validate_transaction(self):
        """
        Validates the transaction

        :return: <bool> True if transaction is valid, False if not.
        """
        if self.validate_AS_assign():
            self.__input.extend([self.prefix, self.as_source, self.as_dest, self.leaseDuration, self.transferTag,
                                 self.last_assign])
            for AS in self.as_dest:
                self.__output.append((self.prefix, AS, self.leaseDuration, self.transferTag))
            return True
        else:
            return False

    def validate_AS_assign(self):
        """
        Checks whether the AS source can assign this prefix to the destination ASes.
        An AS can assign the prefix only if we can verify the signature, it can provide a valid transaction id of the
        last assignment, its lease duration is greater than the one given and it has the right to transfer the prefix
        further to other ASes.

        :return: <bool> True if correct, False if not.
        """
        if self.verify_signature() and \
            self.last_assign == state[self.prefix][-1] and \
            state[self.prefix][1] >= self.leaseDuration and \
            self.as_source in state[self.prefix][0] and \
            state[self.prefix][2] is True:
            return True
        else:
            return False

    def return_transaction(self):
        """
        Returns a valid transaction to be added to a block in the blockchain

        :return: <dict> A valid transaction, or None if the transaction is not valid.
        """
        if self.validate_transaction():
            txid = '{}{}{}'.format(self.__input, self.__output, time()).encode()
            txid_hash = hashlib.sha256(txid).hexdigest()

            txid_to_block[txid_hash] = len(blockchain.chain)

            transaction = {
                'trans': {
                    'input': self.__input,
                    'output': self.__output,
                    'timestamp': time(),
                    'txid': txid_hash
                },
                'signature': self.signature
             }
            return transaction
        else:
            return None

    def verify_signature(self):
        """
        Verifies the origin of the transaction using the public key of the ASN that made this transaction

        :return: <bool> True if signature is verified, False if not.
        """
        ASN_pkey = None
        for asn in ASN_nodes:
            if self.as_source == asn[2]:
                ASN_pkey = asn[-1]
                break

        if ASN_pkey is not None:
            trans_str = '{}{}{}{}{}{}'.format(self.prefix, self.as_source, self.as_dest, self.leaseDuration,
                                              self.transferTag, self.last_assign).encode()
            trans_hash = hashlib.sha256(trans_str).hexdigest().encode()
            if ASN_pkey.verify(trans_hash, self.signature):
                return True
            else:
                return False
        else:
            return False


def init_nodes():
    host = 'localhost'
    port = 5000
    as_list = []
    for asn in as2pref.keys():
        as_list.append(asn)
    as_list.sort()

    for i in range(0,5):
        ASN_nodes.append([host, port + i, as_list[i], None])


def generate_keypair():
    """
    Generates a public-private key pair for the node that is running the script.
    """
    random_generator = Random.new().read
    key = RSA.generate(2048, random_generator)
    return key


node_key = generate_keypair()
my_IP = ''
my_Port = ''

init_nodes()

app = Flask(__name__)


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    """
    Create a new transaction. The AS node that makes the transaction signs it using its private key.
    """
    values = request.get_json()
    # Check that required fields are in the posted data
    required = ['prefix', 'as_source', 'as_dest', 'leaseDuration', 'transferTag', 'last_assign']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new transaction
    prefix = values['prefix']
    as_source = values['as_source']
    as_dest = values['as_dest']
    leaseDuration = values['leaseDuration']
    transferTag = values['transferTag']
    last_assign = values['last_assign']

    trans_str = '{}{}{}{}{}{}'.format(prefix, as_source, as_dest, leaseDuration, transferTag, last_assign).encode()
    trans_hash = hashlib.sha256(trans_str).hexdigest().encode()
    signature = node_key.sign(trans_hash, '')

    new_trans = Transaction(prefix, as_source, as_dest, leaseDuration, transferTag, signature, last_assign)

    # Broadcast it to the rest of the network (to be mined later)
    blockchain.broadcast_transaction(new_trans)

    return 'New transaction created. It was broadcasted to the network', 200


def broadcast_resolve_message():
    """
    Send a message to every other node in the blockchain network to check for any conflicts
    """
    neighbors = blockchain.nodes
    for node in neighbors:
        try:
            response = requests.get('{}/resolve'.format(node[0]))
        except:
            print("Could not contact node {}. Moving on.!.".format(node[0]))
            continue


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


@app.route('/transactions/incoming', methods=['POST'])
def receive_incoming_transaction():
    """
    Receive an incoming transaction sent by an AS.
    """
    values = request.get_json()

    # Check that the required fields are in the posted data
    required = ['prefix', 'as_source', 'as_dest', 'leaseDuration', 'transferTag', 'signature', 'last_assign']
    if not all(k in values for k in required):
        return 'Missing values', 400

    prefix = values['prefix']
    as_source = values['as_source']
    as_dest = values['as_dest']
    leaseDuration = values['leaseDuration']
    transferTag = values['transferTag']
    last_assign = values['last_assign']
    signature = values['signature']

    # Create a new transaction
    new_trans = Transaction(prefix, as_source, as_dest, leaseDuration, transferTag, signature, last_assign)

    new_trans_dict = new_trans.return_transaction()  # also validates the transaction
    if new_trans_dict is not None:
        pending_transactions.append(new_trans_dict)      # to be mined later
        return "Incoming transaction received", 200
    else:
        return "Incoming transaction invalid. Transaction is not accepted", 500


@app.route('/mine', methods=['GET'])
def mine():
    """
    Mine a block to be added to the chain.
    """
    blockchain.resolve_conflicts()

    if len(pending_transactions) > 0:
        last_block = blockchain.get_last_block()
        last_block_hash = last_block.hash

        block = Block(len(blockchain.chain), time(), pending_transactions, last_block_hash)
        print("Mining...")
        block.proof_of_work()

        blockchain.add_block(block)

    # should call broadcast_resolve_message() here but something goes wrong.. to-do! :)
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
                ip = "http://"+asn[0]+":"+str(asn[1])
                blockchain.register_node(ip, asn[2])

    # broadcast your public key
    broadcast_public_key()
    # request all public keys in the network
    request_public_key()
    return "OK", 200


@app.route('/print_nodes', methods=['GET'])
def print_nodes():
    print(ASN_nodes)
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

    if index == 0: # this is the genesis transaction
        block = blockchain.chain[0]
        requested_tran = block.transactions
        response = {
            'transaction': requested_tran
        }
        return jsonify(response), 200

    if index > 0: # every other valid transaction
        chain = blockchain.chain
        block = chain[index]
        for i in range(len(block.transactions)):
            if txid == block.transactions[i]['trans']['txid']:
                requested_tran = block.transactions[i]
                response = {
                    'transaction': requested_tran
                }
                return jsonify(response), 200


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port
    host = 'localhost'
    my_IP = host
    my_Port = port

    app.run(host=my_IP, port=my_Port)
