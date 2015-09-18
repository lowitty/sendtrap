'''
Created on Oct 9, 2014

@author: EJLNOQCC

Version 2.0:
    EJLNOQC 2014-10-14
    Big change in many part.
    1. Add support of Alarm storm mode.
    2. Add log file.
    3. Using the native python SNMP module pysnmp instead of Popen net-snmp.
    
    
'''
#from socket import socket, AF_PACKET, SOCK_RAW
import sys
import os.path
from sys import path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
#print os.path.join(os.path.dirname(__file__), 'lib')
#print sys.path

#import the 3rd party module of pysnmp, note that pysnmp depends on pyasn1

'''from pysnmp.carrier.asynsock.dgram import udp
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import ntforg, context
from pysnmp.proto.api import v2c
import pyasn1, pysnmp'''

# Notification Originator Application (TRAP)
from pysnmp.carrier.asynsock.dispatch import AsynsockDispatcher
from pysnmp.carrier.asynsock.dgram import udp
from pyasn1.codec.ber import encoder
from pysnmp.proto import api

# Protocol version to use
verID = api.protoVersion1
pMod = api.protoModules[verID]

# Build PDU
trapPDU =  pMod.TrapPDU()
pMod.apiTrapPDU.setDefaults(trapPDU)

# Traps have quite different semantics among proto versions
if verID == api.protoVersion1:
    pMod.apiTrapPDU.setEnterprise(trapPDU, (1,3,6,1,1,2,3,4,1))
    pMod.apiTrapPDU.setGenericTrap(trapPDU, 'coldStart')
    var = []
    oid = (1,3,6,1,1,2,3,4,1,1)
    val = pMod.OctetString('Error Type')
    var.append((oid,val))
    oid = (1,3,6,1,1,2,3,4,1,2)
    val = pMod.OctetString('Error Info')
    var.append((oid,val))
    pMod.apiTrapPDU.setVarBinds(trapPDU, var)

# Build message
trapMsg = pMod.Message()
pMod.apiMessage.setDefaults(trapMsg)
pMod.apiMessage.setCommunity(trapMsg, 'public')
pMod.apiMessage.setPDU(trapMsg, trapPDU)

transportDispatcher = AsynsockDispatcher()
transportDispatcher.registerTransport(
    udp.domainName, udp.UdpSocketTransport().openClientMode(( '127.0.0.1', 162))
    )
transportDispatcher.sendMessage(
    encoder.encode(trapMsg), udp.domainName, ('localhost', 162)
    )
transportDispatcher.runDispatcher()
transportDispatcher.closeDispatcher()