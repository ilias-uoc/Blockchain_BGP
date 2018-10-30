import requests
import json

# A basic example..

headers = {
    "Content-Type": "application/json"
}

# Node 5001 makes a new valid transaction
assign_5001 = {
    "prefix": '1.3.33.0/24',
    "as_source": '133741',
    "as_dest": ['133948', '13335'],
    "source_lease": 1000,
    "leaseDuration": 85,
    "transferTag": False,
    "last_assign": -1
}
assign_5001_data = json.dumps(assign_5001)

response = requests.post("http://localhost:5001/transactions/assign/new", data=assign_5001_data, headers=headers)
