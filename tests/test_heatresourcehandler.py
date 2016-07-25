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
