How to run:

	python3 start_network.py -- This starts the network. Runs the script on all the nodes that are in the bgp_network.csv file.

then on a new terminal run one of the scripts below to make a new transaction,

	python3 assign.py -- to make an assign transaction.

	python3 update.py -- to make an update transaction. open the file and enter a valid assign transaction id (it can be found in the blockchain!)

	python3 revoke.py -- to make a revoke transaction. open the file and enter a valid assign transaction id -- (but the lease has propably not expired yet so the transaction will not be added to the chain)

	python3 bgp_announce.py -- to make a bgp announce transaction. Open the file and edit it accordingly. Put a '0' in the as_source_list if the AS advertising the prefix also owns it.


To mine a new block, run python3 parallel_mine.py and enter the number of miners. 
Or you could mine manually by making a request to localhost:[port*]/mine
[*ports: 5000-5004]

Finally,
killall python3.