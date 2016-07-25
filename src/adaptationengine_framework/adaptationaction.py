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
import time
import uuid


class AdaptationType:
    """An object representation of the supported adaptation types"""
    MigrateAction = 0
    VerticalScaleAction = 1
    HorizontalScaleAction = 2
    DeveloperAction = 3
    CombinedAction = 4
    NoAction = 5
    StartAction = 6
    StopAction = 7
    LowPowerAction = 8

    @staticmethod
    def get_string(type_int):
        """
        Return an english string representation of the adaptation type
        based on a supplied integer
        """
        try:
            action_types = [
                'MigrateAction', 'VerticalScaleAction',
                'HorizontalScaleAction', 'DeveloperAction',
                'CombinedAction', 'NoAction', 'StartAction',
                'StopAction', 'LowPowerAction'
            ]
            return action_types[type_int]

        except Exception:
            raise LookupError('invalid adaptation type [{}]'.format(type_int))


class AdaptationAction:
    """An object representation of an adaptation action"""

    def __init__(self, adaptation_type):
        """
        Create an adaptation action object based on a supplied int or string
        """
        action_types = [
            'migrateaction', 'verticalscaleaction',
            'horizontalscaleaction', 'developeraction',
            'combinedaction', 'noaction', 'startaction',
            'stopaction', 'lowpoweraction'
        ]
        try:
            if type(adaptation_type) is int:
                if adaptation_type < len(action_types) and adaptation_type >= 0:
                    self.adaptation_type = adaptation_type
                else:
                    raise Exception
            else:
                normalised_type = str(adaptation_type).lower()
                self.adaptation_type = action_types.index(normalised_type)
        except Exception:
            raise LookupError(
                'invalid adaptation type [{}]'.format(adaptation_type)
            )

        self.target = ""
        self.destination = ""
        self.scale_value = ""
        self.actions = []
        self.score = 0
        self.votes = 0
        self.candidate = ''

        self.target_app = ""  # i.e. stack_id for redirecting to another stack

    def __eq__(self, other):
        """Check two adaptation actions for equality"""
        try:
            if (
                    self.adaptation_type == other.adaptation_type and
                    self.target == other.target and
                    self.destination == other.destination and
                    self.scale_value == other.scale_value and
                    self.actions == other.actions and
					self.votes == other.votes and
	                self.candidate == other.candidate and
                    self.target_app == other.target_app
            ):
                return True
            else:
                return False
        except AttributeError:
            return False

    def __repr__(self):
        """Return a string representing the adaptation action"""
        output = (
            "AdaptationAction(type={type}, target={target}, "
            "destination={destination}, scale_value={scale_value},"
            " score={score}, votes={votes}, candidate={candidate})").format(
                type=AdaptationType.get_string(self.adaptation_type),
                target=self.target,
                destination=self.destination,
                scale_value=self.scale_value,
                score=self.score,
                votes=self.votes,
                candidate=self.candidate
            )

        return output

    def __hash__(self):
        return hash(
            (
                self.adaptation_type,
                self.target,
                self.destination,
                self.scale_value,
                self.votes,
                self.candidate,
                self.target_app
            )
        )

    def to_dict(self):
        """return a json-compatible dictionary representation of the action"""
        output = {
            "type": AdaptationType.get_string(self.adaptation_type),
            "target": self.target,
            "destination": self.destination,
            "scale_value": self.scale_value,
            "score": self.score,
            "votes": self.votes,
            "candidate": self.candidate
        }
        return output

    @staticmethod
    def generate_adaptation_request(
        adaptation_event,
        name=None,
        stack_id=None
    ):
        """
        Return an adaptation-event format json string representing this action
        """
        output = {
            'id': {
                'user_id': adaptation_event.user_id,
                'tenant': adaptation_event.tenant_id,
                'stack_id': stack_id or adaptation_event.stack_id,
                'source': adaptation_event.source,
                'instance': uuid.uuid4().hex,
                'context': 'adaptation request',
                'machines': adaptation_event.machines,
            },
            'timestamp': time.time(),
            'event': {
                'name': name or adaptation_event.name,
                'value': adaptation_event.value,
            },
            'data': adaptation_event.data
        }

        if adaptation_event.severity:
            output['id']['severity'] = adaptation_event.severity

        if adaptation_event.data_center:
            output['id']['data_center'] = adaptation_event.data_center

        return json.dumps(output)
