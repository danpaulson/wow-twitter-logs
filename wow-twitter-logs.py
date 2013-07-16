from local_settings import *

import urllib2
import datetime
import redis
import sys
import HTMLParser

from BeautifulSoup import BeautifulSoup
from twython import Twython

r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
parser = HTMLParser.HTMLParser()
twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)

today = datetime.datetime.now()

# Scrape WoL for updates
url = 'http://worldoflogs.com/guilds/%s/' % WOL_GUILD_ID
response = urllib2.urlopen(url)
soup = BeautifulSoup(response.read())

# Find the latest populated cell (logs), roll over to yesterday if today empty
logs = soup.find(text=today.strftime("%d-%m")).findNext('div').findAll('a')

if len(logs) == 0:  
    today = today - datetime.timedelta(1)
    logs = soup.find(text=today.strftime("%d-%m")).findNext('div').findAll('a')

    if len(logs) == 0:
        sys.exit('There are no logs yet today.')

day = today.strftime("%d-%m")

# Get that night's log page(s)
for log in logs:
    url = 'http://worldoflogs.com%s' % log.get('href')

    response = urllib2.urlopen(url)
    soup = BeautifulSoup(response.read())

    attempts = soup.find(text='Bosses').findNext('ul').findAll('a')

    # Check for new logs, tweet
    for attempt in attempts:
        if 'bosses' not in attempt['href']:
            added = r.sadd(day, attempt.string[:-8])
            attempt_type = 'Wipe' if 'Try' in attempt.string else 'Kill'

            if added:
                status = '#%s %s - http://www.worldoflogs.com%s' % (
                        attempt_type,
                        parser.unescape(attempt.string),
                        attempt['href'])

                twitter.update_status(status=status)

                if VERBOSE:
                    print 'Tweeted: %s' % status

    # Check for Rankings
    ranked_table = soup.find('table', {'class': 'playerRankMixed'})

    if ranked_table:
        ranked = ranked_table.findAll('tr')

        # Remove the header
        ranked.pop(0)

        for ranking in ranked:
            boss = ranking.findAll('td')[2].contents[0]
            dps = ranking.findAll('td')[5].contents[0]
            rank = ranking.find('span').contents
            link = ranking.find('a')

            added = r.sadd('%s_ranked' % day, '%s_%s' % (boss, link.string))
            if added:
                status = '#Rank %s on %s by %s (%s)' % (rank[0], boss, link.string, dps)
                twitter.update_status(status=status)
                if VERBOSE:
                    print 'Tweeted: %s' % status
