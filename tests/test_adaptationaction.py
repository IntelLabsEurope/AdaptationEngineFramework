"""
Copyright 2016 INTEL RESEARCH AND INNOVATION IRELAND LIMITED

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
# pylint: disable=invalid-name, too-many-public-methods
# pylint: disable=unused-argument, no-self-use

import json
import unittest
import sys

import mock

# we don't need any of these installed to test
# but we do need their importing to not-break-everything
NO_IMPORT = mock.Mock()
sys.modules['pymongo'] = NO_IMPORT
sys.modules['heatclient'] = NO_IMPORT
sys.modules['heatclient.client'] = NO_IMPORT
sys.modules['keystoneclient'] = NO_IMPORT
sys.modules['keystoneclient.v2_0'] = NO_IMPORT
sys.modules['keystoneclient.v2_0.client'] = NO_IMPORT
sys.modules['novaclient'] = NO_IMPORT
sys.modules['novaclient.client'] = NO_IMPORT

import adaptationengine_framework.adaptationaction as adaptationaction


class TestAdaptationType(unittest.TestCase):
    """Test cases for the adaptation type class"""

    def setUp(self):
        """Create patchers"""
        self.patchers = []

        # patch logging
        patcher_logger = mock.patch(
            'adaptationengine_framework.utils.logging'
        )
        self.patchers.append(patcher_logger)
        self.mock_logger = patcher_logger.start()

    def tearDown(self):
        """Destroy patchers"""
        for patcher in self.patchers:
            patcher.stop()

    def test__get_string(self):
        """Tests getting a string version of a specific type"""
        type0 = adaptationaction.AdaptationType.get_string(
            adaptationaction.AdaptationType.MigrateAction
        )
        type5 = adaptationaction.AdaptationType.get_string(5)
        type8 = adaptationaction.AdaptationType.get_string(
            adaptationaction.AdaptationType.LowPowerAction
        )

        assert type0 == "MigrateAction"
        assert type5 == "NoAction"
        assert type8 == "LowPowerAction"

    def test__get_string__bad_type(self):
        """
        Tests what happens when trying to get a string of a non-existant type
        """
        with self.assertRaises(AttributeError):
            adaptationaction.AdaptationType.get_string(
                adaptationaction.AdaptationType.FakeAction
            )
        with self.assertRaises(LookupError):
            adaptationaction.AdaptationType.get_string(200)


class TestAdaptationAction(unittest.TestCase):
    """Test cases for the adaptation action class"""

    def setUp(self):
        """Create patchers"""
        self.patchers = []

        # patch logging
        patcher_logger = mock.patch(
            'adaptationengine_framework.utils.logging'
        )
        self.patchers.append(patcher_logger)
        self.mock_logger = patcher_logger.start()

    def tearDown(self):
        """Destroy patchers"""
        for patcher in self.patchers:
            patcher.stop()

    def test__init__int(self):
        """Test initialisation with an int"""
        test = adaptationaction.AdaptationAction(0)

        assert test.adaptation_type == 0
        assert test.target == ""
        assert test.destination == ""
        assert test.scale_value == ""
        assert test.actions == []
        assert test.score == 0
        assert test.target_app == ""

    def test__init__string(self):
        """Test initialisation with a string"""
        test = adaptationaction.AdaptationAction('StartAction')

        assert test.adaptation_type == 6
        assert test.target == ""
        assert test.destination == ""
        assert test.scale_value == ""
        assert test.actions == []
        assert test.score == 0
        assert test.target_app == ""

    def test__init__string_bad_type(self):
        """Test initialisation with an invalid string"""
        with self.assertRaises(LookupError):
            adaptationaction.AdaptationAction('fAkEAcTioN')

    def test__init__int_bad_type(self):
        """Test initialisation with an invalid int"""
        with self.assertRaises(LookupError):
            adaptationaction.AdaptationAction(3000)

    def test__eq(self):
        """Test equality checking"""
        test1 = adaptationaction.AdaptationAction(0)
        test1.target = "target"
        test1.destination = "dest"
        test1.scale_value = "scale"
        test1.actions = ["something"]
        test1.score = 3
        test1.target_app = "app"

        test2 = adaptationaction.AdaptationAction(0)
        test2.target = "target"
        test2.destination = "dest"
        test2.scale_value = "scale"
        test2.actions = ["something"]
        test2.score = 3
        test2.target_app = "app"

        assert test1 == test2

        test2.target_app = "notapp"

        assert not test1 == test2 # have to do it this way because who tf knows

    def test__eq__bad_action(self):
        """Test equality checking where one action is missing attributes"""
        test1 = adaptationaction.AdaptationAction(0)
        test1.target = "target"
        test1.destination = "dest"
        test1.scale_value = "scale"
        test1.actions = ["something"]
        test1.score = 3
        test1.target_app = "app"

        test2 = mock.Mock(spec=[])

        assert not test1 == test2

    def test__repr(self):
        """Test string representation generation"""
        expected = (
            "AdaptationAction(type=DeveloperAction, target=target, "
            "destination=dest, scale_value=scale, score=3, votes=5, candidate=someplugin)"
        )

        test = adaptationaction.AdaptationAction(3)
        test.target = "target"
        test.destination = "dest"
        test.scale_value = "scale"
        test.actions = ["something"]
        test.score = 3
        test.target_app = "app"
        test.votes = 5
        test.candidate = 'someplugin'

        assert str(test) == expected

    def test__hash(self):
        """Test hashing"""
        test1 = adaptationaction.AdaptationAction(0)
        test1.target = "target"
        test1.destination = "dest"
        test1.scale_value = "scale"
        test1.actions = ["something"]
        test1.score = 3
        test1.target_app = "app"

        test2 = adaptationaction.AdaptationAction(0)
        test2.target = "target"
        test2.destination = "dest"
        test2.scale_value = "scale"
        test2.actions = ["something"]
        test2.score = 3
        test2.target_app = "app"

        hash1 = hash(test1)
        hash2 = hash(test2)

        test2.scale_value = "notscale"
        hash3 = hash(test2)

        assert hash1 == hash2
        assert hash1 != hash3

    def test__to_dict(self):
        """Test conversion to a limited dictionary"""
        expected = {
            "type": "VerticalScaleAction",
            "target": "target",
            "destination": "dest",
            "scale_value": "scale",
            "score": 3,
            "votes": 5,
            "candidate": "someplugin"
        }

        test = adaptationaction.AdaptationAction(1)
        test.target = "target"
        test.destination = "dest"
        test.scale_value = "scale"
        test.actions = ["something"]
        test.score = 3
        test.target_app = "app"
        test.votes = 5
        test.candidate = "someplugin"

        result = test.to_dict()

        assert result == expected

    @mock.patch('adaptationengine_framework.adaptationaction.uuid')
    @mock.patch('adaptationengine_framework.adaptationaction.time')
    def test__generate_adaptation_request(self, mock_time, mock_uuid):
        """Test generation of adaptation request json based off event object"""
        mock_event = mock.Mock()
        mock_event.user_id = "test_user_id"
        mock_event.tenant_id = "test_tenant"
        mock_event.stack_id = "test_stack_id"
        mock_event.source = "test_source"
        mock_event.instance_id = "test_instance"
        mock_event.context = "test_context"
        mock_event.machines = ["test_machine1", "test_machine2"]
        mock_event.data_center = "test_data_center"
        mock_event.severity = "test_severity"
        mock_event.name = "test_event_name"
        mock_event.value = "test_event_value"
        mock_event.data = ["test_data"]

        mock_time.time.return_value = "0"
        mock_uuid.uuid4.return_value.hex = "test_instance"

        mock_msg = {
            "id": {
                "user_id": "test_user_id",
                "tenant": "test_tenant",
                "stack_id": "test_stack_id",
                "source": "test_source",
                "instance": "test_instance",
                "context": "adaptation request",
                "machines": ["test_machine1", "test_machine2"],
                "severity": "test_severity",
                "data_center": "test_data_center"
            },
            "timestamp": "0",
            "event": {
                "name": "test_event_name",
                "value": "test_event_value"
            },
            "data": ["test_data"]
        }

        expected = json.dumps(mock_msg)

        # field ordering isn't guaranteed with dicts
        assert (
            json.loads(
                adaptationaction.AdaptationAction.generate_adaptation_request(
                    mock_event
                )
            ) ==
            json.loads(expected)
        )
