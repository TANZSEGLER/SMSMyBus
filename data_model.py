from google.appengine.ext import db
from geo.geomodel import GeoModel

class PhoneLog(db.Model):
  phone       = db.StringProperty()
  date        = db.DateTimeProperty(auto_now_add=True)
  body        = db.StringProperty(multiline=True,indexed=False)
  smsID       = db.StringProperty(indexed=False)
  outboundSMS = db.StringProperty(multiline=True,indexed=False)
## end phoneLog

# note that a stop extends GeoModel   
class StopLocation(GeoModel):
    stopID       = db.StringProperty()
    routeID      = db.StringProperty()
    intersection = db.StringProperty()
    direction    = db.StringProperty()
## end StopLocation    


class RouteListing(db.Model):
    route        = db.StringProperty()
    direction    = db.StringProperty()
    stopID       = db.StringProperty()
    scheduleURL  = db.StringProperty(indexed=False)
    stopLocation = db.ReferenceProperty(StopLocation,collection_name="stops")    
## end RouteListing

class DestinationListing(db.Model):
    id    = db.StringProperty()
    label = db.StringProperty()
## end DestinationListing

class DeveloperKeys(db.Model):
    dateAdded      = db.DateTimeProperty(auto_now_add=True)
    developerName  = db.StringProperty()
    developerKey   = db.StringProperty()
    developerEmail = db.EmailProperty()
    requestCounter = db.IntegerProperty()
    errorCounter   = db.IntegerProperty()
## end DeveloperKeys

class DeveloperRequest(db.Model):
    developer     = db.ReferenceProperty()
    date          = db.DateTimeProperty(auto_now_add=True)
    type          = db.StringProperty()
    error         = db.StringProperty()
    requestTerms  = db.StringProperty()
    remoteAddr    = db.StringProperty()
## end DeveloperRequest

class ParseErrors(db.Model):
    dateAdded = db.DateTimeProperty(auto_now_add=True)
    intersection = db.StringProperty()
    location = db.GeoPtProperty()
    direction = db.StringProperty()
    routeID = db.StringProperty()
    stopID = db.StringProperty()
    metaStringOne = db.TextProperty()
    metaStringTwo = db.TextProperty()
    reviewed = db.BooleanProperty()
## end ParseErrors
    