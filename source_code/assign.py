import requests
import json

# A basic example..

headers = {
    "Content-Type": "application/json"
}

# Node 5000 makes a new valid transaction
assign_5000 = {
    "prefix": '1.0.0.0/24',
    "as_source": '13335',
    "as_dest": ['133948', '9737'],
    "source_lease": 1000,
    "leaseDuration": 85,
    "transferTag": False,
    "last_assign": -1
}
assign_5000_data = json.dumps(assign_5000)

response = requests.post("http://localhost:5000/transactions/assign/new", data=assign_5000_data, headers=headers)
