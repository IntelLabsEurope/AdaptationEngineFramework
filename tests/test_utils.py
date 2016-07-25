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

import adaptationengine_framework.configuration as configuration
import adaptationengine_framework.utils as utils


class TestUtils(unittest.TestCase):
    """Test cases for the plugin manager class"""

    def setUp(self):
        """Create patchers"""
        self.patchers = []

        # patch logging
        patcher_logger = mock.patch(
            'adaptationengine_framework.utils.logging'
        )
        self.patchers.append(patcher_logger)
        self.mock_logger = patcher_logger.start()

        # patch configuration
        patcher_cfg = mock.patch(
            'adaptationengine_framework.utils.cfg'
        )
        self.patchers.append(patcher_cfg)
        self.mock_cfg = patcher_cfg.start()

        # patch database
        patcher_db = mock.patch(
            'adaptationengine_framework.utils.database'
        )
        self.patchers.append(patcher_db)
        self.mock_db = patcher_db.start()

    def tearDown(self):
        """Destroy patchers"""
        for patcher in self.patchers:
            patcher.stop()

    def test__generic_log(self):
        """
        Tests generic logger setup, make sure format and leves are set etc
        """
        logger = "syslog"
        mock_handler = mock.Mock()
        format_string = "nonsense"
        level = "debug?"

        mock_get_logger = mock.Mock()
        self.mock_logger.getLogger.return_value = mock_get_logger

        result = utils.generic_logging(
            logger,
            mock_handler,
            format_string,
            level
        )
        self.mock_logger.getLogger.assert_called_once_with(logger)
        mock_get_logger.setLevel.assert_called_once_with(level)
        self.mock_logger.Formatter.assert_called_once_with(format_string)
        mock_handler.setLevel.assert_called_once_with(level)
        mock_handler.setFormatter.assert_called_once_with(mock.ANY)
        mock_get_logger.addHandler.assert_called_once_with(mock_handler)

        assert result == mock_get_logger

    def test__generic_log__tuple_format(self):
        """
        Tests generic logger setup, where the
        format is passed in as tuple
        """
        logger = "syslog"
        mock_handler = mock.Mock()
        format_string = ("more", "nonsense")
        level = "debug?"

        mock_get_logger = mock.Mock()
        self.mock_logger.getLogger.return_value = mock_get_logger

        utils.generic_logging(
            logger,
            mock_handler,
            format_string,
            level
        )

        self.mock_logger.Formatter.assert_called_once_with(
            format_string[0],
            format_string[1]
        )

    @mock.patch('adaptationengine_framework.utils.generic_logging')
    def test__syslogging(self, mock_genlog):
        """Test creation of syslog handler"""
        name = "adaptation engine"
        level = "a fake level"

        utils.syslog_logging(name, level)

        self.mock_logger.handlers.SysLogHandler.assert_called_once_with(
            address='/dev/log'
        )
        mock_genlog.assert_called_once_with(
            'syslog',
            mock.ANY,
            mock.ANY,
            level
        )

    @mock.patch('adaptationengine_framework.utils.generic_logging')
    def test__healthlogging(self, mock_genlog):
        """Test creation of healthcheck handler"""
        utils.health_logging()

        self.mock_logger.StreamHandler.assert_called_once_with(
            sys.stdout
        )
        mock_genlog.assert_called_once_with(
            'stdout',
            mock.ANY,
            mock.ANY,
            self.mock_logger.INFO
        )

    @mock.patch('adaptationengine_framework.utils.generic_logging')
    def test__stdlogging(self, mock_genlog):
        """Test creation of stdout handler"""
        utils.std_logging()

        self.mock_logger.StreamHandler.assert_called_once_with(
            sys.stdout
        )
        mock_genlog.assert_called_once_with(
            'stdout',
            mock.ANY,
            mock.ANY,
            self.mock_logger.INFO
        )

    @mock.patch('adaptationengine_framework.utils.yaml.load')
    @mock.patch(
        'adaptationengine_framework.utils.pkg_resources.resource_string'
    )
    def test__load_config__resource(self, mock_rsce, mock_yaml):
        """Test loading of configuration from yaml file"""
        configfile = None

        utils.load_config(configfile, clear_db_config=False)
        util_options = dir(utils.cfg)

        # check every config var is represented in utils
        options = dir(configuration)
        for option in options:
            if not option.startswith('__') and not option.endswith('__'):
                assert option in util_options

        self.mock_db.Database.load_config.assert_called_once_with()

    @mock.patch('adaptationengine_framework.utils.sys.exit')
    @mock.patch('adaptationengine_framework.utils.yaml.load')
    @mock.patch(
        'adaptationengine_framework.utils.pkg_resources.resource_string'
    )
    def test__load_config__keyerror(self, mock_rsce, mock_yaml, mock_exit):
        """
        Test loading of configuration from yaml file, but a needed entry
        is missing
        """
        configfile = None
        mock_rsce.return_value = ""
        mock_yaml.return_value = {}

        utils.load_config(configfile, clear_db_config=False)

        # should exit on keyerror
        mock_exit.assert_called_once_with(1)

    @mock.patch('adaptationengine_framework.utils.yaml.load')
    @mock.patch(
        'adaptationengine_framework.utils.pkg_resources.resource_string'
    )
    def test__load_config__clear_db(self, mock_rsce, mock_yaml):
        """
        Test loading of configuration from yaml file, but also clear the db
        """
        configfile = None

        utils.load_config(configfile, clear_db_config=True)

        self.mock_db.Database.delete_db_cfg.assert_called_once_with()

    @mock.patch('adaptationengine_framework.utils.yaml.load')
    @mock.patch('adaptationengine_framework.utils.open')
    def test__load_config__from_file(self, mock_open, mock_yaml):
        """Test loading of configuration from yaml file"""
        configfile = "/tmp/file"
        mock_open.read.return_value = "some_yaml"

        utils.load_config(configfile, clear_db_config=False)

        print mock_open.mock_calls
        mock_open.assert_called_once_with(configfile, 'r')

    @mock.patch('adaptationengine_framework.utils.sys.exit')
    @mock.patch('adaptationengine_framework.utils.yaml.load')
    @mock.patch('adaptationengine_framework.utils.open')
    def test__load_config__from_bad_file(
        self, mock_open, mock_yaml, mock_exit
    ):
        """Test loading of configuration from a bad yaml file"""
        configfile = "/tmp/file"
        mock_open.side_effect = OSError("File doesn't exist!!!!")

        utils.load_config(configfile, clear_db_config=False)

        # should exit on OSError
        mock_exit.assert_called_once_with(1)
