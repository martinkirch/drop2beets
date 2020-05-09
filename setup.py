#!/usr/bin/env python
from setuptools import setup, find_packages

setup(name='drop2beets',
      version='0.1',
      packages=find_packages(),
      install_requires=[
          'beets',
          'inotify',
      ])
