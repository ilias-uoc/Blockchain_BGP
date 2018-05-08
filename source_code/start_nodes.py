import shlex, subprocess, requests
from time import sleep

"""
For instantiating multiple nodes in parallel
"""

command = "python3 main.py -p"
args = shlex.split(command)

print("Please enter how many BC nodes you'd like to start (current max = 5): ", end="")
t = input()

for i in range(5000, 5000+int(t)):
    args.append(str(i))
    process = subprocess.Popen(args)
    args.pop()

sleep(2)

for i in range(5000, 5000+int(t)):
    try:
        requests.get("http://localhost:" + str(i) + "/command")
    except:
        print("Could not contact node {}.".format("http://localhost:"+str(i)))