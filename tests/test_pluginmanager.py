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
# pylint: disable=invalid-name, too-many-arguments
# pylint: disable=protected-access, unused-argument, no-self-use

import unittest
import sys

import mock

# we don't need any of these installed to test
# but we do need their importing to not-break-everything
NO_IMPORT = mock.Mock()
sys.modules['jpype'] = NO_IMPORT
sys.modules['requests'] = NO_IMPORT
sys.modules['heatclient'] = NO_IMPORT
sys.modules['heatclient.client'] = NO_IMPORT
sys.modules['keystoneclient'] = NO_IMPORT
sys.modules['keystoneclient.v2_0'] = NO_IMPORT
sys.modules['keystoneclient.v2_0.client'] = NO_IMPORT
sys.modules['novaclient'] = NO_IMPORT
sys.modules['novaclient.client'] = NO_IMPORT

import adaptationengine_framework.pluginmanager as pluginmanager


class TestPluginManager(unittest.TestCase):
    """Test cases for the plugin manager class"""

    def setUp(self):
        """Create patchers"""
        self.patchers = []

        # patch logging
        patcher_logger = mock.patch(
            'adaptationengine_framework.pluginmanager.LOGGER'
        )
        self.patchers.append(patcher_logger)
        self.mock_logger = patcher_logger.start()

        # patch configuration
        patcher_cfg = mock.patch(
            'adaptationengine_framework.pluginmanager.cfg'
        )
        self.patchers.append(patcher_cfg)
        self.mock_cfg = patcher_cfg.start()

        # patch plugins
        patcher_plg = mock.patch(
            'adaptationengine_framework.pluginmanager.plugins'
        )
        self.patchers.append(patcher_plg)
        self.mock_plg = patcher_plg.start()

        # patch uuid
        patcher_uuid = mock.patch(
            'adaptationengine_framework.pluginmanager.uuid'
        )
        self.patchers.append(patcher_uuid)
        self.mock_uuid = patcher_uuid.start()

    def tearDown(self):
        """Destroy patchers"""
        for patcher in self.patchers:
            patcher.stop()

    @mock.patch(
        'adaptationengine_framework.pluginmanager'
        '.PluginManager._start_jvm'
    )
    @mock.patch(
        'adaptationengine_framework.pluginmanager'
        '.PluginManager._scan_for_java_plugins'
    )
    @mock.patch(
        'adaptationengine_framework.pluginmanager'
        '.PluginManager._scan_for_python_plugins'
    )
    def test__init__jvm_not_needed(self, mock_pyscan, mock_jscan, mock_jvm):
        """Tests class initialisation"""
        def jscan(*args, **kwagrs):
            """Fake scan for java plugins"""
            return False

        mock_jscan.side_effect = jscan
        pluginmanager.PluginManager()
        assert mock_pyscan.called
        assert mock_jscan.called
        assert not mock_jvm.called

    @mock.patch(
        'adaptationengine_framework.pluginmanager.PluginManager._start_jvm'
    )
    @mock.patch(
        'adaptationengine_framework.pluginmanager.'
        'PluginManager._scan_for_java_plugins'
    )
    @mock.patch(
        'adaptationengine_framework.pluginmanager.'
        'PluginManager._scan_for_python_plugins'
    )
    def test__init__jvm_needed(self, mock_pyscan, mock_jscan, mock_jvm):
        """Tests class initialisation with JVM needed set to true"""
        def jscan(*args, **kwagrs):
            """Fake scan for java plugins"""
            return True

        mock_jscan.side_effect = jscan
        pluginmanager.PluginManager()
        assert mock_pyscan.called
        assert mock_jscan.called
        assert mock_jvm.called

    @mock.patch('adaptationengine_framework.pluginmanager.jpype')
    def test__start_jvm__needed_not_started(self, mock_jpype):
        """Tests configuring and starting the JVM as needed"""
        mock_pm_instance = mock.Mock(pluginmanager.PluginManager)
        mock_pm_instance.jvm_needed = True
        mock_pm_instance.jvm_classpath = "your_house"
        mock_jpype.isJVMStarted.return_value = False

        pluginmanager.PluginManager._start_jvm(mock_pm_instance)

        assert mock_jpype.mock_calls == [
            mock.call.isJVMStarted(),
            mock.call.getDefaultJVMPath(),
            mock.call.startJVM(mock.ANY, '-Djava.class.path=your_house'),
        ]

    @mock.patch('adaptationengine_framework.pluginmanager.jpype')
    def test__start_jvm__needed_and_started(self, mock_jpype):
        """Tests configuring and starting the JVM as needed"""
        mock_pm_instance = mock.Mock(pluginmanager.PluginManager)
        mock_pm_instance.jvm_needed = True
        mock_jpype.isJVMStarted.return_value = True

        pluginmanager.PluginManager._start_jvm(mock_pm_instance)

        assert mock_jpype.mock_calls == [
            mock.call.isJVMStarted()
        ]

    @mock.patch('adaptationengine_framework.pluginmanager.jpype')
    def test__start_jvm__exception(self, mock_jpype):
        """Tests configuring and starting the JVM as needed"""
        mock_pm_instance = mock.Mock(pluginmanager.PluginManager)
        mock_jpype.isJVMStarted.side_effect = OSError("Ruh roh!")

        with self.assertRaises(Exception):
            pluginmanager.PluginManager._start_jvm(mock_pm_instance)

    def test__get(self):
        """Test getting a new plugin instance of each plugin in a list"""
        mock_pm_instance = mock.Mock(pluginmanager.PluginManager)
        mock_pm_instance._plugins = mock.Mock()
        mock_pluginlist = ['plugin1', 'plugin2', 'plugin3']

        pluginmanager.PluginManager.get(mock_pm_instance, mock_pluginlist)

        assert mock_pm_instance._plugins.get.mock_calls == [
            mock.call('plugin1'),
            mock.call().next(),
            mock.call('plugin2'),
            mock.call().next(),
            mock.call('plugin3'),
            mock.call().next(),
        ]

    def test__get__not_found(self):
        """
        Test getting a new plugin instance of each plugin in a list, but plugin
        names not found
        """
        mock_pm_instance = mock.Mock(pluginmanager.PluginManager)
        mock_pm_instance._plugins = mock.Mock()
        mock_pm_instance._plugins.get.return_value = None
        mock_pluginlist = ['plugin1', 'plugin2', 'plugin3']

        pluginmanager.PluginManager.get(mock_pm_instance, mock_pluginlist)

        assert mock_pm_instance._plugins.get.mock_calls == [
            mock.call('plugin1'),
            mock.call('plugin2'),
            mock.call('plugin3'),
        ]

    @mock.patch('adaptationengine_framework.pluginmanager.imp')
    @mock.patch('adaptationengine_framework.pluginmanager.os.path.isfile')
    @mock.patch('adaptationengine_framework.pluginmanager.os.path.isdir')
    @mock.patch('adaptationengine_framework.pluginmanager.os.listdir')
    def test__scan_for_python_plugins(
            self, mock_listdir, mock_isdir, mock_isfile, mock_imp
    ):
        """
        Tests a successful scan for python plugins
        """
        # mock values
        self.mock_cfg.plugin_python = '/tmp/python'
        self.mock_uuid.uuid4().hex = 'xxx'
        mock_listdir.return_value = ['plugin1', 'plugin2']
        mock_isdir.return_value = True
        mock_isfile.return_value = True
        mock_imp.find_module.return_value = ('file', 'pathname', 'description')

        # mock expected results
        expected_plugins = [
            mock.call(
                file_path='/tmp/python/plugin1/plugin1.py',
                info=('file', 'pathname', 'description'),
                name='plugin1',
                uuid='xxx',
                weight=1
            ),
            mock.call(
                file_path='/tmp/python/plugin2/plugin2.py',
                info=('file', 'pathname', 'description'),
                name='plugin2',
                uuid='xxx',
                weight=1
            ),
        ]

        # mock a PluginManager instance
        mock_pm_instance = mock.Mock(pluginmanager.PluginManager)
        mock_pm_instance._plugins = {}
        mock_pm_instance._plugin__weightings = {
            'plugin1': 1,
            'plugin2': 1,
        }
        mock_pm_instance._plugin__default_weighting = 1

        # execute
        pluginmanager.PluginManager._scan_for_python_plugins(mock_pm_instance)

        # check results
        assert expected_plugins == (
            self.mock_plg.PythonPluginGenerator.mock_calls
        )

    @mock.patch('adaptationengine_framework.pluginmanager.os.path.isfile')
    @mock.patch('adaptationengine_framework.pluginmanager.os.path.isdir')
    @mock.patch('adaptationengine_framework.pluginmanager.os.listdir')
    def test__scan_for_python_plugins__missing_file(
            self, mock_listdir, mock_isdir, mock_isfile
    ):
        """
        Tests a successful scan for python plugins, but there's a missing file
        """
        # mock values
        mock_listdir.return_value = ['plugin1', 'plugin2']
        mock_isdir.return_value = True
        mock_isfile.return_value = False

        # mock a PluginManager instance
        mock_pm_instance = mock.Mock(pluginmanager.PluginManager)

        # execute
        pluginmanager.PluginManager._scan_for_python_plugins(mock_pm_instance)
        self.mock_logger.warn.assert_called_once_with(mock.ANY)

    @mock.patch('adaptationengine_framework.pluginmanager.os.path.isfile')
    @mock.patch('adaptationengine_framework.pluginmanager.os.path.isdir')
    @mock.patch('adaptationengine_framework.pluginmanager.os.listdir')
    def test__scan_for_java_plugins(
            self, mock_listdir, mock_isdir, mock_isfile
    ):
        """
        Tests a successful scan for java plugins
        """
        # mock values
        self.mock_cfg.plugin_java = '/tmp/java'
        self.mock_uuid.uuid4().hex = 'xxx'
        mock_listdir.return_value = ['plugin1', 'plugin2']
        mock_isdir.return_value = True
        mock_isfile.return_value = True

        # mock expected results
        expected_plugins = [
            mock.call(
                file_path='/tmp/java/plugin1/plugin1.jar',
                lock=mock.ANY,
                name='plugin1',
                uuid='xxx',
                weight=1
            ),
            mock.call(
                file_path='/tmp/java/plugin2/plugin2.jar',
                lock=mock.ANY,
                name='plugin2',
                uuid='xxx',
                weight=1
            ),
        ]

        # mock a PluginManager instance
        mock_pm_instance = mock.Mock(pluginmanager.PluginManager)
        mock_pm_instance._plugins = {}
        mock_pm_instance._jvm_lock = mock.Mock()
        mock_pm_instance.jvm_classpath = "AdaptationEngine.jar"
        mock_pm_instance._plugin__weightings = {
            'plugin1': 1,
            'plugin2': 1,
        }
        mock_pm_instance._plugin__default_weighting = 1

        # execute
        pluginmanager.PluginManager._scan_for_java_plugins(mock_pm_instance)

        # check results
        assert expected_plugins == self.mock_plg.JavaPluginGenerator.mock_calls
        assert mock_pm_instance.jvm_classpath == (
            "AdaptationEngine.jar:/tmp/java/plugin1/"
            "plugin1.jar:/tmp/java/plugin2/plugin2.jar"
        )

    @mock.patch('adaptationengine_framework.pluginmanager.os.listdir')
    def test__scan_for_java_plugins__no_plugins(
            self, mock_listdir
    ):
        """
        Tests a successful scan for java plugins, but there's no plugins??
        """
        # mock values
        self.mock_cfg.plugin_java = '/tmp/java'
        mock_listdir.return_value = []

        # mock a PluginManager instance
        mock_pm_instance = mock.Mock(pluginmanager.PluginManager)
        mock_pm_instance.jvm_classpath = "AdaptationEngine.jar"

        # execute
        pluginmanager.PluginManager._scan_for_java_plugins(mock_pm_instance)

        # check results
        assert [] == self.mock_plg.JavaPluginGenerator.mock_calls
        assert mock_pm_instance.jvm_classpath == "AdaptationEngine.jar"

    @mock.patch('adaptationengine_framework.pluginmanager.os.path.isfile')
    @mock.patch('adaptationengine_framework.pluginmanager.os.path.isdir')
    @mock.patch('adaptationengine_framework.pluginmanager.os.listdir')
    def test__scan_for_java_plugins__missing_file(
            self, mock_listdir, mock_isdir, mock_isfile
    ):
        """
        Tests a successful scan for java plugins, but there's a missing file
        """
        # mock values
        self.mock_cfg.plugin_java = '/tmp/java'
        mock_listdir.return_value = ['plugin1', 'plugin2', 'plugin3']
        mock_isdir.return_value = True
        mock_isfile.return_value = False

        # mock a PluginManager instance
        mock_pm_instance = mock.Mock(pluginmanager.PluginManager)
        mock_pm_instance.jvm_classpath = "AdaptationEngine.jar"

        # execute
        pluginmanager.PluginManager._scan_for_java_plugins(mock_pm_instance)

        # check results
        assert [] == self.mock_plg.JavaPluginGenerator.mock_calls
        assert mock_pm_instance.jvm_classpath == "AdaptationEngine.jar"

    @mock.patch('adaptationengine_framework.pluginmanager.os.path.isdir')
    @mock.patch('adaptationengine_framework.pluginmanager.os.listdir')
    def test__scan_for_java_plugins__file_in_dir_listing(
            self, mock_listdir, mock_isdir
    ):
        """
        Tests a successful scan for java plugins, but there's a file
        in the plugin directory
        """
        # mock values
        self.mock_cfg.plugin_java = '/tmp/java'
        mock_listdir.return_value = ['plugin1', 'plugin2', 'plugin3']
        mock_isdir.return_value = False

        # mock a PluginManager instance
        mock_pm_instance = mock.Mock(pluginmanager.PluginManager)
        mock_pm_instance.jvm_classpath = "AdaptationEngine.jar"

        # execute
        pluginmanager.PluginManager._scan_for_java_plugins(mock_pm_instance)

        # check results
        assert [] == self.mock_plg.JavaPluginGenerator.mock_calls
        assert mock_pm_instance.jvm_classpath == "AdaptationEngine.jar"

    @mock.patch('adaptationengine_framework.pluginmanager.os.path.isfile')
    @mock.patch('adaptationengine_framework.pluginmanager.os.path.isdir')
    @mock.patch('adaptationengine_framework.pluginmanager.os.listdir')
    def test__scan_for_java_plugins__extra_jar(
            self, mock_listdir, mock_isdir, mock_isfile
    ):
        """
        Tests a successful scan for java plugins, but there's an addon jar in
        one of the plugin directories
        """
        # mock values
        self.mock_cfg.plugin_java = '/tmp/java'
        self.mock_uuid.uuid4().hex = 'xxx'
        mock_isdir.return_value = True
        mock_isfile.return_value = True

        list_dir_vals = [
            ["plugin1", "plugin2"],
            ["plugin1.jar"],
            ["plugin2.jar", "garbage.jar"]
        ]

        def mock_listdir_calls(*args, **kwargs):
            """Fake multiple calls to listdir"""
            return list_dir_vals.pop(0)

        mock_listdir.side_effect = mock_listdir_calls

        # mock expected results
        expected_plugins = [
            mock.call(
                file_path='/tmp/java/plugin1/plugin1.jar',
                lock=mock.ANY,
                name='plugin1',
                uuid='xxx',
                weight=1
            ),
            mock.call(
                file_path='/tmp/java/plugin2/plugin2.jar',
                lock=mock.ANY,
                name='plugin2',
                uuid='xxx',
                weight=1
            ),
        ]

        # mock a PluginManager instance
        mock_pm_instance = mock.Mock(pluginmanager.PluginManager)
        mock_pm_instance._plugins = {}
        mock_pm_instance._jvm_lock = mock.Mock()
        mock_pm_instance.jvm_classpath = "AdaptationEngine.jar"
        mock_pm_instance._plugin__weightings = {
            'plugin1': 1,
            'plugin2': 1,
        }
        mock_pm_instance._plugin__default_weighting = 1

        # execute
        pluginmanager.PluginManager._scan_for_java_plugins(mock_pm_instance)

        # check results
        assert expected_plugins == self.mock_plg.JavaPluginGenerator.mock_calls
        print mock_pm_instance.jvm_classpath
        assert mock_pm_instance.jvm_classpath == (
            "AdaptationEngine.jar:"
            "/tmp/java/plugin1/plugin1.jar:/tmp/java/plugin2/plugin2.jar:"
            "/tmp/java/plugin2/garbage.jar"
        )
