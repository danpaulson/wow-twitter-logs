from local_settings import *

import urllib2
import datetime
import redis
import sys

from BeautifulSoup import BeautifulSoup
from twython import Twython

r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
today = datetime.datetime.now()

# Scrape WoL for updates
url = 'http://worldoflogs.com/guilds/%s/' % WOL_GUILD_ID
response = urllib2.urlopen(url)
soup = BeautifulSoup(response.read())

# Find the latest populated cell, roll over to yesterday if today is empty
cell = soup.find(text=today.strftime("%d-%m")).findNext('div').findAll('a')

if len(cell) == 0:  
    today = today - datetime.timedelta(1)
    cell = soup.find(text=today.strftime("%d-%m")).findNext('div').findAll('a')

    if len(cell) == 0:
        sys.exit('There are no logs yet today.')

day = today.strftime("%d-%m")

# Get that night's log page
url = 'http://worldoflogs.com%s' % cell[0].get('href')
response = urllib2.urlopen(url)
soup = BeautifulSoup(response.read())

attempts = soup.find(text='Bosses').findNext('ul').findAll('a')
ranked = soup.find('table', {'class': 'playerRankMixed'}).findAll('tr')

twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)

# Check for new logs, tweet
for attempt in attempts:
    if 'bosses' not in attempt['href']:
        added = r.sadd(day, attempt.string)
        attempt_type = 'Wipe' if 'Try' in attempt.string else 'Kill'

        if added:
            twitter.update_status(status='[%s] %s' % (attempt_type, attempt.string))

# Remove the header
ranked.pop(0)

for ranking in ranked:
    boss = ranking.findAll('td')[2].contents[0]
    dps = ranking.findAll('td')[5].contents[0]
    rank = ranking.find('span').contents
    link = ranking.find('a')
    
    added = r.sadd('%s_ranked' % day, '%s_%s' % (boss, link.string))
    if added:
        twitter.update_status(status='[Rank] %s on %s by %s (%s)' % (rank[0], boss, link.string, dps))
