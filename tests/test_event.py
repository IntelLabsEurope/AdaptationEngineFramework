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

import adaptationengine_framework.event as event


class TestEvent(unittest.TestCase):
    """Test cases for the event class"""

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

    def test__init(self):
        """Tests that the object is created correctly"""
        mock_msg = """
        {
            "id": {
                "user_id": "test_user_id",
                "tenant": "test_tenant",
                "stack_id": "test_stack_id",
                "source": "test_source",
                "instance": "test_instance",
                "context": "test_context",
                "machines": [ "test_machine1", "test_machine2"],
                "severity": "test_severity",
                "data_center": "test_data_center"
            },
            "event": {
                "name": "test_event_name",
                "value": "test_event_value"
            },
            "data": ["test_data"]
        }
        """

        test = event.Event(mock_msg)

        assert test.user_id == "test_user_id"
        assert test.tenant_id == "test_tenant"
        assert test.stack_id == "test_stack_id"
        assert test.source == "test_source"
        assert test.instance_id == "test_instance"
        assert test.context == "test_context"
        assert test.machines == ["test_machine1", "test_machine2"]
        assert test.data_center == "test_data_center"
        assert test.severity == "test_severity"
        assert test.name == "test_event_name"
        assert test.value == "test_event_value"
        assert test.data == ["test_data"]

    def test__init__big_msg(self):
        """Tests what happens when the event message is over 8mb"""
        mock_msg = mock.Mock()
        mock_msg.__len__ = mock.Mock()
        mock_msg.__len__.return_value = 8388609 # 8mb and a bit

        with self.assertRaises(ValueError):
            event.Event(mock_msg)

    def test__init__missing_key(self):
        """
        Tests what happens when the event message is missing
        something important
        """
        mock_msg = """
        {
            "id": {
                "user_id": "test_user_id",
                "tenant": "test_tenant",
                "source": "test_source",
                "instance": "test_instance",
                "context": "test_context",
                "machines": [ "test_machine1", "test_machine2"],
                "severity": "test_severity",
                "data_center": "test_data_center"
            },
            "event": {
                "name": "test_event_name",
                "value": "test_event_value"
            },
            "data": ["test_data"]
        }
        """

        with self.assertRaises(ValueError):
            event.Event(mock_msg)

    def test_init__str_representation(self):
        """Tests that the str representation of the object is correct"""
        mock_msg = """
        {
            "id": {
                "user_id": "test_user_id",
                "tenant": "test_tenant",
                "stack_id": "test_stack_id",
                "source": "test_source",
                "instance": "test_instance",
                "context": "test_context",
                "machines": [ "test_machine1", "test_machine2"],
                "severity": "test_severity",
                "data_center": "test_data_center"
            },
            "event": {
                "name": "test_event_name",
                "value": "test_event_value"
            },
            "data": ["test_data"]
        }
        """
        expected = "test_event_name"

        test = event.Event(mock_msg)

        assert "{}".format(test) == expected
