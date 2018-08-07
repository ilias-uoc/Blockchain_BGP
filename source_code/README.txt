How to run:

	python3 start_network.py -- This starts the network. Runs the script on all the nodes that are in the bgp_network.csv file.

on a new terminal:

	python3 new_nodes.py -- This script runs the main script on all the ASNs that are found in the file /bgpstream/forth_25_7_2018_9_to_10_am/P_139.91.0.0+16-S_1532509200-E_1532512800.csv. Also creates the file new_nodes.csv with the (IP, PORT, ASN) info for every node.

then on a new terminal run one of the scripts below to make a new transaction,

	python3 assign.py -- to make an assign transaction.

	python3 update.py -- to make an update transaction. open the file and enter a valid assign transaction id (it can be found in the blockchain!)

	python3 revoke.py -- to make a revoke transaction. open the file and enter a valid assign transaction id -- (but the lease has propably not expired yet so the transaction will not be added to the chain)

	python3 bgp_announce.py -- to make bgp announce transactions. This script reads this file /bgpstream/forth_25_7_2018_9_to_10_am/P_139.91.0.0+16-S_1532509200-E_1532512800.csv and makes the announcements. You need to edit the port for node 8522. This info can be found in the file new_nodes.csv created by the script new_nodes.py earlier.


To mine a new block, run python3 parallel_mine.py and enter the number of miners. 

Finally,
killall python3.