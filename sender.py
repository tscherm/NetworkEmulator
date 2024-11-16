import argparse
import socket
from datetime import datetime, timedelta
import os
import ctypes
import sys
import traceback
import ipaddress 
import threading

# set up arg
parser = argparse.ArgumentParser(description="Send part of a file in packets to a reciever")

parser.add_argument("-p", "--sender_port", type=int, required=True, dest="sPort")
parser.add_argument("-g", "--requester_port", type=int, required=True, dest="rPort")
parser.add_argument("-r", "--rate", type=int, required=True, dest="rate")
parser.add_argument("-q", "--seq_no", type=int, required=True, dest="seqNo")
parser.add_argument("-l", "--length", type=int, required=True, dest="length")
parser.add_argument("-f", "--f_hostname", type=str, required=True, dest="emulatorName")
parser.add_argument("-e", "--f_port", type=int, required=True, dest="emulatorPort")
parser.add_argument("-i", "--priority", type=int, required=True, dest="priority")
parser.add_argument("-t", "--timeout", type=int, required=True, dest="timeout")

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
    recSoc.setblocking(0)
except:
    print("An error occured binding the socket")
    print(traceback.format_exc())
    sys.exit()

# socket to send from (not the same one)
sendSoc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# get emulator address
eIpAddr = socket.gethostbyname(args.emulatorName)
eAddr = (eIpAddr, args.emulatorPort)

# helper for sendPacketTimed
lastTimeSent = datetime.now() - timedelta(days=1)

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
def sendPacketTimed(packet):
    print("Trying to send")
    global lastTimeSent
    # wait for time to be ready to send 
    while ((datetime.now() - lastTimeSent) < mspp):
        continue

    print(packet)
    print(eAddr)
    sendSoc.sendto(packet, eAddr)
    lastTimeSent = datetime.now()
    print("Packet Sent!")

def sendWindow(packets):
    # -1 num tries means sucessful send
    numTries = [0] * len(packets)
    timeToSend = [datetime.now()] * len(packets)

    # find first packet to send
    toSendIndex = 0

    # helper to see if something needs to be sent
    packToSend = True

    # loop over packets to send
    # pop packet off list when it is sent
    # don't need to keep order because seqNo is in packet
    while len(packets) > 0:
        # create thread to send the next packet and start it

        # check if there is a new packet to send
        if packToSend:
            packToSend = packets[toSendIndex]
            sending = threading.Thread(target=sendPacketTimed, args=([packToSend]))
            sending.start()

            # packet has been sent and is in timeout to be selected to be sent again
            packToSend = False

            # check if this is its fifth try
            if numTries[toSendIndex] >= 4:
                packets.pop(toSendIndex)
                numTries.pop(toSendIndex)
                timeToSend.pop(toSendIndex)
            else:
                numTries[toSendIndex] += 1
                timeToSend[toSendIndex] = datetime.now() + timedelta(milliseconds=int(args.timeout))


        # find next packet to send
        for i in range(len(packets)):
            if timeToSend[i] >= datetime.now():
                toSendIndex = i
                packToSend = True
                break

        # wait on send thread to return
        # this also avoids any race conditions
        hasChecked = False
        while sending.is_alive() or not hasChecked:

            hasChecked = True
            # initialize these so they can be used lower down
            data = 0
            addr2 = 0

            # see if there is an ACK
            try:
                data, addr2 = recSoc.recvfrom(4096)
            except BlockingIOError:
                continue # try to listen again
            except KeyboardInterrupt:
                sys.exit()
            except:
                print("Something when wrong when listening for ACK")

            seqNo = data[18:22]

            # see what packet it is and pop it and its num tries
            for i in range(len(packets)):
                # find which one to pop
                if packets[i][18:22] == seqNo:
                    packets.pop(toSendIndex)
                    numTries.pop(toSendIndex)
                    timeToSend.pop(toSendIndex)


# function to get file name and read file and open file
def openFile(data, nameLen):
    # make global variables
    global toSendName
    global toSend
    global toSendSize
    global windowSize

    # get file name
    toSendName = data[9:9 + nameLen].decode('utf-8')

    # get window size
    windowSize = socket.ntohl(int.from_bytes(data[5:9], 'big'))

    try:
        toSend = open(toSendName, "r")
    except:
        print(f"There was an issue opening the file {toSendName}")
        print(traceback.format_exc())
        sys.exit()
    
    toSendSize = os.stat(toSendName).st_size

# handle big packet
# returns small packet
def handleBigPacket(data):

    priority = data[0]
    srcIP = socket.ntohl(int.from_bytes(data[1:5], 'big'))
    srcPort = socket.ntohs(int.from_bytes(data[5:7], 'big'))
    destIP = socket.ntohl(int.from_bytes(data[7:11], 'big'))
    destPort = socket.ntohs(int.from_bytes(data[11:13], 'big'))
    bigLen = socket.ntohl(int.from_bytes(data[13:17], 'big'))

    if ipaddress.ip_address(destIP) != ipaddress.ip_address(ipAddr) or destPort != int(args.sPort):
        #wrong place
        return 0
    
    # get name size
    nameLen = bigLen - 9

    print("AAAAAAA")
    print(srcIP)

    return (data[17:], nameLen, (srcIP, srcPort))

# handle request packet
def handleReq(pack, addr):

    ret = handleBigPacket(pack)

    data = ret[0]
    nameLen = ret[1]
    reqDest = ret[2]

    # check that it is a request packet
    # 'R' = 82
    if (data[0] != 82):
        return -1

    # get file info
    openFile(data, nameLen)

    # get the number of packets to send
    numPackets = toSendSize // ctypes.c_uint32(args.length).value if toSendSize % ctypes.c_uint32(args.length).value == 0 else toSendSize // ctypes.c_uint32(args.length).value + 1

    # iterate over chunks of data and send it
    seqNum = 1
    sizeLeft = toSendSize
    packets = list()
    for i in range(numPackets):
        # old sender stuff
        # make header
        pSize = ctypes.c_uint32(args.length).value if sizeLeft >= ctypes.c_uint32(args.length).value else sizeLeft
        header = b'D' + socket.htonl(seqNum).to_bytes(4, 'big') + socket.htonl(pSize).to_bytes(4, 'big')

        # get payload and add header to packet
        payload = toSend.read(pSize).encode('utf-8')
        l2Packet = header + payload

        # new sender stuff
        l3Prior = int(args.priority).to_bytes(1, 'big')
        srcAdr = socket.htonl(int(ipaddress.ip_address(ipAddr))).to_bytes(4, 'big') + socket.htons(args.sPort).to_bytes(2, 'big')
        destAdr = socket.htonl(reqDest[0]).to_bytes(4, 'big') + socket.htons(args.rPort).to_bytes(2, 'big')
        l3Len = socket.htonl((pSize + 9)).to_bytes(4, 'big')
        packet = l3Prior + srcAdr + destAdr + l3Len + l2Packet
        print(reqDest[0])
        # for testing
        print("NEW PACKET PROCESSED")
        print(packet)

        packets.append(packet)

        # print packet info
        # supress this
        # printPacket("DATA", lastTime, addr, seqNum, pSize, payload)
        seqNum += 1
        sizeLeft -= pSize

    global windowSize
    # do -1 so there aren't extra windows sent if len(packets) % 0 = 0
    for i in range((len(packets) - 1) // windowSize):
        print("Window to be sent")
        sendWindow(packets[i * windowSize: (i + 1) * windowSize], addr)

    # send END packet
    # new sender stuff
    l3Prior = (int(args.priority)).to_bytes(1, 'big')
    srcAdr = socket.htonl(int(ipaddress.ip_address(ipAddr))).to_bytes(4, 'big') + socket.htons(args.sPort).to_bytes(2, 'big')
    destAdr = socket.htonl(reqDest[0]).to_bytes(4, 'big') + socket.htons(args.rPort).to_bytes(2, 'big')
    l3Len = socket.htonl(0).to_bytes(4, 'big')

    pt = b'E'
    l = 0
    l2Packet = pt + socket.htonl(seqNum).to_bytes(4, 'big') + socket.htonl(l).to_bytes(4, 'big')

    packet = l3Prior + srcAdr + destAdr + l3Len + l2Packet

    packets = list()
    packets.append(packet)
    sendWindow(packets)
    # print end packet
    printPacket("END", datetime.now(), addr, seqNum, l, 0)
    

# fucntion to listen for packets and send packets elsewhere
def waitListen():
    print("SENDER STARTED")
    # make sure the code exits properly
    isListening = True
    # only need to listen and get one request
    while isListening:
        try:
            data, addr = recSoc.recvfrom(4096)
            print("PACKET RECIEVED")
            handleReq(data, addr[0])
            isListening = False
        except BlockingIOError:
            pass # do nothing
        except KeyboardInterrupt:
            sys.exit()
        except:
            print("Something went wrong listening for packets.")
            print(traceback.format_exc())


def cleanup():
    recSoc.close()
    sys.exit()

def main():
    waitListen()
    cleanup()


if __name__ == '__main__':
    main()
