#!/usr/bin/env python2
"""
This script was inspired from tmcw's Ruby script doing the same thing:

    https://gist.github.com/tmcw/1098861

And recent fixes implemented thanks to the login structure by wederbrand:

    https://github.com/wederbrand/workout-exchange/blob/master/garmin_connect/download_all.rb

The goal is to iteratively download all detailed information from Garmin Connect
and store it locally for further perusal and analysis. This is still very much
preliminary; future versions should include the ability to seamlessly merge
all the data into a single file, filter by workout type, and other features
to be determined.
"""

from __future__ import print_function

import json
import mechanize
import os
import re
import urllib

from garmin import GarminStore


class GarminScraper(object):

    def __init__(self, username):
        self.username = username
        self.agent = mechanize.Browser()

        # Apparently Garmin Connect attempts to filter on these browser headers;
        # without them, the login will fail.
        self.agent.addheaders = [
            ('User-agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.2 (KHTML, like Gecko) Chrome/15.0.874.121 Safari/535.2'),
        ]

    def login(self, password):
        """Perform the Garmin Connect login protocol."""
        # Say "hello" to Garmin Connect.
        self.agent.open(
            'https://sso.garmin.com/sso/login?' +
            urllib.urlencode({
                'service': "https://connect.garmin.com/post-auth/login",
                'clientId': 'GarminConnect',
            }))

        # Set up the login form.
        self.agent.select_form(
            predicate=lambda f: f.attrs.get('id') == 'login-form')
        self.agent['username'] = self.username
        self.agent['password'] = password

        # Submit the login!
        response = self.agent.submit().get_data()
        if 'Invalid' in response:
            raise RuntimeError('Login failed! Check your credentials, or submit a bug report.')
        elif 'SUCCESS' in response:
            print('Login successful! Proceeding...')
        else:
            raise RuntimeError('UNKNOWN STATE. This script may need to be updated. Submit a bug report.')

        # Now we need a very specific URL from the response.
        response_url = re.search("response_url\s*=\s*'(.*)';", response).group(1)
        self.agent.open(response_url)

        # In theory, we're in.

    def activities(self, limit=None):
        """Generate activities in reverse chronological order.

        Yields 'raw' activity dicts parsed from the JSON retrieved from the
        server."""
        activities_url = "http://connect.garmin.com/proxy/activity-search-service-1.2/json/activities?start={start}&limit={limit}"

        batch_size = 100  # Max #activities to retrieve per request.
        i = 0
        while limit is None or i < limit:
            if limit is not None:
                batch_size = min(batch_size, limit - i)
            url = activities_url.format(start=i, limit=batch_size)
            response = json.loads(self.agent.open(url).get_data())
            total_activities = response['results']['totalFound']
            for item in response['results']['activities']:
                yield item['activity']
                i += 1
            if i >= total_activities:
                break

    FileType = {
        'json': lambda a: json.dumps(a, sort_keys=True),
        'orig.zip': "https://connect.garmin.com/proxy/download-service/files/activity/{activityId}",
        'tcx': "https://connect.garmin.com/proxy/activity-service-1.1/tcx/activity/{activityId}?full=true",
        'gpx': "https://connect.garmin.com/proxy/activity-service-1.1/gpx/activity/{activityId}?full=true",
        'kml': "https://connect.garmin.com/proxy/activity-service-1.0/kml/activity/{activityId}?full=true",
        'csv': "https://connect.garmin.com/csvExporter/{activityId}.csv",
    }

    def download(self, activity, filetype):
        handler = self.FileType[filetype]
        if callable(handler):
            return handler(activity)
        else:
            # GC gives:
            #  - HTTP 500 when the .kml file does not exist
            #  - HTTP 404 when the .orig.zip file does not exist
            try:
                return self.agent.open(handler.format(**activity)).get_data()
            except mechanize.HTTPError as e:
                if (int(e.code), filetype) in [(404, 'orig.zip'),
                                               (500, 'kml')]:
                    raise KeyError('{}.{}'.format(
                        activity['activityId'], filetype))
                else:
                    raise

    @classmethod
    def filename(cls, activity, filetype):
        assert filetype in cls.FileType
        return '{}.{}'.format(activity['activityId'], filetype)


def credentials_from_prompt():
    import getpass
    print("Please fill in your Garmin account credentials (NOT saved).")
    yield raw_input('Username: '), getpass.getpass('Password: ')


def credentials_from_file(f):
    for line in f:
        try:
            username, password = line.split(',')
            yield username.strip(), password.strip()
        except ValueError:
            print('Skipping malformed line "{}"'.format(line.strip()))


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Garmin Data Scraper',
        epilog='Because the hell with APIs!')
    parser.add_argument(
        '-c', '--csv', required=False, type=argparse.FileType('r'),
        help='CSV file with username/password pairs (comma separated).')
    parser.add_argument(
        '-o', '--output', required=False, default='.',
        help='Output directory.')
    args = parser.parse_args()

    if args.csv:
        credentials = credentials_from_file(args.csv)
    else:
        credentials = credentials_from_prompt()

    for username, password in credentials:
        remote = GarminScraper(username)
        remote.login(password)

        local = GarminStore(os.path.join(args.output, username))
        print('Downloading from {}\'s Garmin account into {}/...'.format(
            username, local.basedir))

        for activity in remote.activities():
            json_filename = remote.filename(activity, 'json')
            remote_json = remote.download(activity, 'json')
            try:
                local_json = local.read(json_filename)
            except KeyError:
                local_json = None

            # If JSON data is unchanged from previous download session, then we
            # assume that any associated (same activity - different file types)
            # previous downloads are unchanged as well
            if local_json == remote_json:
                print('Skipping {} (already exists)...'.format(json_filename))
                unchanged = True
            else:
                print('Downloading {}...'.format(json_filename))
                local.write(json_filename, remote_json)
                unchanged = False

            for filetype in set(remote.FileType.keys()) - {'json'}:
                filename = remote.filename(activity, filetype)
                if unchanged and filename in local:
                    print('Skipping {} (already exists)...'.format(filename))
                    continue
                print('Downloading {}...'.format(filename))
                try:
                    local.write(filename, remote.download(activity, filetype))
                except KeyError:
                    print('Failed to download {}. Skipping!'.format(filename))
                    continue


if __name__ == '__main__':
    main()
