import csv, argparse
import shlex, subprocess, requests
import socket
from time import sleep
from contextlib import closing


nodes = set()


def extract_nodes(filename):
    """
    Adds all the nodes from the bgpstream file to a new set.
    """
    f = open(filename, 'r')

    try:
        reader = csv.reader(f, delimiter='|')
        for row in reader:
            prefix, origin_as, as_path, project, collector, type, timestamp, peer_asn = row
            origin_asns = origin_as.split(",")
            path_asns = as_path.split(",")

            for AS in origin_asns:
                nodes.add(AS)

            for AS in path_asns:
                nodes.add(AS)
    finally:
        f.close()


def find_free_port():
    """
    Finds and returns a free port.
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def dump_nodes():
    """
    Creates a new csv file named new_nodes.csv which contains the IP, Port and ASN of a node.
    """
    with open("new_nodes.csv", 'w') as f:
        csv_writer = csv.writer(f)
        for node in nodes:
            port = find_free_port()
            csv_writer.writerow(['localhost', port, node])


def run_nodes():
    """
    Runs the main script on the new nodes.
    """
    command = "python3 main.py -p"
    args = shlex.split(command)

    f = open('new_nodes.csv', 'r')

    try:
        reader = csv.reader(f)
        for row in reader:
            ip, port, asn = row
            args.append(port)
            args.append('-a')
            args.append(asn)
            args.append('-i')
            args.append(ip)
            process = subprocess.Popen(args)
            for i in range(5):
                args.pop()  # delete the above 5 args for the next iteration.

        sleep(30)  # wait for all the processes to start

        f.seek(0, 0)

        reader = csv.reader(f)

        for row in reader:
            ip, port, asn = row
            try:
                requests.get("http://" + ip + ":" + port + "/")
            except:
                print("Could not contact node")
    finally:
        f.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', default='../bgpstream/forth_25_7_2018_9_to_10_am/P_139.91.0.0+16-S' +
                                                '_1532509200-E_1532512800.csv',
                        type=str, help='file with bgpstream data')
    args = parser.parse_args()
    extract_nodes(args.file)
    dump_nodes()
    run_nodes()


if __name__ == '__main__':
    main()
