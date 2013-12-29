from __future__ import division
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
        sys.exit('There are no logs today.')

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
            description = parser.unescape(attempt.string)
            raid_format_check = RAID_FORMAT in description
            boss_check = True in [boss in description for boss in TRACKED_BOSSES.keys()]

            # Find Boss name
            for name in TRACKED_BOSSES.keys():
                if name in description:
                    boss_name = name

            if added and raid_format_check and boss_check:
                if attempt_type == 'Wipe':
                    url = 'http://www.worldoflogs.com%s' % attempt['href']
                    response = urllib2.urlopen(url)
                    soup = BeautifulSoup(response.read())

                    damage_table = soup.find(text='Damage done by target').findNext('table').find(text=boss_name).parent.parent.parent.findNext('td').text
                    damage_done = int(damage_table.replace(' ',''))
                    damage_total = TRACKED_BOSSES[boss_name]

                    if damage_total > 0:
                        percentage = int(damage_done) / int(damage_total)
                        attempt_type = '%s (%s%%)' % (attempt_type, int(percentage*100))

                status = '#%s %s - http://www.worldoflogs.com%s' % (
                        attempt_type,
                        description,
                        attempt['href'])

                if not DEBUG:
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
                if not DEBUG:
                    twitter.update_status(status=status)
                if VERBOSE:
                    print 'Tweeted: %s' % status
