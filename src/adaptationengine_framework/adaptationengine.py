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
import json
import logging
import multiprocessing
import optparse
import signal
import sys
import time

import adaptationaction
import database
import distributor
import enactor
import event
import heatresourcehandler
import mqhandler
import output
import pluginmanager
import utils


LOGGER = utils.syslog_logging('adaptation-engine', logging.DEBUG)
HEALTHLOGGER = utils.health_logging()


class AdaptationEngine:
    """
    Sit on a message queue waiting for events, pass those events to plugins,
    compile the results, and apply those results to Openstack
    """

    def __init__(self):
        """
        Create plugin and message queue managers
        """
        self._plugin_manager = pluginmanager.PluginManager()
        output.OUTPUT.info("Plugin manager started")
        self._mq_handler = mqhandler.MQHandler(msg_callback=self._on_message)
        output.OUTPUT.info("Message Queue handler started")
        self._heat_resources = heatresourcehandler.HeatResourceHandler(
            mq_handler=self._mq_handler,
        )
        output.OUTPUT.info("Heat resource handler started")

        _manager = multiprocessing.Manager()
        self._locked_stacks = _manager.list()

    def setup(self):
        """Setup required message queue connections"""
        self._mq_handler.setup()

    def _is_passthrough(self, aa_list):
        """These action types are handled without using plugins, for now"""
        for action in aa_list:
            if action.adaptation_type not in [
                adaptationaction.AdaptationType.DeveloperAction,
                adaptationaction.AdaptationType.StartAction,
                adaptationaction.AdaptationType.StopAction
            ]:
                return False

        return True

    def _on_message(self, message):
        """
        Callback executed when a message arrives

        Determine the type of message and act accordingly. It should either
        be a message from a Heat Resource or an Event message.
        """
        try:
            LOGGER.info("message was [{}]".format(str(message)))
            msg_json = json.loads(message)
            if 'heat' in msg_json and len(msg_json) is 1:
                # presumably a message from heat
                self._heat_resources.message(message)
            elif 'id' in msg_json and len(msg_json) >= 4:
                # assuredly an event
                cw_event = event.Event(message)

                if cw_event.stack_id not in self._locked_stacks:
                    self._locked_stacks.append(cw_event.stack_id)
                    try:
                        aa_list = self._heat_resources.get_initial_actions(
                            event_name=cw_event.name,
                            stack_id=cw_event.stack_id
                        )
                        if aa_list:
                            heat_resource = self._heat_resources.get_resource(
                                event_name=cw_event.name,
                                stack_id=cw_event.stack_id
                            )

                            if self._is_passthrough(aa_list):
                                LOGGER.info(
                                    "single initial action is"
                                    "passthrough type [{}]".format(aa_list)
                                )
                                pass_action = aa_list[0]
                                try:
                                    pass_action.target = (
                                        cw_event.machines[0].get('id')
                                    )
                                except Exception, err:
                                    LOGGER.error(
                                        "No machines field in event"
                                        "to set target from"
                                    )
                                LOGGER.info("Enacting adaptation")
                                enactor.Enactor.enact(
                                    event=cw_event,
                                    heat_resource=heat_resource,
                                    stack_id=cw_event.stack_id,
                                    adaptation_action=pass_action,
                                )

                                self._unlock_stack(cw_event.stack_id)
                            else:
                                dist = distributor.Distributor(
                                    cw_event,
                                    initial_action_list=aa_list,
                                    heat_resource=heat_resource,
                                    callback=self._on_distributor_results,
                                    plugin_manager=self._plugin_manager,
                                )
                                dist.start()
                        else:
                            self._unlock_stack(cw_event.stack_id)
                            LOGGER.info(
                                "Enactment invalid: no valid initial"
                                " actions found for event [{}] from "
                                "stack [{}]".format(
                                    cw_event.name,
                                    cw_event.stack_id
                                )
                            )
                    except Exception, err:
                        self._unlock_stack(cw_event.stack_id)
                        raise Exception(err)
                else:
                    LOGGER.info(
                        "Enactment invalid: stack_id [{}] "
                        "already locked".format(
                            cw_event.stack_id
                        )
                    )

                database.Database.log_event_received(
                    stack_id=cw_event.stack_id,
                    event=cw_event
                )
            else:
                raise ValueError('Message invalid')
        except ValueError, err:
            # too large / not json / incorrect message format
            LOGGER.error('{}'.format(err))

        except KeyError, err:
            LOGGER.error("Message missing field: [{}]".format(err))
        except Exception, err:
            LOGGER.error(
                'There was an exception handling a message: [{}]'.format(
                    err
                )
            )
            LOGGER.exception(err)

    def _on_distributor_results(
        self,
        event,
        initial_actions,
        heat_resource,
        results,
    ):
        """
        Callback executed by the distributor when it has gotten results
        back from the plugins
        """
        try:
            whitelist_types = []
            for x in initial_actions:
                whitelist_types.append(x.adaptation_type)

            LOGGER.info('whitelist_types [{}]'.format(whitelist_types))
            LOGGER.info('results [{}]'.format(results))
            if len(results) < 1:
                raise Exception('No results returned')

            chosen_adaptation = results[0]
            LOGGER.info('chosen_adaptation [{}]'.format(chosen_adaptation))
            LOGGER.info(
                'chosen_adaptation score is {}'.format(chosen_adaptation.score)
            )
            if chosen_adaptation.score < 0:
                LOGGER.info("Enacting adaptation")
                LOGGER.info(
                    "adaptation action score is -1 "
                    "so switching to developeraction"
                )
                chosen_adaptation = adaptationaction.AdaptationAction(
                    adaptationaction.AdaptationType.DeveloperAction
                )

            try:
                enactor.Enactor.enact(
                    event=event,
                    heat_resource=heat_resource,
                    stack_id=event.stack_id,
                    adaptation_action=chosen_adaptation,
                )
            except Exception, err:
                LOGGER.error("Error enacting adaptation [{}]".format(err))

        except Exception, err:
            LOGGER.error(
                "There was an exception handling distributor "
                "results: [{}]".format(err)
            )
            #  LOGGER.exception(err)

        self._unlock_stack(event.stack_id)

    def _unlock_stack(self, stackid):
        """
        Remove stackid from the list of locked stacks,
        allowing new adaptations to be performed on it
        """
        try:
            self._locked_stacks.remove(stackid)
        except ValueError:
            LOGGER.warn(
                "Tried to remove a non-existant stack id [{}]"
                " from list of locked stacks".format(stackid)
            )

    def run(self):
        """Connect the message queue handlers"""
        self._mq_handler.run()

    def stop(self):
        """Disconnect the message queue handlers"""
        try:
            self._mq_handler.stop()
        except Exception, err:
            print err

    def healthcheck(self):
        """Run a message queue connection/quality check"""
        self.setup()
        self._mq_handler.healthcheck()
        self._mq_handler.stop()


def main():
    """Do the thing"""
    usage = "usage: %prog"
    description = "Adaptation Engine"
    version = "%prog 0.8.3"

    output.OUTPUT.info("Initialising...")

    opt_parser = optparse.OptionParser(
        usage=usage,
        version=version,
        description=description
    )
    opt_parser.add_option(
        "-c",
        "--cfg",
        metavar="FILE",
        action="store",
        type="string",
        help="specify the full path to an alternate config FILE",
        dest="cfg_file",
        default=None
    )
    opt_parser.add_option(
        "--healthcheck",
        action="store_true",
        help="Perform a healthcheck",
        dest="healthcheck",
        default=False
    )
    opt_parser.add_option(
        "--clear-db-log",
        action="store_true",
        help="Delete log entries in the database",
        dest="clear_log",
        default=False
    )
    opt_parser.add_option(
        "--clear-db-config",
        action="store_true",
        help="Delete config stored in database",
        dest="clear_cfg",
        default=False
    )

    (options, args) = opt_parser.parse_args()

    utils.load_config(
        configfile=options.cfg_file,
        clear_db_config=options.clear_cfg
    )

    if options.clear_log:
        database.Database.delete_db_log()

    daemon = AdaptationEngine()

    def time_to_die(signal, frame):
        """Kill the adaptation engine processes"""
        LOGGER.info("Passing along SIGTERM")
        daemon.stop()
        sys.exit(0)
        output.OUTPUT.info("Done.")

    signal.signal(signal.SIGTERM, time_to_die)

    output.OUTPUT.info("Adaptation Engine started (ctrl+c to quit)...")

    try:
        if options.healthcheck:
            daemon.healthcheck()
        else:
            daemon.run()
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        daemon.stop()
        sys.exit(0)

if __name__ == "__main__":
    main()
