#!/usr/bin/env python3


import hashlib
import json
import requests

from textwrap import dedent
from time import time
from uuid import uuid4
from urllib.parse import urlparse
from flask import Flask, jsonify, request
from argparse import ArgumentParser


class Blockchain(object):

    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.check_before_mining = False

        # Create the genesis block
        self.new_block(proof=100, previous_hash=1)

    def new_block(self, proof, previous_hash=None):
        """
        Create a new Block in the Blockchain

        :param proof: <int> The proof given by the Proof of work algorithm
        :param previous_hash: (Optional) <str> Hash of previous Block
        :return: <dict> New Block
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1])
        }

        # Reset the current list of transactions
        self.current_transactions = []

        self.chain.append(block)

        return block

    def new_transaction(self, sender, recipient, amount):
        """
        Create a new transaction to go into the next mined block

        :param sender: <str> Address of the sender
        :param recipient:  <str> Address of the recipient
        :param amount: <int> Amount
        :return: <int> The index of the Block that will hold this transaction
        """

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        })

        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        """
        Create a SHA-256 hash of a Block

        :param block: <dict> Block
        :return: <str>
        """

        # We must make sure that the Dictionary is Ordered, or we'll have inconsistent hashes
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        """
        Simple Proof of Work Algorithm:
            - Find a number p' such that hash(pp') contains 4 leading zeros where p is the previous p'
            - p is the previous proof, and p' is the new proof

        :param last_proof: <int>
        :return: <int>
        """

        proof = 0
        while not self.valid_proof(last_proof, proof):
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        Validates the Proof: Does hash(last_proof, proof, contain 4 leading zeroes

        :param last_proof: <int> previous Proof
        :param proof: <int> current Proof
        :return: <bool> True if correct, False if not.
        """

        guess = '{}{}'.format(last_proof, proof).encode()
        guess_hash = hashlib.sha256(guess).hexdigest()

        return guess_hash[:4] == "0000"

    def register_node(self, address):
        """
        Add a new node to the list of nodes

        :param address: <str> Address of node. E.g., 'http://192.168.0.5:5000'
        :return: None
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.scheme + "://" + parsed_url.netloc)

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
            print(str(last_block))
            print(str(block))
            print('\n-----------\n')

            # Check that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Check that the Proof of Work is correct
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def broadcast_block(self, block):
        """
        Broadcast a newly created block to the rest of the network

        :param block: : <dict> Block
        :return: nothing
        """

        neighbors = self.nodes
        block_data = json.dumps(block)
        headers = {
            "Content-Type": "application/json"
        }

        for node in neighbors:
            try:
                response = requests.post('{}/blocks/incoming'.format(node), data=block_data, headers=headers)
            except:
                print("Could not contact node {}. Moving on...".format(node))
                continue

    def broadcast_transaction(self, transaction):
        """
        Broadcast a newly created transaction to the rest of the network

        :param transaction: : <dict> Transaction
        :return: nothing
        """

        neighbors = self.nodes
        transaction_data = json.dumps(transaction)
        headers = {
            "Content-Type": "application/json"
        }

        for node in neighbors:
            try:
                response = requests.post('{}/transactions/incoming'.format(node), data=transaction_data, headers=headers)
            except:
                print("Could not contact node {}. Moving on...".format(node))
                continue

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
        for node in neighbors:
            try:
                response = requests.get('{}/chain'.format(node))
            except:
                print("Could not contact node {}. Moving on...".format(node))
                continue

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our own chain if we have discovered a new valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            return True

        return False

# Instantiate our Node
app = Flask(__name__)

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate the new Blockchain
blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():
    # First check if the other chains have deviated...
    if blockchain.check_before_mining:
        replaced = blockchain.resolve_conflicts()
        blockchain.check_before_mining = False

    # Run the Proof of Work algorithm to get the next Proof...
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # Receive reward for finding the proof
    # Sender is symbolically "0" to signify that this node has minded a new coin
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1
    )

    # Forge the new block and add it to the chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)
    blockchain.broadcast_block(block)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash']
    }

    return jsonify(response), 200

@app.route('/blocks/incoming', methods=['POST'])
def receive_incoming_block():
    values = request.get_json()

    # Check that the required fields are in the posted data
    required = ['index', 'timestamp', 'transactions', 'proof', 'previous_hash']
    if not all(k in values for k in required):
        return 'Missing values', 400

    response = {'message': 'incoming block received'}

    if values['index'] > blockchain.last_block['index']:
        blockchain.check_before_mining = True
        # someone else has already mined our broadcast transactions, reset
        blockchain.current_transactions = []

    return jsonify(response), 200

@app.route('/transactions/incoming', methods=['POST'])
def receive_incoming_transaction():
    values = request.get_json()

    # Check that the required fields are in the posted data
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new transaction
    index = blockchain.new_transaction(sender=values['sender'], recipient=values['recipient'], amount=values['amount'])

    response = {'message': 'incoming transaction received'}

    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # Check that required fields are in the posted data
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new transaction
    index = blockchain.new_transaction(sender=values['sender'], recipient=values['recipient'], amount=values['amount'])

    # Broadcast it to the rest of the network (to be mined later)
    blockchain.broadcast_transaction({
        'sender': values['sender'],
        'recipient': values['recipient'],
        'amount': values['amount']
    })

    response = {'message': 'Transaction will be added to Block {}'.format(index)}

    return jsonify(response), 201

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }

    return jsonify(response), 200

@app.route('/nodes/list', methods=['GET'])
def list_nodes():
    response = {
        'message': 'We have {} neighbors'.format(len(blockchain.nodes)),
        'total_nodes': list(blockchain.nodes)
    }

    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes)
    }

    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)
