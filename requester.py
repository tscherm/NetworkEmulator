import argparse
import socket
from datetime import datetime
import sys
import traceback
import ipaddress

# set up arg
parser = argparse.ArgumentParser(description="Request part of a file in packets to a reciever")

parser.add_argument("-p", "--port", type=int, required=True, dest="port")
parser.add_argument("-o", "--file_option", type=str, required=True, dest="fileName")
parser.add_argument("-f", "--f_hostname", type=str, required=True, dest="emulatorName")
parser.add_argument("-e", "--f_port", type=int, required=True, dest="emulatorPort")
parser.add_argument("-w", "--window", type=int, required=True, dest="window")

args = parser.parse_args()

# do not need to check port range

# open port (to listen on only?)
hostname = socket.gethostname()
ipAddr = socket.gethostbyname(hostname)

reqAddr = (ipAddr, args.port)

try:
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    soc.bind(reqAddr)
except:
    print("An error occured binding the socket")
    print(traceback.format_exc())
    sys.exit()

# open file to write to
# this also creates a file assuming it is not there or overwrites it if it exists
try:
    #toWrite = open(args.fileName, 'w')
    pass
except:
    print(f"There was an issue opening the file {args.fileName}")
    print(traceback.format_exc())
    sys.exit()

# get emulator address
eIpAddr = socket.gethostbyname(args.emulatorName)
eAddr = (eIpAddr, args.emulatorPort)

# track size of file written and end size of file and what to write
finalSizeBytes = 0
currSizeBytes = 0
# packetsToWrite = [[(seqNo, payload), ...], ...] 
# each list is from one sender
# each list is ordered by seqNo
packetsFromSenders = list()

def printPacket(ptype, time, srcAddr, srcPort, seq, length, percent, payload):
    print(f"{ptype} Packet")
    timeStr = (time.strftime("%y-%m-%d %H:%M:%S.%f"))[:-3]
    print(f"recv time:\t20{timeStr}")
    print(f"sender addr:\t{srcAddr}:{srcPort}")
    print(f"sequence:\t{seq}")
    print(f"length:\t\t{length}")
    if (ptype == "DATA"):
        print(f"percentage:{percent:^12,.2%}")
        print(f"payload:\t{payload[0:4].decode('utf-8')}\n")
    else:
        print(f"payload:\t0\n")

# function to send request to specified sender
def sendReq(destIP, port):
    pt = b'R'
    seq = 0
    l = len(args.fileName)

    header = pt + socket.htonl(seq).to_bytes(4, 'big') + socket.htonl(int(args.window)).to_bytes(4, 'big')
    payload = args.fileName.encode('utf-8')
    l2Packet = header + payload

    # new sender stuff
    l3Prior = (1).to_bytes(1, 'big')
    srcAdr = socket.htonl(int(ipaddress.ip_address(ipAddr))).to_bytes(4, 'big') + socket.htons(args.port).to_bytes(2, 'big')
    destAdr = socket.htonl(int(ipaddress.ip_address(destIP))).to_bytes(4, 'big') + socket.htons(port).to_bytes(2, 'big')
    l3Len = socket.htonl((l + 9)).to_bytes(4, 'big')
    packet = l3Prior + srcAdr + destAdr + l3Len + l2Packet

    soc.sendto(packet, eAddr)
    #print("REQUEST SENT")

# function to readd the tracker
# Assumed name is tracker.txt
def readTracker():
    # create dictionary with file names
    global files
    files = dict()

    # first pass to get size for arrays of tuples of data
    with open("tracker.txt", 'r') as tracker:
        line = tracker.readline()
        while line:
            vals = line.split()

            # check if the value exists in the dictionary
            if files.get(vals[0]) is None:
                files[vals[0]] = list()
            # add string values to array
            files[vals[0]].append((vals[1], vals[2], vals[3]))

            # get new line
            line = tracker.readline()

        # sort values in arrays for each file
        for k in files.keys():
            # array to replace old array
            tempArr = [(0,0)] * len(files[k])

            # iterate over each element and place it in the right spot
            for t in files[k]:
                spot = int(t[0]) - 1
                # convert host name to ip, port to int
                tempArr[spot] = (socket.gethostbyname(t[1]), int(t[2]))
            # replace old array with the new one
            files[k] = tempArr


# send acknowledgement 
def sendAck(destIP, port, seq):
    pt = b'A'
    l = 0

    header = pt + socket.htonl(seq).to_bytes(4, 'big') + socket.htonl(l).to_bytes(4, 'big')
    l2Packet = header

    # new sender stuff
    l3Prior = (1).to_bytes(1, 'big')
    srcAdr = socket.htonl(int(ipaddress.ip_address(ipAddr))).to_bytes(4, 'big') + socket.htons(args.port).to_bytes(2, 'big')
    destAdr = socket.htonl(int(ipaddress.ip_address(destIP))).to_bytes(4, 'big') + socket.htons(port).to_bytes(2, 'big')
    l3Len = socket.htonl((l + 9)).to_bytes(4, 'big')
    packet = l3Prior + srcAdr + destAdr + l3Len + l2Packet

    soc.sendto(packet, eAddr)
    #print("ACK SENT")

# handle big packet
# returns small packet
def handleBigPacket(data):

    priority = data[0]
    srcIP = socket.ntohl(int.from_bytes(data[1:5], 'big'))
    srcPort = socket.ntohs(int.from_bytes(data[5:7], 'big'))
    destIP = socket.ntohl(int.from_bytes(data[7:11], 'big'))
    destPort = socket.ntohs(int.from_bytes(data[11:13], 'big'))
    bigLen = socket.ntohl(int.from_bytes(data[13:17], 'big'))

    if ipaddress.ip_address(destIP) != ipaddress.ip_address(ipAddr) or destPort != args.port:
        #wrong place
        return 0

    return (data[17:], (srcIP, srcPort), bigLen)

# add the packet to the specific sender packet list
# return 1 if packet is added
# return 0 if packet already exists
def recordPacket(payload, seqNo, senderPackList):
    # iterate over list backwards and place packet in right spot
    for i in range(len(senderPackList)-1, -1, -1):
        cseq = senderPackList[i][0]
        if cseq > seqNo:
            continue
        elif cseq == seqNo:
            # packet already recieved
            return 0
        else:
            # add packet and return
            senderPackList.insert(i+1, (seqNo, payload))
            return 1

    # add packet if there is nothing in the array yet
    if len(senderPackList) <= 0:
        senderPackList.append((seqNo, payload))

# handles a packet from sender
# returns false if it gets something other than data packet (End packet or wrong dest)
# returns true if it gets a data packet
def handlePacket(pack, addr, time, senderPackList):
    # handle big packet
    ret = handleBigPacket(pack)

    if ret == 0:
        return False
    
    
    data = ret[0]

    # get header values
    pType = data[0]
    seqNo = socket.ntohl(int.from_bytes(data[1:5], 'big'))
    pLen = socket.ntohl(int.from_bytes(data[5:9], 'big'))

    # check packet type
    # End type
    if (pType.to_bytes(1, 'big') == b'E'):
        sendAck(ret[1][0], ret[1][1], seqNo)
        #Packet("End", time, addr[0], addr[1], seqNo, pLen, 0, 0)
        return False
    elif (pType.to_bytes(1, 'big') != b'D'):
        # something went wrong
        return False
    # Data packet

    payload = data[9:9 + pLen]
    recordPacket(payload, seqNo, senderPackList)
    #print(f"Recording: {payload}")
    # add bytes written and print packet info
    global currSizeBytes
    currSizeBytes += pLen
    global finalSizeBytes
    finalSizeBytes += pLen

    # supress this
    #printPacket("DATA", time, addr[0], addr[1], seqNo, pLen, currSizeBytes / finalSizeBytes, payload)

    sendAck(ret[1][0], ret[1][1], seqNo)

    return True

# prints summary of what specific sender sent
def printSummary(addr, numP, numB, pps, ms):
    print("Summary")
    print(f"sender addr:\t\t{addr[0]}:{addr[1]}")
    print(f"Total Data packets:\t{numP}")
    print(f"Total Data bytes:\t{numB}")
    print(f"Average packets/second:\t{pps:.0f}")
    print(f"Duration of the test:\t{ms:.0f}  ms\n")
    

# fucntion to listen for packets and send packets elsewhere
# handles packets coming from a specific host
# takes IP that it should be coming from and gets it's port
# also takes number of bytes it expects to recieve
def waitListen(ipToListenFor, senderPackList):

    #print("REQUESTER STARTED")

    isListening = True
    currAddr = ('', 0)
    totalDataPackets = 0
    start = datetime.now()

    while isListening:

        data = 0
        addr = 0

        try:
            data, addr = soc.recvfrom(4096)
            #print("Recieved")
        except BlockingIOError:
            continue
        except KeyboardInterrupt:
            sys.exit()
        except:
            #print("Something went wrong listening for packets")
            continue

        
        now = datetime.now()

        # check if it is from the same address for summary
        # check that it is from the right address
        if (ipaddress.ip_address(socket.ntohl(int.from_bytes(data[1:5], 'big'))) != ipaddress.ip_address(ipToListenFor)):
            continue
        # check if it has even been set yet
        elif (currAddr == ('', 0)):
            currAddr = addr
        
        isListening = handlePacket(data, addr, now, senderPackList)

        # check if data packet was recieved
        if isListening:
            totalDataPackets += 1
    # calculate time and print summary
    end = datetime.now()
    totalTime = (end - start).total_seconds()
    #printSummary(currAddr, totalDataPackets, totalDataPackets, totalDataPackets / totalTime, totalTime * 1000)

# write payload to file
# assume no space is needed for missing sequence numbers
def writePayloadToFile():
    #print(packetsFromSenders)
    with open(args.fileName, 'w') as toWrite:
        for s in packetsFromSenders:
            for p in s:
                toWrite.write(p[1].decode('utf-8'))
            

# gets file from tracker and sends requests to each host in list
def getFile(fileName):

    # iterate over senders to get file from
    for s in files[fileName]:
        # send request to sender
        sendReq(s[0], s[1])
        # wait for and handle to packets
        packetsFromSenders.append(list())
        senderPackList = packetsFromSenders[-1]
        waitListen(s[0], senderPackList)

    writePayloadToFile()

# function to clean and close all parts of the project
def cleanup():
    #toWrite.close()
    soc.close()
    sys.exit()

def main():
    # get files to get
    readTracker()
    # check that file name is in files/tracker
    if args.fileName not in files.keys():
        print("FILE NOT FOUND IN TRACKER")
        sys.exit()
    # get the file
    getFile(args.fileName)
    cleanup()

if __name__ == '__main__':
    main()
