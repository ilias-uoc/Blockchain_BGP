![Python Version](https://img.shields.io/badge/Python-3-blue.svg)
# Blockchain_BGP
Design, implementation and evaluation of a blockchain-based prototype framework
for the management of BGP advertisements.

## Installation

### Requirements
* Python 3

### Prerequisite Python packages
* networkx - `$ pip install networkx`
* requests - `$ pipenv install requests`
* flask - `$ pip install -U Flask`
* pytricia - `$ pip install pytricia`
* statsmodels - `$ pip install --upgrade --no-deps statsmodels`

## How to run
* *Starting the network*
    `$ python3 start_network.py`
    Starts the main script on all the bootstrap nodes of the
    network that are in the bgp_network.csv file.

* *Adding new nodes to the network*
    `$ python3 new_nodes.py -f path_to_bgpstream_file`
    This script runs the main script on the new nodes that
    are found in the bgpstream file passed as an argument. There is a default file if none is given.
    Also creates the file new_nodes.csv with the (IP, PORT, ASN) info for every new node.

* *Making transactions*
    To make an IP Assign transaction:
    `$ python3 assign.py`
    Open the file assign.py and edit accordingly.

    To make an IP Update transaction.
    Open the file update.py and enter a valid IP Assign transaction id.
    (this can be found in the blockchain!)
    `$ python3 update.py`

    To make an IP Revoke transaction after the lease has expired.
    Open the file revoke.py and enter a valid IP Assign transaction id.
    `$python3 revoke.py`

    To make BGP Announce transactions:
    `$python3 bgp_announce.py -f path_to_file`
    This script reads the bgpstream file given (or the default)
    and replays the announcements as BGP Announce transactions in the network.

* *Mining a new block*
    To mine a new block run:
    `$ python3 parallel_mine.py`
    and enter the number of miners you want.

* *Finally*
    `$ killall python3`
    To terminate all Python processes.

### A simple example
Recreating the tests of the thesis report.
You can use a desktop app for HTTP Requests e.g. Postman

First start the network by running `$ python3 start_network.py`

1. **IP Assign**
    AS 13335 assigns the prefix '1.0.0.0/24' to ASes 133741 and 133948 for 2 months.
    Request with the following parameters:

    * "prefix": '1.0.0.0/24',
    * "as_source": '13335',
    * "as_dest": ['133741', '133948'],
    * "source_lease": 1000,
    * "leaseDuration": 2,
    * "transferTag": True,
    * "last_assign": -1

    Run `$ python3 assign.py` after you've updated the file with the above values.
    Mine a new block that contains this transaction `$ python3 parallel_mine.py` and enter the amount of miners

2. **IP Update**
    AS 13335 updates the lease for the ASes 133741 and 133948 from the previous Assign transaction from 2 to 4 months
    Request with the following parameters:

    * "as_source": '13335',
    * "assign_tran": 'transaction id of the Assign transaction',
    * "new_lease": 4

    Run `$ python3 update.py` after you've updated the file with the above values.
    Mine a new block that contains this transaction `$ python3 parallel_mine.py` and enter the amount of miners

3. **IP Revoke**
    After 4 months AS 13335 can get the prefix back.
    Request with the following parameters:

    * "as_source": '13335',
    * "assign_tran": 'transaction id of the Assign transaction'

    Run `$ python3 revoke.py` after you've updated the file with the above values.
    Mine a new block that contains this transaction `$ python3 parallel_mine.py` and enter the amount of miners.

    *Keep in mind that there is an algorith that frequently checks for when a lease expires and automatically
    makes a new Revoke transaction.*

4. **BGP Announce**
    First run `$ python3 new_nodes.py`.
    After that, run `$ python3 bgp_announce.py` to replay the file P_139.91.0.0+16-S_1532509200-E_1532512800
    as BGP Announce transactions
    Mine a new block `$ python3 parallel_mine.py`

5. **BGP Withdraw**
    Make a HTTP POST Request to http://node_ip:node_port/transactions/bgp_withdraw/new with the parameters. You can
    find AS 8522 IP and port in the file new_nodes.csv.

    * "prefix": "139.91.0.0/16",
    * "as_source": "8522"

    Mine a new block `$ python3 parallel_mine.py`

## Misc. scripts


## License
