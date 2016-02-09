"""
Copyright 2015 INTEL RESEARCH AND INNOVATION IRELAND LIMITED

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


LOGGER = logging.getLogger('syslog')


class Consolidator:
    """
    Combine arrays of adaptation actions returned by plugins into a single list
    """

    @staticmethod
    def consolidate(event, first_initial_actions, round_results):
        """
        Consolidate
        """
        LOGGER.info(
            'Consolidator init: event name [{0}]'.format(event.name)
        )

        LOGGER.info('event: [{0}]'.format(str(event)))
        LOGGER.info('results: [{0}]'.format(str(round_results)))
        LOGGER.info('Consolidator start')
        output = []
        for key, value in round_results.items():
            LOGGER.info("Output key [{}] value [{}]".format(key, value))
            output = output + value
        LOGGER.info('Consolidator results: {}'.format(output))

        return output
