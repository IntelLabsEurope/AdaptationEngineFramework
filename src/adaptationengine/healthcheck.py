"""
Copyright 2014 INTEL RESEARCH AND INNOVATION IRELAND LIMITED

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
import logging
import signal
import string
import sys
import time
import uuid


HEALTHLOGGER = logging.getLogger('stdout')


class HealthCheck:
    """
    Perform a message queue healthcheck

    Connect to message queue, send X messages, check correct number of
    messages received, check contents against those sent.
    """

    def __init__(self, mq_interface):
        """Create required variables and create test messages"""
        self._MESSAGES = []
        self._RECEIVED_MESSAGES = []
        self._RECEIVED_COUNTER = 0
        self._NUM_MSGS = 2000
        self._COMPLETE = False

        self._TIME_START = time.time()
        self._TIME_END = None

        self._mq_interface = mq_interface

        self.log(
            'Starting tests for "{0}"'.format(self._mq_interface.test_name), 3
        )
        self.log('Generating messages')
        for x in range(self._NUM_MSGS):
            self._MESSAGES.append(uuid.uuid4().hex)

    def _timeout_alert(self, signum, frame):
        """
        Callback executed if SIGALRM received during healthcheck execution
        """
        raise Exception("Timed out")

    def log(self, msg, status_code=0):
        """Convenience function for printing status updates to stdout"""
        statuseseses = ['----', 'FAIL', 'PASS', '!!!!']
        if status_code > len(statuseseses):
            status_code = 0

        s = string.Template("[${status}] ${message}")
        HEALTHLOGGER.info(
            s.substitute(status=statuseseses[status_code], message=msg)
        )

    def received_msg(self, msg):
        """
        Callback executed on receipt of message on queue

        Save message, update message counter, and check messages if counter
        hits the number of messages originally sent
        """
        self._RECEIVED_COUNTER += 1
        self._RECEIVED_MESSAGES.append(msg)
        if self._RECEIVED_COUNTER == self._NUM_MSGS:
            self._COMPLETE = True
            self.log('Correct number of messages received', 2)
            self._verify_messages()

    def _verify_messages(self):
        """Check messages received against those originally sent"""
        for m in self._MESSAGES:
            if m not in self._RECEIVED_MESSAGES:
                raise Exception('Messages do not match')

        self.log('All messages match', 2)
        self._mq_interface.stop()

    def publish_messages(self):
        """Publish all previously generated messages"""
        self.log('Publishing {0} messages'.format(self._NUM_MSGS))
        for x, msg in enumerate(self._MESSAGES):
            self._mq_interface.publish(msg)
        self.log('Messages published', 2)

    def run_tests(self, import_exception=ImportError):
        """
        Run the message queue health test

        Set up SIGALRM in case of timeout, kick off messaging, time how
        long everything takes
        """
        try:
            signal.signal(signal.SIGALRM, self._timeout_alert)
            signal.alarm(30)
            self._mq_interface.run()
        except import_exception:
            self.log('Import exception. Check system configuration', 1)
            sys.exit(1)
        except Exception, err:
            self.log('{0}'.format(err), 1)
            sys.exit(1)

        while not self._COMPLETE:
            pass

        elapsed_time = time.time() - self._TIME_START
        self.log('This check took about {0} seconds'.format(elapsed_time), 3)
        sys.exit(0)
