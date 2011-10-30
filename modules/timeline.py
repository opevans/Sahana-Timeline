# This file provides the interface for the timeline
# 
#
#
import sys
import datetime
import re
import os
from gluon import *
import gluon

class Timeline:
  
  def addTable(self, table, startfield, namefield, descriptionfield=None , endfield=None):
      self.fieldnames = {'starttime':startfield, 'finishtime':endfield, 'name':namefield, 'desc':descriptionfield}
      db = current.db
      results = db(table[startfield] > 0)
      self.rows = results.select()
#      for x in rows:
#         tml = tml + x.name + " " + str(x.datetime) + "<br>" 
#       self. showtl(rows           

      
      
  def showtl(self): #later may have arguments
      out = """
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
                        {{for row in rows:}}
                        {   'start': '{{=row[fieldnames['starttime']] }}',
                            'title': '{{=row[fieldnames['name']] }}'
                        },
                        {{pass}}
                        
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
"""
  
      return gluon.template.render(out,context = dict(rows=self.rows, fieldnames= self.fieldnames))
      # timeline will ultimately return the javascript that generates the timeline
        #First it will need to take the arguments and make an events.xml file out of them in this format:
        #http://code.google.com/p/simile-widgets/wiki/Timeline_EventSources

        #Then it will need to return timeline-div.html, which gets events from the events.xml file
      


