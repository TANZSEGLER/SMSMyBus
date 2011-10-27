import os
import logging
import time
import re

from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.datastore import entity_pb

from data_model import DeveloperRequest

def validateDevKey(devKey):

    if devKey is None:
        return None
   
    storeKey = memcache.get(devKey)
    if storeKey is None:
        q = db.GqlQuery("SELECT __key__ FROM DeveloperKeys WHERE developerKey = :1", devKey)
        storeKey = q.get()
        if storeKey is None:
            # @todo we can create a black list for abusive keys to avoid the
            #   datastore query all together if this becomes a problem
            logging.debug('API : illegal access using devkey %s' % devKey)
            return None
        else:
            logging.debug('API : devkey cache miss!')
            memcache.set(devKey, storeKey)
    
    # we've validated the dev key at this point... start counting requests
    total = memcache.incr(devKey + ':counter', initial_value=0)
    return storeKey
    
## end validateDevKey()

def conformStopID(stopID):

    # we assume the stopID is four characters long. if we find it is
    # less than that, pad the front-end of it with zeros.
    if len(stopID) < 4:
    	if len(stopID) == 2:
    	    stopID = "00" + stopID
    	elif len(stopID) == 1:
    	    stopID = "000" + stopID
    	else:
    	    stopID = "0" + stopID
    
    return stopID
    
## end conformStopID()

def inthepast(time):
    
    if computeCountdownMinutes(time) < 0:
        return True
    else:
        return False
    
## end inthepast


def getLocalTimestamp():
    
    # get the local, server time
    ltime = time.localtime()
    ltime_hour = ltime.tm_hour - 5  # convert to madison time
    ltime_hour += 24 if ltime_hour < 0 else 0
    ltime_min = ltime_hour * 60 + ltime.tm_min
    #logging.debug("local time... %s (%s:%s) day minutes %s" % (ltime,ltime_hour,ltime.tm_min,ltime_min))
    
    tstamp_min = str(ltime.tm_min) if ltime.tm_min >= 10 else ("0"+str(ltime.tm_min))
    tstamp_hour = str(ltime_hour) if ltime_hour <=12 else str(ltime_hour-12)
    tstamp_label = "pm" if ltime_hour > 11 else "am"

    return(tstamp_hour+':'+tstamp_min+tstamp_label)

## end getLocalTimestamp()

def computeCountdownMinutes(arrivalTime):

    # compute current time in minutes
    ltime = time.localtime()
    ltime_hour = ltime.tm_hour - 5
    ltime_hour += 24 if ltime_hour < 0 else 0
    ltime_min = ltime_hour * 60 + ltime.tm_min
    #logging.debug("local time: %s hours, or %s minutes"  % (ltime_hour,ltime_min))
    
    # pull out the arrival time
    #logging.debug("API: parsing arrival time of %s" % arrivalTime)
    m = re.search('(\d+):(\d+)\s(.*?)',arrivalTime)
    btime_hour = arrival_hour = int(m.group(1))
    btime_hour += 12 if arrivalTime.find('pm') > 0 and arrival_hour < 12 else 0
    btime_min = btime_hour * 60 + int(m.group(2))
    #logging.debug("computing countdown with %s. %s hours %s minutes" % (arrivalTime,btime_hour,btime_min))
                  
    delta_in_min = btime_min - ltime_min
    #logging.debug('API: countdown is %s minutes'% delta_in_min)
    return(delta_in_min)

## end computeCountdownMinutes()

def buildErrorResponse(error,description):
      # encapsulate response in json
      response_dict = {'status':error,
                       'timestamp':getLocalTimestamp(),
                       'description':description,
                       }
      return response_dict
            
## end jsonError()    

# Checks to see if the current time is during the hours
# in which the Metro doesn't operate
#
def afterHours():
      ltime = time.localtime()
      ltime_hour = ltime.tm_hour - 5
      ltime_hour += 24 if ltime_hour < 0 else 0
      if ltime_hour > 1 and ltime_hour < 6:
	      return True
      else:
          return False
## end afterHours()

def getDirectionLabel(directionID):
    directionLabel = memcache.get(directionID)
    if directionLabel is None:
        q = db.GqlQuery("SELECT * FROM DestinationListing WHERE id = :1", directionID)
        directionQuery = q.fetch(1)
        if len(directionQuery) > 0:
            #logging.debug("Found destination ID mapping... %s :: %s" % (directionQuery[0].id,directionQuery[0].label))
            directionLabel = directionQuery[0].label
            memcache.set(directionID, directionLabel)
        else:
            logging.error("ERROR: We don't have a record of this direction ID!?! Impossible! %s" % directionID)
            directionLabel = "unknown"
            
    return directionLabel

## end getDirectionLabel()

GETARRIVALS = "get arrivals"
GETVEHICLE = "get vehicle"
GETSTOPS = "get stops"
GETNEARBYSTOPS = "get nearby stops"

def recordDeveloperRequest(devKey,type,terms,ipaddr,error='success'):

    # this is too damn expensive to store all of these on app engine
    # so we're going to ignore these requests
    if False:
      req = DeveloperRequest()
      req.developer = devKey
      req.type = type
      req.error = error
      req.requestTerms = terms
      req.remoteAddr = ipaddr
      req.put()

## end recordDeveloperRequest()



def serialize_entities(models):
    if models is None:
        return None
    elif isinstance(models, db.Model):
        # Just one instance
        return db.model_to_protobuf(models).Encode()
    else:
        # A list
        return [db.model_to_protobuf(x).Encode() for x in models]

def deserialize_entities(data):
    if data is None:
        return None
    elif isinstance(data, str):
        # Just one instance
        return db.model_from_protobuf(entity_pb.EntityProto(data))
    else:
        return [db.model_from_protobuf(entity_pb.EntityProto(x)) for x in data]
        
        