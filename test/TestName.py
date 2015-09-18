'''
Created on Jan 9, 2015

@author: yang
'''

import time
import datetime as pydate

import sys
import os.path
from sys import path


if __name__ == '__main__':
    print "Hello"
    #print os.path.dirname(__file__)

    '''sched = Scheduler()
    sched.start()

    def some_job():
        print "Every 10 seconds"

    sched.add_interval_job(some_job, seconds = 10)

    sched.shutdown()'''
    
    
    
    #print getHexNow()
    ''''i, s = getHexFromStr('2015-01-01 01:01:01', 687776)
    print i
    print s
    print format(100, 'x')
    pass'''



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
        #writeLog(msg)
        return 1, "Time format error!"
        
    high, low = divmod(dt.year, 256)
    if high < 16:
        hexValue += "0"
    hexValue += format(high, 'x')
    if low < 16:
        hexValue += "0"
    hexValue += format(low, 'x')
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
    #deli-second
    hexValue += "0" + format(int(round(delisecond / 10000)), 'x')
    
    hexValue += format(ord(directionFromUTC), 'x')
    hexValue += "0" + format(hoursFromUTC, 'x')
    if minutesFromUTC < 16:
        hexValue += "0"
    hexValue += format(minutesFromUTC, 'x')
    return 0, hexValue


