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
import multiprocessing
import threading

import adaptationengine_framework.configuration as cfg
import adaptationengine_framework.consolidator as consolidator
import adaptationengine_framework.database as database
import adaptationengine_framework.openstack as openstack


LOGGER = logging.getLogger('syslog')


class Distributor(threading.Thread):
    """
    Pass an event and everything we know about a stack to X amount of plugins
    and wait for their results, sending those to a callback function
    """

    def __init__(
            self,
            event,
            input_action_list,
            heat_resource,
            agreement_map,
            callback,
            plugin_manager,
    ):
        """Create the thread, openstack interface, and some additional setup"""
        LOGGER.info(
            "distributor init. event name: [{0}]".format(event.name)
        )
        self._callback = callback
        self._cw_event = event
        self._manager = multiprocessing.Manager()
        self._plugin_manager = plugin_manager
        self._round_results = self._manager.dict()
        self._blacklisted_actions = []
        self._heat_resource = heat_resource
        self._logged_results = {}
        self._agreement_map = agreement_map

        # load initial adaptation list
        self._initial_actions = input_action_list
        LOGGER.info('event: [{0}]'.format(str(self._cw_event)))
        LOGGER.info(
            '_initial_actions: [{0}]'.format(str(self._initial_actions))
        )

        self._openstack = openstack.OpenStackInterface()

        self._plugin_rounds = cfg.plugin__grouping or []

        threading.Thread.__init__(self)

    def remove_blacklisted(self):
        """
        make a new plugin rounds 2d list that excludes plugins blacklisted
        for this event name
        """
        blacklist = self._heat_resource.get('blacklist')

        LOGGER.info(
            "Blacklist for [{}] event is [{}]".format(
                self._cw_event.name, blacklist
            )
        )

        if blacklist:
            plugin_grouping = []
            for rnd in self._plugin_rounds:
                new_round = []
                for plugin in rnd:
                    if plugin not in blacklist:
                        new_round.append(plugin)

                if new_round:
                    plugin_grouping.append(new_round)

            return plugin_grouping
        else:
            return self._plugin_rounds

    def run(self):
        """
        Execute the thread. Kick off plugin processes and wait for the results
        """
        consolidated_results = []
        try:
            LOGGER.info('distributor start')
            LOGGER.info('plugin__grouping is {}'.format(self._plugin_rounds))

            # clear blacklisted plugins
            plugin_grouping = self.remove_blacklisted()
            LOGGER.info('clearing blacklisted plugins for this action')
            LOGGER.info(
                'plugin__grouping is now {}'.format(plugin_grouping)
            )

            # start them off
            consolidated_results = self._initial_actions
            LOGGER.info(
                'initial actions: {}'.format(consolidated_results)
            )
            for rnd_num, rnd in enumerate(plugin_grouping):
                LOGGER.info(
                    "Starting plugin round {} with plugins {}".format(
                        rnd_num,
                        rnd
                    )
                )

                plugins = self._plugin_manager.get(rnd)

                for plugin in plugins:
                    LOGGER.info(
                        "Setting up plugin: {}".format(plugin.plugin_name)
                    )
                    plugin.setup(
                        self._cw_event,
                        consolidated_results,
                        self._round_results,
                        self._agreement_map
                    )
                    plugin.start()
                    LOGGER.info(
                        "Started plugin: {}".format(plugin.plugin_name)
                    )

                # wait for them to finish (for a while)
                timeout = cfg.plugin__timeout or 30
                LOGGER.info(
                    "Waiting {} seconds for plugins to execute".format(timeout)
                )
                for plugin in plugins:
                    plugin.join(
                        timeout
                    )

                LOGGER.info(
                    "results for round {}: {}".format(
                        rnd_num,
                        self._round_results
                    )
                )
                if not self._round_results:
                    consolidated_results = self._initial_actions
                    LOGGER.info("No results this round, so just passing along previous round's")
                else:
                    for plugin_name, plugin_data in self._round_results.items():
                        database.Database.log_plugin_result(
                            stack_id=self._cw_event.stack_id,
                            plugin_name=plugin_name,
                            plugin_weight=plugin_data.get('weight'),
                            input_actions=consolidated_results,
                            output_actions=plugin_data.get('results'),
                        )

                    if plugins == []:
                        raise Exception("No plugins were retrieved!")
                    else:
                        LOGGER.info('calling consolidator')
                        current_bl_len = len(self._blacklisted_actions)
                        (consolidated_results, self._blacklisted_actions) = (
                            consolidator.Consolidator.consolidate(
                                self._cw_event,
                                self._initial_actions,
                                self._round_results,
                                self._blacklisted_actions
                            )
                        )
                        new_bl_len = len(self._blacklisted_actions)
                        LOGGER.info(
                            "Added {} actions to the blacklist".format(
                                new_bl_len - current_bl_len
                            )
                        )

                    self._logged_results[rnd_num] = copy.deepcopy(
                        consolidated_results
                    )

                    self._round_results = {}

                    if rnd_num < (len(plugin_grouping) - 1):
                        # keep the scores on the last round
                        for action in consolidated_results:
                            action.score = 0

        except Exception, err:
            LOGGER.error('Distributor error')
            LOGGER.exception(err)
            consolidated_results = []
        finally:
            self._callback(
                self._cw_event,
                self._initial_actions,
                self._heat_resource,
                consolidated_results,
                self._logged_results
            )

