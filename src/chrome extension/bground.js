	/**
	 * background script for manifest version 2. 
	 * This is the Controller Script for the Google Chrome Datware.
	 * It receives requests from the content and popup scripts.
	 */

	//-- Setup constants that will be required
	
	DOCUMENT_TYPE = "web";
	APPLICATION_NAME = "Google Chrome";
	COOKIE_NAME = "prefstore_logged_in"
	//DOMAIN = "http://www.prefstore.org/";
	DOMAIN = "http://localhost:80/";
	//PREFSTORE =  "http://www.prefstore.org/";
	PREFSTORE =  "http://localhost:80/";
	//-- give the cache a one hour duration
	CACHE_DURATION = 60 * 60;
	
	//-- A list of domains that won't be parsed (predominantly search engines)
	IGNORE_LIST = new Array( 
		"www.bing", "www.google", "search.yahoo", "ask.com", "search.aol", "www.prefstore"
	)

	window.localStorage.setItem( "cookie_name", COOKIE_NAME );
	window.localStorage.setItem( "domain", DOMAIN );
	window.localStorage.setItem( "prefstore", PREFSTORE );
	//console.log('prefstore is **** ' + window.localStorage.getItem( "prefstore" ));
	
	//-- initialize by parsing the extensions corresponding cookie	
	parse_cookie()
	
	
	//-- Listener to receive word vectors from the content script.
	chrome.extension.onMessage.addListener(
			function( request, sender, sendResponse ) {
				processVector( request.text, sender.tab.url, sender.tab.title );
			}
	);
				
	//-- setup a listener so that if cookies change we refresh the page
	chrome.cookies.onChanged.addListener( 
		function( info ) { parse_cookie(); }
	);
	
	
	//-- determine whether the user is logged in
	function parse_cookie() {
		//console.log('inside parse cookie is ' + DOMAIN);
		chrome.cookies.get({ "url" : DOMAIN, "name" : COOKIE_NAME },
			function( cookie ) {
				window.localStorage.removeItem( "user_id" );
				window.localStorage.removeItem( "user_name" );
				
				if ( cookie ) {
					
					//jsonString = eval( '(' + cookie.value + ')' );
					//console.log('cookie values are '+ cookie.value);
					//var jsonString = cookie.value;
					//jsonString = JSON.parse( "\ cookie.value \");
					//data = eval( '(' + jsonString + ')' );
					//jsonString = jsonString.replace(/\\054/g,",");
					data = JSON.parse( '[' + cookie.value.replace(/\\054/g,",") + ']' );
					var jsonData = JSON.parse(data);
					//console.log('data is ******' +  jsonData.user_name);
					
					if ( jsonData.user_id ) {
						//console.log('user_id is ******' +  jsonData.user_id);
						window.localStorage.setItem( "user_id", jsonData.user_id );
					}
					
					if ( jsonData.user_name ) {
						//console.log('user_name is ******' +  jsonData.user_name);
						window.localStorage.setItem( "user_name", jsonData.user_name );
					}
				}
				else
					console.log( "no cookie" );

				user_id = window.localStorage.getItem( "user_id" );
				user_name = window.localStorage.getItem( "user_name" );
			
				refresh();
			}
		);
	}


	//-- the init function (called refresh as it is called every time
	//-- something changes - namely cookie updates.
	function refresh() {
		
		//--retrieve and fill the global variables
		user_id = window.localStorage.getItem( "user_id" );
		user_name = window.localStorage.getItem( "user_name" );
		
		//-- Make sure the correct favicon is displayed
		if ( user_id && user_name ) {
			console.log('user_name is ******' +  user_id);
			chrome.browserAction.setIcon( { path:"icon.png" } );
		} else {
			chrome.browserAction.setIcon( { path:"icon-dormant.png" } );
		}
	}
	

	/*
	 *
	 */
	function isIgnored( url ) {

		//-- check whether the url contains an ignore_list match.
		for ( i=0; i < IGNORE_LIST.length; i++ )
			if ( url.indexOf( IGNORE_LIST[ i ] ) != -1 )
				return true;

		return false;
	}

	
    /**
     * Main entry point to the script - contentScript.js essentially 
	 * bundles up the text from a web page ready for parsing, and 
	 * transmitting to the prefstore
	 */
	function processVector( text, url, title ) {

		//-- remove any items that have expired
		cleanCache();

		//--retrieve and fill the global variables
		var user_id = window.localStorage.getItem( "user_id" );
		var user_name = window.localStorage.getItem( "user_name" );
		
		//-- if the user is logged in (and we have their details, then we 
		//-- can organize sending the data to their prefstore. Otherwise
		//-- for the moment we discard it
		if ( !( user_id && user_name ) ) 
			return;


		//-- parse the text with min_word_length 3, min_support 3
		doc = new Parser( text, 3, 3 );
		
		//-- create the distillation object (default duration to 10s for now)
		var distillation = new Distillation( doc.fv, url, 10, title, doc.totalWords );

		//-- store the current page being observed, for the stats dropdown.
		window.localStorage.setItem( "lastPage", distillation.stringify() );
		window.localStorage.setItem( "lastPageStatus", null );

		//-- determine whether the page passes the ignore_list
		if ( isIgnored( url ) ) {
			window.localStorage.setItem( "lastPageStatus", "blacklisted url - distillation not sent" );
			return;
		}

		//-- check if the page is new, or we have an identical one in the cache
		if ( !isPageNew( distillation ) ) {
			window.localStorage.setItem( "lastPageStatus", "repeated page - distillation not sent" );
			return
		}

		//-- check if we actually have any keywords to send...
		if ( distillation.fv.length == 0 ) {
			window.localStorage.setItem( "lastPageStatus", "no keywords unearthed - distillation not sent" );
			return
		}

		//-- store the current page being observed, for the stats dropdown.
		window.localStorage.setItem( "lastPage", distillation.stringify() );
		window.localStorage.setItem( "lastPageStatus", null );
		incrementUserStat( "pagesAnalysed" );
		addToCache( distillation );

		//-- transmit to the prefstore
		chrome.browserAction.setIcon( { path:"icon-progress.png" } );
		transmitDistillation( distillation );
		incrementUserStat( "pagesSent" );

	}
	

	/**
     * add the current distillation to the cache
	 */
	function addToCache( distillation ) {

		var cache = window.localStorage.getItem( "cache" );
		if ( cache == null || cache == "null" ) {
			cache = [];
		}
		else {
			cache = JSON.parse( cache );
			cache.push( distillation );
		}

		window.localStorage.setItem( "cache", JSON.stringify( cache ) );
	}


	/**
     * add the current distillation to the cache
	 */
	function cleanCache() {

		var cache = window.localStorage.getItem( "cache" );
		if ( cache == null || cache == "null" )  return;
		else cache = JSON.parse( cache ); 

		now = Math.round ( new Date().getTime() / 1000 );

		for ( index = 0; index < cache.length; index++ ) 
			if ( cache[ index ].mtime > now - CACHE_DURATION )
				break;

		cache = cache.slice( index )
		window.localStorage.setItem( "cache", JSON.stringify( cache ) );
	}


	/**
     * detect if we have seen this exact same page before
	 */
	function isPageNew( distillation ) {
		
		var cache = window.localStorage.getItem( "cache" );
		if ( cache == null || cache == "null" )  return true;
		else cache = JSON.parse( cache ); 
		for ( i=0; i < cache.length; i++ ) {
			if ( cache[ i ].docId == distillation.docId ) {
				if ( cache[ i ].fv.length == distillation.fv.length )
					return false;		
			}
		}

		return true;
	}



	/**
     * Using AJAX, transmit the vector to the user's prefstore.
	 */
	function transmitDistillation( distillation ) {

		user_id = window.localStorage.getItem( "user_id" );
		data = "user_id=" + user_id + "&data=" + distillation.stringify();
		console.log('inside transmit distillation' + user_id + ' and data ' + distillation.stringify());
		//-- attempt to send the distill to the prefstore
		$.ajax({ 
			type : "POST", 
			data : data ,
			url  :  "http://localhost/submitDistill", 
			cache : false,
			timeout : 30000,
			error : function( data ) { transmitFailure( distillation, data ); },
			success : function( data ) { transmitSuccess( distillation, data ); }
		});
	}

	
	/**
     * When a transmission is successful, we still need to check whether
	 * the distillation was successfully processed by the server
	 */
	function transmitSuccess( distillation, response ) {
		
		//-- parse the response
		//var result = eval( '(' + response + ')' );
				
		var result = JSON.parse(  response.replace(/'/g, '"') );
		console.log('result is ******' + result.success);
		if ( result.success ) {
			processSuccess( distillation );
		}
		else {
			processFailure( distillation, "delivery failure: " + result.cause );
		}
	}


	/**
     * The following function is fired when for some reason the distillation
	 * that we packaged up and sent did not reach the server
	 */
	function transmitFailure( distillation, response ) {

		//-- Error find the submitDistill endpoint
		if ( response.status == 404 ) {
			processFailure( distillation, "delivery failure - API unreachable (404)" );
		}

		//-- Error reaching the server
		else if ( response.status == 0 ) {
			processFailure( distillation, "delivery failure - Server unreachable (OOO)" );
		}

		//-- An unknown error has occurred
		else {
			processFailure( distillation, "delivery failure - Cause unknown (" + response.status + ")" );
		}
	}


	/**
     * When a failure occurs we can cache the page visited and try again later
	 */
	function processSuccess( distillation ) {

		//-- TODO: change the logo to a tick for this page.
		chrome.browserAction.setIcon( { path:"icon-success.png" } );
		chrome.browserAction.setBadgeText( { text:"" } );

		//-- update user statistics
		incrementUserStat( "pagesComplete" );

		//-- change last page to be successfully sent
		window.localStorage.setItem( "lastPageStatus", "delivered successfully" );

		//-- no. distillations
	}


	/**
     * When a failure occurs we can cache the page visited and try again later
	 */
	function processFailure( distillation, cause ) {

		//-- update the favicon information to reflect the failure
		chrome.browserAction.setIcon( { path:"icon-failure.png" } );
		chrome.browserAction.setBadgeText({text:""});
		
		//-- specify that the "last page" failed
		window.localStorage.setItem( "lastPageStatus", cause );
	}


	/**
	 * Update user statistics by first retrieving them from the data store
	 * before simply incrementing, and rewriting back to the local data store
	 */
	function incrementUserStat( parameter ) {
		amount = window.localStorage.getItem( parameter );
		if ( !amount ) amount = 0;
		console.log('parameter in bground is ' + parameter + ' and amount is ' + amount);
		window.localStorage.setItem( parameter, ++amount );
	}