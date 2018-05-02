import shlex, subprocess

"""
For instantiating multiple nodes in parallel
"""

command = "python3 main.py -p"
args = shlex.split(command)

for i in range(5000, 5002):
    args.append(str(i))
    process = subprocess.Popen(args)
    args.pop()
