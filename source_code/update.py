import requests, json

headers = {
    "Content-Type": "application/json"
}

update_5000 = {
    "as_source": '13335',
    "assign_tran": '--txid goes here--',
    "new_lease": 25
}
update_5000_data = json.dumps(update_5000)

res = requests.post("http://localhost:5000/transactions/update/new", data=update_5000_data, headers=headers)

res = requests.get("http://localhost:5001/mine")

res = requests.get("http://localhost:5001/print")

chain5001 = requests.get("http://localhost:5001/chain")

print(chain5001.json()['chain'])