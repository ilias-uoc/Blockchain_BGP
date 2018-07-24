import shlex, subprocess, requests
from time import sleep
import csv

"""
Inits the network from the file
"""

command = "python3 main.py -p"
args = shlex.split(command)

f = open('bgp_network.csv', 'r')

try:
    reader = csv.reader(f)
    for row in reader:
        if reader.line_num != 1:
            ip, port, asn = row
            args.append(port)
            args.append('-a')
            args.append(asn)
            args.append('-i')
            args.append(ip)
            process = subprocess.Popen(args)
            for i in range(5):
                args.pop()

    sleep(2)

    f.seek(0, 0)

    reader = csv.reader(f)

    for row in reader:
        if reader.line_num != 1:
            ip, port, asn = row
            try:
                requests.get("http://" + ip + ":" + port + "/")
            except:
                print("Could not contact node")
finally:
    f.close()