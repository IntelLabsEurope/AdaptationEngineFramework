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
# pylint: disable=protected-access,invalid-name, too-many-public-methods
# pylint: disable=unused-argument, no-self-use

import unittest
import sys

import mock

# we don't need any of these installed to test
# but we do need their importing to not-break-everything
NO_IMPORT = mock.Mock()
sys.modules['web'] = NO_IMPORT

import adaptationengine_framework.configuration as configuration
import adaptationengine_framework.rest as rest


class TestWebboNoPrinto(unittest.TestCase):
    """Test cases for a class that purposefully does nothing. Coverage!"""

    def test__write(self):
        test = rest.WebboNoPrinto()
        test.write("data")

    def test__flush(self):
        test = rest.WebboNoPrinto()
        test.flush()


class TestWebbo(unittest.TestCase):
    """Test cases for the plugin manager class"""

    def setUp(self):
        """Create patchers"""
        self.patchers = []

        # patch logging
        patcher_logger = mock.patch(
            'adaptationengine_framework.rest.logging'
        )
        self.patchers.append(patcher_logger)
        self.mock_logger = patcher_logger.start()

        # patch configuration
        patcher_cfg = mock.patch(
            'adaptationengine_framework.rest.cfg'
        )
        self.patchers.append(patcher_cfg)
        self.mock_cfg = patcher_cfg.start()

        # patch webpy
        patcher_web = mock.patch(
            'adaptationengine_framework.rest.web'
        )
        self.patchers.append(patcher_web)
        self.mock_web = patcher_web.start()

        # patch threading
        patcher_thread = mock.patch(
            'adaptationengine_framework.rest.threading'
        )
        self.patchers.append(patcher_thread)
        self.mock_thread = patcher_thread.start()

    def tearDown(self):
        """Destroy patchers"""
        for patcher in self.patchers:
            patcher.stop()

    def test__init(self):
        """Test that it can be initialised"""
        mock_agreement_map = {"a": {"agreement": 1, "event": "event"}}
        mock_agreement_update_function = mock.Mock()
        mock_agreement_update_function.return_value = mock_agreement_map

        test = rest.Webbo(mock_agreement_update_function)

        assert test._get_agreement_map() == mock_agreement_map

    def test__load_agreements(self):
        """Test loading the agreement map pre-request"""
        mock_handler = mock.Mock()
        mock_agreement_map = {"a": {"agreement": 1, "event": "event"}}
        mock_agreement_update_function = mock.Mock()
        mock_agreement_update_function.return_value = mock_agreement_map

        test = rest.Webbo(mock_agreement_update_function)

        result = test.load_agreements(mock_handler)

        assert mock_agreement_update_function.called
        assert result == mock_handler()
        assert self.mock_web.ctx.agreements == mock_agreement_map

    def test__run(self):
        """Test running the webserver"""
        self.mock_cfg.webbo__port = 0
        test = mock.Mock(rest.Webbo)
        rest.Webbo.run(test)

        self.mock_web.application.assert_called_once_with(
            (
                '/agreements', 'RESTAgreements',
                '/(.*)', 'RESTRoot',
            ),
            mock.ANY,
        )
        self.mock_web.application().add_processor.assert_called_once_with(
            mock.ANY
        )
        self.mock_web.httpserver.runsimple.assert_called_once_with(
            mock.ANY,
            ("0.0.0.0", 0)
        )

    def test__run__exception(self):
        """Test running the webserver except problems"""
        self.mock_cfg.webbo__port = 0
        self.mock_web.httpserver.runsimple.side_effect = Exception
        test = mock.Mock(rest.Webbo)
        rest.Webbo.run(test)

        self.mock_web.application.assert_called_once_with(
            (
                '/agreements', 'RESTAgreements',
                '/(.*)', 'RESTRoot',
            ),
            mock.ANY,
        )
        self.mock_web.application().add_processor.assert_called_once_with(
            mock.ANY
        )
        self.mock_web.httpserver.runsimple.assert_called_once_with(
            mock.ANY,
            ("0.0.0.0", 0)
        )

    def test__stop(self):
        """Test stopping the webserver"""
        mock_agreement_update_function = mock.Mock()
        test = rest.Webbo(mock_agreement_update_function)
        test._app = mock.Mock()

        test.stop()

        test._app.stop.assert_called_once_with()


class TestRestRoot(unittest.TestCase):
    """Test cases for the plugin manager class"""

    def setUp(self):
        """Create patchers"""
        self.patchers = []

        # patch webpy
        patcher_web = mock.patch(
            'adaptationengine_framework.rest.web'
        )
        self.patchers.append(patcher_web)
        self.mock_web = patcher_web.start()

    def tearDown(self):
        """Destroy patchers"""
        for patcher in self.patchers:
            patcher.stop()

    def test__GET(self):
        """Test the the root response is a message"""
        test = rest.RESTRoot()
        result = test.GET()
        assert result == "No"

        # agruments shouldn't matter
        test = rest.RESTRoot()
        result = test.GET("shrug")

        assert result == "No"


class TestRestAgreements(unittest.TestCase):
    """Test cases for the plugin manager class"""

    def setUp(self):
        """Create patchers"""
        self.patchers = []

        # patch webpy
        patcher_web = mock.patch(
            'adaptationengine_framework.rest.web'
        )
        self.patchers.append(patcher_web)
        self.mock_web = patcher_web.start()

    def tearDown(self):
        """Destroy patchers"""
        for patcher in self.patchers:
            patcher.stop()

    def test__GET(self):
        """
        Test that the agreement mapping gets switched around
        and displayed as JSON
        """
        self.mock_web.ctx.agreements = {
            '<agreement-id>': {
                'stack_id': '<stack-id>',
                'event': '<event-name>'
            }
        }

        test = rest.RESTAgreements()
        results = test.GET()

        assert results == """{"<agreement-id>": {"stack_id": "<stack-id>", "event": "<event-name>"}}"""

        # agruments shouldn't matter
        test = rest.RESTAgreements()
        results = test.GET("shrug")

        assert results == """{"<agreement-id>": {"stack_id": "<stack-id>", "event": "<event-name>"}}"""
