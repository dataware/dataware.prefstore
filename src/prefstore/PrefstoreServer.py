"""
Created on 12 April 2011
@author: jog
"""
from __future__ import division
from WebCountUpdater import *       #@UnusedWildImport
from bottle import *                #@UnusedWildImport
from ProcessingModule import *      #@UnusedWildImport
from InstallationModule import *    #@UnusedWildImport
from DatawareDB import *            #@UnusedWildImport
from PrefstoreDB import *           #@UnusedWildImport
#from NewsDB import *           #@UnusedWildImport
import time                         #@Reimport
import OpenIDManager
import logging.handlers
import validictory
import math

#//////////////////////////////////////////////////////////
# SETUP LOGGING FOR THIS MODULE
#//////////////////////////////////////////////////////////

log = logging.getLogger( "console_log" )
data_log = logging.getLogger( "data_log" )

class std_writer( object ):
    def __init__( self, msg ):
        self.msg = msg
    
    def write(self, data):
        data = data.replace( '\n', '' ) \
                   .replace( '\t', '' )
        if len( data ) > 0 :
            log.error( self.msg + ": " + data )
        
                   
#//////////////////////////////////////////////////////////
# CONSTANTS
#//////////////////////////////////////////////////////////

TOTAL_WEB_DOCUMENTS = 25000000000


#//////////////////////////////////////////////////////////
# DEMO FUNCTIONS
#//////////////////////////////////////////////////////////


@route('/compare')
def compare() :

    try:
        user = check_login()
    except RegisterException, e:
        redirect( "/register" )
    except LoginException, e:
        return error( e.msg )
    except Exception, e:
        return error( e ) 
    
    #if the user doesn't exist or is not logged in,
    #then send them home. naughty user.
    if ( not user ) : redirect( ROOT_PAGE )
    
    terms = {}
    for k,v in request.GET.items():
        terms[ k.lower() ] = float( v )

    _run_compare( user[ "user_id" ], terms )
    

#///////////////////////////////////////////////

#TODO - a single term will give a value of 1!? Why?
def _run_compare( user_id, terms ) :

    parameters = { "input_doc" : terms  } 
    MAX_TERMS_IN_DOC = 90
    MIN_FREQ = 0
    MAX_FREQ = 1
    DEFAULT_IDF = 7

    input_doc = parameters[ 'input_doc' ]
    
    #-----------------------------------------------
    # INVARIANCE CHECKS
    #-----------------------------------------------
    #check that the input is a dictionary of terms and frequencies
    if not type( input_doc ).__name__ == 'dict':
        raise Exception( 'Invariance Check failed - input_doc is not a dictionary' )
    
    #check that the maximum no. terms isn't exceeded (100)
    if len( input_doc ) > MAX_TERMS_IN_DOC :
        raise Exception( 'Invariance Check failed - Document exceeds maximum terms limit' )
    
    #check that the term frequencies are within bounds
    #n.b. the limits of this are zero and one, but these can be changed
    #to allow a user greater privacy (i.e. max < 0.25 say)
    for v in input_doc.values():
        if v < MIN_FREQ or v > MAX_FREQ :
            raise Exception( 'Invariance Check failed - Term frequencies out of permitted bounds' ) 
    
    #check that the term frequencies do not sum to greater than one   
    if sum( [ i for i in input_doc.values() ] ) > 1.05 :
        raise Exception( 'Invariance Check failed - Term frequencies sum to a value greater than one' ) 
    
    #check that the number of terms doesn't exceed the maximum allowed.
    #n.b. this has impact on the efficiency of the IN clause in the SQL query.
    #Some databases (e.g. PostgreSQL) are purported to hard limit at 1000 terms.
    if len( input_doc ) > MAX_TERMS_IN_DOC :
        raise Exception( 'Invariance Check failed - Document exceeds maximum terms limit')


    #-----------------------------------------------
    # INITIALIZATION
    #-----------------------------------------------

    #setup some format strings required for use in SQL IN clauses
    format_strings = ',' . join( [ '%s' ] * len( input_doc ) )
    terms = list( input_doc.keys() )
    
    #We will need to know the total words in the users preference document
    query = """SELECT SUM( total_appearances ) total  
        FROM prefstore.tblTermAppearances
        WHERE user_id = %s  
    """
    prefdb.cursor.execute( query ,( user_id ) )
    row = prefdb.cursor.fetchone()
    user_doc_total_terms = row.get( 'total' )

    #check that the user actually has data to compare against
    if user_doc_total_terms == None :
        raise Exception( 'User has no preference records' )
        
    #-----------------------------------------------
    # INPUT DOCUMENT CALCULATIONS
    #-----------------------------------------------
    
    #first we need to find the idf scores for all of the input terms.
    #if we don't have information for these, we assume a default idf.
    idfs = dict( ( k, DEFAULT_IDF ) for k, v in input_doc.items() )
    
    #retrieve the true idf scores for the terms we do know  
    query = '''SELECT term, log( %s / count ) idf
        FROM prefstore.tblTermDictionary 
        WHERE term IN ( %s )
        AND count IS NOT NULL
    '''  % ( TOTAL_WEB_DOCUMENTS, format_strings )
    prefdb.cursor.execute( query, tuple( terms ) )
    result = prefdb.cursor.fetchall()
    
    #overwrite the default idfs for real ones we know
    for r in result: 
        idfs[ r.get( 'term' ) ] = r.get( 'idf' )
        

    #calculate the weight vector for the input doc
    input_doc_weights = dict( ( k, v * idfs[ k ] ) for k, v in input_doc.items() )
   
    #calculate the length (norm) of the input document vector
    input_doc_norm = math.sqrt( sum( [ (w * w) for w in input_doc_weights.values() ] ) )

    #-----------------------------------------------
    # USER DOCUMENT CALCULATIONS
    #-----------------------------------------------

    #get the term appearances from the user doc relevent to the query
    query = '''
        SELECT term, total_appearances / %s tf 
        FROM prefstore.tblTermAppearances  
        WHERE term IN ( %s ) AND user_id = %s
    ''' % ( '%s', format_strings, '%s' )

    params = tuple([ user_doc_total_terms ] + terms + [ user_id ] )
    prefdb.cursor.execute( query, params )
    result = prefdb.cursor.fetchall()
        
    #and from their totalAppeances, work out a weight for each
    user_doc_weights = dict( 
        ( r.get( 'term' ), r.get( 'tf' ) * idfs[ r.get( 'term' ) ] ) 
        for r in result 
    )
    
    #calculate the length (norm) of the input document vector
    user_doc_norm = math.sqrt( sum( [ (w * w) for w in user_doc_weights.values() ] ) )
    
    #-----------------------------------------------
    # FINAL SIMILARITY CALCULATIONS
    #-----------------------------------------------

    sum_of_weights = sum( [ 
        weight * input_doc_weights[ term ] 
        for term, weight in user_doc_weights.items() 
    ] )
    
    try:
        cosine_similarity =  sum_of_weights  / ( input_doc_norm * user_doc_norm )
    except ZeroDivisionError:
        cosine_similarity = 0

    #-----------------------------------------------
    # OUTPUT THE RESULT
    #-----------------------------------------------
    return str(cosine_similarity) 


#///////////////////////////////////////////////


@route('/images')
def get_images():

    try:
        user = check_login()
    except RegisterException, e:
        redirect( "/register" )
    except LoginException, e:
        return error( e.msg )
    except Exception, e:
        return error( e ) 
    
    #if the user doesn't exist or is not logged in,
    #then send them home. naughty user.
    if ( not user ) : redirect( ROOT_PAGE )
    
    try:
        try:
            order_by = request.GET[ "order_by" ] 
        except:
            order_by = "total appearances"
        
        results = prefdb.fetch_terms( 
            user_id=user[ "user_id" ], 
            order_by=order_by, 
            direction="DESC", 
            LIMIT=14, 
            MIN_WEB_PREVALENCE=30000
        )
        

        if results:
            #below is some code for image representations of your interests
            #Very neato ;)
            BING_KEY = "580DDBFFD1A4581F90038B9D5B80BA065FEFE4E7"
            
            #LOCAL WEB_PROXY = 'http://mainproxy.nottingham.ac.uk:8080'    
            #LOCAL search = WebSearch( proxy=WEB_PROXY, bing_key=BING_KEY )
            search = WebSearch( bing_key=BING_KEY )
            
            data = "["
            
            for row in results:
                #the name of the term
                term = row[ 'term' ]
                 
                #the number of times the user has seen this term
                total_appearances = row[ 'total_appearances' ] 
                
                #the number of documents the term has been seen in
                doc_appearances = row[ 'doc_appearances' ]
                
                #the unix timestamp of when the term was last seen
                last_seen = row[ 'last_seen' ]
                
                #the term frequency in the users model (tf)
                frequency = total_appearances / user [ "total_term_appearances" ]

                #at this point there may be no count yet
                #TODO: check that this "relevance tdidf is correct"
                if ( row[ 'count' ] > 0 ) :
                    importance = row[ 'count' ] / TOTAL_WEB_DOCUMENTS
                    relevance = ( frequency * ( 1 / importance ) )
                
                
                data += """{
                        'term':'%s',
                        'relevance':%f,
                        'total_appearances':%d,
                        'urls':%s
                    },""" % (
                    term,
                    relevance,
                    total_appearances,   
                    search.getBingImage( term )
                )    
                
            data = data[:-1].replace("u'", "'") + "]"                            
            return template( 'image_cloud_template', data=data)
    except Exception, e:
        return error( e )    
    
    
#//////////////////////////////////////////////////////////
# DATAWARE WEB-API CALLS
#//////////////////////////////////////////////////////////


def format_success( url, ):
   
    return json.dumps({
        'success':True, 
        'redirect':url,  
    })
        

#///////////////////////////////////////////////


def format_failure( cause, error, ):
   
    return json.dumps({ 
        'success':False, 
        'cause':cause,        
        'error':error,  
    })
        

#///////////////////////////////////////////////
 
 
@route( '/install', method = "GET", )
def install():

    try:
        user = check_login()
        if ( not user ): redirect( ROOT_PAGE )
    except RegisterException, e:
        redirect( "/register" )
    except LoginException, e:
        return error( e.msg )
    except Exception, e:
        return error( e )        
        
    return template( 'install_page_template', user=user ) 
    

#///////////////////////////////////////////////
 
 
@route( '/install_request', method = "GET" )
def install_request():
    
    try:
        user = check_login()
        if ( not user ): redirect( ROOT_PAGE )
    except RegisterException, e:
        redirect( "/register" )
    except LoginException, e:
        return error( e.msg )
    except Exception, e:
        return error( e )        

    catalog_uri = request.GET.get( "catalog_uri", None )
    
    try:
        url = im.initiate_install( user[ "user_id" ], catalog_uri  )
        return format_success( url )
    except ParameterException, e:
        return format_failure( "resource", e.msg )
    except CatalogException, e:    
        return format_failure( "catalog", e.msg )
        
         
#///////////////////////////////////////////////


@route( '/install_complete', method = "GET" )
def install_complete():
    
    try:
        user = check_login()
    except RegisterException, e:
        redirect( "/register" )
    except LoginException, e:
        return error( e.msg )
    except Exception, e:
        return error( e )  
    
    error = request.GET.get( "error", None )
    state = request.GET.get( "state", None )
    code = request.GET.get( "code", None )
        
    if ( error ):
        try:
            im.fail_install( user, state )
            #TODO: tell the user that the installation failed (a redirect?)
            return "installation failed: %s" % \
                ( request.GET.get( "error_description", "unspecified error" ) )
                
        except ParameterException, e:
            return e.msg

    else:
        #complete the install, swapping the authorization code
        #we've received from the catalog, for the access_token
        try:
            im.complete_install( user, state, code )
            
        except ParameterException, e:
            #TODO: make this more explanatory
            return e.msg
        
        except CatalogException, e:
            #TODO: make this more explanatory
            return e.msg
        
        except Exception, e:
            return error( e )
        
        #TODO: tell the user that the installation succeeded (a redirect?)
        return "installation success"

        
    
#//////////////////////////////////////////////////////////
# 3RD PARTY PROCESSOR SPECIFIC WEB-API CALLS
#//////////////////////////////////////////////////////////
   
    
@route( '/invoke_processor', method = "POST")
def invoke_processor():
    
    try:
        access_token = request.forms.get( 'access_token' )
        jsonParams = request.forms.get( 'parameters' )
        result = pm.invoke_processor( 
            access_token, 
            jsonParams )
        return result
    except Exception, e:
        raise e
     

#///////////////////////////////////////////////
 
 
@route( 'permit_processor', method = "POST" )
def permit_processor():

    #we receive a resource_token and resource_id that matches us,
    #proving that the message is from the catalog, along with 
    #details of the query the client is proposing...
    try:
        install_token = request.forms.get( 'install_token' )
        client_id = request.forms.get( 'client_id' )
        query = request.forms.get( 'query' ).replace( '\r\n','\n' )
        expiry_time = request.forms.get( 'expiry_time' )        

        result = pm.permit_processor( 
            install_token,
            client_id,
            query,
            expiry_time 
        )
        
        #the result, if successful, will include an processing_token
        return result
    
    except Exception, e:
        raise e
          

#///////////////////////////////////////////////
 
 
@route( 'revoke_processor', method = "POST" )
def revoke_processor( user_name = None ):
    
    try:
        install_token = request.forms.get( 'install_token' )
        access_token = request.forms.get( 'access_token' )

        result = pm.revoke_processor( 
            install_token=install_token,
            access_token=access_token,
        )
        
        return result
    
    except Exception, e:
        raise e


    
#//////////////////////////////////////////////////////////
# OPENID SPECIFIC WEB-API CALLS
#//////////////////////////////////////////////////////////


@route( '/login', method = "GET" )
def openID_login():

    try: 
        username = request.GET[ 'username' ]    
    except: 
        username = None
     
    try:      
        provider = request.GET[ 'provider' ]
    except: 
        return template( 'login_page_template', user=None )
    
    try:
        url = OpenIDManager.process(
            realm=REALM,
            return_to=REALM + "/checkauth",
            provider=provider,
            username=username
        )
    except Exception, e:
        return error( e )
    
    #Here we do a javascript redirect. A 302 redirect won't work
    #if the calling page is within a frame (due to the requirements
    #of some openid providers who forbid frame embedding), and the 
    #template engine does some odd url encoding that causes problems.
    return "<script>self.parent.location = '%s'</script>" % (url,)
    

#///////////////////////////////////////////////

 
@route( "/checkauth", method = "GET" )
def authenticate():
    
    o = OpenIDManager.Response( request.GET )
    
    #check to see if the user logged in succesfully
    if ( o.is_success() ):
        
        user_id = o.get_user_id()
         
        #if so check we received a viable claimed_id
        if user_id:
            
            try:
                user = prefdb.fetch_user_by_id( user_id )
                
                #if this is a new user add them
                if ( not user ):
                    prefdb.insert_user( o.get_user_id() )
                    prefdb.commit()
                    user_name = None
                else :
                    user_name = user[ "user_name" ]
                
                set_authentication_cookie( user_id, user_name  )
                
            except Exception, e:
                return error( e )
            
            
        #if they don't something has gone horribly wrong, so mop up
        else:
            delete_authentication_cookie()

    #else make sure the user is still logged out
    else:
        delete_authentication_cookie()
        
    return "<script>self.parent.location = '%s'</script>" % ( REALM + ROOT_PAGE,)
       
       
#///////////////////////////////////////////////


@route( "/login_local", method = "GET" )
def login_local():
    
    user_name = request.GET.get( "user_name", None )   
    try:
        user = prefdb.fetch_user_by_name( user_name )
        set_authentication_cookie( user[ "user_id" ], user_name  )
                
    except Exception, e:
        return error( e )
        
    return "<script>self.parent.location = '%s'</script>" % ( REALM + ROOT_PAGE,)
       
       
#///////////////////////////////////////////////


@route('/logout')
def logout():
    
    delete_authentication_cookie()
    redirect( ROOT_PAGE )
    
        
#///////////////////////////////////////////////
 
         
def delete_authentication_cookie():
    
    response.delete_cookie( 
        key=EXTENSION_COOKIE,
    )
            
#///////////////////////////////////////////////


def set_authentication_cookie( user_id, user_name = None ):
    
    #if the user has no "user_name" it means that they
    #haven't registered an account yet    
    if ( not user_name ):
        json = '{"user_id":"%s","user_name":null}' \
            % ( user_id, )
        
    else:
        json = '{"user_id":"%s","user_name":"%s"}' \
            % ( user_id, user_name )
         
    response.set_cookie( EXTENSION_COOKIE, json )
                            

#//////////////////////////////////////////////////////////
# PREFSTORE SPECIFIC WEB-API CALLS
#//////////////////////////////////////////////////////////


class LoginException ( Exception ):
    
    def __init__(self, msg):
        self.msg = msg


#///////////////////////////////////////////////  


class RegisterException ( Exception ):
    """Base class for RegisterException in this module."""
    
    pass

    
#///////////////////////////////////////////////


def valid_email( str ):
    
    return re.search( "^[A-Za-z0-9%._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4}$", str )


#///////////////////////////////////////////////


def valid_name( str ):

    return re.search( "^[A-Za-z0-9 ']{3,64}$", str )


#///////////////////////////////////////////////
    

@route( '/register', method = "GET" )
def user_register():
    
    try:
        user_id = extract_user_id()
    except LoginException, e:
        return error( e.msg )
    except Exception, e:
        return error( e )
    
    errors = {}
    
    #if the user has submitted registration info, parse it
    try: 
        request.GET[ "submission" ]
        submission = True;
    except:
        submission = False
        
    if ( submission ): 
        #validate the user_name supplied by the user
        try:
            user_name = request.GET[ "user_name" ]
            if ( not valid_name( user_name ) ):
                errors[ 'user_name' ] = "Must be 3-64 legal characters"
            else: 
                match = prefdb.fetch_user_by_name( user_name ) 
                if ( not match is None ):
                    errors[ 'user_name' ] = "That name has already been taken"                    
        except:
            errors[ 'user_name' ] = "You must supply a valid user name"
    
        #validate the email address supplied by the user
        try:
            email = request.GET[ "email" ]
            if ( not valid_email( email ) ):
                errors[ 'email' ] = "The supplied email address is invalid"
            else: 
                match = prefdb.fetch_user_by_email( email ) 
                if ( not match is None ):
                    errors[ 'email' ] = "That email has already been taken"
        except:
            errors[ 'email' ] = "You must supply a valid email"


        #if everything is okay so far, add the data to the database    
        if ( len( errors ) == 0 ):
            try:
                match = prefdb.insert_registration( user_id, user_name, email) 
                prefdb.commit()
            except Exception, e:
                return error( e )

            #update the cookie with the new details
            set_authentication_cookie( user_id, user_name )
            
            #return the user to the home page
            redirect( ROOT_PAGE )

    #if this is the first visit to the page, or there are errors    
    else:
        email = ""
        user_name = ""
        
    return template( 
        'register_page_template', 
        user=None, 
        email=email,
        user_name=user_name,
        errors=errors ) 
    

#///////////////////////////////////////////////


def error( e ):
    
    return  "An error has occurred: %s" % ( e )

      
#///////////////////////////////////////////////  
    
    
def extract_user_id():
    
    cookie = request.get_cookie( EXTENSION_COOKIE )
        
    #is the user logged in? First check we have a cookie...
    if cookie:
        #and that it contains suitably formatted data
        try:
            data = json.loads( cookie )
        except:
            delete_authentication_cookie()
            raise LoginException( "Your login data is corrupted. Resetting." )
        
        #and then that it contains a valid user_id
        try:
            user_id =  data[ "user_id" ]
            return user_id
        except:
            delete_authentication_cookie()
            raise LoginException( "You are logged in but have no user_id. Resetting." )
    else:
        None

  
#///////////////////////////////////////////////  
    
    
def check_login():

    #first try and extract the user_id from the cookie. 
    #n.b. this can generate LoginExceptions
    user_id =extract_user_id()
    
    if ( user_id ) :
        
        #we should have a record of this id, from when it was authenticated
        user = prefdb.fetch_user_by_id( user_id )
        
        if ( not user ):
            delete_authentication_cookie()
            raise LoginException( "We have no record of the id supplied. Resetting." )
        
        #and finally lets check to see if the user has registered their details
        if ( user[ "user_name" ] is None ):
            raise RegisterException()
        
        return user
        
    #if the user has made it this far, their page can be processed accordingly
    else:
        return None   
    
 
    
#//////////////////////////////////////////////////////////
# PREFSTORE SPECIFIC CHROME-API CALLS
#//////////////////////////////////////////////////////////


schema = {
    "type" : "object",
        "properties" : {
            "docId" : {
                "type" : "string",  
                "minLength" : 3 
            },
            "docType" :  {
                "type" : "string",
                "minLength" : 3
            },
            "docName" :  {
                "type" : "string",
                "minLength" : 0
            },
            "appName" : {
                "type" : "string",
                "minLength" : 3
            },
            "totalWords" : {
                "type" : "integer" 
            },
            "duration" : {
                "type" : "integer" 
            },
            "mtime" : {
                "type" : "integer" 
            },
            "fv" : {
                "type" : "object",
                "patternProperties": { ".*": { "type": "integer" } } 
            }      
        }
    }   

       
#///////////////////////////////////////////////


@route( '/submitDistill', method = "POST" )
def submit_distill():
    """ 
        A Distillation is packaged as a json message of the form
        {user:u, docid:d, docType:t, appName:a, duration:d, mtime:m, fv:{ word:freq } }    
    """

    try:
        print "inside submit distillation *****************************************"
        # First extracted the necessary POST parameters
        user_id = request.forms.get( 'user_id' )
        data = request.forms.get( 'data' ) 
    except:
        log.debug( 
            "%s: Incorrect parameters in submission API call" 
            % ( "prefstore", user_id ) 
        )
        return "{'success':false,'cause':'required parameters missing'}"
        
    try:
        #convert the data into a json object
        data = json.loads( data )

        #Make sure the message is in the correct distill format.
        validictory.validate( data, schema )
               
    except ValueError, e:
        log.error( 
            "%s: Message from '%s': JSON validation error - %s" 
            % ( "prefstore", user_id, e ) 
        )          
        return "{'success':false,'cause':'JSON error'}"       
        
    
    # Log that we have received the distill message.
    log.debug( 
        "%s: Message from '%s' successfully unpacked" 
        % ( "prefstore", user_id ) 
    )
    
       
    try:    
        # First db interaction of this method so safety check in case 
        # a mysql timeout has occurred since we last accessed the db.
        user = prefdb.fetch_user_by_id( user_id ) 
    except Exception, e: 
        log.error( 
            "%s: User Lookup Error %s' due to message from '%s'" 
            % ( "prefstore", e, user_id,  ) 
        )          
        return "{'success':false,'cause':'User Lookup error'}"   
    
    # Authenticate the user, using the supplied key
    if user:
        
        log.debug( 
            "%s: Message successfully authenticated as belonging to '%s'" 
            % ( "prefstore", user[ "user_name" ]  ) 
        )

        # And finally process it into the database
        try:
            process_distill( user, data )
            return "{'success':true}"
        except:
            log.info( 
                "%s: Processing Failure for message from '%s'" 
                % ( "prefstore", user[ "user_name" ]  )
            ) 
            return "{'success':false,'cause':'Processing error'}"
    
    else:
        log.warning( 
            "%s: Identification Failure for message from '%s'" 
            % ( "prefstore", user_id  ) 
        )
        return "{'success':false,'cause':'Authentication error'}"
            
    
#///////////////////////////////////////////////        
       
        
def process_distill( user, data ) :
    
    #Extract entry information
    user_id =  user[ "user_id" ]
    mtime = data.get( 'mtime' )
    fv = data.get( 'fv' )
    start_processing = time.time()
    total_terms = len( fv )
    new_terms = None

    #add the distillation to a log file for future analysis
    #n.b. this will only work if bottle.py has been patched
    data_log.info( "%s: %s" % ( request.remote_addr, data ) ) 

    #Remove any blacklisted terms from the feature vector
    prefdb.removeBlackListedTerms( fv )
    no_terms = len( fv )
    total_appearances = sum( fv.values() )

    #Process the terms we haven't seen before
    try:
        if no_terms > 0:
            new_terms = prefdb.insertDictionaryTerms( fv )
    except:
        log.warning( 
            "%s: Error trying to add terms to dictionary"
            % ( "prefstore" ) 
        )
        raise Exception

    #Process the terms that already exist in the dictinoary            
    try:
        if no_terms > 0:
            prefdb.updateTermAppearances( user_id, fv );    
    except:
        log.warning( 
            "%s: Failed to increment term appearances for '%s'" 
            % ( "prefstore", user_id ) 
        )
        raise Exception        

    #Update user info, incrementing the number of documents we have received.
    userUpdated = prefdb.incrementUserInfo( 
        user_id, total_appearances, mtime 
    )

    if not userUpdated :
        log.error( 
            "%s: User '%s' could not be updated. Ignoring." 
            % ( "prefstore", user[ "user_name" ] ) 
        )
        return False    
      
    #Everything seems okay, so commit the transaction
    prefdb.commit()
    
    #Log the distillation results
    log.info( 
        "%s: Distillation processed for '%s' (%d terms, %d processed, %d new, %d appearances, %.4f secs)" % ( 
            "prefstore", 
            user[ "user_name" ], 
            total_terms,
            no_terms, 
            new_terms,
            total_appearances,
            time.time() - start_processing 
        ) 
    )

    #And return from the function successfully
    return True
        

#///////////////////////////////////////////////   


@route('/static/:filename')
def get_static_file( filename ):
    
    return static_file( filename, root='static/' )


#///////////////////////////////////////////////  

   
@route('/analysis')
def analysis():
    
    try:
        user = check_login()
    except RegisterException, e:
        redirect( "/register" )
    except LoginException, e:
        return error( e.msg )
    except Exception, e:
        return error( e )        
        
    #if the user doesn't exist or is not logged in, send them home
    if ( not user ) :
        redirect( ROOT_PAGE )
    
    try:
        type = request.GET[ "type" ]
    except:
        type = None
        
    try:
        message = "top 1000 terms by total appearances"
        match_type = ""
        search_term = ""
        order_by = ""
        direction = ""
        
        if ( type == "search" ):
            try:
                search_term = request.GET[ "search_term" ]
                match_type = request.GET[ "match_type" ] 
            except:
                pass
            results =  prefdb.search_terms( user[ "user_id" ], search_term, match_type )
            message = "'%s' search for '%s' - %d results" % ( match_type, search_term, len( results ) ) 
        
        elif ( type == "filter" ):
            try:
                direction = request.GET[ "direction" ]
            except:
                direction = "DESC"
                
            try:
                order_by = request.GET[ "order_by" ] 
            except:
                order_by = "total appearances"
                
            results =  prefdb.fetch_terms( user[ "user_id" ], order_by, direction  )
            message = "filtered on '%s' - %s %d results" % ( 
                order_by, 
                "bottom" if direction == "ASC" else "top", 
                len( results )
            ) 
        else:
            results =  prefdb.fetch_terms( user[ "user_id" ] )
            message = "top 1000 results by 'total appearances'" 
        
        data = ""
        
        #TODO: Should also add ability to blacklist terms at some point
        if results:
            for row in results:
                
                #the name of the term
                term = row[ 'term' ]
                
                #the number of times the user has seen this term
                total_appearances = row[ 'total_appearances' ] 
                
                #the number of documents the term has been seen in
                doc_appearances = row[ 'doc_appearances' ]
                
                #the unix timestamp of when the term was last seen
                last_seen = row[ 'last_seen' ]
                
                #the term frequency in the users model (tf)
                frequency = total_appearances / user [ "total_term_appearances" ]

                #the number of web documents the term occurs in (df)
                importance = 0
                
                #the users relevance weight for this term (tf-idf)
                relevance = 0
                
                #at this point there may be no count yet
                if ( row[ 'count' ] > 0 ) :
                    importance = row[ 'count' ] / TOTAL_WEB_DOCUMENTS
                    relevance = ( frequency * ( 1 / importance ) )
                  
                #note below that multiplying by a million serves only to eliminate
                #rounding error that made everything zero.
                data += """
                    {c:[{v:'%s'},{v:%d,f:%s},{v:%d,f:%s},{v:%d,f:'%s'},{v:%d,f:'%s'},{v:%d,f:'%s'},{v:%d,f:'%s'}]},
                """ % ( 
                    term, 
                    total_appearances,str( total_appearances ), 
                    doc_appearances, str( doc_appearances ),
                    frequency * 10000000, '%.5f%%' % round( frequency * 100, 5 ),  
                    importance * 10000000, 'unknown' if ( importance == 0 ) else '%.5f%%' % round( importance * 100, 5 ),
                    relevance * 10000000, 'unknown' if ( relevance == 0 ) else '%.4f' % round( relevance * 100, 4 ),
                    last_seen , time.strftime( "%d %b %Y %H:%M", time.gmtime( last_seen ) )
                )
                
                
        return template(     
            'analysis_page_template',
             data=data,
             user=user,             
             type=type,
             search_term=search_term,
             match_type=match_type,
             order_by=order_by, 
             direction=direction,
             message=message
        )
  
    except Exception, e:
        return error( e )        
  

#///////////////////////////////////////////////  

      
@route('/visualize')
def word_cloud():
    
    try:
        user = check_login()
    except RegisterException, e:
        redirect( "/register" )
    except LoginException, e:
        return error( e.msg )
    except Exception, e:
        return error( e )        
        
    #if the user doesn't exist or is not logged in,
    #then send them home. naughty user.
    if ( not user ) : redirect( ROOT_PAGE )
    
    try:

        try:
            order_by = request.GET[ "order_by" ] 
        except:
            order_by = "total appearances"
        
        results = prefdb.fetch_terms( 
            user_id=user[ "user_id" ], 
            order_by=order_by, 
            direction="DESC", 
            LIMIT=50, 
            MIN_WEB_PREVALENCE=30000
        )
        
        message = "The %d terms with highest '%s'" % ( 
           len( results ), order_by, 
        ) 
        
        data_str = "{'text':'%s', weight:%d, url:'javascript:select(\"%s\")'},"
        total_appearance_data = ""
        doc_appearance_data = ""
        web_importance_data = ""        
        relevance_data = ""
     
        if results:
            for row in results:
                
                #the name of the term
                term = row[ 'term' ]
                
                #the number of times the user has seen this term
                total_appearances = row[ 'total_appearances' ] 
                
                #the number of documents the term has been seen in
                doc_appearances = row[ 'doc_appearances' ]
                
                #the term frequency in the users model (tf)
                frequency = total_appearances / user [ "total_term_appearances" ]

                #the number of web documents the term occurs in (df)
                importance = 0
                
                #the users relevance weight for this term (tf-idf)
                relevance = 0
                
                #at this point there may be no count yet
                if ( row[ 'count' ] > 0 ) :
                    importance = row[ 'count' ] / TOTAL_WEB_DOCUMENTS
                    relevance = ( frequency * ( 1 / importance ) )
                
                total_appearance_data +=  data_str % ( term, total_appearances, term )
                doc_appearance_data +=  data_str % ( term, doc_appearances, term )
                web_importance_data +=  data_str % ( term, importance  * 10000, term )
                relevance_data +=  data_str % ( term, relevance * 10000, term )
              
       
        data =""" {
            'total appearances':[ %s ],
            'doc appearances':[ %s ],
            'web importance':[ %s ],
            'relevance':[ %s ]
        } """ % (
            total_appearance_data[:-1],
            doc_appearance_data[:-1],
            web_importance_data[:-1],
            relevance_data[:-1],               
        )    
    
        return template(     
            'word_cloud_template',
             user=user,
             data=data,
             order_by=order_by, 
             message=message
        )
  
    except Exception, e:
        return error( e )        
      
  
#///////////////////////////////////////////////  
    
    
@route( '/', method = "GET" )     
@route( '/home', method = "GET" )
def home( ):

    try:
        user = check_login()
    except RegisterException, e:
        redirect( "/register" ) 
    except LoginException, e:
        return error( e.msg )
  
    if ( not user ):
        summary = None
    else:
        user[ "registered_str" ] = time.strftime( "%d %b %Y %H:%M", time.gmtime( user[ "registered" ] ) )
        user[ "last_distill_str" ] = time.strftime( "%d %b %Y %H:%M", time.gmtime( user[ "last_distill" ] ) )
        
        if user[ "total_documents" ]:
            user[ "average_appearances" ] = round( user[ "total_term_appearances" ] / user[ "total_documents" ], 2 )
        else:
            user[ "average_appearances" ] = 0
            
        summary = prefdb.fetch_user_summary( user[ "user_id" ] )

    return template( 'home_page_template', user=user, summary=summary );
    
    
#///////////////////////////////////////////////  
    
    
@route('/summary')
def summary():
  
    try:
        user = check_login()
    except RegisterException, e:
        redirect( "/register" ) 
    except LoginException, e:
        return error( e.msg )
    except Exception, e:
        return error( e )     
    
    #if the user doesn't exist or is not logged in,
    #then send them home. naughty user.
    if ( not user ) : redirect( ROOT_PAGE )

    user[ "registered_str" ] = time.strftime( "%d %b %Y %H:%M", time.gmtime( user[ "registered" ] ) )
    user[ "last_distill_str" ] = time.strftime( "%d %b %Y %H:%M", time.gmtime( user[ "last_distill" ] ) )
    if user[ "total_documents" ]:
        user[ "average_appearances" ] = round( user[ "total_term_appearances" ] / user[ "total_documents" ], 2 )
    else:
        user[ "average_appearances" ] = 0
    summary = prefdb.fetch_user_summary( user[ "user_id" ] )

    return template( 'summary_page_template', user=user, summary=summary );
    
    
#///////////////////////////////////////////////  
    
    
@route('/news')
def news():


    limit = int( request.GET.get( "limit", 385 ) )

    try:
        user = check_login()
    except RegisterException, e:
        redirect( "/register" ) 
    except LoginException, e:
        return error( e.msg )
    except Exception, e:
        return error( e )  
    
    #if the user doesn't exist or is not logged in,
    #then send them home. naughty user.
    if ( not user ) : redirect( ROOT_PAGE )

    #summary = newsdb.items_user_summary( user[ "user_id" ] );
    
    #stories = newsdb.items_user_fetch(
    #    user[ "user_id" ],
    #    limit
    #)
    
    #sorted_stories = [ i for i in stories ]
    #for i in range( limit ): sorted_stories[ i ][ "id" ] = i
    #sorted_stories.sort( key=lambda k:k["score"], reverse = True )
    #score_positions = [ i.get( "id" ) for i in sorted_stories ]
    
    return template( 'audit_page_template', 
        user=user) 
        #score_positions = score_positions,
        #stories = stories,
        #summary = summary ); 
    
            
#//////////////////////////////////////////////////////////
# MAIN FUNCTION
#//////////////////////////////////////////////////////////


if __name__ == "__main__":

    #-------------------------------
    # setup logging
    #-------------------------------
    log.setLevel( logging.DEBUG )
    data_log.setLevel( logging.DEBUG )    

    # create handlers
    #LOCAL
    ch = logging.StreamHandler(sys.stdout)
    
    #ch = logging.handlers.TimedRotatingFileHandler( 
    #    filename='logs/prefstore.log',
    #    when='midnight', 
    #    interval=21 )
    
    fh = logging.handlers.TimedRotatingFileHandler( 
        filename='logs/prefstore_data.log',
        when='midnight', 
        interval=21 )
        
    # create formatter and add it to the handlers
    formatter = logging.Formatter( '--- %(asctime)s [%(levelname)s] %(message)s' )
    ch.setFormatter( formatter )
    fh.setFormatter( formatter )    

    # add the handlers to the logger
    log.addHandler( ch )
    data_log.addHandler( fh )    
            
    # redirect standard outputs to prevent errors running the process
    # as a daemon (due to print statements in python socket libraries.
    sys.stdout = std_writer( "stdout" )
    sys.stderr = std_writer( "stderr" )
    
    #-------------------------------
    # constants
    #-------------------------------
    EXTENSION_COOKIE = "prefstore_logged_in"
    PORT = 80
    HOST = "0.0.0.0"  
    BOTTLE_QUIET = True 
    ROOT_PAGE = "/"
    RESOURCE_NAME = "http://www.mydataware.info/prefstore"
    RESOURCE_URI = "http://www.prefstore.org"
    #REALM = "http://www.prefstore.org"
    #LOCAL! 
    REALM = "http://localhost:80"
    WEB_PROXY = "http://mainproxy.nottingham.ac.uk:8080"
            
    #-------------------------------
    # declare initialization in logs
    #-------------------------------        
    print "-"*40
    print "PREFSTORE IGNITION"
    print "PORT = %s" % PORT
    print "HOST = %s" % HOST
    print "REALM = %s" % REALM
    print "BOTTLE_QUIET = %s" % BOTTLE_QUIET
    print "-"*40
    
    #---------------------------------
    # Initialization
    #---------------------------------
    try:
        print "start"
        datadb = DataDB()
        print "after start"
        datadb.connect()
        print "after connect"
        datadb.check_tables()
        prefdb = PrefDB()
        prefdb.connect()
        prefdb.check_tables()
        log.info( "database initialization completed... [SUCCESS]" );
        
        #newsdb = NewsDB()
        #newsdb.connect()
        #newsdb.check_tables()
        #log.info( "news initialization completed... [SUCCESS]" );
        
    except Exception, e:
        log.error( "database initialization error: %s" % ( e, ) )
        exit()
         
    #---------------------------------
    # module initialization
    #---------------------------------
    try:    
        pm = ProcessingModule( datadb )
        im = InstallationModule( RESOURCE_NAME, RESOURCE_URI, datadb )
        log.info( "module initialization completed... [SUCCESS]" );
    except Exception, e:
        log.error( "module initialization error: %s" % ( e, ) )
        

    #---------------------------------
    # Web Count Updater initialization
    #---------------------------------
    updater = WebCountUpdater()
    updater.start()
    log.info( "web updater initialisation completed... [SUCCESS]" );
      
    #---------------------------------
    # Web Server initialization
    #---------------------------------
    try:
        debug( True )
        run( host=HOST, port=PORT, quiet=BOTTLE_QUIET )
    except Exception, e:  
        log.error( "Web Server Exception: %s" % ( e, ) )
        exit()
   
    #---------------------------------
    # Initialization Complete
    #---------------------------------
    print "Catalog Firing on all cylinders..."
    print "-"*40

    
   
