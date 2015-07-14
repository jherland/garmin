#!/usr/bin/env python2

from __future__ import print_function

import os

import garmin
import strava


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Strava Activity lister')
    parser.add_argument(
        '-g', '--garmin', default='./garmin',
        help='Directory where Garmin activities are stored.')
    parser.add_argument(
        '-s', '--strava', default='./strava',
        help='Directory where Strava activities (.gpx files) are stored.')
    parser.add_argument(
        '-b', '--both', action='store_true',
        help='List activities that appear both on Garmin and Strava.')
    parser.add_argument(
        '-f', '--format', default='tcx',
        help='Provide filenames for upload in this format (defaults to tcx).')
    args = parser.parse_args()

    s_acts = list(strava.walk_activities(args.strava, sorted=True))
    print('Found {} Strava activities in {}'.format(len(s_acts), args.strava))
    g_store = garmin.GarminStore(args.garmin)
    g_acts = list(sorted(g_store.walk(), key=lambda a: a.when))
    print('Found {} Garmin activities in {}'.format(len(g_acts), args.garmin))

    g_only, both, s_only = [], [], []
    while g_acts and s_acts:
        if g_acts[0].when < s_acts[0].when:
            g_only.append(g_acts.pop(0))
        elif g_acts[0].when == s_acts[0].when:
            both.append((g_acts.pop(0), s_acts.pop(0)))
        else:  # g_acts[0].when > s_acts[0].when
            s_only.append(s_acts.pop(0))

    if both:
        print('Present on both Garmin and Strava ({}):'.format(len(both)))
        if args.both:
            for g, s in both:
                print('   ', g, '/', s)
    if g_only:
        print('Only on Garmin ({}):'.format(len(g_only)))
        for g in g_only:
            print('   ', g)
    if s_only:
        print('Only on Strava ({}):'.format(len(s_only)))
        for s in s_only:
            print('   ', s)

    # Prepare the last 25 from g_only for bulk upload to Strava.
    def chunks(l, chunk_size):
        for i in range(0, len(l), chunk_size):
            yield l[i:i + chunk_size]

    for chunk in chunks(list(reversed(g_only)), 25):
        print('---')
        print(' '.join(
            '"' + os.path.abspath(a.path(args.format) + '"') for a in chunk))


if __name__ == '__main__':
    main()
