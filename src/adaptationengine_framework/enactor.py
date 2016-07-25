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
import time
import uuid
import yaml

import adaptationengine_framework.adaptationaction as adaptationaction
import adaptationengine_framework.configuration as cfg
import adaptationengine_framework.database as database
import adaptationengine_framework.mqhandler as mqhandler
import adaptationengine_framework.openstack as openstack


LOGGER = logging.getLogger('syslog')


class Enactor:
    """
    Affect changes to the Openstack system
    """

    @staticmethod
    def poll_migrate_complete(
            nova_client,
            adaptation_action,
            retry_wait=10,
            retries=20
    ):
        """
        Continually check Nova for physical location of VM until it is
        confirmed to be on the right host, or retry count runs out
        """
        for attempt in xrange(retries):
            # get all hypervisors running VMs
            hypervisors = nova_client.hypervisors.search(
                adaptation_action.destination,
                servers=True
            )
            LOGGER.info("adaptation_action: {}".format(adaptation_action))
            for hypervisor in hypervisors:
                # look for our instance
                try:
                    for server in hypervisor.servers:
                        LOGGER.info(server)
                        # return true if we find it
                        if (
                                server.get('uuid', None) ==
                                adaptation_action.target
                        ):
                            nova_client.servers.get(
                                server.get('uuid')
                            )
                            LOGGER.info('Instance is on correct host machine')
                            return True
                except AttributeError:
                    pass  # no servers? skip

            # otherwise loop and try again
            LOGGER.info(
                "Server not migrated yet. Will retry {} more times"
                ", the next in {} seconds".format(
                    (retries - attempt - 1),
                    retry_wait
                )
            )
            time.sleep(retry_wait)

        LOGGER.warn("Server did not seem to migrate, returning False")

        return False

    @staticmethod
    def poll_stack_update_complete(
            heat_client,
            stack_id,
            retry_wait=10,
            retries=20
    ):
        """
        Continually check Heat for status of stack until it is marked
        as 'COMPLETE' or retries run out
        """
        for attempt in xrange(retries):
            stack = heat_client.stacks.get(stack_id)
            if stack.status == 'COMPLETE':
                LOGGER.info("Stack update complete")
                LOGGER.info("Adaptation complete. Returning True.")
                return True
            else:
                LOGGER.info(
                    "Stack update not complete yet, current status is "
                    "{status}. Will retry {retries} more times in {retry} "
                    "seconds".format(
                        status=stack.status,
                        retries=(retries - attempt - 1),
                        retry=retry_wait
                    )
                )
                time.sleep(retry_wait)
        LOGGER.info("Stack update seemed to fail, returning False")
        return False

    @staticmethod
    def poll_start_complete(
            nova_client,
            instance_id,
            retry_wait=5,
            retries=20
    ):
        """
        Check Nova for current instance power state and compare to
        known power on state
        """
        return Enactor.poll_power_state(
            nova_client,
            instance_id,
            [1],  # power on state
            retry_wait,
            retries
        )

    @staticmethod
    def poll_stop_complete(
            nova_client,
            instance_id,
            retry_wait=10,
            retries=20
    ):
        """
        Check Nova for current instance power state and compare to
        known power off state
        """
        return Enactor.poll_power_state(
            nova_client,
            instance_id,
            [0, 4],  # power off states
            retry_wait,
            retries
        )

    @staticmethod
    def poll_power_state(
            nova_client,
            instance_id,
            desired_states,
            retry_wait,
            retries
    ):
        """
        Check Nova for current instance power state and compare to
        desired_states, returning True if current is in desired and
        False otherwise
        """
        power_error = [-1]
        for attempt in xrange(retries):
            server = nova_client.servers.get(instance_id)
            server_dict = server.to_dict()
            power_state = server_dict.get(
                'OS-EXT-STS:power_state',
                power_error
            )

            if power_state in desired_states:
                LOGGER.error(
                    "Power state {} for instance {} is correct".format(
                        power_state,
                        instance_id
                    )
                )
                return True
            elif power_state in power_error:
                LOGGER.error(
                    "Power state {} for instance {} "
                    "could not be retrieved".format(power_state, instance_id)
                )
                return False

            # otherwise loop and try again
            LOGGER.info(
                "Instance {} power state {} unchanged. "
                "Will retry {} more times, the next in {} seconds".format(
                    instance_id,
                    power_state,
                    (retries - attempt - 1),
                    retry_wait
                )
            )
            time.sleep(retry_wait)

        LOGGER.info(
            "Instance {} power state did not seem to change, "
            "returning False".format(instance_id)
        )

        return False

    @staticmethod
    def enact(
            event,
            heat_resource,
            stack_id,
            adaptation_action,
            logged_results={}
    ):
        """
        Enact an adaptation action upon a specified stack using Openstack APIs,
        posting message queue notficiations as appropriate
        """
        enact_status = False
        LOGGER.info("This is when I do openstack things")
        LOGGER.info(
            "Got action {} from stack id {} and "
            "event name {} with heat resource {}".format(
                adaptation_action,
                stack_id,
                event.name,
                heat_resource
            )
        )

        # Connect to Rabbit
        try:
            openstack_broker = mqhandler.QuickRabbit(
                host=cfg.openstack_event__host,
                port=cfg.openstack_event__port,
                username=cfg.openstack_event__username,
                password=cfg.openstack_event__password,
            )

            app_feedback_broker = mqhandler.QuickRabbit(
                host=cfg.app_feedback__host,
                port=cfg.app_feedback__port,
                username=cfg.app_feedback__username,
                password=cfg.app_feedback__password,
            )
        except Exception, err:
            raise Exception(
                "Couldn't connect to rabbit broker [{}]".format(err)
            )

        # Connect to OpenStack
        try:
            keystone_client = openstack.OpenStackClients.get_keystone_client()
            heat_client = openstack.OpenStackClients.get_heat_client(
                keystone_client
            )
            nova_client = openstack.OpenStackClients.get_nova_client()
        except Exception, err:
            raise Exception(
                "Couldn't connect to openstack [{}]".format(err)
            )

        app_feedback_event_payload = {
            'type': adaptationaction.AdaptationType.get_string(
                adaptation_action.adaptation_type
            ),
            'target': adaptation_action.target,
            'destination': adaptation_action.destination,
            'scale_value': adaptation_action.scale_value,
            'score': adaptation_action.score,
        }

        # Publish start notifications
        openstack_broker.publish_openstack_start_event(
            cfg.openstack_event__exchange,
            cfg.openstack_event__key,
            stack_id,
            event.name
        )
        app_feedback_broker.publish_app_feedback_start_event(
            cfg.app_feedback__exchange,
            cfg.app_feedback__key,
            stack_id,
            event.name,
            app_feedback_event_payload
        )

        database.Database.log_adaptation_started(
            stack_id=stack_id,
            event_name=event.name,
            adaptation=adaptation_action,
            consolidated_results=logged_results
        )

        # ENACT
        LOGGER.info("Openstack is doing things now....")
        if (
                adaptation_action.adaptation_type ==
                adaptationaction.AdaptationType.MigrateAction
        ):
            nova_client.servers.live_migrate(
                adaptation_action.target,
                adaptation_action.destination,
                False,
                False
            )
            LOGGER.info(
                "[ENACTMENT] MigrateAction, {} moves to {}".format(
                    adaptation_action.target,
                    adaptation_action.destination
                )
            )
            enact_status = Enactor.poll_migrate_complete(
                nova_client,
                adaptation_action
            )
        elif (
                adaptation_action.adaptation_type ==
                adaptationaction.AdaptationType.VerticalScaleAction
        ):
            try:
                desired_id = None
                for flavor in nova_client.flavors.list():
                    if flavor.name == adaptation_action.scale_value:
                        desired_id = flavor.id

                nova_client.servers.resize(
                    adaptation_action.target,
                    desired_id
                )
                LOGGER.info(
                    "[ENACTMENT] VerticalScaleAction, "
                    "{} scales to {}. ".format(
                        adaptation_action.target,
                        adaptation_action.scale_value
                    )
                )

            except Exception, err:
                LOGGER.exception(err)
                enact_status = False
            else:
                enact_status = Enactor.poll_stack_update_complete(
                    heat_client,
                    stack_id
                )
        elif (
                adaptation_action.adaptation_type ==
                adaptationaction.AdaptationType.HorizontalScaleAction
        ):
            LOGGER.info("[ENACTMENT] HorizontalScaleAction")
            try:
                # get the stack we're scaling out
                # get its template
                stack_json_template = heat_client.stacks.template(stack_id)
                new_template = stack_json_template
                # get the horizontal_scale_out from the original stack template
                resource_config = heat_resource.get('horizontal_scale_out', {})
                new_resource_name = '{prefix}-{uuid}'.format(
                    prefix=resource_config.get(
                        'name_prefix',
                        'adaptation'
                    ),
                    uuid=uuid.uuid4().hex
                )
                LOGGER.info(
                    "name_prefix is {}".format(
                        resource_config.get('name_prefix', 'adaptation'))
                )
                LOGGER.info(
                    "new resource name is {}".format(new_resource_name)
                )

                # generate a new instance for the template
                new_resource = {
                    'type': 'OS::Nova::Server',
                    'properties': {
                        'key_name': resource_config.get('key_name'),
                        'image': resource_config.get('image'),
                        'flavor': resource_config.get('flavor'),
                        'networks': [
                            {'network': resource_config.get('network_id')}
                        ]
                    }
                }
                # add to template
                new_template['resources'][new_resource_name] = new_resource
                LOGGER.info('new template ------ {}'.format(new_template))
                # update stack with new template
                the_yaml = yaml.load(json.dumps(new_template))
                heat_client.stacks.update(stack_id, template=the_yaml)
            except Exception, err:
                LOGGER.exception(err)
                enact_status = False
            else:
                enact_status = Enactor.poll_stack_update_complete(
                    heat_client,
                    stack_id
                )

        elif (
                adaptation_action.adaptation_type ==
                adaptationaction.AdaptationType.DeveloperAction
        ):
            LOGGER.info(
                "[ENACTMENT] DeveloperAction, {} has value {}".format(
                    event.name,
                    event.value
                )
            )
            adaptation_request_broker = mqhandler.QuickRabbit(
                host=cfg.mq__host,
                port=cfg.mq__port,
                username=cfg.mq__username,
                password=cfg.mq__password,
            )
            adaptation_request_broker.publish_adaptation_request(
                cfg.mq__exchange,
                cfg.mq__outbound,
                adaptation_action,
                event
            )
            adaptation_request_broker.disconnect()
            enact_status = True
        elif (
                adaptation_action.adaptation_type ==
                adaptationaction.AdaptationType.NoAction
        ):
            LOGGER.info(
                "[ENACTMENT] NoAction for stack {}".format(
                    stack_id
                )
            )
            enact_status = True

        elif (
                adaptation_action.adaptation_type ==
                adaptationaction.AdaptationType.StartAction
        ):
            LOGGER.info(
                "[ENACTMENT] StartAction for stack {}".format(
                    stack_id
                )
            )
            try:
                nova_client.servers.start(
                    adaptation_action.target
                )
            except Exception, err:
                LOGGER.warn("Powerstate start change problem")
            enact_status = Enactor.poll_start_complete(
                nova_client,
                adaptation_action.target
            )

        elif (
                adaptation_action.adaptation_type ==
                adaptationaction.AdaptationType.StopAction
        ):
            LOGGER.info(
                "[ENACTMENT] StopAction for stack {}".format(
                    stack_id
                )
            )
            try:
                nova_client.servers.stop(
                    adaptation_action.target
                )
            except Exception, err:
                LOGGER.warn("Powerstate stop change problem")
            enact_status = Enactor.poll_stop_complete(
                nova_client,
                adaptation_action.target
            )

        elif (
                adaptation_action.adaptation_type ==
                adaptationaction.AdaptationType.LowPowerAction
        ):
            LOGGER.info(
                "[ENACTMENT] LowPowerAction directed at {}".format(
                    adaptation_action.application
                )
            )
            adaptation_request_broker = mqhandler.QuickRabbit(
                host=cfg.mq__host,
                port=cfg.mq__port,
                username=cfg.mq__username,
                password=cfg.mq__password,
            )
            adaptation_request_broker.publish_lowpower_request(
                cfg.mq__exchange,
                cfg.mq__outbound,
                adaptation_action,
                event
            )
            adaptation_request_broker.disconnect()
            enact_status = True
        else:
            LOGGER.info(
                "[ENACTMENT] Unsupported action type [{}]!".format(
                    str(adaptation_action.adaptation_type)
                )
            )
            enact_status = False

        # sleep for a while, if extend_embargo is set
        extend_embargo = heat_resource.get('extend_embargo', 0)
        if enact_status is True and extend_embargo > 0:
            LOGGER.info(
                "Stack adaptation embargo extended by {} "
                "seconds. Sleeping.".format(
                    extend_embargo
                )
            )
            time.sleep(extend_embargo)

        # Publish notifications
        openstack_broker.publish_openstack_complete_event(
            cfg.openstack_event__exchange,
            cfg.openstack_event__key,
            stack_id,
            event.name
        )

        if enact_status is True:
            app_feedback_broker.publish_app_feedback_complete_event(
                cfg.app_feedback__exchange,
                cfg.app_feedback__key,
                stack_id,
                event.name,
                app_feedback_event_payload
            )

            database.Database.log_adaptation_completed(
                stack_id=stack_id,
                event_name=event.name,
                adaptation=adaptation_action
            )
        else:
            app_feedback_broker.publish_app_feedback_failed_event(
                cfg.app_feedback__exchange,
                cfg.app_feedback__key,
                stack_id,
                event.name,
                app_feedback_event_payload
            )

            database.Database.log_adaptation_failed(
                stack_id=stack_id,
                event_name=event.name,
                adaptation=adaptation_action
            )

        # Disconnect from Rabbit
        openstack_broker.disconnect()
        app_feedback_broker.disconnect()

        return True
