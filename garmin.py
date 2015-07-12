#!/usr/bin/env python2

from __future__ import print_function

from contextlib import contextmanager
from datetime import datetime
import json
import os


class Activity(object):
    def __init__(self, json_path):
        self.json_path = json_path
        with open(self.json_path) as f:
            self.json = json.load(f)

    def __unicode__(self):
        return u'{} {} {}: {}'.format(
            self.when, self.activityId, self.what, self.name)

    def __str__(self):
        return unicode(self).encode('utf8')

    @property
    def activityId(self):
        return self.json['activityId']

    @property
    def when(self):
        return datetime.strptime(
            self.json['activitySummary']['BeginTimestamp']['value'],
            '%Y-%m-%dT%H:%M:%S.000Z')

    @property
    def what(self):
        return self.json['activityType']['display']

    @property
    def name(self):
        return self.json['activityName']


class GarminStore(object):

    FileType = {
        'json': '.json',
        'orig': '.orig.zip',
        'tcx': '.tcx',
        'gpx': '.gpx',
        'kml': '.kml',
        'csv': '.csv',
    }

    def __init__(self, where):
        self.basedir = where

        if not os.path.exists(self.basedir):
            os.makedirs(self.basedir)

    @classmethod
    def filename(cls, activityId, filetype):
        return activityId + cls.FileType[filetype]

    def path(self, filename):
        assert os.sep not in filename
        return os.path.join(self.basedir, filename)

    def __contains__(self, filename):
        return os.path.exists(self.path(filename))

    @contextmanager
    def open(self, filename, mode='r'):
        if mode == 'r':
            with open(self.path(filename), 'rb') as f:
                yield f
            return

        assert mode == 'w'
        # Write into tmp file; rename into place on success
        path = self.path(filename) + '.tmp'
        f = open(path, 'wb')
        try:
            yield f
        except:  # failure -> roll back
            f.close()
            os.remove(path)
            raise
        else:  # success -> commit
            f.close()
            os.rename(path, self.path(filename))

    def read(self, filename):
        if filename not in self:
            raise KeyError(filename)
        with self.open(filename, 'r') as f:
            return f.read()

    def write(self, filename, data):
        with self.open(filename, 'w') as f:
            f.write(data)

    def walk(self, sorted=False):
        for dirpath, dirnames, filenames in os.walk(self.basedir):
            if sorted:
                filenames.sort()
            for fname in filenames:
                if fname.endswith(self.FileType['json']):
                    yield Activity(os.path.join(dirpath, fname))


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Garmin Activity lister')
    parser.add_argument(
        '-d', '--dir', default='.',
        help='Directory where Garmin activities (.json files) are stored.')
    args = parser.parse_args()

    for act in GarminStore(args.dir).walk(sorted=True):
        print(act)


if __name__ == '__main__':
    main()
