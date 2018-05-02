from parse_utils import get_as_prefs
from Crypto.PublicKey import RSA
from Crypto import Random

"""
The global variables and structures all other modules should be able to see
"""

state = {}  # state: {'prefix' : [ (AS1, lease duration(in months), transfer tag, txid), ... ,(ASN, lease duration(in months), transfer tag, txid) ] }
txid_to_block = {}  # {'txid' : block index}

ASN_nodes = []  # ASN nodes = [ [IP Address, Port, AS Number, ASN Public Key] ]
pending_transactions = []

as2pref, pref2as_pyt = get_as_prefs()


def init_nodes():
    host = 'localhost'
    port = 5000
    as_list = []
    for asn in as2pref.keys():
        as_list.append(asn)
    as_list.sort()

    for i in range(0, 5):
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
my_ASN = ''

init_nodes()
