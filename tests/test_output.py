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
# pylint: disable=no-self-use

import unittest

import adaptationengine_framework.output as output

# we apparently can't mock python keywords so these tests
# just execute the code for coverage, and don't check anything


class TestOutput(unittest.TestCase):
    """Test cases for the output class"""

    def test__info(self):
        """Test printing an info string"""
        test_string = "test"
        output.OUTPUT.info(test_string)
        assert True

    def test__info_with_addon(self):
        """Test printing an info string with an addon string"""
        test_string = "test"
        test_addon = "addon"
        output.OUTPUT.info(test_string, addon=test_addon)
        assert True

    def test__error(self):
        """Test printing an error string"""
        test_string = "test"
        output.OUTPUT.error(test_string)
        assert True
