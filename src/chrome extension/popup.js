// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

//-- Setup the constants that for the pages scripts
	DIV_NAMES = new Array();
	DIV_NAMES[ 0 ] = "loggedInBox";
	DIV_NAMES[ 1 ] = "loggedOutBox";
	DIV_NAMES[ 2 ] = "registerBox";
	DIV_NAMES[ 3 ] = "loggedOutMsg";
	PREFSTORE = window.localStorage.getItem( "prefstore" );
	COOKIE_NAME = window.localStorage.getItem( "cookie_name" );	
	DOMAIN = window.localStorage.getItem( "domain" );	
	
	//-- Setup the global variables for the page
	var user_id;
	var user_name;
	
	//-- and startup the main function
	refresh( 0 );
	
	//-- Main function (also named refresh because it is called after 
	//-- any action has occurred in order to update the page view)	
	function refresh( duration ) {
		
		user_id = window.localStorage.getItem( "user_id" );
		user_name = window.localStorage.getItem( "user_name" );
		
		$( '#user_name' ).html( user_name ); 
		
		//-- create the appropriate information box
		if ( user_id && !user_name ) {
			
			displayBox( "registerBox", duration );
		}
		else if ( user_id && user_name ) {
			
			displayBox( "loggedInBox", duration );
		}
		else {
			
			chrome.browserAction.setIcon( { path:"icon-dormant.png" } );
			displayBox( "loggedOutBox", duration );
			$( '#loggedOutMsg' ).show( duration );
		}
		
		UpdateCurrentPageBox( duration );
	}


	/**
	 *
	 */
	function UpdateCurrentPageBox( duration ) {

		if (  user_id && user_name ) {

			pagesAnalysed = window.localStorage.getItem( "pagesAnalysed" );
			pagesSent = window.localStorage.getItem( "pagesSent" );
			pagesComplete = window.localStorage.getItem( "pagesComplete" );
			console.log('pages analysed is ' + pagesAnalysed + ' pagesSent is ' + pagesSent + ' pagesComplete is ' + pagesComplete);
			pagesSent = pagesSent ? pagesSent : 0;
			pagesComplete = pagesComplete ? pagesComplete : 0;
			pagesAnalysed = pagesAnalysed ? pagesAnalysed : 0;

			//lastPage = eval( '(' + window.localStorage.getItem( "lastPage" ) + ')' );
			//console.log('last page before ' + window.localStorage.getItem( "lastPage" ));
			lastPage = JSON.parse(window.localStorage.getItem( "lastPage" ));
			
			//console.log('last page after '+ lastPage.fv + ' type is ' + typeof lastPage );
			lastPageStatus = window.localStorage.getItem( "lastPageStatus" );

			$('#pagesAnalysed').html( "Pages distilled: " + pagesAnalysed );
			$('#pagesSent').html( "Deliveries attempted: " + pagesSent );
			$('#pagesComplete').html( "Deliveries completed: " + pagesComplete );
			
			$('#termlist').html( "" );
			if ( lastPage ) {
				fvLength = 0;
				$.each( lastPage.fv, function( key, value ){
					fvLength++;
					$( '#termlist' ).append( 
						"<span class='blockTerm'><span class='blockNum'>" + value + "</span> " + key + " </span> &nbsp;"  
					);
				});
				
				$( '#pageTitle' ).html( "Page Title: " + unescape( lastPage.docName.substring( 0, 40 ) ) + "..." );
				$( '#pageStats' ).html( "Stats: " + lastPage.totalWords + " words / " + fvLength + " terms extracted" );
				$( '#pageStatus' ).html( "Status: <i>" + lastPageStatus + "</i>" ); 
			}
			else {
				$( '#pageTitle' ).html( "Page Title:" );
				$( '#pageStats' ).html( "Stats:" );
				$( '#pageStatus' ).html( "Status:" ); 
			}
			
			$( '#currentPageBox' ).show( duration );
		}
		else {
			$( '#currentPageBox' ).hide( duration );
		}
	}
	
	
	/**
	 * Function that hides or displays boxes depending on 
	 * the state of the model
	 */ 
	function displayBox( divToShow, duration ) {
		for( i = 0; i < DIV_NAMES.length; i++ ) {
			if ( divToShow == DIV_NAMES[ i ] ) {
				$( '#' + DIV_NAMES[ i ] ).show( duration );
			} 
			else {
				$( '#' + DIV_NAMES[ i ] ).hide( duration );
			}
		}
	}
	
	
	/**
	 * Function that redirects the user to the server's openid login
	 */ 
	function login( provider ) {
		window.open( PREFSTORE + "login?provider=" + provider, "_blank" );
	}
	
	
	/**
	 * Function that redirects the user to the server's openid login
	 */ 
	function logout( provider ) {

		chrome.cookies.remove({ "url" : DOMAIN, "name" : COOKIE_NAME }, function(info) {
				user_id = window.localStorage.removeItem( "user_id" );
				user_name = window.localStorage.removeItem( "user_name" );
				refresh(0);
			}
		);
	}
	
	
	/**
	 * Function that redirects the user to the server's account registration page
	 */ 
	function register( provider ) {
		window.open( PREFSTORE + "register", "_blank" )
	}
	
	
	/**
	 * Function that resets all of the extensions statistics
	 */
	function clearLocalStorage() {
		if ( confirm( 'Are you sure you want to clear Local Storage? This is not undoable...' ) ) {
			window.localStorage.setItem( "pagesAnalysed" ) = 0;
			window.localStorage.setItem( "pagesSent" ) = 0;
			window.localStorage.setItem( "pagesComplete" ) = 0;
			window.localStorage.setItem( "lastPage" ) = "{}";  
			window.localStorage.setItem( "lastPageStatus" ) = "";
			refresh( 0 );
		}
	}
	
	$(function() {
        // Initialization work goes here.
		refresh();
      });
	
    document.addEventListener('DOMContentLoaded', function () {
        var google = document.getElementById('google');
        google.addEventListener('click',function() {
        	login('google');
	    });
        var gimage = google.getElementsByTagName("img")[0];
        gimage.addEventListener("mouseover", mouseover(google), false);
        gimage.addEventListener("mouseout", mouseover(google), false);
        
        var yahoo = document.getElementById('yahoo');
        yahoo.addEventListener('click',function() {
        	login('yahoo');
	    });
        var yimage = yahoo.getElementsByTagName("img")[0];
        yimage.addEventListener("mouseover", mouseover(yahoo), false);
        yimage.addEventListener("mouseout", mouseover(yahoo), false);
        
        var aol = document.getElementById('aol');
        aol.addEventListener('click',function() {
        	login('aol');
	    });
        aimage = aol.getElementsByTagName("img")[0];
        aimage.addEventListener("mouseover", mouseover(aol), false);
        aimage.addEventListener("mouseout", mouseover(aol), false);
        
        var myopenid = document.getElementById('myopenid');
        myopenid.addEventListener('click',function() {
        	login('myopenid');
	    });
        var mimage = myopenid.getElementsByTagName("img")[0];
        mimage.addEventListener("mouseover", mouseover(myopenid), false);
        mimage.addEventListener("mouseout", mouseover(myopenid), false);
        
        document.getElementById('logout').addEventListener('click',function() {
        	logout();
	    });
       
        
    });    
        
    function mouseover(element){
    	element.className = "openid_over";
    }
    function mouseout(element){
    	element.className =  "openid_out";
    } 
	
