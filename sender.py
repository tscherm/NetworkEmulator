import argparse
import socket
from datetime import datetime, timedelta
import os
import ctypes
import sys
import traceback

# set up arg
parser = argparse.ArgumentParser(description="Send part of a file in packets to a reciever")

parser.add_argument("-p", "--sender_port", type=int, required=True, dest="sPort")
parser.add_argument("-g", "--requester_port", type=int, required=True, dest="rPort")
parser.add_argument("-r", "--rate", type=int, required=True, dest="rate")
parser.add_argument("-q", "--seq_no", type=int, required=True, dest="seqNo")
parser.add_argument("-l", "--length", type=int, required=True, dest="length")

args = parser.parse_args()

# check port numbers
if 2049 > args.sPort or args.sPort > 65536:
    print("Sender port out of range.")
    sys.exit()
if 2049 > args.rPort or args.rPort > 65536:
    print("Requester port out of range.")
    sys.exit()

# do not need to check any other parameters

# milliseconds per packet
mspp = timedelta(seconds = (1 / args.rate))

# open port (to listen on only?)
hostname = socket.gethostname()
ipAddr = socket.gethostbyname(hostname)

reqAddr = (ipAddr, args.sPort)

try:
    recSoc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recSoc.bind(reqAddr)
except:
    print("An error occured binding the socket")
    print(traceback.format_exc())
    sys.exit()

# socket to send from (not the same one)
sendSoc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def printPacket(ptype, time, destAddr, seqNo, length, payload):
    print(f"{ptype} Packet")
    timeStr = (time.strftime("%y-%m-%d %H:%M:%S.%f"))[:-3]
    print(f"send time:\t20{timeStr}")
    print(f"requester addr:\t{destAddr}:{args.rPort}")
    print(f"sequence:\t{seqNo}")
    print(f"length:\t\t{ctypes.c_uint32(length).value}")
    if ptype == "DATA":
        print(f"payload:\t{payload[0:4].decode('utf-8')}\n")
    else:
        print(f"payload:\t\t\n")

# send packet with respect to time
def sendPacketTimed(packet, addr, lastTimeSent):
    # wait for time to be ready to send 
    while ((datetime.now() - lastTimeSent) < mspp):
        continue

    toReturn = datetime.now()
    sendSoc.sendto(packet, (addr, args.rPort))

    return toReturn

# function to get file name and read file and open file
def openFile(data):
    # make global variables
    global toSendName
    global toSend
    global toSendSize

    # get file name
    nameLen = socket.ntohl(int.from_bytes(data[5:9], 'big'))
    
    toSendName = data[9:9 + nameLen].decode('utf-8')

    try:
        toSend = open(toSendName, "r")
    except:
        print(f"There was an issue opening the file {toSendName}")
        print(traceback.format_exc())
        sys.exit()
    
    toSendSize = os.stat(toSendName).st_size

# handle request packet
def handleReq(data, addr):
    # check that it is a request packet
    # 'R' = 82
    if (data[0] != 82):
        return -1

    # get file info
    openFile(data)

    # get the number of packets to send
    numPackets = toSendSize // ctypes.c_uint32(args.length).value if toSendSize % ctypes.c_uint32(args.length).value == 0 else toSendSize // ctypes.c_uint32(args.length).value + 1

    # iterate over chunks of data and send it
    lastTime = datetime.now() - timedelta(days=1)
    seqNum = args.seqNo
    sizeLeft = toSendSize
    for i in range(numPackets):
        # make header
        pSize = ctypes.c_uint32(args.length).value if sizeLeft >= ctypes.c_uint32(args.length).value else sizeLeft
        header = b'D' + socket.htonl(seqNum).to_bytes(4, 'big') + socket.htonl(pSize).to_bytes(4, 'big')

        # get payload and add header to packet
        payload = toSend.read(pSize).encode('utf-8')
        packet = header + payload

        lastTime = sendPacketTimed(packet, addr, lastTime)

        # print packet info
        printPacket("DATA", lastTime, addr, seqNum, pSize, payload)
        seqNum += pSize
        sizeLeft -= pSize

    # send END packet
    pt = b'E'
    l = 0
    packet = pt + socket.htonl(seqNum).to_bytes(4, 'big') + socket.htonl(l).to_bytes(4, 'big')
    sendPacketTimed(packet, addr, lastTime)

    # print end packet
    printPacket("END", lastTime, addr, seqNum, l, 0)
    

# fucntion to listen for packets and send packets elsewhere
def waitListen():
    # only need to listen and get one request
    data, addr = recSoc.recvfrom(2048)
    handleReq(data, addr[0])


def cleanup():
    toSend.close()
    recSoc.close()
    sys.exit()

def main():
    waitListen()
    cleanup()


if __name__ == '__main__':
    main()
