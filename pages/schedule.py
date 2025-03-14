from __future__ import division
from __future__ import print_function

# -*- coding: utf-8 -*-
# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = 'ericbidelman@chromium.org (Eric Bidelman)'

import json
import logging
import os

from framework import permissions
from framework import ramcache
import requests
# from google.appengine.api import users
from framework import users

from framework import basehandlers
from internals import models
import settings
from internals import fetchchannels

SCHEDULE_CACHE_TIME = 60 * 60  # 1 hour

# TODO(shivamag00): remove these methods and use Channels API instead
def fetch_chrome_release_info(version):
  key = 'chromerelease|%s' % version

  data = ramcache.get(key)
  if data is None:
    url = ('https://chromiumdash.appspot.com/fetch_milestone_schedule?'
           'mstone=%s' % version)
    result = requests.get(url, timeout=60)
    if result.status_code == 200:
      try:
        logging.info('result.content is:\n%s', result.content)
        result_json = json.loads(result.content)
        if 'mstones' in result_json:
          data = result_json['mstones'][0]
          del data['owners']
          del data['feature_freeze']
          del data['ldaps']
          ramcache.set(key, data, time=SCHEDULE_CACHE_TIME)
      except ValueError:
        pass  # Handled by next statement

    if not data:
      data = {
          'stable_date': None,
          'earliest_beta': None,
          'latest_beta': None,
          'mstone': version,
          'version': version,
      }
      # Note: we don't put placeholder data into ramcache.

  return data

def construct_chrome_channels_details():
  omaha_data = fetchchannels.get_omaha_data()
  channels = {}
  win_versions = omaha_data[0]['versions']

  for v in win_versions:
    channel = v['channel']
    major_version = int(v['version'].split('.')[0])
    channels[channel] = fetch_chrome_release_info(major_version)
    channels[channel]['version'] = major_version

  # Adjust for the brief period after next miletone gets promted to stable/beta
  # channel and their major versions are the same.
  if channels['stable']['version'] == channels['beta']['version']:
    new_beta_version = channels['stable']['version'] + 1
    channels['beta'] = fetch_chrome_release_info(new_beta_version)
    channels['beta']['version'] = new_beta_version
    new_dev_version = channels['beta']['version'] + 1
    channels['dev'] = fetch_chrome_release_info(new_dev_version)
    channels['dev']['version'] = new_dev_version

  return channels


class ScheduleHandler(basehandlers.FlaskHandler):

  TEMPLATE_PATH = 'schedule.html'
  # TODO(shivamag00): fetch data from Channels API and Features API using JS instead of passing it here

  def get_template_data(self):
    template_data = {
      'channels': json.dumps(construct_chrome_channels_details(),
                             indent=4)
    }
    return template_data


app = basehandlers.FlaskApplication([
  ('/features/schedule', ScheduleHandler),
], debug=settings.DEBUG)
