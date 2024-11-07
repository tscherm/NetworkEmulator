import argparse
import sys
import socket
from datetime import datetime, timedelta
import traceback

parser = argparse.ArgumentParser(description="Network Emulator")

parser.add_argument("-p", "--port", type=int, required=True, dest="port")
parser.add_argument("-f", "--filename", type=str, required=True, dest="fileName")
parser.add_argument("-q", "--queue_size", type=int, required=True, dest="queueSize")
parser.add_argument("-l", "--log", type=str, required=True, dest="logName")

args = parser.parse_args()

# check port numbers
if 2049 > args.port or args.port > 65536:
    print("Sender port out of range.")
    sys.exit()
if 2049 > args.port or args.port > 65536:
    print("Requester port out of range.")
    sys.exit()

# open port (to listen on only?)
hostname = socket.gethostname()
ipAddr = socket.gethostbyname(hostname)

reqAddr = (ipAddr, args.port)

try:
    recSoc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recSoc.bind(reqAddr)
    recSoc.settimeout(0)
except:
    print("An error occured binding the socket")
    print(traceback.format_exc())
    sys.exit()

# socket to send from (not the same one)
sendSoc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

priority1 = list()
p1Len = 0
priority2 = list()
p2Len = 0
priority3 = list()
p3Len = 0

# variable for determining if emulator should keep listening for packets
isListening = True


# function to read the forwarding table
def readTracker():
    # create dictionary with file names
    global table
    table = dict()

    # first pass to get size for arrays of tuples of data
    with open(args.fileName, 'r') as ftable:
        line = ftable.readline()
        while line:
            vals = line.split()

            # check if it is the right emulator
            if vals[0] != hostname or vals[1] != args.port:
                continue

            # check if the value exists in the dictionary
            destKey = f"{vals[2]}:{vals[3]}"
            if table.get(destKey) is None:
                table[destKey] = list()
            # add string values to array
            table[destKey].append((vals[4], vals[5], vals[6], vals[7]))

            # get new line
            line = ftable.readline()

def handlePacket(pack, addr, time):
    pass
    # add packet to queue
    
def getPackets():
    while isListening:
        try:
            # try to recieve packet and handle it
            data, addr = recSoc.recvfrom(2048)
            handlePacket(data, addr, datetime.now())
        except socket.timeout:
            pass # Do nothing
        except:
            print("Something went wrong!")
            print(traceback.format_exc())

        # send packet from queue

        



def cleanup():
    recSoc.close()
    sys.exit()

def main():
    getPackets()
    cleanup()


if __name__ == '__main__':
    main()