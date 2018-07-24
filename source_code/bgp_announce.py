import requests
import json

# A basic example..

headers = {
    "Content-Type": "application/json"
}

# Node 5000 makes a new valid transaction
announce = {
    "prefix": '1.3.33.0/24',
    "as_source": '133741',
    "as_source_list": ['0'],
    "as_dest_list": ['13335', '18046']
}
announce_data = json.dumps(announce)

response = requests.post("http://localhost:5001/transactions/bgp_announce/new", data=announce_data, headers=headers)