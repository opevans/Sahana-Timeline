# This file provides the interface for the timeline
# 
#
#'
import sys
import datetime
import re
import os
from gluon import *
import gluon

class Timeline:
  def __init__(self):
      self.eventlist = [] 
      self.valid = True
  
  def addTable(self, table, namefield, startfield,  endfield=None,descriptionfield=None ,color = None, link = None):
    db = current.db
    validfields =table.keys()
    validfields.append(None)


    if not {endfield, descriptionfield, namefield,startfield}.issubset(validfields):
      self.valid = False
      return
    
    results = db(table[startfield] > 0)
    rows = results.select()
    for row in rows:
      thisevent = {}
      thisevent['start'] = row[startfield]
      thisevent['title'] = row[namefield] 
      thisevent['end'] = (row[endfield] if endfield else None)
      thisevent['description'] = (row[descriptionfield] if descriptionfield else None)
      thisevent['color'] = color
      
      self.eventlist.append(thisevent)
    return True
      


      
      
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
                        {{for event in eventlist:}}
                        {   
                          
                          {{keys = filter(lambda x: event[x], event.keys())}}
                          {{for key in keys:}}
                          '{{=key}}': '{{=event[key]}}'
                          {{if key != keys[-1]:}} , {{pass # The last attribute has no comma to comply with IE}}
                          {{pass}}
                        }{{if event != eventlist[-1]:}}, {{pass # The last event has no comma to comply with IE}}
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
      if self.valid:
        return gluon.template.render(out,context = dict(eventlist=self.eventlist)) 
      else:
        return "Invalid fields specified"
      # timeline will ultimately return the javascript that generates the timeline
        #First it will need to take the arguments and make an events.xml file out of them in this format:
        #http://code.google.com/p/simile-widgets/wiki/Timeline_EventSources

        #Then it will need to return timeline-div.html, which gets events from the events.xml file
      


