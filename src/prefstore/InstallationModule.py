"""
Created on 12 April 2011
@author: jog
"""

from new import * #@UnusedWildImport
import json
import base64
import random
import MySQLdb
import hashlib
import logging
import urllib2
import urllib
import re

#setup logger for this module
log = logging.getLogger( "console_log" )

#///////////////////////////////////////////////


class ParameterException ( Exception ):
    def __init__(self, msg):
        self.msg = msg

#///////////////////////////////////////////////  


class CatalogException ( Exception ):
    def __init__(self, msg):
        self.msg = msg

        
#///////////////////////////////////////////////

        
class InstallationModule( object ) :
    

    #///////////////////////////////////////////////
    
    
    def __init__( self, resource_name, redirect_uri, datadb, web_proxy = None ):
        
        self.db = datadb;
        self.resource_name = resource_name
        self.redirect_uri = redirect_uri
        self.web_proxy = web_proxy  

         
    #///////////////////////////////////////////////

    def is_valid_uri( self, uri ):
        
        print "uri=%s" % ( uri, )
        if not uri: return False
        
        regex = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE )
        
        return regex.search( uri )


    #///////////////////////////////////////////////


    def resource_register( self, catalog_uri ):
    
        #--------------------------------
        # Invariance Check Parameters
        #--------------------------------
        
        #check that a valid catalog_uri has been supplied
        if not self.is_valid_uri( catalog_uri ):
            raise ParameterException( "invalid catalog URI" )
    
        #also confirm that its and endpoint (not a directory)
        if catalog_uri[-1] == "/":
            raise ParameterException( "catalog URI must not end with /" )
        
        #determine if we have already registered at this resource
        #TODO: Sort out the database    
        
        #--------------------------------
        # Communicate with the catalog
        #--------------------------------
        
        #if necessary setup a proxy
        if ( self.web_proxy  ):
            proxy = urllib2.ProxyHandler( self.web_proxy )
            opener = urllib2.build_opener( proxy )
            urllib2.install_opener( opener )
        
        #first communicate with the resource provider   
        try:
            data = urllib.urlencode({
                'resource_name': self.resource_name,
                'redirect_uri': self.redirect_uri, })
            url = "%s/resource_register" % ( catalog_uri, )
            req = urllib2.Request( url, data )
            response = urllib2.urlopen( req )
            output = response.read()
    
        except urllib2.URLError:
            raise CatalogException( "Could not contact supplied catalog" )
        
        #--------------------------------
        # Parse the Registration results
        #--------------------------------
        
        #parse the json response from the provider
        try:
            output = json.loads( output.replace( '\r\n','\n' ), strict=False )
        except:
            raise CatalogException( "Invalid json returned by catalog" )
    
        #determine whether the registration has been successful
        try:
            success = output[ "success" ]
        except:
            raise CatalogException( "Catalog has not returned successfully" )
    
        #if it has then extract the access_token that will be used
        if not success:
            try:
                error = "%s: %s" % ( output[ "error" ], output[ "error_description" ], )
            except:
                error = "Unknown problems at catalog accepting request"
                
            raise CatalogException( error );
        
        #attempt to extract the resource_id
        try:
            resource_id = output[ "resource_id" ]
        except:
            raise CatalogException( "Catalog failed to return resource id" ) 
        
        #store the results
        #TODO: STORE THE RESULTS
        #state = datadb.insert_catalog( user_id, catalog_uri )
        #datadb.commit()
            
        #and with victory ensured, continue onwards...
        return resource_id

            
    #///////////////////////////////////////////////

             
    def generateAccessToken( self ):
        
        token = base64.b64encode(  
            hashlib.sha256( 
                str( random.getrandbits( 256 ) ) 
            ).digest() 
        )  
            
        #replace plus signs with asterisks. Plus signs are reserved
        #characters in ajax transmissions, so just cause problems
        return token.replace( '+', '*' ) 

        
    
    