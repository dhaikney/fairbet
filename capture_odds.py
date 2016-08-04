#!/usr/bin/env python

import urllib, urllib2, cookielib, pprint, json, time, sys, codecs

#sys.stdout = codecs.getwriter('utf8')(sys.stdout)

IN_PLAY_MATCHES_URL='https://strands.betfair.com/api/ems/inplay/v0?eventTypeId=1&marketBettingTypes=%5B%22ODDS%22%5D'
GET_MARKETS_URL='https://strands.betfair.com/api/ems/all-markets/v0?eventId={0}&eventTypeId=1&marketBettingTypes=%5B%22ODDS%22%5D'
EVENT_URL="https://www.betfair.com/inplayservice/v1.1/eventTimeline?alt=json&eventId={0}&locale=en_GB&ts=1457730988749"
MARKET_DETAILS_URL="https://strands.betfair.com/api/ems/market-data-aggregator/v0?marketId={0}"
AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1"
HEADERS={ 'User-Agent': AGENT , 'X-Application': 'ajhWsonjIgux55OJ'}
LIVE_EVENTS=[]
NEXT_GOAL_MARKETS={}
MATCH_ODDS_MARKETS={}
EVENT_DETAILS={}
output_file=""

def dump(out_string):
  output_file.write(out_string + '\n')
  output_file.flush()


def get_URL(target_url):
  while True:
    try:
      req = urllib2.Request(target_url,headers=HEADERS)
      return urllib2.urlopen(req, timeout=5).read()
    except Exception as e:
      dump ("Could not retrieve URL: " + str(target_url) + str(e))
      time.sleep(1)


def refresh_active_events():
  in_play_results = {}

  # Hit in-play list end_point until a valid result is found
  while 'values' not in in_play_results:
    dump("Refreshing Live Events at " + str(time.time()))
    in_play_json = get_URL(IN_PLAY_MATCHES_URL)
    in_play_results = json.loads(in_play_json)['result']
    if 'values' not in in_play_results:
      time.sleep(10)
  in_play_events = in_play_results['values']

  event_id_list = []  
  for event_list in in_play_events:
    event_id_list += [event['eventId'] for event in event_list['next']['values']]
  # Check for finished events
  for event in LIVE_EVENTS:
    if event not in event_id_list:
      dump ("Event " + str(event) + " looks finished" )
      LIVE_EVENTS.remove(event)
      details_response = get_URL(EVENT_URL.format(event))
      EVENT_DETAILS[str(event)] = json.loads(details_response)
      dump(json.dumps(EVENT_DETAILS[str(event)]))
  # Now check for new ones, note down the next goal market
  for event in event_id_list:
    if event not in LIVE_EVENTS:
      market_response = get_URL(GET_MARKETS_URL.format(event))
      market_events = json.loads(market_response)['markets']
      for market in market_events:
        if market['marketName'] == "Match Odds":
           MATCH_ODDS_MARKETS[str(event)] = market['marketId']
        if market['marketName'] == "Next Goal":
           dump("New event: " + str(event))
           details_response = get_URL(EVENT_URL.format(event))
           EVENT_DETAILS[str(event)] = json.loads(details_response)
           dump(json.dumps (EVENT_DETAILS[str(event)]))
           LIVE_EVENTS.append(event)
           NEXT_GOAL_MARKETS[str(event)] = market['marketId']

def dump_odds_for_market(market_id,event_id):
  market_response = get_URL(MARKET_DETAILS_URL.format(market_id))
  market_data = json.loads(market_response)
  # Occasionally the response is duff...
  if 'eventTypes' not in market_data:
  	return

  latest_odds=str(time.time()) + "," + str(event_id)
  for outcome in market_data['eventTypes'][0]['eventNodes'][0]['marketNodes'][0]['runners']:
    name = outcome['description']['runnerName']
    try:
#          odds_to_back = [p['price'] for p in outcome['exchange']['availableToBack'] ]
      odds_to_back = outcome['exchange']['availableToBack'][0]['price']
      odds_to_lay  = outcome['exchange']['availableToLay'][0]['price']
    except:
      odds_to_back = "n/a"
      odds_to_lay  = "n/a"
    latest_odds += ","+name + "," + str(odds_to_back) + "," + str(odds_to_lay)
  dump(latest_odds)

def grab_odds_main_loop():
  last_events_refresh = 0
  last_odds_refresh = 0
  while True:
    curr_time = time.time()
    if (curr_time - last_events_refresh) > 60:
      refresh_active_events()
      last_events_refresh = curr_time
    if (curr_time - last_odds_refresh) > 20:
      last_odds_refresh = curr_time
      for event in LIVE_EVENTS:
        dump_odds_for_market(NEXT_GOAL_MARKETS[str(event)],event)
        dump_odds_for_market(MATCH_ODDS_MARKETS[str(event)],event)
    else:
      time.sleep(1)

print "Opening: ",sys.argv[1]
output_file = open(sys.argv[1], 'a')
grab_odds_main_loop()
