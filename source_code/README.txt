How to run:

1) python3 start_nodes.py  -- and choose the number of nodes

on a new terminal:
2) python3 assign.py   -- To make an assign transaction

3) python3 parallel_mine.py -- and choose the number of miners


optional:

python3 update.py -- to make an update transaction. open the file and enter a valid assign txid
python3 revoke.py -- to make a revoke transaction. open the file and enter a valid assign txid -- (but the lease has propably not expired yet so the transaction will not be added to the chain)


4) killall python3 -- to stop all the nodes