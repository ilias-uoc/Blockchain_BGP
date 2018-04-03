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


state = {}

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
        as2pref, pref2as_pyt = get_as_prefs()
        input = []
        output = []

        for AS in as2pref.keys():
            bc = hashlib.sha256(str(AS).encode()).hexdigest()
            for pref in as2pref[AS]:
                input.append((pref, AS))
                output.append((pref, AS, bc))
                state[pref] = (AS, -1)

        txid = '{}{}{}'.format(input, output, time()).encode()
        txid_hash = hashlib.sha256(txid).hexdigest()

        genesis_transaction = [{
            'input': input,
            'output': output,
            'txid': txid_hash,
            'timestamp': time(),
        }]

        genesis_block = Block(time(), genesis_transaction, -1)
        self.chain.append(genesis_block)

    def add_block(self, block):
        self.chain.append(block)

    def get_last_block(self):
        """
        Returns Blockchain's last block
        :return: <Block> the last block of the chain
        """
        return self.chain[-1]

    @staticmethod
    def hash(block):
        """
        Create a SHA-256 hash of a Block

        :param block: <dict> Block
        :return: <str> The hash of the block
        """
        block_string = json.dumps(block, sort_keys=True).encode()  # sorting dictionary for consistent hashes
        return hashlib.sha256(block_string).hexdigest()

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
            if block.previousHash != self.hash(last_block.__dict__):
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

    def register_node(self, address):
        """
        Add a new node to the list of nodes

        :param address: <str> Address of node. E.g., 'http://192.168.0.5:5000'
        :return: None
        """
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.scheme + "://" + parsed_url.netloc)


class Block():
    def __init__(self, timestamp, transactions, previousHash):
        self.timestamp = timestamp
        self.transactions = transactions
        self.previousHash = previousHash
        self.nonce = 0
        self.hash = self.calculate_hash()

        if not isinstance(transactions, list):
            raise TypeError("Transactions must be set to a list of dictionaries")

    def proof_of_work(self):
        """
        Simple Proof of Work Algorithm:
            - Find a number, nonce, such that the hash of the block contains 4 leading zeros

        :param nonce: <int>
        """
        while not self.valid_proof(self.nonce):
            self.nonce += 1
        self.hash = self.calculate_hash() # The hash of the block is now calculated with the updated nonce

    def calculate_hash(self):
        """
        Create a SHA-256 hash of a Block

        :return: <str> The hash of the block
        """
        block_str = '{}{}{}{}'.format(self.timestamp, self.previousHash, json.dumps(self.transactions, sort_keys=True), self.nonce).encode()
        block_hash = hashlib.sha256(block_str).hexdigest()
        return block_hash

    def mine_block(self):
        pass

    def valid_proof(self, nonce):
        """
        Validates the Proof: Does the hash of the block contain 4 leading zeroes?

        :param nonce: <int>
        :return: <bool> True if correct, False if not.
        """
        block_str = '{}{}{}{}'.format(self.timestamp, self.previousHash, json.dumps(self.transactions, sort_keys=True), nonce).encode()
        block_hash = hashlib.sha256(block_str).hexdigest()
        if block_hash[:4] == "0000":
            return True
        else:
            return False


chain = Blockchain()


class Transaction():
    def __init__(self, prefix, as_source, bc_origin, as_dest, leaseDuration, transferTag, txid):
        self.prefix = prefix
        self.as_source = as_source
        self.bc = bc_origin
        self.as_dest = as_dest
        self.leaseDuration = leaseDuration
        self.transferTag = transferTag
        self.last_assign = txid
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
        if self.last_assign == state[self.prefix][-1] and self.valid_as2prefix_chain():
            self.__input.extend([self.prefix, self.as_source, self.bc, self.as_dest, self.leaseDuration, self.transferTag, self.last_assign])

            for AS in self.as_dest:
                as_bc = hashlib.sha256(str(AS).encode()).hexdigest()
                self.__output.append((self.prefix, AS, self.leaseDuration, self.transferTag, as_bc))
            return True
        else:
            return False

    def valid_as2prefix_chain(self):
        """
        Can ASY assign the prefix?: Builds the chain of events from genesis to the current transaction

        :return: <bool> True if correct, False if not.
        """
        AS_chain = []

        for block in chain.chain:
            block_output = block.transactions['output']
            for i in range (0, len(block_output)):
                # search every tuple in the output for the prefix
                if block_output[i][0] == self.prefix:
                    AS_chain.append(block_output[i][1])
        if self.as_source in AS_chain and self.transferTag == True:
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

            transaction = {
                'input': self.__input,
                'output': self.__output,
                'timestamp': time(),
                'txid': txid_hash
             }
            return transaction
        else:
            return None

def init_ASnum():
    "Assigns a AS number to the node ---- (Not correct/final!)"
    random.seed()
    as2pref, pref2as_pyt = get_as_prefs()
    as_list = list(as2pref.keys())
    node_ASnum = as_list[random.randint(0, len(as_list) - 1)]
    return node_ASnum

def generate_keypair():
    """
    Generates a public-private key pair for the node that is running the script.
    """
    random_generator = Random.new().read
    key = RSA.generate(2048, random_generator)
    return key


node_ASnum = init_ASnum()

bc = hashlib.sha256(str(node_ASnum).encode()).hexdigest()

node_key = generate_keypair()


if __name__ == '__main__':
    pass
