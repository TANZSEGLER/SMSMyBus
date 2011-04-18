import os
import wsgiref.handlers
import logging
import time
import re

from google.appengine.api import users
from google.appengine.api import datastore_errors
from google.appengine.api.urlfetch import DownloadError
from google.appengine.api.labs import taskqueue
from google.appengine.api.labs.taskqueue import Task
from google.appengine.ext import webapp
from google.appengine.ext import db

from google.appengine.runtime import apiproxy_errors

from django.utils import simplejson

from api.v1 import utils
from api import asynch

from data_model import *

class MainHandler(webapp.RequestHandler):
    # POST not support by the API
    def post(self):
        self.response.headers['Content-Type'] = 'application/javascript'
        self.response.out.write(simplejson.dumps(utils.buildErrorResponse('-1','The API does not support POST requests')))
        return
    
    def get(self):
      
      # validate the request parameters
      devStoreKey = validateRequest(self.request)
      if devStoreKey is None:
          logging.error("failed to validate the request paramters")
          self.response.headers['Content-Type'] = 'application/javascript'
          self.response.out.write(simplejson.dumps(utils.buildErrorResponse('-1','Illegal developer key received')))
          return
      
      # snare the inputs
      stopID = self.request.get('stopID')
      routeID = self.request.get('routeID')
      vehicleID = self.request.get('vehicleID')
      logging.debug('getarrivals request parameters...  stopID %s routeID %s vehicleID %s' % (stopID,routeID,vehicleID))
      
      # stopID requests...
      if stopID is not '' and routeID is '':
          json_response = stopRequest(stopID, devStoreKey)
          utils.recordDeveloperRequest(devStoreKey,utils.GETARRIVALS,self.request.query_string,self.request.remote_addr);
      elif stopID is not '' and routeID is not '':
          json_response = stopRouteRequest(stopID, routeID, devStoreKey)
          utils.recordDeveloperRequest(devStoreKey,utils.GETARRIVALS,self.request.query_string,self.request.remote_addr);
      elif routeID is not '' and vehicleID is not '':
          json_response = routeVehicleRequest(routeID, vehicleID, devStoreKey)
          utils.recordDeveloperRequest(devStoreKey,utils.GETVEHICLE,self.request.query_string,self.request.remote_addr);
      else:
          logging.debug("API: invalid request")
          utils.recordDeveloperRequest(devStoreKey,utils.GETARRIVALS,self.request.query_string,self.request.remote_addr,'illegal query string combination');
          json_response = utils.buildErrorResponse('-1','Invalid Request parameters')

      # encapsulate response in json or jsonp
      logging.debug('API: json response %s' % json_response);

      callback = self.request.get('callback')
      if callback is not '':
          self.response.headers['Content-Type'] = 'application/javascript'
          self.response.headers['Access-Control-Allow-Origin'] = '*'
          self.response.headers['Access-Control-Allow-Methods'] = 'GET'
          response = callback + '(' + simplejson.dumps(json_response) + ');'
      else:
          self.response.headers['Content-Type'] = 'application/json'
          response = simplejson.dumps(json_response)
      
      self.response.out.write(response)

## end RequestHandler

def validateRequest(request):
    
    # validate the key
    devStoreKey = utils.validateDevKey(request.get('key'))
    if devStoreKey is None:
        utils.recordDeveloperRequest(None,utils.GETARRIVALS,request.query_string,request.remote_addr,'illegal developer key specified');
        return None
    stopID = request.get('stopID')
    routeID = request.get('routeID')
    vehicleID = request.get('vehicleID')
    
    # a stopID or routeID is required
    if stopID is None and routeID is None:
        utils.recordDeveloperRequest(devStoreKey,utils.GETARRIVALS,request.query_string,request.remote_addr,'either a stopID or a routeID must be included');
        return None
    
    # the routeID requires either a vehicleID or stopID
    if routeID is not None:
        if vehicleID is None and stopID is None:
            utils.recordDeveloperRequest(devStoreKey,utils.GETARRIVALS,request.query_string,request.remote_addr,'if routeID is specified, either a vehicleID or stopID is required');
            return None
    
    # the vehicleID requires a routeID
    if vehicleID is not None:
        if routeID is None:
            utils.recordDeveloperRequest(devStoreKey,utils.GETVEHICLE,request.query_string,request.remote_addr,'if a vehicleID is specified, you must include a routeID');
            return False
        
    logging.debug("successfully validated command parameters")
    return devStoreKey

## end validateRequest()

def stopRequest(stopID, devStoreKey):

    logging.debug("Stop Request started")
    response_dict = {'status':'0',
                     'timestamp':utils.getLocalTimestamp()
                     }    
    
    # @todo the really busy stops have their data cached. hook this up
    # q = db.GqlQuery("SELECT * FROM LiveRouteStatus WHERE stopID = :1 ORDER BY dateAdded DESC LIMIT 24", stopID)
    # routes = q.fetch(24)
    
    # got fetch all of the data for this stop
    sid = stopID + str(devStoreKey) + str(time.time())
    routes = asynch.aggregateBusesAsynch(sid,stopID)

    # get the stop details
    stop_dict = {'stopID':stopID,}
    
    # take the first 10 results. we assume the results are sorted by time
    #route_results = sorted(route_results, key=attrgetter('time'))
    route_results = []
    for r in routes:
        minutes = utils.computeCountdownMinutes(r.arrivalTime)
        if minutes > 0:
            route_results.append(dict({'routeID':r.routeID,
                          'vehicleID':'unknown',
                          'minutes':str(minutes),
                          'arrivalTime':r.arrivalTime,
                          'destination':r.destination,
                          }))            
    
    # add the populated stop details to the response
    stop_dict.update({'route':route_results});
    response_dict.update({'stop':stop_dict})
        
    return response_dict

## end stopRequest()


def stopRouteRequest(stopID, routeID, devStoreKey):
    logging.debug("Stop/Route Request started")

    # got fetch all of the data for this stop
    sid = stopID + str(devStoreKey) + str(time.time())
    routes = asynch.aggregateBusesAsynch(sid,stopID,routeID)
    if routes is None:
        response_dict = {'status':'0',
                         'timestamp':utils.getLocalTimestamp(),
                         'info':'No routes found'
                        }
        return response_dict
    
    # query the live route store by stopID
    #q = db.GqlQuery("SELECT * FROM LiveRouteStatus WHERE stopID = :1 and routeID = :2 ORDER BY dateAdded DESC LIMIT 3", stopID, routeID)
    #routes = q.fetch(3)

    response_dict = {'status':'0',
                     'timestamp':utils.getLocalTimestamp()
                     }    
    
    # there should only be results. we assume the results are sorted by time
    stop_dict = {'stopID':stopID,}
    route_results = []
    for r in routes:
        if not utils.inthepast(r.arrivalTime):
            route_results.append(dict({'routeID':r.routeID,
                          'vehicleID':'unknown',
                          'minutes':str(utils.computeCountdownMinutes(r.arrivalTime)),
                          'arrivalTime':r.arrivalTime,
                          'destination':r.destination,
                          }))
    
    # add the populated stop details to the response
    stop_dict.update({'route':route_results});
    response_dict.update({'stop':stop_dict})
        
    return response_dict

## end stopRouteRequest()

def routeVehicleRequest(routeID, vehicleID, devStoreKey):
    logging.debug("Route/Vehicle Request started for %s, route %s vehicle %s" % (devStoreKey,routeID,vehicleID))
    
    # encapsulate response in json
    return {'status':'-1',
            'timestamp':getLocalTimestamp(),
            'description':'Vehicle requests calls are not yet supported',
           }

## end stopRouteRequest()


class DevKeyHandler(webapp.RequestHandler):
    def get(self,key=""):
        if key == "":
          logging.error("Illegal access to dev key handler - missing key");
          return

        dev = DeveloperKeys()
        dev.developerName = "Testing"
        dev.developerKey = key
        dev.developerEmail = "gtracy@gmail.com"
        dev.requestCounter = 0
        dev.errorCounter = 0
        dev.put()
        
## end DevKeyHandler


def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([('/api/v1/getarrivals', MainHandler),
                                        ('/api/v1/createdevkey/(.*)', DevKeyHandler),
                                        ],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
