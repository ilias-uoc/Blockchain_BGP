import hashlib
from time import time
from config import ASN_nodes, txid_to_block, state
from Blockchain import blockchain

"""
The IP Allocation Transaction module. Includes all the functionality for the IP allocation transactions
"""


class IPAllocationTransaction():
    """
    IPTransaction is the superclass of all the IP Address Allocation type of transactions
    """
    def __init__(self, as_source, txid, time):
        self.as_source = as_source
        self.txid = txid
        self.signature = None
        self.time = time
        self.type = "IPAllocationSuperDuperClass"
        self.__input = []
        self.__output = []

    def sign(self, signature):
        self.signature = signature

    def verify_signature(self, trans_hash):
        """
        Verifies the origin of the transaction using the public key of the ASN that made this transaction

        :return: <bool> True if signature is verified, False if not.
        """
        ASN_pkey = None
        for asn in ASN_nodes:  # find ASN public key
            if self.as_source == asn[2]:
                ASN_pkey = asn[-1]
                break

        if ASN_pkey is not None:
            if ASN_pkey.verify(trans_hash.encode(), self.signature):
                return True
            else:
                return False
        else:
            return False

    def calculate_hash(self):
        trans_str = '{}{}{}'.format(self.as_source, self.txid, self.time).encode()
        trans_hash = hashlib.sha256(trans_str).hexdigest()
        return trans_hash

    def get_input(self):
        """
        Getter method for input

        :return: <list> The input of this transaction
        """
        return self.__input

    def set_input(self, input):
        """
        Setter method for input
        """
        self.__input.extend(input)

    def get_output(self):
        """
        Getter method for output

        :return: <list> The output of this transaction
        """
        return self.__output

    def set_output(self, output):
        """
        Setter method for output
        """
        self.__output.append((output))

    def validate_transaction(self):
        """
        Is overridden in all the sub classes.
        """
        pass

    def return_transaction(self):
        """
        Returns a valid transaction to be added to a block in the blockchain

        :return: <dict> A valid transaction, or None if the transaction is not valid.
        """
        if self.validate_transaction():

            txid_hash = self.calculate_hash()

            transaction = {
                'trans': {
                    'type': self.type,
                    'input': self.get_input(),
                    'output': self.get_output(),
                    'timestamp': self.time,
                    'txid': txid_hash
                },
                'signature': self.signature
            }
            return transaction
        else:
            return None


class AssignTransaction(IPAllocationTransaction):
    def __init__(self, prefix, as_source, as_dest, source_lease, leaseDuration, transferTag, time, txid):
        super().__init__(as_source, txid, time)
        self.prefix = prefix
        self.as_dest = as_dest
        self.leaseDuration = leaseDuration
        self.transferTag = transferTag  # can the ASes in the AS destination list further transfer the prefix?
        self.last_assign = self.txid
        self.source_lease = source_lease
        self.type = "Assign"

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
            input = [self.prefix, self.as_source, self.as_dest, self.source_lease, self.leaseDuration, self.transferTag,
                     self.last_assign]
            self.set_input(input)

            for AS in self.as_dest:
                output = (self.prefix, AS, self.leaseDuration, self.transferTag)
                self.set_output(output)
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
        if self.verify_signature(self.calculate_hash()) and self.check_state():
            return True
        else:
            return False

    def check_state(self):
        """
        Checks whether the state of the prefix agrees with the transaction made or not

        :return: <bool> True if verified, False if not.
        """
        for tup in state[self.prefix]:
            if self.as_source == tup[0] and \
                    self.last_assign == tup[-1] and \
                    tup[1] >= self.leaseDuration and \
                    tup[1] == self.source_lease and \
                    tup[2] is True:
                return True
        return False


class RevokeTransaction(IPAllocationTransaction):
    def __init__(self, as_source, txid, time):
        super().__init__(as_source, txid, time)
        self.assign_tran_id = self.txid
        self.assign_tran = self.get_assign_tran()
        self.type = "Revoke"

    def validate_transaction(self):
        """
        Validates the transaction

        :return: <bool> True if transaction is valid, False if not.
        """
        if self.verify_signature(self.calculate_hash()) and self.lease_expired() and self.check_state():

            prefix = self.assign_tran['trans']['input'][0]
            new_leaseDuration = self.calculate_new_lease()

            input = [self.as_source, self.assign_tran_id]
            self.set_input(input)

            output = (prefix, self.as_source, new_leaseDuration, True)  # the as source can always transfer the prefix
            self.set_output(output)

            return True
        else:
            return False

    def lease_expired(self):
        """
        Checks if the lease has expired for the Assign transaction given

        :return: <bool> True if the lease is expired, False if not.
        """
        if self.assign_tran is not None:
            lease = self.assign_tran['trans']['input'][4]
            timestamp = self.assign_tran['trans']['timestamp']

            if self.time >= timestamp + 2629743.83 * lease:  # 1 month = 2629743.83 secs
                return True

        return False

    def get_assign_tran(self):
        """
        Finds the assign transaction from the blockchain with the txid that was given
        when creating this Revoke transaction

        :return: <dict> The Assign transaction if found, None if not.
        """
        if self.assign_tran_id in txid_to_block.keys():
            index = txid_to_block[self.assign_tran_id]
            block = blockchain.chain[index]
            for i in range(len(block.transactions)):
                if block.transactions[i]['trans']['type'] == "Assign":
                    if self.assign_tran_id == block.transactions[i]['trans']['txid']:
                        return block.transactions[i]
        return None

    def check_state(self):
        """
        Checks whether the source that made this transaction can be found in the Assign transaction
        and whether the destination ASes found in this assign transaction own this prefix currently
        (all the ASes that own the prefix right now should be in the state dictionary)

        :return: <bool> True if correct, False if not.
        """
        if self.assign_tran is not None:
            prefix = self.assign_tran['trans']['input'][0]
            as_source = self.assign_tran['trans']['input'][1]
            as_dest = self.assign_tran['trans']['input'][2]

            if self.as_source == as_source:
                # find if all ASes in the transaction are currently the owners of the prefix(from state)
                for ASN in as_dest:
                    found = 0
                    for tuple in state[prefix]:
                        if ASN in tuple:
                            found = 1
                            break  # found one ASN keep searching for the rest
                    if found == 0:
                        return False  # an ASN was not found so the transaction should not be valid
                return True  # found every ASN in as_dest in the state
        return False

    def calculate_new_lease(self):
        """
        Calculates the new lease for the AS that did the revocation

        :return: <int> The new lease period (in months)
        """
        old_lease = self.assign_tran['trans']['input'][4]
        my_prev_lease = self.assign_tran['trans']['input'][3]
        my_new_lease = my_prev_lease - old_lease
        return my_new_lease


class UpdateTransaction(IPAllocationTransaction):
    def __init__(self, as_source, txid, time, new_lease):
        super().__init__(as_source, txid, time)
        self.new_lease = new_lease
        self.assign_tran_id = txid
        self.assign_tran = self.get_assign_tran()
        self.type = "Update"

    def validate_transaction(self):
        if self.verify_signature(self.calculate_hash()) and not self.lease_expired() and self.check_state():
            prefix = self.assign_tran['trans']['input'][0]
            as_dest = self.assign_tran['trans']['input'][2]
            transfer_tag = self.assign_tran['trans']['input'][5]

            input = [self.as_source, self.assign_tran_id, self.new_lease]
            self.set_input(input)

            for AS in as_dest:
                output = (prefix, AS, self.new_lease, transfer_tag)
                self.set_output(output)

            return True
        else:
            return False

    def check_state(self):
        """
        Checks whether the source that made this transaction can be found in the Assign transaction
        and whether the destination ASes found in this assign transaction own this prefix currently
        (all the ASes that own the prefix right now should be in the state dictionary)

        Also checks whether the new lease duration is less than the original that AS source has

        :return: <bool> True if correct, False if not.
        """
        if self.assign_tran is not None:
            prefix = self.assign_tran['trans']['input'][0]
            as_source = self.assign_tran['trans']['input'][1]
            as_dest = self.assign_tran['trans']['input'][2]
            my_prev_lease = self.assign_tran['trans']['input'][3]
            current_lease = 2000  # doesn't matter

            if self.as_source == as_source:
                # find if all ASes in the transaction are currently the owners of the prefix(from state)
                for ASN in as_dest:
                    found = 0
                    for tuple in state[prefix]:
                        if ASN in tuple:
                            found = 1
                            current_lease = tuple[1]
                            break  # found one ASN keep searching for the rest
                    if found == 0:
                        return False  # an ASN was not found so the transaction should not be valid

            if current_lease >= self.new_lease or self.new_lease > my_prev_lease:
                return False

            return True

        return False

    def lease_expired(self):
        """
        Checks if the lease has expired for the Assign transaction given

        :return: <bool> True if the lease is expired, False if not.
        """
        if self.assign_tran is not None:
            lease = self.assign_tran['trans']['input'][4]
            timestamp = self.assign_tran['trans']['timestamp']

            if self.time >= timestamp + 2629743.83 * lease:  # 1 month = 2629743.83 secs
                return True

        return False

    def get_assign_tran(self):
        """
        Finds the assign transaction from the blockchain with the txid that was given
        when creating this Update transaction

        :return: <dict> The Assign transaction if found, None if not.
        """
        if self.assign_tran_id in txid_to_block.keys():
            index = txid_to_block[self.assign_tran_id]
            block = blockchain.chain[index]
            for i in range(len(block.transactions)):
                if block.transactions[i]['trans']['type'] == "Assign":
                    if self.assign_tran_id == block.transactions[i]['trans']['txid']:
                        return block.transactions[i]
        return None