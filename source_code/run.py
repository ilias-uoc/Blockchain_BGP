import requests
import json

# A basic example..

r5000 = requests.get("http://localhost:5000/command")
r5001 = requests.get("http://localhost:5001/command")

headers = {
    "Content-Type": "application/json"
}

# Node 5000 makes a new valid transaction
trans_5000 = {

    "prefix": '1.0.0.0/24',
    "as_source": '13335',
    "as_dest": ['133948', '9737'],
    "leaseDuration": 10,
    "transferTag": False,
    "last_assign": -1
}
trans_5000_data = json.dumps(trans_5000)

response = requests.post("http://localhost:5000/transactions/new", data=trans_5000_data, headers=headers)

# Node 5001 mines the transaction into a new block
res = requests.get("http://localhost:5001/mine")

# different chains
chain5000 = requests.get("http://localhost:5000/chain")
chain5001 = requests.get("http://localhost:5001/chain")

print(chain5000.json()['chain'])
print("---------------------------------------")
print(chain5001.json()['chain'])
# Resolve conflicts

resolve = requests.get("http://localhost:5000/resolve")
print(resolve.text)

# Chains should be the same now

chain5000 = requests.get("http://localhost:5000/chain")
chain5001 = requests.get("http://localhost:5001/chain")

print(chain5000.json()['chain'])
print("---------------------------------------")
print(chain5001.json()['chain'])