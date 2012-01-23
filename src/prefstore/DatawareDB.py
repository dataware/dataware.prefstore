'''    
Created on 12 April 2011
@author: jog
'''

import MySQLdb
import ConfigParser
import hashlib
import logging
import base64
import random
log = logging.getLogger( "console_log" )


#///////////////////////////////////////


def safety_mysql( fn ) :
    """ I have included this decorator because there are no 
    gaurantees the user has mySQL setup so that it won't time out. 
    If it has, this function remedies it, by trying (one shot) to
    reconnect to the database.
    """

    def wrapper( self, *args, **kwargs ) :
        try:
            return fn( self, *args, **kwargs )
        except MySQLdb.Error, e:
            if e[ 0 ] == 2006:
                self.reconnect()
                return fn( self, *args, **kwargs )
            else:
                raise e  
    return wrapper
    

#///////////////////////////////////////

    
class DataDB( object ):
    ''' classdocs '''
    
    DB_NAME = 'prefstore'
    TBL_DATAWARE_QUERIES = 'tblDatawareQueries'
    TBL_DATAWARE_CATALOGS = 'tblDatawareCatalogs'
    TBL_DATAWARE_INSTALLS = 'tblDatawareInstalls'
    CONFIG_FILE = "prefstore.cfg"
    SECTION_NAME = "DatawareDB"
    
    #///////////////////////////////////////

  
    createQueries = { 
               
        TBL_DATAWARE_QUERIES : """
            CREATE TABLE %s.%s (
                access_token varchar(256) NOT NULL,
                client_id varchar(256) NOT NULL,
                user_name varchar(256) NOT NULL,
                expiry_time int(11) unsigned NOT NULL,
                query text NOT NULL,
                checksum varchar(256) NOT NULL,
                PRIMARY KEY (access_token) USING BTREE,
                UNIQUE KEY UNIQUE (client_id,user_name,checksum)
            ) ENGINE=InnoDB DEFAULT CHARSET=latin1;
        """  % ( DB_NAME, TBL_DATAWARE_QUERIES ),
       
        TBL_DATAWARE_CATALOGS : """ 
            CREATE TABLE %s.%s (
                catalog_uri varchar(256) NOT NULL,                
                resource_id varchar(256) NOT NULL,
                registered int(10) unsigned DEFAULT NULL,
                PRIMARY KEY (catalog_address)
            ) ENGINE=InnoDB DEFAULT CHARSET=latin1;
        """  % ( DB_NAME, TBL_DATAWARE_CATALOGS ),  
        
        TBL_DATAWARE_INSTALLS : """ 
            CREATE TABLE %s.%s (
                user_name varchar(256) NOT NULL,
                catalog_uri varchar(256) NOT NULL,                
                access_token varchar(256) NOT NULL,
                state varchar(256) NOT NULL,
                registered int(10) unsigned DEFAULT NULL,
                PRIMARY KEY (user_name) 
                FOREIGN KEY (user_id) REFERENCES %s(user_id) 
                ON DELETE CASCADE ON UPDATE CASCADE,
            ) ENGINE=InnoDB DEFAULT CHARSET=latin1;
        """  % ( DB_NAME, TBL_DATAWARE_INSTALLS, TBL_DATAWARE_CATALOGS ),            
    } 
    
        
    #///////////////////////////////////////
    
    
    def __init__( self, name = "DatawareDB" ):
            
        #MysqlDb is not thread safe, so program may run more
        #than one connection. As such naming them is useful.
        self.name = name
        
        Config = ConfigParser.ConfigParser()
        Config.read( self.CONFIG_FILE )
        self.hostname = Config.get( self.SECTION_NAME, "hostname" )
        self.username =  Config.get( self.SECTION_NAME, "username" )
        self.password =  Config.get( self.SECTION_NAME, "password" )
        self.dbname = Config.get( self.SECTION_NAME, "dbname" )
        self.connected = False;
        
        
    #///////////////////////////////////////
    

    def connect( self ):
        
        log.info( "%s: connecting to mysql database..." % self.name )

        self.conn = MySQLdb.connect( 
            host=self.hostname,
            user=self.username,
            passwd=self.password,
            db=self.dbname
        )
 
        self.cursor = self.conn.cursor( MySQLdb.cursors.DictCursor )
        self.connected = True
                    
                    
    #///////////////////////////////////////
    
    
    def reconnect( self ):
        log.info( "%s: Database reconnection process activated..." % self.name );
        self.close()
        self.connect()
        

    #///////////////////////////////////////
          
          
    @safety_mysql                
    def commit( self ) : 
        self.conn.commit();
        
        
    #///////////////////////////////////////
        

    def close( self ) :   
        if self.conn.open:
            log.info( "%s: disconnecting from mysql database..." % self.name );
            self.cursor.close();
            self.conn.close()
                     
   
    #///////////////////////////////////////
    
    
    @safety_mysql        
    def check_tables( self ):
        
        log.info( "%s: checking system table integrity..." % self.name );
                
        #-- first check that the database itself exists        
        self.cursor.execute ( """
            SELECT 1
            FROM information_schema.`SCHEMATA`
            WHERE schema_name='%s'
        """ % self.DB_NAME )
                
        row = self.cursor.fetchone()

        if ( row is None ):
            log.info( "%s: database does not exist - creating..." % self.name );    
            self.cursor.execute ( "CREATE DATABASE catalog" )
        
        
        #-- then check it is populated with the required tables
        self.cursor.execute ( """
            SELECT table_name
            FROM information_schema.`TABLES`
            WHERE table_schema='%s'
        """ % self.DB_NAME )
        
        tables = [ row[ "table_name" ] for row in self.cursor.fetchall() ]
        
        #if they don't exist for some reason, create them.    
        for t, q in self.createQueries.iteritems():
            if not t in tables : 
                log.warning( "%s: Creating missing system table: '%s'" % ( self.name, t ) );
                self.cursor.execute( q )
        
        self.commit()
        
        
        
    #///////////////////////////////////////
    
    
    @safety_mysql                  
    def createTable( self, tableName ):
        
        log.warning( 
            "%s: missing system table detected: '%s'" 
            % ( self.name, tableName ) 
        );
        
        if tableName in self.createQueries :
            
            log.info( 
                "%s: --- creating system table '%s' " 
                % ( self.name, tableName )
            );  
              
            self.cursor.execute( self.createQueries[ tableName ] )

      
    #////////////////////////////////////////////////////////////////////////////////////////////


    @safety_mysql   
    def insert_request( self, access_token, client_id, user_name, expiry_time, query_code ):
       
        #create a SHA checksum for the file
        checksum = hashlib.sha1( query_code ).hexdigest()
        
        query = """
             INSERT INTO %s.%s VALUES ( %s, %s, %s, %s, %s, %s )
        """  % ( self.DB_NAME, self.TBL_DATAWARE_QUERIES, '%s', '%s', '%s', '%s', '%s', '%s' ) 
        
        self.cursor.execute( 
            query, ( 
                access_token, 
                client_id, 
                user_name, 
                expiry_time, 
                query_code, 
                checksum 
            ) 
        )
        self.commit()
        
        
    
    #///////////////////////////////////////////////
    
    
    @safety_mysql       
    def delete_request( self, access_token, user_name ):

        query = """
             DELETE FROM %s.%s WHERE access_token = %s AND user_name = %s 
        """  % ( self.DB_NAME, self.TBL_DATAWARE_QUERIES, '%s', '%s' ) 

        self.cursor.execute( query, ( access_token, user_name ) )
        self.commit()
                
        #how many rows have been affected?
        if ( self.cursor.rowcount == 0 ) : 
            return False
        else :
            return True 
        
    
    
    #///////////////////////////////////////////////
    
    
    @safety_mysql       
    def fetch_request( self, access_token ):
        
        query = """
            SELECT * FROM %s.%s WHERE access_token = %s
        """  % ( self.DB_NAME, self.TBL_DATAWARE_QUERIES, '%s' ) 
        self.cursor.execute( query, access_token )
        row = self.cursor.fetchone()
        return row
    
    
    #///////////////////////////////////////
    
    
    @safety_mysql                    
    def insert_catalog( self, catalog_uri, resource_id ):
            
        if ( catalog_uri ):
            
            log.info( 
                "%s %s: Inserting catalog '%s' in database with resource_id '%s'" 
                % ( self.name, "insert_catalog", catalog_uri, resource_id ) 
            );
            
            
            query = """
                  INSERT INTO %s.%s ( catalog_uri, resource_id, registered ) 
                  VALUES ( %s, %s, %s )
              """  % ( self.DB_NAME, self.TBL_DATAWARE_CATALOGS, '%s', '%s', '%s', )
            
            state = self.generateAccessToken()
            self.cursor.execute( query, (  catalog_uri, resource_id ) )
                
            return state;
        
        else:
            log.warning( 
                "%s %s: Catalog insert requested with incomplete details" 
                % (  self.name, "insert_catalog", ) 
            );
            return None;    
        
        
    #///////////////////////////////////////
    
    
    @safety_mysql                    
    def fetch_catalog( self, catalog_uri ):
            
        if catalog_uri :
            query = """
                SELECT * FROM %s.%s t where catalog_uri = %s 
            """  % ( self.DB_NAME, self.TBL_DATAWARE_CATALOGS, '%s' ) 
        
            self.cursor.execute( query, ( catalog_uri, ) )
            row = self.cursor.fetchone()

            if not row is None:
                return row
            else :
                return None
        else :
            return None   
            
        
                
    #///////////////////////////////////////
    
    
    @safety_mysql                    
    def insert_install( self, user_name, catalog_uri, state ):
            
        if ( user_name and catalog_uri ):
            
            log.info( 
                "%s %s: Inserting user '%s' catalog as '%s' in database" 
                % ( self.name, "insert_catalog", user_name, catalog_uri, ) 
            );
            
            
            query = """
                  INSERT INTO %s.%s ( user_name, catalog_uri, access_token, state, registered ) 
                  VALUES ( %s, %s, null, %s, null )
              """  % ( self.DB_NAME, self.TBL_DATAWARE_CATALOGS, '%s', '%s', '%s', )
            
            state = self.generateAccessToken()
            self.cursor.execute( query, ( user_name, catalog_uri, state ) )
                
            return state;
        
        else:
            log.warning( 
                "%s %s: Installation insert requested with incomplete details" 
                % (  self.name, "insert_catalog", ) 
            );
            return None;    
        
        
    #///////////////////////////////////////////////
    
    
    @safety_mysql       
    def authenticate( self, user_name, access_token ) :
        
        if user_name and access_token:
            query = """
                SELECT 1 FROM %s.%s WHERE user_name = %s AND access_token = %s  
            """  % ( self.DB_NAME, self.TBL_DATAWARE_CATALOGS, '%s', '%s' ) 

            self.cursor.execute( query, ( user_name, access_token ) )
            row = self.cursor.fetchone()
            
            if ( row is None ):
                return False
            else:    
                return True
        else:    
            return False


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