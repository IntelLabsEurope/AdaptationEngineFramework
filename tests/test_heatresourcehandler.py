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
# pylint: disable=protected-access,no-self-use,too-many-public-methods
# pylint: disable=no-member,invalid-name,unused-variable

import multiprocessing
import unittest
import sys

import mock

# we don't need any of these installed to test
# but we do need their importing to not-break-everything
NO_IMPORT = mock.Mock()
sys.modules['requests'] = NO_IMPORT

import adaptationengine_framework.heatresourcehandler as heatresourcehandler


def generic_setup(instance):
    """Create patchers"""
    instance.patchers = []

    # patch logging
    patcher_logger = mock.patch(
        'adaptationengine_framework.heatresourcehandler.LOGGER'
    )
    instance.patchers.append(patcher_logger)
    instance.mock_logger = patcher_logger.start()

    # patch configuration
    patcher_cfg = mock.patch(
        'adaptationengine_framework.heatresourcehandler.cfg'
    )
    instance.patchers.append(patcher_cfg)
    instance.mock_cfg = patcher_cfg.start()

    # patch openstack
    patcher_ops = mock.patch(
        'adaptationengine_framework.heatresourcehandler.openstack'
    )
    instance.patchers.append(patcher_ops)
    instance.mock_ops = patcher_ops.start()

    # patch database
    patcher_db = mock.patch(
        'adaptationengine_framework.heatresourcehandler.database'
    )
    instance.patchers.append(patcher_db)
    instance.mock_db = patcher_db.start()

    # patch output
    patcher_output = mock.patch(
        'adaptationengine_framework.heatresourcehandler.output'
    )
    instance.patchers.append(patcher_output)
    instance.mock_output = patcher_output.start()

    # patch adaptationaction
    patcher_action = mock.patch(
        'adaptationengine_framework.heatresourcehandler.adaptationaction'
    )
    instance.patchers.append(patcher_action)
    instance.mock_action = patcher_action.start()


def generic_teardown(self):
    """Destroy patchers"""
    for patcher in self.patchers:
        patcher.stop()


class TestHeatResourceHandler(unittest.TestCase):
    """Test cases for the openstack api class"""

    def setUp(self):
        """Create patchers"""
        generic_setup(self)

    def tearDown(self):
        """Destroy patchers"""
        generic_teardown(self)

    @mock.patch(
        'adaptationengine_framework.heatresourcehandler.'
        'HeatResourceHandler._recover_state'
    )
    def test__init(self, mock_state):
        """create the class"""
        mock_mq_handler = mock.Mock()
        heatresourcehandler.HeatResourceHandler(mock_mq_handler)

    @mock.patch(
        'adaptationengine_framework.heatresourcehandler.'
        'HeatResourceHandler._update_agreement_map'
    )
    def test__recover_state(self, mock_update):
        """test recovering heat templates"""
        mock_hrh_instance = mock.Mock(heatresourcehandler.HeatResourceHandler)
        mock_hrh_instance._active_vms = {}
        mock_hrh_instance._active_resources = {}
        mock_hrh_instance._agreement_map = {}

        name = mock.PropertyMock(return_value='tenant1')
        mock.Mock.name = name

        mock_ks = self.mock_ops.OpenStackClients.get_keystone_client()
        mock_ks.tenants.list.return_value = [mock.Mock()]

        mock_heatc = self.mock_ops.OpenStackClients.get_heat_client
        mock_heatc.return_value.stacks.list.return_value = [
            mock.Mock(id='xxx')
        ]

        resource_json = (
            {
                'resources': {
                    'some_resource': {
                        'properties': {
                            'name': 'some_name',
                            'agreement_id': 'agreement_id',
                            'allowed_actions': ['action1'],
                            'horizontal_scale_out': '',
                        }
                    }
                }
            }
        )

        self.mock_ops.OpenStackClients.get_heat_client.return_value.stacks.template.return_value = resource_json

        self.mock_ops.OpenStackClients.get_heat_client().resources.list.return_value = [
            mock.Mock(
                resource_name='some_resource',
                resource_type="AdaptationEngine::Heat::AdaptationResponse",
                physical_resource_id='some_id'
            ),
            mock.Mock(
                resource_name='some_resource2',
                resource_type="OS::Nova::Server",
                physical_resource_id='some_vm_id'
            )
        ]

        heatresourcehandler.HeatResourceHandler._recover_state(
            mock_hrh_instance
        )

        print self.mock_ops.mock_calls
        print mock_hrh_instance._active_vms
        print mock_hrh_instance._active_resources
        print mock_hrh_instance._agreement_map
        assert False

    @mock.patch(
        'adaptationengine_framework.heatresourcehandler.'
        'HeatResourceHandler._update_agreement_map'
    )
    def test__recover_state_no_keystone(self, mock_update):
        """test recovering heat templates but no keystone access"""
        mock_hrh_instance = mock.Mock(heatresourcehandler.HeatResourceHandler)
        mock_hrh_instance._active_vms = {}
        mock_hrh_instance._active_resources = {}
        mock_hrh_instance._agreement_map = {}

        def no_keystone(*args, **kwargs):
            raise Exception("ruh roh")

        self.mock_ops.OpenStackClients.get_keystone_client.side_effect = (
            no_keystone
        )

        heatresourcehandler.HeatResourceHandler._recover_state(
            mock_hrh_instance
        )

    @mock.patch(
        'adaptationengine_framework.heatresourcehandler.'
        'HeatResourceHandler._update_agreement_map'
    )
    def test__recover_state__tenant_no_heat_client(self, mock_update):
        """
        test recovering heat templates but the tenant can't access
        resources of the stack
        """
        mock_hrh_instance = mock.Mock(heatresourcehandler.HeatResourceHandler)
        mock_hrh_instance._active_vms = {}
        mock_hrh_instance._active_resources = {}
        mock_hrh_instance._agreement_map = {}

        name = mock.PropertyMock(return_value='tenant1')
        mock.Mock.name = name

        mock_ks = self.mock_ops.OpenStackClients.get_keystone_client()
        mock_ks.tenants.list.return_value = [mock.Mock()]

        def throw_exception(*args, **kwargs):
            raise Exception

        self.mock_ops.OpenStackClients.get_heat_client.side_effect = (
            throw_exception
        )

        heatresourcehandler.HeatResourceHandler._recover_state(
            mock_hrh_instance
        )

    @mock.patch(
        'adaptationengine_framework.heatresourcehandler.'
        'HeatResourceHandler._update_agreement_map'
    )
    def test__recover_state__tenant_no_resource_access(self, mock_update):
        """
        test recovering heat templates but the tenant can't access
        resources of the stack
        """
        mock_hrh_instance = mock.Mock(heatresourcehandler.HeatResourceHandler)
        mock_hrh_instance._active_vms = {}
        mock_hrh_instance._active_resources = {}
        mock_hrh_instance._agreement_map = {}

        name = mock.PropertyMock(return_value='tenant1')
        mock.Mock.name = name
        mock_ks = self.mock_ops.OpenStackClients.get_keystone_client()
        mock_ks.tenants.list.return_value = [mock.Mock()]

        mock_heatc = self.mock_ops.OpenStackClients.get_heat_client
        mock_heatc.return_value.stacks.list.return_value = [
            mock.Mock(id='xxx')
        ]

        def throw_exception(*args, **kwargs):
            raise Exception

        mock_heatc = self.mock_ops.OpenStackClients.get_heat_client()
        mock_heatc.resources.list.side_effect = throw_exception

        heatresourcehandler.HeatResourceHandler._recover_state(
            mock_hrh_instance
        )

    def test__get_initial_actions(self):
        mock_hrh_instance = mock.Mock(heatresourcehandler.HeatResourceHandler)
        mock_event_name = '<event-name>'
        mock_stack_id = '<stack-id>'
        mock_actions = ['action1']

        mock_hrh_instance._active_resources = {
            'resource1': {
                'stack_id': mock_stack_id,
                'event': mock_event_name,
                'actions': mock_actions
            },
            'notthisone': {
                'stack_id': '<xxx>',
                'event': '<yyy>',
                'actions': mock_actions
            }
        }

        results = heatresourcehandler.HeatResourceHandler.get_initial_actions(
            mock_hrh_instance,
            mock_event_name,
            mock_stack_id
        )

        assert results == mock_actions

    def test__get_initial_actions_no_match(self):
        mock_hrh_instance = mock.Mock(heatresourcehandler.HeatResourceHandler)
        mock_event_name = '<event-name>'
        mock_stack_id = '<stack-id>'

        mock_hrh_instance._active_resources = {
            'resource1': {
                'stack_id': '<zzz>',
                'event': '<kkk>'
            },
            'notthisone': {
                'stack_id': '<xxx>',
                'event': '<yyy>'
            }
        }

        results = heatresourcehandler.HeatResourceHandler.get_initial_actions(
            mock_hrh_instance,
            mock_event_name,
            mock_stack_id
        )

        assert results is None

    def test__get_resource(self):
        mock_hrh_instance = mock.Mock(heatresourcehandler.HeatResourceHandler)

        mock_event_name = '<event-name>'
        mock_stack_id = '<stack-id>'

        mock_hrh_instance._active_resources = {
            'resource1': {
                'stack_id': '<zzz>',
                'event': '<kkk>'
            },
            'thisone': {
                'stack_id': mock_stack_id,
                'event': mock_event_name
            }
        }

        results = heatresourcehandler.HeatResourceHandler.get_resource(
            mock_hrh_instance,
            mock_event_name,
            mock_stack_id
        )

        assert results == {
            'stack_id': mock_stack_id,
            'event': mock_event_name
        }

    def test__get_resource_no_match(self):
        mock_hrh_instance = mock.Mock(heatresourcehandler.HeatResourceHandler)

        mock_event_name = '<event-name>'
        mock_stack_id = '<stack-id>'

        mock_hrh_instance._active_resources = {
            'resource1': {
                'stack_id': '<zzz>',
                'event': '<kkk>'
            },
            'thisone': {
                'stack_id': '<no-match>',
                'event': '<no-match>'
            }
        }

        results = heatresourcehandler.HeatResourceHandler.get_resource(
            mock_hrh_instance,
            mock_event_name,
            mock_stack_id
        )

        assert results is None

    def test__get_agreement_map(self):
        _manager = multiprocessing.Manager()

        mock_hrh_instance = mock.Mock(heatresourcehandler.HeatResourceHandler)
        mock_hrh_instance._agreement_map = _manager.dict()

        results = (
            heatresourcehandler.HeatResourceHandler.get_agreement_map(
                mock_hrh_instance,
            )
        )

        assert isinstance(results, dict)
        assert not isinstance(results, multiprocessing.managers.DictProxy)

    def test___update_agreement_map(self):
        mock_hrh_instance = mock.Mock(heatresourcehandler.HeatResourceHandler)
        mock_hrh_instance._agreement_map = {}

        mock_event_name = '<event-name>'
        mock_stack_id = '<stack-id>'
        mock_agreement_id = '<agreement-id>'

        mock_hrh_instance._active_resources = {
            'resource1': {
                'stack_id': mock_stack_id,
                'event': mock_event_name,
                'agreement_id': mock_agreement_id
            },
            'thisone': {
                'stack_id': '<no-match>',
                'event': '<no-match>'
            }
        }

        heatresourcehandler.HeatResourceHandler._update_agreement_map(
            mock_hrh_instance
        )

        assert mock_hrh_instance._agreement_map == {
            mock_agreement_id: {
                'stack_id': mock_stack_id, 'event': mock_event_name
            }
        }

    def test__message(self):
        mock_hrh_instance = mock.Mock(heatresourcehandler.HeatResourceHandler)
        mock_hrh_instance._agreement_map = {}

        mock_message = (
            """
            {
                "heat": {
                    "type": "",
                    "data": {
                        "resource_id": "",
                        "name": "",
                        "stack_id": "",
                        "agreement_id": "",
                        "horizontal_scale_out": {},
                        "actions": [],
                    },
                }
            }
            """
        )

    def test__message_bad_message(self):
        mock_hrh_instance = mock.Mock(heatresourcehandler.HeatResourceHandler)
        mock_hrh_instance._agreement_map = {}

        mock_message = "zzz"

        try:
            heatresourcehandler.HeatResourceHandler.message(
                mock_hrh_instance,
                mock_message
            )
        except Exception:
            self.fail

    def test__message_short_message(self):
        mock_hrh_instance = mock.Mock(heatresourcehandler.HeatResourceHandler)
        mock_hrh_instance._agreement_map = {}

        mock_message = "{}"

        try:
            heatresourcehandler.HeatResourceHandler.message(
                mock_hrh_instance,
                mock_message
            )
        except Exception:
            self.fail
