import json
import requests
import networkx as nx
from time import time
from urllib.parse import urlparse
from Block import Block
from config import state, txid_to_block, ASN_nodes, pending_transactions, as2pref, pref2as_pyt
from config import my_assignments, node_key, AS_topo, invalid_transactions
from config import mutex, topo_mutex, asn_nodes_mutex, bc_nodes_mutex


"""
The Blockchain module. Includes all the functionality for the blockchain
"""


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
                state[pref] = []
                AS_topo[pref] = nx.DiGraph()
                for asn in pref2as_pyt[pref]:
                    state[pref].append((asn, 1000, True, -1))
                    AS_topo[pref].add_edge(asn, pref)

        txid_to_block[-1] = len(self.chain)

        genesis_transaction = [{
            'input': input,
            'output': output,
            'txid': -1,
            'timestamp': time(),
        }]

        genesis_block = Block(len(self.chain), time(), genesis_transaction, -1)
        self.add_block(genesis_block)

    def add_block(self, block):
        """
        Adds a new block to our Blockchain
        :param block: <Block> A Block object
        """
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

            # check if you can verify the block's miner origin
            if not self.verify_signature(block):
                return False

            # check if a transaction in a block is in the invalid chain list
            if self.check_for_invalid_tran(block):
                return False

            last_block = block
            current_index += 1
        return True

    def verify_signature(self, block):
        """
        Verifies the origin of the miner of the block

        :param block: <Block>
        :return: <bool> True if signature is verified, False if not.
        """
        ASN_pkey = None
        asn_nodes_mutex.acquire()
        for asn in ASN_nodes:  # find miner's public key
            if block.miner == asn[2]:
                ASN_pkey = asn[-1]
                break
        asn_nodes_mutex.release()

        if ASN_pkey is not None:
            block_hash = block.calculate_hash()
            return ASN_pkey.verify(block_hash.encode(), block.signature)
        else:
            return False

    def check_for_invalid_tran(self, block):
        """

        :param block: <Block>
        :return: <bool> True if the txid is of an invalid transaction, False if not.
        """
        for i in range(len(block.transactions)):
            transaction = block.transactions[i]['trans']

            if transaction['txid'] in invalid_transactions:
                return True
        return False

    def resolve_conflicts(self):
        """
        This is our Consensus Algorithm, it resolves conflicts
        by replacing our chain with the longest one in the network.

        :return: <bool> True if our chain was replaced, False if not
        """
        new_chain = None

        # We are looking for chains longer than ours
        mutex.acquire()
        neighbors = self.nodes
        max_length = len(self.chain)
        mutex.release()

        for node in neighbors:
            try:
                response = requests.get('{}/chain'.format(node[0]))  # possible deadlock here
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
        if new_chain is not None:
            mutex.acquire()
            self.chain = new_chain
            self.txid_to_block_update()
            self.state_update()
            self.check_before_mining = True
            mutex.release()
            return True
        else:
            return False

    def dict_to_block_chain(self, chain):
        """
        Converts a chain of dictionaries that was received from a node
        to a chain of Block objects.

        :param chain: <list> A chain of dictionaries
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
            miner = block['miner']
            signature = block['signature']

            new_block = Block(index, timestamp, transactions, previousHash)
            new_block.hash = hash
            new_block.nonce = nonce
            new_block.miner = miner
            new_block.signature = signature

            bc.append(new_block)
        return bc

    def register_node(self, address, ASN):
        """
        Add a new node to the list of nodes in the blockchain network.
        Also updates the ASN Nodes list.

        :param address: <str> Address of node. E.g., 'http://192.168.0.5:5000'
        :param ASN: <str> AS number of the node
        :return: None
        """
        parsed_url = urlparse(address)
        bc_nodes_mutex.acquire()
        self.nodes.add((parsed_url.scheme + "://" + parsed_url.netloc, ASN))
        bc_nodes_mutex.release()

        ip_port_list = parsed_url.netloc.split(":")
        ip_addr = ip_port_list[0]
        port = int(ip_port_list[1])

        found_it = 0
        asn_nodes_mutex.acquire()
        for asn in ASN_nodes:
            if ip_addr in asn and port == asn[1]:
                found_it = 1
                break
        asn_nodes_mutex.release()

        if not found_it:
            ASN_nodes.append([ip_addr, port, ASN, None])

    def broadcast_transaction(self, transaction):
        """
        Broadcast a newly created transaction to the rest of the network.

        :param transaction: : <Transaction>
        """
        transaction_dict = transaction.__dict__
        transaction_type = transaction_dict['type']
        transaction_data = json.dumps(transaction_dict)
        headers = {
            "Content-Type": "application/json"
        }
        print("Broadcasting the transaction to the rest of the network...")

        bc_nodes_mutex.acquire()
        neighbors = self.nodes
        for node in neighbors:
            try:
                if transaction_type == "Assign":
                    requests.post('{}/transactions/assign/incoming'.format(node[0]), data=transaction_data,
                                  headers=headers)
                elif transaction_type == "Revoke":
                    requests.post('{}/transactions/revoke/incoming'.format(node[0]), data=transaction_data,
                                  headers=headers)
                elif transaction_type == "Update":
                    requests.post('{}/transactions/update/incoming'.format(node[0]), data=transaction_data,
                                  headers=headers)
                elif transaction_type == "BGP Announce":
                    requests.post('{}/transactions/bgp_announce/incoming'.format(node[0]),
                                  data=transaction_data, headers=headers)
                elif transaction_type == "BGP Withdraw":
                    requests.post('{}/transactions/bgp_withdraw/incoming'.format(node[0]),
                                  data=transaction_data, headers=headers)
            except:
                print("Could not contact node {}. Moving on...".format(node[0]))
                continue
        bc_nodes_mutex.release()

    def txid_to_block_update(self):
        """
        Updates the txid_to_block dictionary after the chain has been replaced
        """
        for block in self.chain:
            index = block.index
            for i in range(len(block.transactions)):
                if index > 0:
                    txid = block.transactions[i]['trans']['txid']
                    txid_to_block[txid] = index

    def state_update(self):
        """
        Updates the state dictionary after the chain has been replaced
        """
        for block in self.chain:  # go through every block from the beginning
            if block.index > 0:
                for i in range(len(block.transactions)):
                    transaction = block.transactions[i]['trans']

                    if transaction['type'] == "Assign":
                        self.update_assign(transaction)
                        if transaction['txid'] in my_assignments:
                            self.check_revoke(transaction)

                    elif transaction['type'] == "Revoke":
                        self.update_revoke(transaction)

                    elif transaction['type'] == "Update":
                        self.update_update(transaction)

                    elif transaction['type'] == "BGP Announce":
                        self.update_bgp_announce(transaction)

                    elif transaction['type'] == "BGP Withdraw":
                        self.update_bgp_withdraw(transaction)

    def update_assign(self, transaction):
        """
        Updates the state for an Assign transaction

        :param transaction: <dict> An assign transaction
        """
        prefix = transaction['input'][0]
        as_source = transaction['input'][1]
        asn_list = transaction['input'][2]
        ld = transaction['input'][4]
        tt = transaction['input'][5]
        last_assign = transaction['input'][-1]

        found = 0
        for asn in asn_list:
            for i in range(len(state[prefix])):
                if asn in state[prefix][i]:
                    found = 1
                    break
            if found == 0:
                state[prefix].append((asn, ld, tt, last_assign))

        for i in range(len(state[prefix])):
            if as_source == state[prefix][i][0]:
                state[prefix].pop(i)
                break  # the as_source has been removed from the state dict.

        # also reject the previous topo for this prefix and start a new one.
        topo_mutex.acquire()
        topo = AS_topo[prefix]
        self.clear_topology(topo, prefix, as_source)

        for AS in asn_list:
            topo.add_edge(AS, prefix)
        topo_mutex.release()

    def update_revoke(self, transaction):
        """
        Updates the state for a Revoke transaction

        :param transaction: <dict> A revoke transaction
        """
        as_source = transaction['input'][0]
        assign_tran_id = transaction['input'][1]
        ld = transaction['output'][0][2]
        tt = transaction['output'][0][-1]
        assign_tran = self.find_by_txid(assign_tran_id)

        if assign_tran is not None:
            tran = assign_tran['trans']
            prefix = tran['input'][0]
            as_dest_list = tran['input'][2]
            last_assign = tran['input'][-1]

            for asn in as_dest_list:
                for i in range(len(state[prefix])):
                    if asn == state[prefix][i][0]:
                        state[prefix].pop(i)  # remove the others
                        break  # found it!
            found = 0
            for i in range(len(state[prefix])):
                if as_source in state[prefix][i]:
                    state[prefix].pop(i)
                    state[prefix].append((as_source, ld, tt, last_assign))  # ?
                    found = 1
                    break
            if found == 0:
                state[prefix].append((as_source, ld, tt, last_assign))  # the one that did the revocation

            # also restore the topology of this prefix.
            topo_mutex.acquire()
            topo = AS_topo[prefix]

            for AS in as_dest_list:
                self.clear_topology(topo, prefix, AS)  # remove the ASes that no longer own the prefix.

            topo.add_edge(as_source, prefix)  # add the AS that did the revocation and now owns the prefix.
            topo_mutex.release()

    def update_update(self, transaction):
        """
        Updates the state for an Update transaction

        :param transaction: <dict> An update transaction
        """
        assign_id = transaction['input'][1]
        new_lease = transaction['input'][2]
        assign_tran = self.find_by_txid(assign_id)

        if assign_tran is not None:

            tran = assign_tran['trans']
            prefix = tran['input'][0]
            as_dest_list = tran['input'][2]

            for asn in as_dest_list:
                for i in range(len(state[prefix])):
                    if asn == state[prefix][i][0]:
                        last_assign = state[prefix][i][-1]
                        tt = state[prefix][i][-2]
                        state[prefix].pop(i)  # remove the current entry
                        state[prefix].append((asn, new_lease, tt, last_assign))  # update the entry with the new lease
                        break

    def check_revoke(self, transaction):
        """
        Checks occasionally if a revocation of a prefix needs to happen
        It creates and broadcasts a new Revoke transaction for this prefix if true.
        """
        from Transaction import RevokeTransaction

        as_source = transaction['input'][1]
        txid = transaction['txid']

        new_revoke = RevokeTransaction(as_source, txid, time())

        trans_hash = new_revoke.calculate_hash()
        signature = node_key.sign(trans_hash.encode(), '')

        new_revoke.sign(signature)

        new_revoke_dict = new_revoke.return_transaction()

        if new_revoke_dict is not None:
            pending_transactions.append(new_revoke_dict)
            self.broadcast_transaction(new_revoke)
            my_assignments.remove(txid)

    def update_bgp_announce(self, transaction):
        """
        Updates the topology of a prefix given in an Announce transaction.

        :param transaction: <dict> A BGP Announce transaction
        """
        prefix = transaction['input'][0]
        sub_paths = transaction['output']
        topo_mutex.acquire()
        topo = AS_topo[prefix]

        for path in sub_paths:
            if path[1] == '0':
                topo.add_edges_from([(path[2], prefix), (path[3], path[2])])  # don't add the 0 node in the graph
            else:
                topo.add_edges_from([(path[2], path[1]), (path[3], path[2])])
        topo_mutex.release()

    def update_bgp_withdraw(self, transaction):
        """
        Updates the topology of a prefix after a Withdraw transaction.

        :param transaction: <dict> A BGP Withdraw transaction.
        """
        redundant_nodes = set()
        prefix = transaction['input'][0]
        as_source = transaction['input'][1]
        topo_mutex.acquire()
        topo = AS_topo[prefix]
        # remove the edges between the withdrawing node and its predecessors.
        pred_edges = []
        for pred in topo.predecessors(as_source):
            pred_edges.append((pred, as_source))
        topo.remove_edges_from(pred_edges)
        # find all the other nodes that cannot reach the prefix.
        for node in topo.nodes:
            paths = nx.all_simple_paths(topo, node, prefix)
            if len(list(paths)) == 0 and node != prefix:
                redundant_nodes.add(node)  # these nodes cannot reach the prefix.
        topo.remove_nodes_from(redundant_nodes)
        topo_mutex.release()

    def clear_topology(self, topo, prefix, source):
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

    def find_by_txid(self, txid):
        """
        Finds a transaction based on a txid.

        :return: <dict> the requested transaction, None if a transaction is not found.
        """
        try:
            index = txid_to_block[txid]
            block = self.chain[index]
        except KeyError:
            print("Txid not found")
            return None

        for i in range(len(block.transactions)):
            if txid == block.transactions[i]['trans']['txid']:
                requested_tran = block.transactions[i]
                return requested_tran
        return None


blockchain = Blockchain()
