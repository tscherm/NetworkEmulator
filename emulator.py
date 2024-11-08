import argparse
import sys
import socket
from datetime import datetime, timedelta
import traceback
import logging
import random

parser = argparse.ArgumentParser(description="Network Emulator")

parser.add_argument("-p", "--port", type=int, required=True, dest="port")
parser.add_argument("-f", "--filename", type=str, required=True, dest="fileName")
parser.add_argument("-q", "--queue_size", type=int, required=True, dest="queueSize")
parser.add_argument("-l", "--log", type=str, required=True, dest="logName")

args = parser.parse_args()

# configure logging
try:
    logging.basicConfig(filename=args.logName, encoding='utf-8', level=logging.DEBUG)
except:
    print("An error occured while trying to configure logging.")
    print(traceback.format_exc())
    sys.exit()

# check port numbers
if 2049 > args.port or args.port > 65536:
    logging.critical("Sender port out of range.")
    sys.exit()
if 2049 > args.port or args.port > 65536:
    logging.critical("Requester port out of range.")
    sys.exit()

# open port (to listen on only?)
hostname = socket.gethostname()
ipAddr = socket.gethostbyname(hostname)

reqAddr = (ipAddr, args.port)

# open socket
try:
    recSoc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recSoc.bind(reqAddr)
    recSoc.settimeout(0)
except:
    logging.critical("An error occured binding the socket")
    logging.critical(traceback.format_exc())
    sys.exit()

# socket to send from (not the same one)
sendSoc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# these lists will have (packet, timeToSend)
queue = [list(), list(), list()]

# variable for determining if emulator should keep listening for packets
isListening = True

# set up random
random.seed(9)

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

# write logs
def logPacket(pack, recAddr, destAddr, recTime, reason):

    logging.info(f"Packet recieved at {recTime} and dropped at {datetime.now()} because {reason}.")

    if destAddr is None:
        logging.info(f"Recieved from: {recAddr}\n")
    else:
        logging.info(f"Recieved from: {recAddr}\nTo be sent to: {destAddr}\n")

    logging.info(f"{pack}")

# queue the packet and if possible
# steps 2 & 3
# return 1 if packet is added to queue
# return 0 if the packet had to be dropped
# return -1 if there is an error
def queuePacket(pack, addr, time):
    # check if it is in the forwarding table
    destIP = socket.ntohl(int.from_bytes(pack[7:11], 'big'))
    destPort = socket.ntohl(int.from_bytes(pack[11:13], 'big'))
    destKey = f"{destIP}:{destPort}"

    tableEnt = table.get(destKey)

    if tableEnt is None:
        # drop (simply don't add to queue) and log
        logPacket(pack, addr, None, time, "destination is not in forwarding table")
        return 0

    # check priority of packet
    priority = int.from_bytes(pack[0], byteorder='big') - 1

    if priority > 2 or priority < 0:
        logPacket(pack, addr, None, time, "priority was outside of 1, 2, or 3")
        return -1

    # check if you can add it
    if len(queue[priority]) < args.queueSize:
        # calculate time to send
        tts = time + timedelta(milliseconds=table[destKey][2])

        # add to queue and return
        queue[priority].append((pack, tts))
        return 1
    else:
        # drop packet (don't add it to queue) and log it
        logPacket(pack, addr, f"{tableEnt[0]}:{tableEnt[1]}", time, "the queue is full")
        return 0
    
# look at queue and find a packet to send if one is available
# steps 4 - 7
# return 1 if a packet is sent
# return 0 if no packet is in queue
# return -1 if there is an error
def sendPacket():
    for q in queue:
        for p in q:
            pass
    

# wait for packets
# step 1 and 
def getPackets():
    while isListening:
        try:
            # try to recieve packet and handle it
            data, addr = recSoc.recvfrom(2048)
            queuePacket(data, addr, datetime.now())
        except socket.timeout:
            pass # skip down to sendPacket()
        except:
            logging.error("Something went wrong when listening for packet.")
            logging.error(traceback.format_exc())

        # send packet from queue
        sendPacket()

        



def cleanup():
    recSoc.close()
    sys.exit()

def main():
    getPackets()
    cleanup()


if __name__ == '__main__':
    main()