import hashlib
import copy
import networkx as nx
from config import ASN_nodes, txid_to_block, state, AS_topo, topo_mutex


class BGP_Transaction():
    """
    BGP_Transaction is the superclass of all the types of BGP transactions.
    """
    def __init__(self, prefix, bgp_timestamp, as_source, time, project, collector, asn_peer):
        self.as_source = as_source
        self.prefix = prefix
        self.bgp_timestamp = bgp_timestamp
        self.time = time
        self.project = project
        self.collector = collector
        self.asn_peer = asn_peer
        self.type = "BGPSuperClass"
        self.signature = None
        self.__input = []
        self.__output = []

    def sign(self, signature):
        """
        Sets the signature of the transaction.

        :param signature: <tuple> The signature that was calculated for this transaction.
        """
        self.signature = signature

    def verify_signature(self, trans_hash):
        """
        Verifies the origin of the transaction using the public key of the ASN that made this transaction.

        :param trans_hash: <str> The hash of the transaction that was used to sign it.
        :return: <bool> True if the signature could be verified, False otherwise.
        """
        as_source_public_key = self.find_asn_public_key()

        if as_source_public_key is not None:
            return as_source_public_key.verify(trans_hash.encode(), self.signature)
        else:
            return False

    def find_asn_public_key(self):
        """
        Finds the public key of the AS node that made this transaction.

        :return: <RSA key> The public key of the node, or None if the key is not found.
        """
        ASN_pkey = None
        for asn in ASN_nodes:  # find ASN public key
            if self.as_source == asn[2]:
                ASN_pkey = asn[-1]
                break
        return ASN_pkey

    def calculate_hash(self):
        """
        Calculates the hash of the transaction.

        :return: <str> The SHA-256 hash of this transaction.
        """
        trans_str = '{}{}{}'.format(self.as_source, self.prefix, self.time).encode()
        trans_hash = hashlib.sha256(trans_str).hexdigest()
        return trans_hash

    def get_input(self):
        """
        Getter method for input.

        :return: <list> The input of this transaction.
        """
        return self.__input

    def set_input(self, input):
        """
        Setter method for input.
        """
        self.__input.extend(input)

    def get_output(self):
        """
        Getter method for output.

        :return: <list> The output of this transaction.
        """
        return self.__output

    def set_output(self, output):
        """
        Setter method for output.
        """
        self.__output.append((output))

    def validate_transaction(self):
        """
        Should be overridden in all the subclasses.
        """
        pass

    def return_transaction(self):
        """
        Returns a valid transaction to be added to a block in the blockchain.

        :return: <dict> A valid transaction, or None if the transaction is not valid.
        """
        if self.validate_transaction():
            transaction = {
                'trans': {
                    'type': self.type,
                    'input': self.get_input(),
                    'output': self.get_output(),
                    'timestamp': self.time,
                    'txid': self.calculate_hash()
                },
                'signature': self.signature
            }
            return transaction
        else:
            return None


class BGP_Announce(BGP_Transaction):
    def __init__(self, prefix, bgp_timestamp, adv_AS, source_ASes, dest_ASes, time, project, collector, asn_peer):
        super().__init__(prefix, bgp_timestamp, adv_AS, time, project, collector, asn_peer)
        self.as_source_list = source_ASes
        self.as_dest_list = dest_ASes
        self.type = "BGP Announce"

    def validate_transaction(self):
        """
        Validates the transaction.

        :return: <bool> True if the transaction is valid, False otherwise.
        """
        if self.verify_signature(self.calculate_hash()) and self.check_origin() and not self.check_loops():
            input = [self.prefix, self.as_source, self.as_source_list, self.as_dest_list, self.project, self.collector,
                     self.bgp_timestamp, self.asn_peer]

            self.set_input(input)

            for AS_src in self.as_source_list:
                for AS_dst in self.as_dest_list:
                    output = (self.prefix, AS_src, self.as_source, AS_dst)
                    self.set_output(output)
            return True
        else:
            return False

    def check_origin(self):
        """
        Verifies the origin of this transaction, based on the topo of this prefix.

        :return: <Bool> True if the origin is verified. False otherwise.
        """
        topo_mutex.acquire()
        topo = AS_topo[self.prefix]
        topo_mutex.release()

        if len(self.as_source_list) == 0 or not self.check_network():
            return False

        if self.as_source_list[0] == '0' and len(self.as_source_list) == 1:
            return topo.has_edge(self.as_source, self.prefix)

        elif self.as_source_list[0] == '0' and len(self.as_source_list) > 1:
            direct = topo.has_edge(self.as_source, self.prefix)
            src_l = self.as_source_list[1:]
            src_l.append(self.prefix)
            successors = list(topo.successors(self.as_source))
            src_l.sort()
            successors.sort()
            return direct and src_l == successors

        else:
            src_l = self.as_source_list
            successors = list(topo.successors(self.as_source))
            src_l.sort()
            successors.sort()
            return src_l == successors

    def check_network(self):
        """
        Checks if all the ASNs in the source and dest are in the blockchain network.

        :return: <bool> True if they are in the network, False otherwise.
        """
        ASes = ['0']
        for i in range(len(ASN_nodes)):
            ASes.append(ASN_nodes[i][2])

        for AS in self.as_dest_list:
            if AS not in ASes:
                return False
            
        for AS in self.as_source_list:
            if AS not in ASes:
                return False

        return True

    def check_loops(self):
        """
        Checks if this transaction introduces loops in the topology of this prefix.

        :return: <bool> True if there are loops. False otherwise.
        """
        topo_mutex.acquire()
        old_topo = AS_topo[self.prefix]
        new_topo = copy.deepcopy(old_topo)
        topo_mutex.release()
        self.find_new_topo(new_topo)
        try:
            nx.find_cycle(new_topo, source=self.as_source, orientation='original')
            return True
        except nx.NetworkXNoCycle:
            return False

    def find_new_topo(self, topo):
        """
        Calculates how the topo for this prefix will be after this transaction, before it is approved.

        :param topo: <Digraph> A topology.
        """
        sub_paths = []
        for AS_src in self.as_source_list:
            for AS_dst in self.as_dest_list:
                path = (self.prefix, AS_src, self.as_source, AS_dst)
                sub_paths.append(path)

        for path in sub_paths:
            if path[1] == '0':
                topo.add_edges_from([(path[2], self.prefix), (path[3], path[2])])  # don't add the 0 node in the graph
            else:
                topo.add_edges_from([(path[2], path[1]), (path[3], path[2])])


class BGP_Withdraw(BGP_Transaction):
    pass