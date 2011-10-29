# This file provides the interface for the timeline
# 
#
#
import sys
import datetime
import re
import os
import gluon
class Timeline:

  def showtl(self): #later may have arguments
      return("""
	  
<script type="text/javascript" src="/eden/static/scripts/timeline/timeline_ajax/simile-ajax-api.js?bundle=false"></script>
<script type="text/javascript" src="/eden/static/scripts/timeline/timeline_ajax/simile-ajax-bundle.js"></script>
<link rel="stylesheet" type="text/css" href="/eden/static/scripts/timeline/timeline_ajax/styles/graphics.css">
<link rel="stylesheet" type="text/css" href="/eden/static/scripts/timeline/timeline_js/timeline-bundle.css">
<script type="text/javascript" src="/eden/static/scripts/timeline/timeline_js/timeline-api.js?bundle=false"></script>
<script type="text/javascript" src="/eden/static/scripts/timeline/timeline_js/timeline-bundle.js"></script>
<script type="text/javascript" src="/eden/static/scripts/timeline/timeline_js/scripts/l10n/en/labellers.js"></script>
<script type="text/javascript" src="/eden/static/scripts/timeline/timeline_js/scripts/l10n/en/timeline.js"></script>

<div id="my-timeline" style="height: 150px; border: 1px solid #aaa"></div>
<script>
var tl;
window.onload=onLoad;
window.onresize=onResize;

  function onLoad() {

    var eventSource = new Timeline.DefaultEventSource();    
    var bandInfos = [
      Timeline.createBandInfo({
        trackGap: 1.0,
        width:          "70%", 
        intervalUnit:   Timeline.DateTime.WEEK, 
        intervalPixels: 100,
        eventSource: eventSource
        
     }),
     Timeline.createBandInfo({
         width:          "30%", 
         intervalUnit:   Timeline.DateTime.YEAR, 
         intervalPixels: 200,
        eventSource: eventSource
     })
   ];
   bandInfos[1].syncWith = 0;
   bandInfos[1].highlight = true;

   tl = Timeline.create(document.getElementById("my-timeline"), bandInfos);

   eventSource.loadJSON(
                {
                    'dateTimeFormat': 'iso8601',
                    'events': [
                        {   'start': '2009-03-18',
                            'title': 'A: 2009-03-18'
                        },
                        {   'start': '2009-03-18T00:00:00',
                            'title': 'B: 2009-03-18T00:00:00'
                        },
                        {   'start': '2009-03-19T00:00:00Z',
                            'title': 'C: 2009-03-18T00:00:00Z'
                        },
                        {   'start': '2009-03-18T00:00:00-08:00',
                            'title': 'D: 2009-03-18T00:00:00-08:00'
                        }
                    ]
                },

    document.location.href
   );


 
 }

 var resizeTimerID = null;
 function onResize() {
     if (resizeTimerID == null) {
         resizeTimerID = window.setTimeout(function() {
             resizeTimerID = null;
             tl.layout();
         }, 500);
     }
 }
</script>
""" )
        
      # timeline will ultimately return the javascript that generates the timeline
        #First it will need to take the arguments and make an events.xml file out of them in this format:
        #http://code.google.com/p/simile-widgets/wiki/Timeline_EventSources

        #Then it will need to return timeline-div.html, which gets events from the events.xml file
      


