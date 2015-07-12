#!/usr/bin/env python2

from __future__ import print_function

from contextlib import contextmanager
import os


class GarminStore(object):

    def __init__(self, where):
        self.basedir = where

        if not os.path.exists(self.basedir):
            os.makedirs(self.basedir)

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
        except: # failure -> roll back
            f.close()
            os.remove(path)
            raise
        else: # success -> commit
            f.close()
            os.rename(path, self.path(filename))

    def read(self, filename):
        if not filename in self:
            raise KeyError(filename)
        with self.open(filename, 'r') as f:
            return f.read()

    def write(self, filename, data):
        with self.open(filename, 'w') as f:
            f.write(data)
