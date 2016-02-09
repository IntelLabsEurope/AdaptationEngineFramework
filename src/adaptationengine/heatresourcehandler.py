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

import adaptationaction
import openstack


LOGGER = logging.getLogger('syslog')


class HeatResourceHandler:
    """
    Interface with the custom Heat template resource

    The custom resource is added to a Heat template and, when the template
    is deployed, sends JSON messages via the existing message queue to the
    Adaptation Engine. This makes the Engine aware of what stacks have been
    deployed and their configuration details. This is currently the primary
    interface by which application-owners can interact with the Adaptation
    Engine
    """

    def __init__(self, mq_handler):
        """
        Set up variables, set up message queue, attempt to recover state
        i.e. any existing stacks and their details
        """
        LOGGER.debug('heat resource handler init')
        self._active_resources = {}
        self._mq_handler = mq_handler

        self._recover_state()

    # TODO: recover plugin config
    def _recover_state(self):
        """
        Poll openstack for existing custom heat resources and parse their
        templates to recover previous stacks
        """
        LOGGER.info("Trying to recover stack / resource state...")

        try:
            ks_admin_client = openstack.OpenStackClients.get_keystone_client()
        except:
            LOGGER.warn(
                'Could not connect to openstack to recover state'
            )
        else:
            for tenant in ks_admin_client.tenants.list():
                LOGGER.info("Trying tenant {}".format(tenant.name))
                try:

                    ks_tenant_client = (
                        openstack.OpenStackClients.get_keystone_client(
                            tenant_name=tenant.name
                        )
                    )

                    heat_client = openstack.OpenStackClients.get_heat_client(
                        ks_tenant_client
                    )

                    for stack in heat_client.stacks.list():
                        for resource in heat_client.resources.list(stack.id):
                            if (
                                resource.resource_type ==
                                "AdaptationEngine::Heat::AdaptationResponse"
                            ):
                                da_stack = heat_client.stacks.template(
                                    stack.id
                                )

                                resource_json = da_stack.get(
                                    'resources',
                                    {},
                                ).get(resource.resource_name)

                                event_name = resource_json.get(
                                    'properties',
                                    {},
                                ).get('name')

                                event_actions = resource_json.get(
                                    'properties',
                                    {},
                                ).get('allowed_actions')

                                event_h_scale = resource_json.get(
                                    'properties',
                                    {},
                                ).get('horizontal_scale_out', None)

                                actions = []
                                for action in event_actions:
                                    actions.append(
                                        adaptationaction.AdaptationAction(
                                            action
                                        )
                                    )
                                self._active_resources[
                                    resource.physical_resource_id
                                ] = {
                                    'stack_id': stack.id,
                                    'event': event_name,
                                    'actions': actions,
                                    'horizontal_scale_out': event_h_scale
                                }

                except Exception, err:
                    LOGGER.warn(
                        "Not able to recover state for tenant {}."
                        " [Error: {}]".format(tenant.name, err)
                    )
                else:
                    LOGGER.info(
                        "Recovered state for tenant {}".format(tenant.name)
                    )

        LOGGER.info(
            'Current active resources: {0}'.format(self._active_resources)
        )

    def get_initial_actions(self, event_name, stack_id):
        """Return the 'allowed_actions' of this event for this stack"""
        LOGGER.info('getting initial action list')
        for resource in self._active_resources.itervalues():
            if (
                resource.get('stack_id') == stack_id and
                resource.get('event') == event_name
            ):
                return resource.get('actions')

        return None

    def get_resource(self, event_name, stack_id):
        """Return the full records of this event for this stack"""
        LOGGER.info(
            'getting resource of name {} for stack {}'.format(
                event_name,
                stack_id
            )
        )
        for resource in self._active_resources.itervalues():
            if (
                resource.get('stack_id') == stack_id and
                resource.get('event') == event_name
            ):
                return resource

        return None

    def message(self, message):
        """
        Callback function executed on receipt of message

        Parse message and respond as needed
        """
        LOGGER.info('got message')
        try:
            msg = json.loads(message)
            if len(msg) != 1:
                raise Exception('invalid message: incorrect length')

            heat_msg = msg['heat']
            heat_msg_type = heat_msg['type']
            heat_msg_data = heat_msg['data']
            resource_id = heat_msg_data['resource_id']

            LOGGER.info('Got heat message type [{0}]'.format(heat_msg_type))
            if heat_msg_type == "heat_create":
                # stack id
                stack_id = heat_msg_data['stack_id']
                # allowed actions
                actions = []
                for action in heat_msg_data['actions']:
                    LOGGER.info('action is [{0}]'.format(str(action)))
                    actions.append(adaptationaction.AdaptationAction(action))

                self._active_resources[resource_id] = {
                    'stack_id': stack_id,
                    'event': heat_msg_data['name'],
                    'actions': actions,
                    'horizontal_scale_out': heat_msg_data.get(
                        'horizontal_scale_out',
                        None
                    ),
                    # 'default_weighting': default_weighting,
                    # 'weightings': weightings,
                    # 'grouping': grouping
                }

                self._mq_handler.publish_to_heat_resource(
                    resource_id=resource_id,
                    message=json.dumps({'response': resource_id})
                )

            elif heat_msg_type == 'heat_check_create_complete':
                self._mq_handler.publish_to_heat_resource(
                    resource_id=resource_id,
                    message=json.dumps({'response': True})
                )

            elif heat_msg_type == 'heat_delete':
                try:
                    del self._active_resources[resource_id]
                except KeyError, err:
                    LOGGER.info(
                        "KeyError for resource [{}], "
                        "responding as if deleted".format(resource_id)
                    )
                except Exception, err:
                    raise Exception(err)
                self._mq_handler.publish_to_heat_resource(
                    resource_id=resource_id,
                    message=json.dumps({'response': True})
                )

            elif heat_msg_type == 'heat_query':
                output = []

                for (event_resource_id, event) in (
                    self._active_resources.iteritems()
                ):
                    json_actions = []

                    for action in event['actions']:
                        json_actions.append(action.__dict__)

                    output.append({
                        'resource_id': event_resource_id,
                        'stack_id': event['stack_id'],
                        'event_name': event['event'],
                        'actions': json_actions,
                        'horizontal_scale_out': event.get(
                            'horizontal_scale_out',
                            None
                        )
                    })

                LOGGER.info('Ouput: {0}'.format(output))

                self._mq_handler.publish_to_heat_resource(
                    resource_id=resource_id,
                    message=json.dumps({'resources': output})
                )
            else:
                raise Exception('invalid message: unrecognised heat type')

            LOGGER.info('Current active resources: {0}'.format(
                self._active_resources)
            )

        except Exception, err:
            LOGGER.error(
                'There was an exception handling a message: [{0}]'.format(err)
            )
            LOGGER.exception(err)
