import  json
import hashlib

"""
The Block module. Includes all the functionality for the creation of a block in the blockchain
"""


class Block():
    def __init__(self, index, timestamp, transactions, previousHash):
        self.timestamp = timestamp
        self.transactions = []
        self.transactions.extend(transactions)
        self.previousHash = previousHash
        self.nonce = 0
        self.index = index
        self.hash = self.calculate_hash()
        self.signature = None
        self.miner = None

    def proof_of_work(self):
        """
        Simple Proof of Work Algorithm:
            - Find a number, nonce, such that the hash of the block contains 4 leading zeros.
        """
        while not self.valid_proof(self.nonce):
            self.nonce += 1
        self.hash = self.calculate_hash()  # update the hash of the block with the new nonce value

    def valid_proof(self, nonce):
        """
        Validates the Proof: Does the hash of the block contain 4 leading zeroes?

        :param nonce: <int>
        :return: <bool> True if correct, False otherwise.
        """
        block_hash = self.calculate_hash(nonce)
        if block_hash[:4] == "0000":
            return True
        else:
            return False

    def calculate_hash(self, nonce=None):
        """
        Create a SHA-256 hash of a Block.

        :return: <str> The hash of the block.
        """
        block_str = '{}{}{}{}'.format(self.timestamp, self.previousHash, json.dumps(self.transactions, sort_keys=True),
                                      nonce or self.nonce).encode()
        block_hash = hashlib.sha256(block_str).hexdigest()
        return block_hash

    def sign(self, signature):
        """
        The miner signs the block.
        """
        self.signature = signature

    def mined_by(self, miner):
        """
        Sets the miner of this block.
        """
        self.miner = miner
