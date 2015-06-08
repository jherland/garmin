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
import shutil
import urllib


def file_exists_in_folder(filename, folder):
    "Check if the file exists in folder or any subfolder"
    for _, _, files in os.walk(folder):
        if filename in files:
            return True
    return False


class GarminScraper(object):

    ORIG_ZIP = "https://connect.garmin.com/proxy/download-service/files/activity/%s"
    TCX = "https://connect.garmin.com/proxy/activity-service-1.1/tcx/activity/%s?full=true"
    GPX = "https://connect.garmin.com/proxy/activity-service-1.1/gpx/activity/%s?full=true"
    KML = "https://connect.garmin.com/proxy/activity-service-1.0/kml/activity/%s?full=true"
    SPLITS_CSV = "https://connect.garmin.com/csvExporter/%s.csv"

    def __init__(self, username):
        self.username = username
        self.agent = mechanize.Browser()

        # Apparently Garmin Connect attempts to filter on these browser headers;
        # without them, the login will fail.
        self.agent.addheaders = [
            ('User-agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.2 (KHTML, like Gecko) Chrome/15.0.874.121 Safari/535.2'),
        ]

    def login(self, password):
        base_url = "http://connect.garmin.com/en-US/signin"
        gauth_url = "http://connect.garmin.com/gauth/hostname"
        sso_url = "https://sso.garmin.com/sso"
        css_url = "https://static.garmincdn.com/com.garmin.connect/ui/css/gauth-custom-v1.1-min.css"
        redirect_url = "https://connect.garmin.com/post-auth/login"

        # First establish contact with Garmin and decipher the local host.
        page = self.agent.open(base_url)
        pattern = "\"\S+sso\.garmin\.com\S+\""
        script_url = re.search(pattern, page.get_data()).group()[1:-1]
        self.agent.open(script_url)
        hostname_url = self.agent.open(gauth_url)
        hostname = json.loads(hostname_url.get_data())['host']

        # Package the full login GET request...
        data = {
            'service': redirect_url,
            'webhost': hostname,
            'source': base_url,
            'redirectAfterAccountLoginUrl': redirect_url,
            'redirectAfterAccountCreationUrl': redirect_url,
            'gauthHost': sso_url,
            'locale': 'en_US',
            'id': 'gauth-widget',
            'cssUrl': css_url,
            'clientId': 'GarminConnect',
            'rememberMeShown': 'true',
            'rememberMeChecked': 'false',
            'createAccountShown': 'true',
            'openCreateAccount': 'false',
            'usernameShown': 'false',
            'displayNameShown': 'false',
            'consumeServiceTicket': 'false',
            'initialFocus': 'true',
            'embedWidget': 'false',
            'generateExtraServiceTicket': 'false',
        }

        # ...and officially say "hello" to Garmin Connect.
        login_url = 'https://sso.garmin.com/sso/login?%s' % urllib.urlencode(data)
        self.agent.open(login_url)

        # Set up the login form.
        self.agent.select_form(predicate=lambda f: 'id' in f.attrs and f.attrs['id'] == 'login-form')
        self.agent['username'] = self.username
        self.agent['password'] = password

        # Submit the login!
        res = self.agent.submit()
        if res.get_data().find("Invalid") >= 0:
            quit("Login failed! Check your credentials, or submit a bug report.")
        elif res.get_data().find("SUCCESS") >= 0:
            print('Login successful! Proceeding...')
        else:
            quit('UNKNOWN STATE. This script may need to be updated. Submit a bug report.')

        # Now we need a very specific URL from the response.
        response_url = re.search("response_url\s*=\s*'(.*)';", res.get_data()).groups()[0]
        self.agent.open(response_url)

        # In theory, we're in.

    def activities(self, outdir, increment=100, limit=None):
        activities_url = "http://connect.garmin.com/proxy/activity-search-service-1.2/json/activities?start=%s&limit=%s"

        if limit and increment > limit:
            increment = limit
        currentIndex = 0
        initUrl = activities_url % (currentIndex, increment)  # 100 activities seems a nice round number
        try:
            response = self.agent.open(initUrl)
        except:
            print('Wrong credentials for user {}. Skipping.'.format(self.username))
            return
        search = json.loads(response.get_data())
        totalActivities = int(search['results']['totalFound'])
        if limit and limit < totalActivities:
            totalActivities = limit
        while True:
            for item in search['results']['activities']:
                # Read this list of activities and save the files.
                activityId = item['activity']['activityId']
                url = self.TCX % activityId
                file_name = '{}_{}.txt'.format(self.username, activityId)
                if file_exists_in_folder(file_name, outdir):
                    print('{} already exists in {}. Skipping.'.format(file_name, outdir))
                    continue
                print('{} is downloading...'.format(file_name))
                datafile = self.agent.open(url).get_data()
                file_path = os.path.join(outdir, file_name)
                f = open(file_path, "w")
                f.write(datafile)
                f.close()
                shutil.copy(file_path, os.path.join(os.path.dirname(os.path.dirname(file_path)), file_name))

            if (currentIndex + increment) >= totalActivities:
                # All done!
                break

            # We still have at least 1 activity.
            currentIndex += increment
            url = activities_url % (currentIndex, increment)
            response = self.agent.open(url)
            search = json.loads(response.get_data())


def download_files_for_user(username, password, output):
    gs = GarminScraper(username)
    gs.login(password)

    user_output = os.path.join(output, username)
    download_folder = os.path.join(user_output, 'Historical')

    # Create output directory (if it does not already exist).
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    # Scrape all the activities.
    gs.activities(download_folder)


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
        print('Downloading files from {}\'s Garmin account'.format(username))
        download_files_for_user(username, password, args.output)


if __name__ == '__main__':
    main()
