import requests, json

headers = {
    "Content-Type": "application/json"
}

revoke_5000 = {
    "as_source": '13335',
    "assign_tran": '--txid goes here--'
}
revoke_5000_data = json.dumps(revoke_5000)

res = requests.post("http://localhost:5000/transactions/revoke/new", data=revoke_5000_data, headers=headers)

res = requests.get("http://localhost:5001/mine")

res = requests.get("http://localhost:5001/print")

chain5001 = requests.get("http://localhost:5001/chain")

print(chain5001.json()['chain'])
