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
import copy
import logging

import adaptationengine_framework.adaptationaction as adaptationaction
import adaptationengine_framework.database as database
import adaptationengine_framework.stv as stv

LOGGER = logging.getLogger('syslog')


class Consolidator:
    """
    Combine arrays of adaptation actions returned by plugins into a single list
    """

    @staticmethod
    def consolidate(
            event, first_initial_actions, round_results, blacklisted_actions
    ):
        """
        Use a voting system to combine and reorder the plugin round-results
        into one list. Return that combined list, along with any actions
        blacklisted by plugins
        """
        LOGGER.info(
            'Consolidator init: event name [{0}]'.format(event.name)
        )

        LOGGER.info('event: [{0}]'.format(str(event)))
        LOGGER.info('results: [{0}]'.format(str(round_results)))
        LOGGER.info("Blacklist: {}". format(blacklisted_actions))
        LOGGER.info('Consolidator start')

        LOGGER.info('Removing non-whitelisted actions')
        whitelisted_types = (
            [action.adaptation_type for action in first_initial_actions]
        )
        whitelisted_types.append(
            adaptationaction.AdaptationType.LowPowerAction
        )
        whitelisted_results = copy.deepcopy(round_results)
        for name, data in round_results.items():
            for action in data.get('results', []):
                if action.adaptation_type not in whitelisted_types:
                    whitelisted_results[name]['results'].remove(action)

        LOGGER.info('Starting voting')
        (output, blacklisted_actions) = stv.SingleTransferrableVote.tally(
            whitelisted_results,
            blacklisted_actions
        )
        LOGGER.info("Blacklist: {}". format(blacklisted_actions))

        LOGGER.info('Consolidator results: {}'.format(output))

        if output is not []:
            database.Database.log_consolidation(
                stack_id=event.stack_id,
                consolidated_results=output
            )

        # return consolidated results and new blacklist
        return (output, blacklisted_actions)
