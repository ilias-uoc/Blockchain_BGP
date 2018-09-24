from parse_utils import get_as_prefs
from Crypto.PublicKey import RSA
from Crypto import Random
import threading
import csv

"""
The global variables and structures all other modules should be able to see
"""

ASN_nodes = []  # ASN nodes = [ [IP Address, Port, ASN, ASN Public Key] ]

state = {}  # state: {'prefix' : [ (AS1, lease duration(in months), transfer tag, txid), ... ,
#                                  (ASN, lease duration(in months), transfer tag, txid) ] }

txid_to_block = {}  # {'txid' : block index}

my_assignments = set()  # a set of the txids of all the assign transactions a node has made

pending_transactions = []

as2pref, pref2as_pyt = get_as_prefs()

update_sum = {}  # { 'AS Number' : sum }
assign_sum = {}  # { 'AS Number' : sum }

bgp_txid_announced = {}  # { 'txid' : True/False }
as_to_announced_txids = {}  # { 'AS' : [txid1, txid2, ... , txidn] }

AS_topo = {}  # { 'prefix' : Graph for this prefix }

assigned_prefixes = set()
assign_txids = set()

mutex = threading.Lock()
pt_mutex = threading.Lock()
bgpa_mutex = threading.Lock()
topo_mutex = threading.Lock()


def init_nodes():
    """
    Reads the known ASes from the file and updates the ASN_nodes list.
    """
    f = open('bgp_network.csv', 'r')
    try:
        reader = csv.reader(f)
        for row in reader:
            if reader.line_num != 1:
                ip, port, asn = row
                ASN_nodes.append([ip, int(port), asn, None])
    finally:
        f.close()


def generate_keypair():
    """
    Generates a public-private key pair for the node that is running the script.
    """
    random_generator = Random.new().read
    key = RSA.generate(2048, random_generator)
    return key


node_key = generate_keypair()
init_nodes()

my_IP = ''
my_Port = ''
my_ASN = ''
