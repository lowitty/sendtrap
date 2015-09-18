#encoding=utf-8
import time
import datetime as pydate

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


if __name__ == '__main__':
    l, m = getHexNow()
    print m
    #funca()
    #funcb()
    #glb = glb + 4
    #print glb
    '''print "main: " + str(glb)
    funca()
    print "main: " + str(glb)
    funcb()
    pass'''



