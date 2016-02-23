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
import multiprocessing
import threading

import configuration as cfg
import consolidator
import database
import openstack


LOGGER = logging.getLogger('syslog')


class Distributor(threading.Thread):
    """
    Pass an event and everything we know about a stack to X amount of plugins
    and wait for their results, sending those to a callback function
    """

    def __init__(
        self,
        event,
        initial_action_list,
        heat_resource,
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
        self._heat_resource = heat_resource

        # load initial adaptation list
        self._initial_actions = initial_action_list
        LOGGER.info('event: [{0}]'.format(str(self._cw_event)))
        LOGGER.info(
            '_initial_actions: [{0}]'.format(str(self._initial_actions))
        )

        self._openstack = openstack.OpenStackInterface()

        self._plugin_rounds = cfg.plugin__grouping or []

        threading.Thread.__init__(self)

    def run(self):
        """
        Execute the thread. Kick off plugin processes and wait for the results
        """
        try:
            consolidated_results = []
            LOGGER.info('distributor start')
            LOGGER.info('plugin__grouping is {}'.format(self._plugin_rounds))

            # start them off
            consolidated_results = self._initial_actions
            LOGGER.info(
                'consolidated_results: {}'.format(consolidated_results)
            )
            for rnd_num, rnd in enumerate(self._plugin_rounds):
                LOGGER.info(
                    "Starting plugin round {} with plugins {}".format(
                        rnd_num,
                        rnd
                    )
                )

                plugins = self._plugin_manager.get(rnd)
                plugin_weights = {}
                for plugin in plugins:
                    LOGGER.info(
                        "Setting up plugin: {}".format(plugin.plugin_name)
                    )
                    plugin.setup(
                        self._cw_event,
                        consolidated_results,
                        self._round_results
                    )
                    plugin.start()
                    plugin_weights[plugin.plugin_name] = plugin.weight
                    LOGGER.info(
                        "Started plugin: {}".format(plugin.plugin_name)
                    )

                # wait for them to finish (for a while)
                for plugin in plugins:
                    plugin.join(30)  # TODO: should this be configurable?

                LOGGER.info(
                    "results for round {}: {}".format(
                        rnd_num,
                        self._round_results
                    )
                )
                for key, results in self._round_results.items():
                    weight = plugin_weights.get(key, -1)
                    database.Database.log_plugin_result(
                        stack_id=self._cw_event.stack_id,
                        plugin_name=key,
                        plugin_weight=weight,
                        input_actions=consolidated_results,
                        output_actions=results,
                    )

                LOGGER.info('calling consolidator')
                consolidated_results = consolidator.Consolidator.consolidate(
                    self._cw_event,
                    self._initial_actions,
                    self._round_results,
                )
                self._round_results = {}

                if rnd_num < (len(self._plugin_rounds) - 1):
                    # keep the scores on the last round
                    for action in consolidated_results:
                        action.score = 0

            self._callback(
                self._cw_event,
                self._initial_actions,
                self._heat_resource,
                consolidated_results,
            )
        except Exception, err:
            LOGGER.error('Distributor error')
            LOGGER.exception(err)
