![CI status](https://img.shields.io/badge/build-passing-blue.svg) ![Python Version](https://img.shields.io/badge/Python-3-blue.svg)
# Blockchain_BGP
Design, implementation and evaluation of a blockchain-based prototype framework 
for the management of BGP advertisements.

## Installation

### Requirements
* Python 3

### Prerequisite Python packages
* **TODO**

## How to run
* *Starting the network*
	`$ python3 start_network.py`
	Runs the main script on all the initial nodes of the 
	network that are in the bgp_network.csv file.

* *Adding new nodes to the network*
	`$ python3 new_nodes.py`
	This script runs the main script on the new nodes that
	are found in the file /bgpstream/forth_25_7_2018_9_to_10_am/P_139.91.0.0+16-S_1532509200-E_1532512800.csv
	Also creates the file new_nodes.csv with the (IP, PORT, ASN) info for every node.

* *Making transactions*
    To make an IP assign transaction:
    `$ python3 assign.py`
    Open the file and edit accordingly.

    To make an IP Update transaction.
    Open the file and enter a valid assign transaction id 
    (it can be found in the blockchain!)
    `$python3 update.py`

    To make an IP revoke transaction after the lease has expired. 
    Open the file and enter a valid assign transaction id.
    `$python3 revoke.py`

    To make BGP Announce transactions:
    `$python3 bgp_announce.py`
    This script reads the  file /bgpstream/forth_25_7_2018_9_to_10_am/P_139.91.0.0+16-S_1532509200-E_1532512800.csv 
    and makes the announcements. You need to edit the port for node 8522. 
    This info can be found in the file *new_nodes.csv* created by the script *new_nodes.py* earlier.

* *Mining a new block*
    To mine a new block run:
    `$ python3 parallel_mine.py`
    and enter the number of miners.

* *Finally*
    `$ killall python3`

### A simple example
* **TODO**

## License
[GNU GPLv3](https://choosealicense.com/licenses/gpl-3.0/)

## Acknowledgments