import requests, threading


def mine(i):
    print(threading.current_thread().getName() + ":  Node " + str(i) + " started")
    requests.get("http://localhost:" + str(i) + "/mine")
    print(threading.current_thread().getName() + ": Node " + str(i) + " finished")


if __name__ == "__main__":
    print("Number of miners: ", end="")
    t = input()
    for i in range(5000, 5000+int(t)):
        t = threading.Thread(target=mine, args=(i,))
        t.start()