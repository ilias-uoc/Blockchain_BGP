import requests
import json

# A basic example..

#r5000 = requests.get("http://localhost:5000/command")
#r5001 = requests.get("http://localhost:5001/command")
#r5002 = requests.get("http://localhost:5002/command")
#r5003 = requests.get("http://localhost:5003/command")
#r5004 = requests.get("http://localhost:5004/command")

headers = {
    "Content-Type": "application/json"
}

# Node 5000 makes a new valid transaction
trans_5000 = {
    "prefix": '1.0.0.0/24',
    "as_source": '13335',
    "as_dest": ['133948', '9737'],
    "source_lease": 1000,
    "leaseDuration": 10,
    "transferTag": False,
    "last_assign": -1
}
trans_5000_data = json.dumps(trans_5000)

response = requests.post("http://localhost:5000/transactions/assign/new", data=trans_5000_data, headers=headers)
    
trans_5000_1 = {
    "prefix": '1.0.0.0/24',
    "as_source": '13335',
    "as_dest": ['1414', '1010'],
    "source_lease": 1000,
    "leaseDuration": 20,
    "transferTag": False,
    "last_assign": -1
}

trans_5000_1_data = json.dumps(trans_5000_1) 

response = requests.post("http://localhost:5000/transactions/assign/new", data=trans_5000_1_data, headers=headers)

# Node 5001 mines the transaction into a new block
res = requests.get("http://localhost:5001/mine")

# different chains
#chain5000 = requests.get("http://localhost:5000/chain")
#chain5001 = requests.get("http://localhost:5001/chain")

#print(chain5000.json()['chain'])
print("---------------------------------------")
#print(chain5001.json()['chain'])

'''Resolve conflicts

resolve = requests.get("http://localhost:5000/resolve")
print(resolve.text)

Chains should be the same now

chain5000 = requests.get("http://localhost:5000/chain")
chain5001 = requests.get("http://localhost:5001/chain")

print(json.dumps(chain5000.json()['chain'], indent=2, sort_keys=True))
print("---------------------------------------")
print(chain5001.json()['chain'])'''
