#!/usr/bin/env python2.7
# Parse Odds received from Betfair

import re, sys,pprint, json, ast 
from collections import defaultdict
from datetime import datetime
import calendar
import dateutil.parser
EVENT_LIST=[]
BIG_ODDS_LIST=[]
NEXT_GOAL_ODDS=defaultdict(list)
MATCH_ODDS=defaultdict(list)

def getEventByTeams(home_team,away_team):
  for event in EVENT_LIST:
    if event['score']['away']['name'] == away_team and \
       event['score']['home']['name'] == home_team:
       return event
  # print "Didn't find for",home_team,away_team
  return None

def getEventByID(event_id):
  for event in EVENT_LIST:
   if event['eventId'] == event_id:
    return event
  # print "Didn't find for",home_team,away_team
  return None

def convertDateToTimestamp(event_time):
  TIME_FORMAT="%Y-%m-%dT%H:%M:%S.%fZ"
  event_date_time = datetime.strptime(event_time,TIME_FORMAT)
  res = calendar.timegm(event_date_time.utctimetuple()) # Stack Overflow
  return res

def convertTimestamptoUTC(timestamp):
  res = datetime.utcfromtimestamp(timestamp)
  return res

def addOddsToEvents(odds):
  event = odds['event_id']
  if odds['other_outcome'] == "No Goal": # Next Goal
    NEXT_GOAL_ODDS[event].append(odds)
  else: 
    MATCH_ODDS[event].append(odds)

def addEventToList(event):
  for i in range(len(EVENT_LIST)):
    if EVENT_LIST[i]['eventId'] == event['eventId']:
      EVENT_LIST[i] = event
      return
  # Not found, new event
  EVENT_LIST.append(event)

def getOddsClosestToTime(event, update_time):
  # 2016-03-13T23:19:13.985Z
  TIME_FORMAT="%Y-%m-%dT%H:%M:%S.%fZ"
  goal_time = datetime.strptime(update_time,TIME_FORMAT)
  current_best_time=datetime.fromtimestamp(0)
  res = {}
  for odds in event['next_goal_odds']:
    odds_time = datetime.fromtimestamp(odds['timestamp'])
    if odds_time < goal_time and \
       odds_time > current_best_time and \
       odds['home_back'] != "n/a":
      res = odds
      current_best_time = odds_time
  return res


def analyseLateGoals():
  for event in EVENT_LIST:
    if event['status'] == "COMPLETE":
      # print "FINITO "
      for update in event['updateDetails']:
        if update['updateType'] == 'Goal' and update['matchTime'] >=90:
          print update['teamName'], update['updateTime']
          # pprint.pprint(event)
          odds = getOddsClosestToTime(event,update['updateTime'])
          if odds != {}:
            pprint.pprint(datetime.fromtimestamp(odds['timestamp']))  
            print odds
          break

def parseEventCompletion(completion_event):
  master_event = getEventByID(completion_event['eventId'])
  if master_event == None:
    print "did not find start of event",completion_event['eventId']
    master_event = completion_event
    addEventToList(master_event)
  master_event['status'] = "COMPLETE"
  master_event['home_score'] = completion_event['score']['home']['score']
  master_event['away_score'] = completion_event['score']['away']['score']
  for update in completion_event['updateDetails']:  
    update_timestamp = convertDateToTimestamp(update['updateTime'])
    if update['updateType'] == 'KickOff':
      master_event['kick_off_time'] = update_timestamp
    elif update['updateType'] == 'FirstHalfEnd':
      master_event['first_half_end'] = update_timestamp
    elif update['updateType'] == 'SecondHalfKickOff':
      master_event['second_half_start'] = update_timestamp
    elif update['updateType'] == 'SecondHalfEnd':
      master_event['full_time'] = update_timestamp

def getMatchTime(timestamp,match_event):
  if timestamp >= match_event['second_half_start']:
    offset = match_event['second_half_start'] - (45 * 60 ) 
  else:
    offset = match_event['kick_off_time']
  match_time = timestamp - offset 
  mins= int(match_time / 60)
  secs= int(match_time % 60)
  return (mins,secs)

def passesScoreFilter(event):
  # True if nil nil
  return True
  return (event['home_score'] == 0 and event['away_score'] == 0)

def getFilteredEvents():
  res = []
  for event in EVENT_LIST:
    if event['status'] == "COMPLETE" and passesScoreFilter(event):
      res.append(event)
  return res

def dumpOdds():
  for event in getFilteredEvents():
    event_id = str(event['eventId'])
    print event_id, event['kick_off_time'], event['second_half_start'], event['full_time']
    for odds in MATCH_ODDS[event_id]:
      odds_time = convertTimestamptoUTC(odds['timestamp']).strftime("%H:%M:%S")
      match_time = getMatchTime(odds['timestamp'], event)

      output_values=[odds_time,odds['home_back'], odds['away_back'],odds['other_back']]
      print ",".join(map(str,output_values))

def readJSONLine(line):
  try:
    # event = ast.literal_eval(line)
    event = json.loads(line)
  except Exception as e:
    print "Ignoring duff JSON line:", line
    return

  if 'eventId' not in event:
    print "Didn't find eventId: ", line
  elif event['status'] == "IN_PLAY":
    event['next_goal_odds'] = []
    event['match_odds']     = []
    addEventToList(event)
  elif event['status'] == "COMPLETE":
    parseEventCompletion(event)

def readOddsline(line):
# Example:
# 1458600815.49,27722176,Rosario Central,1.12,1.13,Sarmiento de Junin,44,90,The Draw,10,11
  values = unicode(line,"utf-8").split(",")
  odds_snapshot = {
                        'timestamp': float(values[0]),
                        'event_id' : values[1],
                        'home_team': values[2],
                        'home_back': values[3],
                        'home_lay' : values[4],
                        'away_team': values[5],
                        'away_back': values[6],
                        'away_lay' : values[7],
                        'other_outcome': values[8],
                        'other_back': values[9],
                        'other_lay' : values[10],
                        }
  addOddsToEvents(odds_snapshot)

def parse_file(fname):
  f = open(fname, 'r')
  line = f.readline()
  while line:
    if line[0] == '{':
      readJSONLine(line)
    elif "The Draw" in line or "No Goal" in line:
      readOddsline(line)
    line = f.readline()
  print "Parsed", len(EVENT_LIST), "Events"

def main(args):
  if len(args) != 2:
    print "Usage: {} <filename>".format(args[0])
    print "Analysis of live odds"
    sys.exit(1)
  parse_file(args[1])
  dumpOdds()

if __name__=='__main__':
  sys.exit(main(sys.argv))
