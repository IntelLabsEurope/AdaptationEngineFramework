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

import unittest
import sys

import mock

# we don't need any of these installed to test
# but we do need their importing to not-break-everything
NO_IMPORT = mock.Mock()
sys.modules['pymongo'] = NO_IMPORT
sys.modules['requests'] = NO_IMPORT

import adaptationengine_framework.plugins as plugins


def generic_setup(instance):
    """Create patchers"""
    instance.patchers = []

    # patch logging
    patcher_logger = mock.patch(
        'adaptationengine_framework.plugins.LOGGER'
    )
    instance.patchers.append(patcher_logger)
    instance.mock_logger = patcher_logger.start()

    # patch configuration
    patcher_cfg = mock.patch(
        'adaptationengine_framework.plugins.cfg'
    )
    instance.patchers.append(patcher_cfg)
    instance.mock_cfg = patcher_cfg.start()

    # patch openstack
    patcher_ops = mock.patch(
        'adaptationengine_framework.plugins.openstack'
    )
    instance.patchers.append(patcher_ops)
    instance.mock_ops = patcher_ops.start()

def generic_teardown(self):
    """Destroy patchers"""
    for patcher in self.patchers:
        patcher.stop()


class TestOpenStackAPI(unittest.TestCase):
    """Test cases for the openstack api class"""

    def setUp(self):
        """Create patchers"""
        generic_setup(self)

    def tearDown(self):
        """Destroy patchers"""
        generic_teardown(self)

    def test__init(self):
        """Test initialisation"""
        test = plugins.OpenStackAPI("plugin1")

        (
            self.mock_ops.OpenStackClients.
            get_keystone_client.assert_called_once_with()
        )

        assert test._keystone is not None
        assert test._token is not None
        assert test._auth is None
        assert test._headers is not None

    def test__init__bad_connection(self):
        """Test initialisation, except with a bad connection"""
        self.mock_ops.OpenStackClients.get_keystone_client.side_effect = (
            Exception("You goofed")
        )

        test = plugins.OpenStackAPI("plugin1")

        assert test._keystone is None
        assert test._token is None
        assert test._auth is None
        assert test._headers is None

    @mock.patch('adaptationengine_framework.plugins.requests')
    def test__get(self, mock_requests):
        """Test getting a url"""
        url = "stacks/"
        mock_osa_instance = mock.Mock(plugins.OpenStackAPI)
        mock_osa_instance._plugin_name = "plugin1"
        mock_osa_instance._endpoint = "http://127.0.0.1:80/endpoint/"
        mock_osa_instance._headers = "some headers"
        mock_osa_instance._auth = None

        mock_response = mock.Mock()
        mock_response.text = "hello"
        mock_requests.get.return_value = mock_response

        result = plugins.OpenStackAPI.get(mock_osa_instance, url)

        mock_requests.get.assert_called_once_with(
            (mock_osa_instance._endpoint + url),
            auth=None,
            headers=mock_osa_instance._headers
        )
        assert result == mock_response.text

    @mock.patch('adaptationengine_framework.plugins.requests')
    def test__get__with_tenant_id(self, mock_requests):
        """Test getting a url with a supplied tenant id"""
        url = "stacks/"
        mock_osa_instance = mock.Mock(plugins.OpenStackAPI)
        mock_osa_instance._plugin_name = "plugin1"
        mock_osa_instance._endpoint = "http://127.0.0.1:80/endpoint/"
        mock_osa_instance._headers = "some headers"
        mock_osa_instance._auth = None
        mock_osa_instance._service_name = "test-service"

        mock_admin_keystone = mock.Mock()
        mock_admin_keystone.tenants.get.return_value.name = "chuckles"
        mock_osa_instance._keystone = mock_admin_keystone

        mock_tenant_keystone = mock.Mock()
        mock_tenant_keystone.auth_ref = {'token': {'id': 'spooky_ghost'}}
        self.mock_ops.OpenStackClients.get_keystone_client.return_value = (
            mock_tenant_keystone
        )

        mock_other_endpoint = "http://127.0.0.1:80/endpoint/tenant/"
        self.mock_ops.OpenStackClients._find_endpoint.return_value = (
            mock_other_endpoint
        )

        mock_tenant_id = "<tenant-id>"

        mock_response = mock.Mock()
        mock_response.text = "hello"
        mock_requests.get.return_value = mock_response

        result = plugins.OpenStackAPI.get(
            mock_osa_instance, url,
            tenant_id=mock_tenant_id
        )

        mock_requests.get.assert_called_once_with(
            (mock_other_endpoint + url),
            auth=None,
            headers={'X-Auth-Token': 'spooky_ghost'}
        )
        assert result == mock_response.text

    @mock.patch('adaptationengine_framework.plugins.requests')
    def test__get__with_tenant_id_exception(self, mock_requests):
        """Test getting a url with a supplied tenant id, but can't get id"""
        url = "stacks/"
        mock_osa_instance = mock.Mock(plugins.OpenStackAPI)
        mock_osa_instance._plugin_name = "plugin1"
        mock_osa_instance._endpoint = "http://127.0.0.1:80/endpoint/"
        mock_osa_instance._headers = "some headers"
        mock_osa_instance._auth = None
        mock_osa_instance._service_name = "test-service"

        mock_admin_keystone = mock.Mock()
        mock_admin_keystone.tenants.get.return_value.name = "chuckles"
        mock_osa_instance._keystone = mock_admin_keystone

        mock_tenant_keystone = mock.Mock()
        mock_tenant_keystone.auth_ref = {'token': {'id': 'spooky_ghost'}}

        def no_dice(*args):
            raise Exception("Uh uh uh, you didn't say the magic word")

        self.mock_ops.OpenStackClients.get_keystone_client.side_effect = (
            no_dice
        )

        mock_tenant_id = "<tenant-id>"

        result = plugins.OpenStackAPI.get(
            mock_osa_instance, url,
            tenant_id=mock_tenant_id
        )

        assert not mock_requests.called
        assert result is None

    def test__get__no_endpoint(self):
        """Test getting a url with no endpoint"""
        url = "stacks/"
        mock_osa_instance = mock.Mock(plugins.OpenStackAPI)
        mock_osa_instance._plugin_name = "plugin1"
        mock_osa_instance._endpoint = None
        mock_osa_instance._headers = None

        result = plugins.OpenStackAPI.get(mock_osa_instance, url)

        assert result is None

    @mock.patch('adaptationengine_framework.plugins.requests')
    def test__get__exception(self, mock_requests):
        """Test getting a url with no connection"""
        url = "stacks/"
        mock_osa_instance = mock.Mock(plugins.OpenStackAPI)
        mock_osa_instance._plugin_name = "plugin1"
        mock_osa_instance._endpoint = "http://127.0.0.1:80/endpoint/"
        mock_osa_instance._headers = "some headers"

        mock_requests.get.side_effect = Exception()

        result = plugins.OpenStackAPI.get(mock_osa_instance, url)

        assert result is None


class TestOpenStackAPIChildren(unittest.TestCase):
    """Test cases for the openstack api class children"""

    def setUp(self):
        """Create patchers"""
        generic_setup(self)

    def tearDown(self):
        """Destroy patchers"""
        generic_teardown(self)

    def test__init(self):
        """Test initialisation of each child class"""
        metrics = plugins.Metrics()
        compute = plugins.Compute()
        orchestration = plugins.Orchestration()

        assert (
            self.mock_ops.OpenStackClients.get_keystone_client.call_count == 3
        )

        assert (
            self.mock_ops.OpenStackClients._find_endpoint.call_count == 3
        )


class TestAgreements(unittest.TestCase):
    """Test cases for the sla api class"""

    def setUp(self):
        """Create patchers"""
        generic_setup(self)

    def tearDown(self):
        """Destroy patchers"""
        generic_teardown(self)

    def test__init(self):
        """Test initialisation"""
        self.mock_cfg.sla_agreements__username = "user"
        self.mock_cfg.sla_agreements__endpoint = "endpoint"
        self.mock_cfg.sla_agreements__password = "pass"

        mock_agreement_map = {
            "a stack id": {
                "agreement": "an agreement id",
                "event": "an event name"
            }
        }

        test = plugins.Agreements(mock_agreement_map)

        assert test._plugin_name == mock.ANY
        assert test._agreement_map == mock_agreement_map
        assert test._endpoint == self.mock_cfg.sla_agreements__endpoint
        assert test._auth == (
            self.mock_cfg.sla_agreements__username,
            self.mock_cfg.sla_agreements__password
        )
        assert test._headers == {'Accept': 'application/json'}

    def test__get_agreement_id(self):
        """Test getting an agreement id based on a stack id"""
        mock_agree_instance = mock.Mock(plugins.Agreements)
        mock_stack = "<stack-id>"
        mock_agree_id = "<agreement-id>"
        mock_event = "<event-name>"
        mock_agree_instance._agreement_map = {
            "<wrong agreement-id>": {
                "stack_id": "<wrong stack-id>", "event": "<event-name>"
            },
            mock_agree_id: {"stack_id": mock_stack, "event": mock_event}
        }

        results = plugins.Agreements.get_agreement_id(
            mock_agree_instance, mock_stack
        )

        assert results == mock_agree_id


class TestPluginLogger(unittest.TestCase):
    """Test cases for the plugin logging class"""

    def setUp(self):
        """Create patchers"""
        generic_setup(self)

    def tearDown(self):
        """Destroy patchers"""
        generic_teardown(self)

    def test__log(self):
        """Test logging"""
        test = plugins.PluginLogger()
        test.log("message")

        self.mock_logger.info.assert_called_once_with(mock.ANY)


class TestPythonPlugin(unittest.TestCase):
    """Test cases for the python plugin classes"""

    def setUp(self):
        """Create patchers"""
        generic_setup(self)

    def tearDown(self):
        """Destroy patchers"""
        generic_teardown(self)

    @mock.patch('adaptationengine_framework.plugins.Orchestration')
    @mock.patch('adaptationengine_framework.plugins.Compute')
    @mock.patch('adaptationengine_framework.plugins.Metrics')
    @mock.patch('adaptationengine_framework.plugins.imp')
    def test__python_plugin(self, mock_imp, mock_met, mock_com, mock_orc):
        """Tests initialisation and setup of a plugin"""
        mock_name = "plugin1"
        mock_event = "this would be a event type normally"
        mock_info = ('file', 'pathname', 'description')
        mock_initial_actions = ["this would be a list of actions"]
        mock_agreement_map = {"stackid": "agreementid"}
        mock_results = {"somewhere": ["to put your", "output actions"]}

        test = plugins.PythonPlugin(
            file_path="/tmp/plugin/plugin.file",
            info=mock_info,
            name=mock_name,
            uuid="a uuid",
            weight=1
        )

        test.setup(
            event=mock_event,
            initial_actions=mock_initial_actions,
            results=mock_results,
            agreement_map=mock_agreement_map,
        )

        test._log_info("info message")
        test._log_debug("debug message")
        test._log_error("error message")

        assert self.mock_logger.info.called
        assert self.mock_logger.error.called

        test.run()

        assert mock_imp.load_module.mock_calls == [
            mock.call(
                (mock_name + '.py'),
                mock_info[0],
                mock_info[1],
                mock_info[2],
            ),
            mock.call().run(
                mock_event,
                mock_initial_actions,
                mock_met(),
                mock_com(),
                mock_orc(),
                mock.ANY, # agreement instance
                mock.ANY # plugin logger instance
            )
        ]

        assert mock_results.get(mock_name)

    @mock.patch('adaptationengine_framework.plugins.PythonPlugin')
    def test__python_generator(self, mock_pyplugin):
        """Test that python generator returns a correct pythonplugin"""
        mock_name = "plugin1"
        mock_file = "/tmp/plugin/plugin.file"
        mock_uuid = "a uuid"
        mock_info = ('file', 'pathname', 'description')

        test = plugins.PythonPluginGenerator(
            file_path=mock_file,
            info=mock_info,
            name=mock_name,
            uuid=mock_uuid,
            weight=1
        )

        result = test.next()

        mock_pyplugin.assert_called_once_with(
            mock_file, mock_info, mock_name, mock_uuid, 1
        )
        assert result == mock_pyplugin()


class TestJavaPlugin(unittest.TestCase):
    """Test cases for the java plugin classes"""

    def setUp(self):
        """Create patchers, with some extra this time"""
        generic_setup(self)

        # patch jpype
        patcher_jpype = mock.patch(
            'adaptationengine_framework.plugins.jpype'
        )
        self.patchers.append(patcher_jpype)
        self.mock_jpype = patcher_jpype.start()

        # patch Metrics
        patcher_metrics = mock.patch(
            'adaptationengine_framework.plugins.Metrics'
        )
        self.patchers.append(patcher_metrics)
        self.mock_met = patcher_metrics.start()

        # patch Compute
        patcher_compute = mock.patch(
            'adaptationengine_framework.plugins.Compute'
        )
        self.patchers.append(patcher_compute)
        self.mock_com = patcher_compute.start()

        # patch Orchestration
        patcher_orchestration = mock.patch(
            'adaptationengine_framework.plugins.Orchestration'
        )
        self.patchers.append(patcher_orchestration)
        self.mock_orc = patcher_orchestration.start()

        # patch AdaptationAction
        patcher_aaction = mock.patch(
            'adaptationengine_framework.plugins.'
            'adaptationaction.AdaptationAction'
        )
        self.patchers.append(patcher_aaction)
        self.mock_aaction = patcher_aaction.start()

    def tearDown(self):
        """Destroy patchers"""
        generic_teardown(self)

    def generic_javaplugintest(self):
        """Tests initialisation and setup of a plugin"""
        mock_name = "plugin1"
        mock_event = mock.Mock()
        mock_event.data = '{ "lol": "data "}'
        mock_lock = mock.Mock()
        mock_initial_actions = [mock.Mock()]
        mock_results = {"somewhere": ["to put your", "output actions"]}

        test = plugins.JavaPlugin(
            file_path="/tmp/plugin/plugin.file",
            lock=mock_lock,
            name=mock_name,
            uuid="a uuid",
            weight=1
        )

        test.setup(
            event=mock_event,
            initial_actions=mock_initial_actions,
            results=mock_results
        )

        test._log_info("info message")
        test._log_debug("debug message")
        test._log_error("error message")

        mock_plugin_response = mock.Mock()
        child1 = self.mock_jpype.JClass.return_value
        child2 = child1.return_value
        child2.run.return_value = [mock_plugin_response]

        test.run()

        assert self.mock_logger.info.called
        assert self.mock_logger.error.called

        assert self.mock_jpype.attachThreadToJVM.called
        assert self.mock_jpype.detachThreadFromJVM.called

        expected_jcalls = [
            mock.call.JProxy('cloudwave.Metrics', self.mock_met),
            mock.call.JProxy('cloudwave.Compute', self.mock_com),
            mock.call.JProxy(
                'cloudwave.Orchestration', self.mock_orc
            ),
            mock.call.JClass('cloudwave.Event'),
            mock.call.JProxy('cloudwave.Logger', mock.ANY),
            mock.call.JClass('cloudwave.AdaptationType'),
            mock.call.JClass('cloudwave.AdaptationAction'),
            mock.call.JClass('cloudwave.plugins.' + mock_name),
        ]
        assert [expected_jcalls in x for x in self.mock_jpype.mock_calls]

        assert mock_results.get(mock_name)

    def test__java_plugin(self):
        """Test initialising and executing a java plugin"""
        self.generic_javaplugintest()

    def test__java_plugin__except_com(self):
        """Test initialising and executing a java plugin with an exception"""
        self.mock_com.side_effect = Exception("BAD COM")
        self.generic_javaplugintest()
        assert (
            mock.call(self.mock_com.side_effect) in
            self.mock_logger.exception.mock_calls
        )

    def test__java_plugin__except_met(self):
        """Test initialising and executing a java plugin with an exception"""
        self.mock_met.side_effect = Exception("BAD MET")
        self.generic_javaplugintest()
        assert (
            mock.call(self.mock_met.side_effect) in
            self.mock_logger.exception.mock_calls
        )

    def test__java_plugin__except_orc(self):
        """Test initialising and executing a java plugin with an exception"""
        self.mock_orc.side_effect = Exception("BAD ORC")
        self.generic_javaplugintest()
        assert (
            mock.call(self.mock_orc.side_effect) in
            self.mock_logger.exception.mock_calls
        )

    def test__java_plugin__except_jarray(self):
        """Test initialising and executing a java plugin with an exception"""
        self.mock_jpype.JArray.side_effect = Exception("BAD INITIAL ACTIONS")
        self.generic_javaplugintest()
        assert (
            mock.call(self.mock_jpype.JArray.side_effect) in
            self.mock_logger.exception.mock_calls
        )

    @mock.patch('adaptationengine_framework.plugins.JavaPlugin')
    def test__java_generator(self, mock_jplugin):
        """Test that java generator returns a correct javaplugin"""
        mock_name = "plugin1"
        mock_file = "/tmp/plugin/plugin.file"
        mock_uuid = "a uuid"
        mock_lock = mock.Mock()

        test = plugins.JavaPluginGenerator(
            file_path=mock_file,
            lock=mock_lock,
            name=mock_name,
            uuid=mock_uuid,
            weight=1
        )

        result = test.next()

        mock_jplugin.assert_called_once_with(
            mock_file, mock_lock, mock_name, mock_uuid, 1
        )
        assert result == mock_jplugin()
