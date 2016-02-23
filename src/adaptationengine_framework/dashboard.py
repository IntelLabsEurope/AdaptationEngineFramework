"""
Copyright 2015 INTEL RESEARCH AND INNOVATION IRELAND LIMITED

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import datetime
import logging

import pymongo

import adaptationaction
import configuration as cfg


LOGGER = logging.getLogger('syslog')
HEALTHLOGGER = logging.getLogger('stdout')


class Dashboard:
    """Interface to the adaptation engine dashboard"""

    @staticmethod
    def clear():
        """Delete the existing posts in the dashboard"""
        try:
            _client = pymongo.MongoClient(
                cfg.dashboard__host, int(cfg.dashboard__port)
            )
            _db = _client[cfg.dashboard__database]
            _db.drop_collection(cfg.dashboard__collection)
        except Exception, err:
            LOGGER.error(
                "Could not connect to Adaptation Engine Dashboard: {}".format(
                    err
                )
            )


class DashboardPost:
    """
    Object representation of an adaptation engine dashboard post

    TODO: the actual posting should be done by the interface, not this class
    """

    def __init__(self, event_name, stack_id):
        """Create a mongo client and the skeleton of a post"""
        self._client = pymongo.MongoClient(
            cfg.dashboard__host, int(cfg.dashboard__port)
        )
        self._db = self._client[cfg.dashboard__database]
        self._collection = self._db[cfg.dashboard__collection]

        self._stack_id = stack_id
        self._event_name = event_name

        self._chosen_added = False
        self._engine_added = False

        self._the_post = {
            'stack_id': stack_id,
            'enactment_event': {
                'name': event_name
            },
            'engines': {},
            'adaptation': {},
            'timestamp': '',
        }

    def add_engine_result(self, name, adaptation_action, weight):
        """Add the result from a plugin/sub-engine to the existing post"""
        self._the_post['engines'][name] = {
            'result': {
                'type': adaptationaction.AdaptationType.get_string(
                    adaptation_action.adaptation_type
                ),
                'target': adaptation_action.target,
                'destination': adaptation_action.destination,
                'score': adaptation_action.score,
            },
            'weight': weight
        }
        self._engine_added = True

    def add_chosen_adaptation(self, adaptation_action):
        """
        Add details about the adaptation that was chosen to be enacted
        to the post
        """
        self._the_post['adaptation'] = {
            'type': adaptationaction.AdaptationType.get_string(
                adaptation_action.adaptation_type
            ),
            'target': adaptation_action.target,
            'destination': adaptation_action.destination,
            'score': adaptation_action.score,
        }
        self._chosen_added = True

    def post(self):
        """
        Post this entry to the database

        TODO: move this to the interface class
        """
        utc = datetime.datetime.utcnow()
        timestamp = utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        self._the_post['timestamp'] = timestamp

        if self._engine_added and self._chosen_added:
            try:
                return self._collection.insert_one(
                    self._the_post
                )  # returns ID object
            except Exception, err:
                raise Exception(err)
        else:
            raise Exception(
                "Dashboard post missing either engine"
                " or adaptation details: {}".format(self._the_post)
            )
