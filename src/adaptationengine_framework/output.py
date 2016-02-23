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


class OUTPUT:

    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CLOSE = '\033[0m'
    FAIL = '\033[91m'

    @staticmethod
    def info(message, addon=None):
        output = OUTPUT.HEADER + str(message) + OUTPUT.CLOSE
        if addon:
            output += OUTPUT.BLUE + " [" + str(addon) + "]" + OUTPUT.CLOSE
        print output

    @staticmethod
    def error(message):
        print OUTPUT.FAIL + str(message) + OUTPUT.CLOSE
