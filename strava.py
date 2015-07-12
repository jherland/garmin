#!/usr/bin/env python2

from __future__ import print_function

from datetime import datetime
import os
import gpxpy


class Activity(object):
    def __init__(self, gpx_path):
        self.path = gpx_path
        fname = os.path.splitext(os.path.basename(self.path))[0]
        date, time, self.what = fname.split('-', 2)
        self.when = datetime.strptime(date + time, '%Y%m%d%H%M%S')
        self._gpx = None

    def __unicode__(self):
        return u'{} {}: {}'.format(self.when, self.what, self.name)

    def __str__(self):
        return unicode(self).encode('utf8')

    @property
    def gpx(self):
        if self._gpx is None:
            with open(self.path) as f:
                self._gpx = gpxpy.parse(f)
        return self._gpx

    @property
    def name(self):
        try:
            return self.gpx.tracks[0].name
        except IndexError:
            return 'Unknown'


def walk_activities(act_dir, sorted=False):
    for dirpath, dirnames, filenames in os.walk(act_dir):
        if sorted:
            filenames.sort()
        for fname in filenames:
            if fname.endswith('.gpx'):
                yield Activity(os.path.join(dirpath, fname))


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Strava Activity lister')
    parser.add_argument(
        '-d', '--dir', default='.',
        help='Directory where Strava activities (.gpx files) are stored.')
    args = parser.parse_args()

    for act in walk_activities(args.dir, sorted=True):
        print(act)


if __name__ == '__main__':
    main()
