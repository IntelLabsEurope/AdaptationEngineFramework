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
import json
import logging


LOGGER = logging.getLogger('syslog')


class Event:
    """
    Object representation of JSON Event message
    """

    def __init__(self, event_message):
        """
        Accept JSON message and parse into object, checking length
        and structure validity
        """
        self.user_id = None
        self.tenant_id = None
        self.stack_id = None
        self.source = None
        self.instance_id = None
        self.context = None
        self.machines = None
        self.data_center = None
        self.severity = None
        self.name = None
        self.value = None
        self.data = None

        # check length of message
        if len(event_message) > 8388608:  # 8MB
            raise ValueError('message too large')

        cwevent = json.loads(event_message)

        # check structure
        required_id_fields = set(
            [
                'user_id',
                'tenant',
                'stack_id',
                'source',
                'instance',
                'context',
                'machines'
            ]
        )
        if (
                type(cwevent['id']) is dict and
                required_id_fields.issubset(set(cwevent['id']))
        ):
            self.user_id = cwevent['id']['user_id']
            self.tenant_id = cwevent['id']['tenant']
            self.stack_id = cwevent['id']['stack_id']
            self.source = cwevent['id']['source']
            self.instance_id = cwevent['id']['instance']
            self.context = cwevent['id']['context']
            self.machines = cwevent['id']['machines']
            self.data_center = cwevent['id'].get('data_center') or None
            self.severity = cwevent['id'].get('severity') or None
            self.name = cwevent['event']['name']
            self.value = cwevent['event']['value']
            self.data = cwevent['data']
        else:
            raise ValueError('unsupported message')

    def __str__(self):
        """Return the event name as a string representation of this object"""
        return self.name
