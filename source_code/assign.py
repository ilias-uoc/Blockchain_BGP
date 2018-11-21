import requests
import json

# A basic example..

headers = {
    "Content-Type": "application/json"
}

# Node 5001 makes a new valid transaction
assign_5001 = {
    "prefix": '139.91.0.0/16',
    "as_source": '8522',
    "as_dest": ['8522'],
    "source_lease": 1000,
    "leaseDuration": 1000,
    "transferTag": True,
    "last_assign": -1
}
assign_5001_data = json.dumps(assign_5001)

response = requests.post("http://localhost:64330/transactions/assign/new", data=assign_5001_data, headers=headers)
