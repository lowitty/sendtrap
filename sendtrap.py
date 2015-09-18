#encoding=utf-8
'''
Created on Oct 9, 2014

@author: EJLNOQCC

Version 2.0:
    EJLNOQC 2014-10-14
    Big change in many part.
    1. Add support of Alarm storm mode.
    2. Add log file.
    3. Using the native python SNMP module pysnmp instead of Popen net-snmp.
    
Version 3.0:
    EJLNOQC 2015-02-11
    Big change in many part.
    1. Add support of Alarm special mode, will send paired new and clear alarms.
    2. Normal mode will read the counter as alarm ID, do not need to change the alarm ID each time.
    3. Normal mode can specify custom timestamp of alarm trap.
    
    
'''
import sys
import os.path
from sys import path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
#print os.path.join(os.path.dirname(__file__), 'lib')
#print sys.path

#import the 3rd party module of pysnmp, note that pysnmp depends on pyasn1
from pysnmp.carrier.asynsock.dgram import udp
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import ntforg, context
from pysnmp.proto.api import v2c
import pyasn1, pysnmp

import datetime as pydate
import time, shutil
from optparse import OptionParser, OptionGroup
#import fileinput
#from cuslibs import props

versionInfo = "\nPython & Module Info:"
versionInfo += "\nPython: " + sys.version
versionInfo += "\nPyasn1: " + pyasn1.__version__
versionInfo += "\nPysnmp: " + pysnmp.__version__
#print versionInfo

snmpEngine = snmpContext = ntfOrg = None
mappings = {}
logfile = ""
alarm_counter = 0
alarm_rec_path = None


#定义告警时间戳对用的TRAP ID
oidTimeStamp = [
                "1.3.6.1.4.1.193.183.4.1.3.5.1.7.0", 
                "1.3.6.1.4.1.193.83.1.1.1.3.0", 
                "1.3.6.1.4.1.193.82.1.8.1.4.0", 
                "1.3.6.1.4.1.193.183.4.1.4.5.1.7.0",
                "1.3.6.1.4.1.193.176.50.3.3.0"
                ]
#定义告警id对用的TRAP ID
oidAlarmIDs = [
               "1.3.6.1.4.1.193.83.1.1.1.1.0",
               "1.3.6.1.4.1.193.82.1.8.1.1.0",
               "1.3.6.1.4.1.193.176.50.3.1.0"
               ]

#define alarm oid which have id prefix, like OCG's alarm id have date as prefix
oidAlarmIDsPrefix = [
                     "1.3.6.1.4.1.193.176.50.3.1.0"
                     ]

#初始化发送告警的引擎，将会指定将要发送trap的目的server地址以及端口等。
def initTarget(host='127.0.0.1', community='LIC_OSS', port=162):
    global snmpEngine, snmpContext, ntfOrg
    # Create SNMP engine instance
    snmpEngine = engine.SnmpEngine()
    
    # SecurityName <-> CommunityName mapping
    config.addV1System(snmpEngine, 'my-area', community)
    
    # Specify security settings per SecurityName (SNMPv2c -> 1)
    config.addTargetParams(snmpEngine, 'my-creds', 'my-area', 'noAuthNoPriv', 1)
    
    # Setup transport endpoint and bind it with security settings yielding
    # a target name
    config.addSocketTransport(
        snmpEngine,
        udp.domainName,
        udp.UdpSocketTransport().openClientMode()
    )
    config.addTargetAddr(
        snmpEngine, 'my-nms',
        udp.domainName, (host, port),
        'my-creds',
        tagList='all-my-managers'
    )
    
    # Specify what kind of notification should be sent (TRAP or INFORM),
    # to what targets (chosen by tag) and what filter should apply to
    # the set of targets (selected by tag)
    config.addNotificationTarget(
        snmpEngine, 'my-notification', 'my-filter', 'all-my-managers', 'trap'
    )
    
    # Allow NOTIFY access to Agent's MIB by this SNMP model (2), securityLevel
    # and SecurityName
    config.addContext(snmpEngine, '')
    config.addVacmUser(snmpEngine, 2, 'my-area', 'noAuthNoPriv', (), (), (1,3,6))
    
    # *** SNMP engine configuration is complete by this line ***
    
    # Create default SNMP context where contextEngineId == SnmpEngineId
    snmpContext = context.SnmpContext(snmpEngine)
    
    # Create Notification Originator App instance. 
    ntfOrg = ntforg.NotificationOriginator(snmpContext)

#盖房将会发送告警, oid指定告警的trap id，traps指定告警内容
def sendTrap(oid, traps = None, uptime = 0, counts = 0):    
    # Build and submit notification message to dispatcher
    global ntforg, snmpEngine
    ntfOrg.sendNotification(
        snmpEngine,
        # Notification targets
        'my-notification',
        # Trap OID (SNMPv2-MIB::coldStart)
        (oid),
        # ( (oid, value), ... )
        traps
    )
    
    msg = str(counts)
    # + '\tNotification is scheduled to be sent.' + str(traps)
    writeLog(msg)
    #print msg
    
    # Run I/O dispatcher which would send pending message and process response
    #global snmpEngine
    snmpEngine.transportDispatcher.runDispatcher()

#strDate is in format of "%Y-%m-%d %H:%M:%S".
#该方法将传入的string类型的时间转换为snmp时间戳的模式，即16进制模式。
def getHexFromStr(strDate, delisecond = 0):
    hexValue = ""
    directionFromUTC = hoursFromUTC = minutesFromUTC = None
    zone = dt = None
    t = time.time()
    if(time.localtime(t).tm_isdst and time.daylight):
        zone = time.altzone
    else:
        zone = time.timezone
    
    if zone < 0:
        directionFromUTC = '+'
    else:
        directionFromUTC = '-'
    
    hoursFromUTC = zone / -(60*60)
    minutesFromUTC = -1 * (zone % 60)
    try:
        dt = pydate.datetime.strptime(strDate, '%Y-%m-%d %H:%M:%S')
    except Exception as e:
        msg = "The time format should be like \"2012-05-05 05:05:54\", " + e.message
        print msg
        writeLog(msg)
        return 1, "Time format error!"
        
    high, low = divmod(dt.year, 256)
    if high < 16:
        hexValue += "0"
    hexValue += format(high, 'x')
    if low < 16:
        hexValue += "0"
    hexValue += format(low, 'x')
    months = dt.month
    hexValue += "0" + format(dt.month, 'x')
    if dt.day < 16:
        hexValue += "0"
    hexValue += format(dt.day, 'x')
    if dt.hour < 16:
        hexValue += "0"
    hexValue += format(dt.hour, 'x')
    if dt.minute < 16:
        hexValue += "0"
    hexValue += format(dt.minute, 'x')
    if dt.second < 16:
        hexValue += "0"
    hexValue += format(dt.second, 'x')
    #deli-second, dt.microsecond
    deli_sec = int(round(delisecond / 10000))
    if(deli_sec < 16):
        hexValue += "0" 
    hexValue += format(deli_sec, 'x')  
    hexValue += format(ord(directionFromUTC), 'x')
    hexValue += "0" + format(hoursFromUTC, 'x')
    if minutesFromUTC < 16:
        hexValue += "0"
    hexValue += format(minutesFromUTC, 'x')
    return 0, hexValue    

#该方法读入计数器的值。
def initCounter(path = None):
    global alarm_counter
    global alarm_rec_path
    #tgtPath = None
    if(path is None):
        alarm_rec_path = os.path.normpath(os.getcwd() + os.sep + "counter" + os.sep + "prop")
    else:
        alarm_rec_path = os.path.normpath
    
    if(not os.path.isfile(alarm_rec_path)):
        if(len(os.listdir(os.path.normpath(os.getcwd() + os.sep + "counter"))) > 0):
            newPath = os.path.normpath( os.getcwd() + os.sep + "counter" + os.listdir( os.path.normpath( os.getcwd() + os.sep + "counter" ) )[0] )
            if(os.path.isfile(newPath)):
                alarm_rec_path = newPath
            else:
                msg = "No counter record file is found under directory of 'counter'!"
                writeLog(msg)
                print msg
                return 1, msg
        else:
            msg = "Counter record file is missing, please check the file of path: ./counter."
            writeLog(msg)
            print msg
            return 2, msg
    
    try:
        f = open(alarm_rec_path, 'r+')
        line = f.readline()
        line_info = line.split("=")
        f.close()
        if(len(line_info) < 2):
            msg = "Counter record file has wrong format!"
            writeLog(msg)
            print msg
            return 4, msg
        else:
            str_coun = line_info[1]
            try:
                alarm_counter = int(str_coun)
                return 0, "Get the counter value successfully."
            except Exception as e:
                msg = "Format the counter value failed!"
                print msg
                writeLog(msg)
                return 5, msg
        
    except Exception as e:
        msg = e.message
        print msg
        writeLog(msg)
        return 3, msg

#该方法初始化读取mapping.txt的映射关系，工具将会依照此映射关系寻找告警的模板文件。
def initMapping(path=None):
    msg = "Start to read the mapping file, try to get the mapping relation between number and alarms."
    writeLog(msg)
    #print msg
    
    global mappings
    targetPath = None
    if(path is None):
        targetPath = os.path.normpath(os.getcwd() + os.path.sep + "conf" + os.path.sep + "mapping.txt")
    else:
        targetPath = os.path.normpath(path)
    
    if(not os.path.isfile(targetPath)):
        if len(os.listdir(os.path.normpath(os.getcwd() + os.path.sep + "conf" ))) > 0 :
            newPath = os.path.normpath(os.getcwd() + os.path.sep + "conf" + os.path.sep + os.listdir(os.path.normpath(os.getcwd() + os.path.sep + "conf" ))[0])
            if(os.path.isfile(newPath)):
                targetPath = newPath
            else:
                msg = "No mapping file is found under directory of \"conf\"!"
                writeLog(msg)
                print msg
                return 2, "No mapping file is found under directory of \"conf\"!"
        else:
            msg = "The alarms mapping file is missing, none file is under directory of: " + os.path.normpath(os.getcwd() + os.path.sep + "conf" )
            writeLog(msg)
            print msg
            return 1, "The alarms mapping file is missing!"
    
    msg = "Open the mapping file of path: " + targetPath
    writeLog(msg)
    #print msg
    
    try:
        f = open(targetPath, 'r+')
        for line in f.readlines():
            line_info = line.split("=")
            if len(line_info) > 1:
                mappings[line_info[0].strip()] = line_info[1].strip()
        f.close()
        #print type(mappings)
        #print mappings
        msg = "Get mapping successfully, mapping is: " + str(mappings)
        writeLog(msg)
        #print msg
        return 0, "Mapping Successfully!"
    except Exception as e:
        return 3, "Fail to open the mapping file, " + e.message


#该方法用于读取和处理用户传入的命令参数并进行合法性校验
def parseOptions():
    global versionInfo
    parser = OptionParser(usage="%prog [-L] [-M] [-H] [-P] [-T] [-I] [-i] [-D] [-R]" + "\n" + "This tool is used to simulate to send SNMP trap. All Rights Reserved by Ericsson CBC/XN team." + versionInfo, version="%prog 2.0")
    group = OptionGroup(parser, "Mandatory Options",
                        "Caution: These are mandatory Options, you must specify these options in order to use this tool."
                        "Otherwise the tool cannot work.")
    group.add_option("-l", "--list", action="store", type = "string", help = "Specify the alarms that you want to send, using \",\" to separate if you want to send more than one alarm at the same time. e.g. -L 2,31,32", dest="list")
    parser.add_option_group(group)
    optionalGroup = OptionGroup(parser, "Optional options", "These options are optional.")
    optionalGroup.add_option("-m", "--many", action="store", type="string", default="n", help = "Use \"-m\" to specify how will send the alarm, valid values are [n, m, s].", dest="many")
    optionalGroup.add_option("-H", "--host", action="store", type="string", default = "127.0.0.1", help = "Specify the destination HOST IP that you want to send a trap to.[default: %default]", dest="host")
    optionalGroup.add_option("-p", "--port", action="store", type="int", default = "162", help = "Specify the destination HOST IP that you want to send a trap to.[default: %default]", dest="port")
    optionalGroup.add_option("-w", "--waitingtime", action="store", type="int", default = "1", help = "The waiting time between two rounds, [1, Infinity)", dest="waitingtime")
    optionalGroup.add_option("-n", "--interval", action="store", type="float", default = "1.0", help = "The amount of alarms that will be send in 1 second. Range[1.0, 100.0] with unit of mili-second(ms).[default: %default]", dest="interval")
    optionalGroup.add_option("-t", "--timeofevent", action="store", type="string", default = "", help = "Custom the alarm event time, should be format of '%Y-%h-%d %H:%M:%S'.[default: %default]", dest="timeofevent")
    optionalGroup.add_option("-I", "--intervalshift", action="store", type="int", default = "1", help = "The time interval shift of alarm event, range[1, no-limited] with unit of second(s).[default: %default]", dest="intervalshift")
    optionalGroup.add_option("-d", "--duration", action="store", type="int", default = "1", help = "Duration of the alarm storm in unit of minute, range[1, 59].[default: %default]", dest="duration")
    optionalGroup.add_option("-r", "--round", action="store", type="int", default = "1", help = "Specify the frequency of the alarm storm, there will be a alarm storm every two hours if you specify '-R 2'.[default: %default]", dest="round")
    parser.add_option_group(optionalGroup)
    
    (options, args) = parser.parse_args()
    #print options
    if(options.list is None):
        print "Please use '-L' to specify the alarm that you want to send, this command option is mandatory!"
        print parser.print_help()
        writeLog("Please use '-L' to specify the alarm that you want to send, this command option is mandatory!")
        return 1, "Please use '-L' to specify the alarm that you want to send, this command option is mandatory!"
    else:
        msg = "Get the command options successfully, options: " + str(options)
        writeLog(msg)
        #print msg
        options.interval = bounderCheck(options.interval, 1.0, 100.0)
        #options.interval = modifyTimes(options.interval, 1, 100, 3, 26)
        options.interval = options.interval * (1 + options.interval / 1000.0)
        options.intervalshift = bounderCheck(options.intervalshift, 1)
        options.duration = bounderCheck(options.duration, 1, 55)
        options.round = bounderCheck(options.round, 1)
        options.many = checkSendTypes(options.many)
        options.waitingtime = bounderCheck(options.waitingtime, 1)
        return 0, options

#检查整数数值的合法性
def bounderCheck(i, lowBound = None, upBonder = None):
    if lowBound is not None:
        if i < lowBound:
            i = lowBound
    if upBonder is not None:
        if i > upBonder:
            i = upBonder
    return i

#检查命令选项mode的数值的合法性。
def checkSendTypes(many):
    if(many != "n" and many != "m" and many != "s" and many != "c"):
        return "n"
    else:
        return many

#初始化log文件
def startLog():
    global logfile
    nowtime = pydate.datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
    try:
        log_file_path = os.path.normpath(os.path.dirname(os.path.realpath(__file__)) + os.path.sep + "log" + os.path.sep + "sendtrap.log")
        if(os.path.isfile(log_file_path)):
            str_time = pydate.datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
            log_file_path_new = log_file_path + "." + str_time
            shutil.copyfile(log_file_path, os.path.normpath(log_file_path_new))
        logfile = open(log_file_path, 'wb')
        print "Log file stored as: " + log_file_path
    except Exception as e:
        print e.message
    writeLog("Start to log:")
    #print "Start to log:"

#结束记录日志并释放指针
def stopLog():
    global logfile
    try:
        time.sleep(0.02)
        writeLog("Finish the log.")
        logfile.close()
        #print "Finish the log."
    except Exception as e:
        print e.message

#写日志
def writeLog(str):
    global logfile
    timeStamp = pydate.datetime.now().strftime("%Y-%m-%d %H.%M.%S.%f")
    logfile.write(timeStamp + "\t" + str + "\r\n")
    logfile.flush()
    
    log_file_path = os.path.normpath(os.path.dirname(os.path.realpath(__file__)) + os.path.sep + "log" + os.path.sep + "sendtrap.log")
    if(os.path.getsize(log_file_path) > 10485760):
        msg = "the size of log file is more than 10M, will backup the log file now..."
        timeStamp = pydate.datetime.now().strftime("%Y-%m-%d %H.%M.%S.%f")
        logfile.write(timeStamp + "\t" + msg + "\r\n")
        logfile.flush()
        
        logfile.close()
        str_time = pydate.datetime.now().strftime("%Y-%m-%d_%H:%M%S:%f")
        log_file_path_new = log_file_path + "." + str_time
        shutil.copyfile(log_file_path, log_file_path_new)
        try:
            logfile = open(log_file_path, 'wb')
            msg = "Log file stored as: " + log_file_path
            writeLog(msg)
            print msg
        except Exception as e:
            print "try to creat new log file failed...."

#将-l制定的告警从告警模板中读取并存储为list，其中如果制定-t，将会修改模板中的告警时间戳
def initTrapInformation(strMap, option):
    global oidTimeStamp
    global oidAlarmIDs
    arrInfo = []
    alarmList = option.list.split(",")
    #if using custom time stamp
    bCustom = False
    timeUsed = None
    timeDel = pydate.timedelta(seconds = 0)
    if (option.timeofevent != ""):
        if(option.timeofevent == "now"):
            timeUsed = pydate.datetime.now()
            msg = "Will use current time as the alarm time."
            writeLog(msg)
            print msg
        else:
            bCustom = True
            timeUsed = pydate.datetime.strptime(option.timeofevent, "%Y-%m-%d %H:%M:%S")
            timeDel = pydate.timedelta(seconds = option.intervalshift)
            msg = "Will use user specified time as alarm time: " + option.timeofevent
            writeLog(msg)
            print msg
    else:
        msg = "Will use the time in alarm definition file as the alarm time."
        writeLog(msg)
        print msg          

    for iAlarm in alarmList:
        try:
            fileName = strMap[iAlarm]
            path = os.path.normpath(os.getcwd() + os.path.sep + "alarms" + os.path.sep + fileName)
            if(not os.path.isfile(path)):
                msg = "Cannot find the alarm definition file: " + path
                writeLog(msg)
                print msg
            else:
                try:
                    #Store the information of time stamp of the alarm information
                    oidOfTime = []
                    #Store the information of Alarm ID
                    alarmIdInfo = []
                    #Store the information of OID
                    arrOid = []
                    #Store other 
                    otherStuff = []
                    f = open(path, 'r+')
                    lineNo = 0
                    for line in f.readlines():
                        lineInfo = line.split(" : ")
                        if(len(lineInfo) < 2):
                            msg = "The format of Alarm definition file is wrong, file is: " + path
                            writeLog(msg)
                            print msg
                            return 3, "Wrong File Format!"
                        else:
                            oid = lineInfo[0].strip()
                            oidInfo = lineInfo[1].strip()
                            if(lineNo == 0):
                                arrOid.append(oidInfo)
                            else:
                                if(oid in oidTimeStamp):
                                    if(not bCustom):
                                        i, s = getHexFromStr(oidInfo)
                                        if(i > 0):
                                            msg = "Time format in alarm file is wrong, file is: " + path
                                            writeLog(msg)
                                            print msg
                                            return 4, "Wrong Time Format!"
                                        else:
                                            oidOfTime.append(oid)
                                            oidOfTime.append(s)
                                    else:
                                        i, s = getHexFromStr(timeUsed.strftime("%Y-%m-%d %H:%M:%S"))
                                        oidOfTime.append(oid)
                                        oidOfTime.append(s)
                                        timeUsed = timeUsed + timeDel
                                elif(oid in oidAlarmIDs):
                                    alarmIdInfo.append(oid)
                                    alarmIdInfo.append(oidInfo)
                                else:
                                    if(oidInfo.isdigit()):
                                        otherStuff.append(("i", oid, oidInfo))
                                    else:
                                        otherStuff.append(("s", oid, oidInfo))
                            lineNo += 1
                    arrInfo.append((arrOid, oidOfTime, alarmIdInfo, otherStuff))
                    msg = "Alarm info, alarm OID: " + str(arrOid) + ", alarm time: " + str(oidOfTime) + ", other info: " + str(otherStuff) + "."
                    writeLog(msg)
                    #print msg
                except Exception as e:
                    msg = e.message
                    writeLog(msg)
                    print msg
                    return 2, "Open File Error!"
        except Exception as e:
            msg = "You have inputed the wrong alarm ID, " + e.message
            writeLog(msg)
            print msg
            return 1, "Key Not Found."
    return 0, arrInfo

#将当前时间转换为十六进制时间戳
def getHexNow(nowtime = None):
    hexValue = ""
    directionFromUTC = hoursFromUTC = minutesFromUTC = zone = None
    t = time.time()
    if(time.localtime(t).tm_isdst and time.daylight):
        zone = time.altzone
    else:
        zone = time.timezone
    
    #Direction from UTC
    if zone < 0:
        directionFromUTC = '+'
    else:
        directionFromUTC = '-'    
    
    #Hours and minutes from UTC
    hoursFromUTC = zone / -(60*60)
    minutesFromUTC = -1 * (zone % 60)

    #Get the time of now
    if(nowtime is None):
        nowtime = pydate.datetime.now()
    dt = nowtime
    #Get the year formated
    high, low = divmod(dt.year, 256)
    if high < 16:
        hexValue += "0"
    hexValue += format(high, 'x')
    if low < 16:
        hexValue += "0"
    hexValue += format(low, 'x')
    
    #Format month
    hexValue += "0" + format(dt.month, 'x')
    
    #Format day
    if dt.day < 16:
        hexValue += "0"
    hexValue += format(dt.day, 'x')   
    
    #Format hour, minute, second
    if dt.hour < 16:
        hexValue += "0"
    hexValue += format(dt.hour, 'x')
    if dt.minute < 16:
        hexValue += "0"
    hexValue += format(dt.minute, 'x')
    if dt.second < 16:
        hexValue += "0"
    hexValue += format(dt.second, 'x')
    
    #Format the Deli second
    deli_sec = int(round(dt.microsecond / 10000))
    if(deli_sec < 16):
        hexValue += "0"
    hexValue += format(deli_sec, 'x')
    #Direction
    hexValue += format(ord(directionFromUTC), 'x')
    #Hour from UTC
    hexValue += "0" + format(hoursFromUTC, 'x')
    #Minute from UTC
    if minutesFromUTC < 16:
        hexValue += "0"
    hexValue += format(minutesFromUTC, 'x')
    return 0, hexValue

#普通模式发送告警
def sendTrapNormalMode(options, arrTraps):
    global alarm_counter
    initTarget(options.host, "LIC_OSS", options.port)
    
    bCusTime = True
    if(options.timeofevent == ""):
        bCusTime = False
    
    for oid, trap in arrTraps:
        if(not bCusTime):
            i, s = getHexNow()
            trap[1][1] = v2c.OctetString(hexValue = s)
        
        #trap[2][1] = v2c.Gauge32(alarm_counter)
        trap[2][1] = getAlarmId(trap[2][0], alarm_counter, True)
        sendTrap(oid[0], trap)
        alarm_counter += 1
        if(alarm_counter > 4294967295):
            alarm_counter = 0
        time.sleep(options.waitingtime)
    writeCounterBak()

#Send clear alarms sendTrapClear
def sendTrapClear(options, arrTraps):
    global alarm_counter
    initTarget(options.host, "LIC_OSS", options.port)
    
    bCusTime = True
    if(options.timeofevent == ""):
        bCusTime = False
    
    for oid, trap in arrTraps:
        if(not bCusTime):
            i, s = getHexNow()
            trap[1][1] = v2c.OctetString(hexValue = s)
        
        #trap[2][1] = v2c.Gauge32(alarm_counter)
        alarm_counter -= 1
        trap[2][1] = getAlarmId(trap[2][0], alarm_counter, True)
        sendTrap(oid[0], trap)
        time.sleep(options.waitingtime)

def busy_wait(dt):
    ct = pydate.datetime.now()
    while(pydate.datetime.now() < ct + pydate.timedelta(microseconds = dt)):
        pass

#风暴模式发送告警
def sendTrapManyMode(options, arrTraps):
    global alarm_counter
    initTarget(options.host, "LIC_OSS", options.port)
    iIndex = len(arrTraps)
    rounds = options.round
    duration = options.duration
    counter = 0
    sleeptime = 1000.0 / options.interval
    #print sleeptime
    for r in range(0, rounds):
        timeDel = pydate.timedelta(minutes = duration)
        #timeDel = pydate.timedelta(seconds = 2)
        starTime = pydate.datetime.now()
        endTime = starTime + timeDel
        jIndex = 0
        while(pydate.datetime.now() < endTime):
            #timerstart = pydate.datetime.now()
            oid = arrTraps[jIndex][0]
            trap = arrTraps[jIndex][1]
            jIndex += 1
            if(jIndex >= iIndex):
                jIndex = 0
            i, s = getHexNow()
            #alarmLog = ""
            if(i != 0):
                msg = "Get the hex value of the real time failed, please check the code!"
                print msg
                writeLog(msg)
            else:
                trap[1][1] = v2c.OctetString(hexValue = s)
                #trap[2][1] = v2c.Gauge32(alarm_counter)
                trap[2][1] = getAlarmId(trap[2][0], alarm_counter, True)
                counter += 1
                sendTrap(oid[0], trap, 0, counter)
                alarm_counter += 1
                if(alarm_counter > 4294967295):
                    alarm_counter = 0
            #time.sleep((sleeptime - 3) / 1000.0)
            busy_wait((sleeptime - 3) * 1000)
        #The deviation of the non real time OS is about 7ms.
        time.sleep(options.waitingtime)

    msg = "Finished to send " + str(counter) + " pieces of alarms in " + str(rounds * duration * 60) + " seconds, " + str(round( counter /(rounds * duration * 60.0), 2 )) + " pieces alarms each second in average."
    print msg
    writeLog(msg)
    
    #write the counter bak
    writeCounterBak()
            #print (options.interval / 1000.0)
        #time.sleep(options.waitingtime)

#特殊模式发送告警
def sendTrapSpecialModeOne(options, arrTraps):
    global alarm_counter
    initTarget(options.host, "LIC_OSS", options.port)
    iIndex = len(arrTraps)
    rounds = options.round
    duration = options.duration
    counter = 0
    sleeptime = 1000.0 / options.interval
    #print sleeptime
    for r in range(0, rounds):
        timeDel = pydate.timedelta(minutes = duration)
        #timeDel = pydate.timedelta(seconds = 2)
        starTime = pydate.datetime.now()
        endTime = starTime + timeDel
        jIndex = 0
        while(pydate.datetime.now() < endTime):
            #timerstart = pydate.datetime.now()
            oid = arrTraps[jIndex][0]
            trap = arrTraps[jIndex][1]
            jIndex += 1
            if(jIndex >= iIndex):
                jIndex = 0
            i, s = getHexNow()
            #alarmLog = ""
            if(i != 0):
                msg = "Get the hex value of the real time failed, please check the code!"
                print msg
                writeLog(msg)
            else:
                trap[1][1] = v2c.OctetString(hexValue = s)
                #trap[2][1] = v2c.Gauge32(alarm_counter)
                trap[2][1] = getAlarmId(trap[2][0], alarm_counter, True)
                sendTrap(oid[0], trap, 0, counter)
                counter += 1
                if((counter + 1) % (iIndex) != 0):
                    alarm_counter += 1
                    if(alarm_counter > 4294967295):
                        alarm_counter = 0
            #time.sleep((sleeptime - 3) / 1000.0)
            busy_wait((sleeptime - 3) * 1000)   
        #The deviation of the non real time OS is about 7ms.
        time.sleep(options.waitingtime)

    msg = "Finished to send " + str(counter) + " pieces of alarms in " + str(rounds * duration * 60) + " seconds, " + str(round( counter /(rounds * duration * 60.0), 2 )) + " pieces alarms each second in average."
    print msg
    writeLog(msg)
    
    #write the counter bak
    writeCounterBak()
    
    
    '''for oid, trap in arrTraps:
        i, s = getHexNow()
        if(i != 0):
            msg = "Get the hex value of the real time failed, please check the code!"
            print msg
            writeLog(msg)
        else:
            trap[1][1] = v2c.OctetString(hexValue = s)
            sendTrap(oid[0], trap)
            time.sleep(options.interval / 1000)'''

def writeCounterBak():
    global alarm_rec_path, alarm_counter
    try:
        open(alarm_rec_path, 'w').close()
        f = open(alarm_rec_path, 'w')
        f.write("counter = " + str(alarm_counter))
        f.flush()
        f.close()
        msg = "Writing the counter value back to the file successfully."
        print msg
        writeLog(msg)
    except Exception as e:
        msg = e.message

def getAlarmId(given_oid, alarm_id, need_prefix = False):
    global oidAlarmIDsPrefix
    if(given_oid in oidAlarmIDsPrefix):
        if(need_prefix):
            today = pydate.datetime.now().strftime("%Y%m%d")
            return v2c.OctetString(today + str(alarm_id))
        else:
            return v2c.OctetString(alarm_id)
    else:
        return v2c.Gauge32(alarm_id)

if __name__ == '__main__':
    #global glb_options
    glb_options = None
    try:
        startLog()
        i, s = initMapping()
        j, t = initCounter()
        if(i == 0 and j == 0):
            iP,iS = parseOptions()
            if(iP == 0):
                glb_options = iS
                if(iS.timeofevent != "" and iS.timeofevent.lower() != "now"):
                    try:
                        timeEvent = pydate.datetime.strptime(iS.timeofevent, "%Y-%m-%d %H:%M:%S")
                    except Exception as e:
                        iS.timeofevent = ""
                        msg = "The alarm event time you have input is in wrong format, will use the time stamp in file instead."
                        writeLog(msg)
                        print msg
                iInfo, sInfo = initTrapInformation(mappings, iS)
                #print str(sInfo)
                if(iInfo == 0):
                    msg = "Try to initial the trap information."
                    writeLog(msg)
                    #print msg
                    arrTraps = []
                    for oid, trapTime, alarmId, arr in sInfo:
                        trapInfo = []
                        trapInfo.append((('1.3.6.1.2.1.1.3.0'), v2c.Gauge32(0)))
                        hexList = []
                        hexList.append(trapTime[0])
                        #print trapTime[1]
                        sttt = v2c.OctetString(hexValue=trapTime[1])
                        hexList.append(v2c.OctetString(hexValue=trapTime[1]))
                        trapInfo.append(hexList)
                        
                        #Format the alarm ID info
                        alarmIdList = []
                        alarmIdList.append(alarmId[0])
                        #alarmIdList.append(v2c.Gauge32(alarmId[1]))
                        alarmIdList.append(getAlarmId(alarmId[0], alarmId[1]))
                        trapInfo.append(alarmIdList)
                        
                        #trapInfo.append(((trapTime[0]), v2c.OctetString(hexValue=trapTime[1])))
                        for info in arr:
                            if(info[0] == "i"):
                                trapInfo.append(((info[1]), v2c.Gauge32(info[2])))
                            elif(info[0] == "s"):
                                trapInfo.append(((info[1]), v2c.OctetString(bytearray(info[2]))))
                        arrTraps.append((oid, trapInfo))
                    msg = "Trap information format successfully: " + str(arrTraps)
                    writeLog(msg)
                    #print msg
                    if(iS.many == "m"):
                        msg = "We will simulate to send alarm in real time and alarm storm mode!"
                        writeLog(msg)
                        print msg
                        sendTrapManyMode(iS, arrTraps)
                        #print "We are now in alarm storm mode!"
                    elif(iS.many == "n"):
                        msg = "We will simulate to send alarm in normal mode."
                        writeLog(msg)
                        print msg
                        sendTrapNormalMode(iS, arrTraps)
                    elif(iS.many == "s"):
                        print "We are now in special mode!"
                        sendTrapSpecialModeOne(iS, arrTraps)
                    elif(iS.many == "c"):
                        print "We are now in special mode!"
                        sendTrapClear(iS, arrTraps)
        stopLog()
    except KeyboardInterrupt:
        if(glb_options is None or glb_options.many == "n"):
            msg = "Keyboard interrupt event captured, exiting now!"
            print msg
            writeLog(msg)
        else:
            msg = "Keyboard interrupt event captured, will write the counter value to the counter record file."
            print msg
            writeLog(msg)
            writeCounterBak()
            
        
