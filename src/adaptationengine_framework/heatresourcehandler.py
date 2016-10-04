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

import requests

import adaptationengine_framework.adaptationaction as adaptationaction
import adaptationengine_framework.configuration as cfg
import adaptationengine_framework.database as database
import adaptationengine_framework.openstack as openstack
import adaptationengine_framework.output as output


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
        self._active_vms = {}
        self._mq_handler = mq_handler

        _manager = multiprocessing.Manager()
        self._agreement_map = _manager.dict()

        self._recover_state()

    # TODO: recover plugin config
    def _recover_state(self):
        """
        Poll openstack for existing custom heat resources and parse their
        templates to recover previous stacks
        """
        LOGGER.info("Trying to recover stack / resource state...")
        output.OUTPUT.info("Trying to recover stack / resource state...")

        try:
            ks_admin_client = openstack.OpenStackClients.get_keystone_client()
        except:
            LOGGER.warn(
                'Could not connect to openstack to recover state'
            )
            output.OUTPUT.error("...could not connect to openstack")
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
                        ks_tenant_client,
                        admin_ks_client=ks_admin_client
                    )

                    for stack in heat_client.stacks.list():
                        try:
                            self._active_vms[stack.id] = []
                            for resource in heat_client.resources.list(
                                stack.id
                            ):
                                if (
                                        resource.resource_type ==
                                        (
                                            "AdaptationEngine::Heat::"
                                            "AdaptationResponse"
                                        )
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

                                    agreement_id = resource_json.get(
                                        'properties',
                                        {},
                                    ).get('agreement_id')

                                    event_actions = resource_json.get(
                                        'properties',
                                        {},
                                    ).get('allowed_actions')

                                    event_plugin_bl = resource_json.get(
                                        'properties',
                                        {},
                                    ).get(
                                        'plugins',
                                        {}
                                    ).get('blacklist')

                                    event_embargo = resource_json.get(
                                        'properties',
                                        {},
                                    ).get('extend_embargo')

                                    event_h_scale = resource_json.get(
                                        'properties',
                                        {},
                                    ).get('horizontal_scale_out', None)

                                    if event_h_scale:
                                        event_embargo = event_h_scale.get(
                                            'extend_embargo',
                                            event_embargo
                                        )

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
                                        'agreement_id': agreement_id,
                                        'event': event_name,
                                        'actions': actions,
                                        'embargo': event_embargo,
                                        'blacklist': event_plugin_bl,
                                        'horizontal_scale_out': event_h_scale
                                    }
                                elif(
                                    resource.resource_type ==
                                    "OS::Nova::Server"
                                ):
                                    self._active_vms[stack.id].append(
                                        resource.physical_resource_id
                                    )

                        except Exception, err:
                            LOGGER.warn(
                                "Tenant {} cannot access resources"
                                " of stack {}. [Error: {}]".format(
                                    tenant.name, stack.id, err
                                )
                            )
                            # LOGGER.exception(err)
                        else:
                            LOGGER.info(
                                "Recovered stack {} for tenant {}".format(
                                    stack.id,
                                    tenant.name
                                )
                            )

                except Exception, err:
                    LOGGER.warn(
                        "Not able to recover state for tenant {}."
                        " [Error: {}]".format(tenant.name, err)
                    )
                else:
                    LOGGER.info(
                        "Recovered state for tenant {}".format(tenant.name)
                    )
            database.Database.update_stack_list(self._active_vms)
            output.OUTPUT.info("Recovered state")

        self._update_agreement_map()
        LOGGER.info(
            'Current active resources: {0}'.format(self._active_resources)
        )
        LOGGER.info(
            'Current agreement map: {0}'.format(self._agreement_map)
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

    def get_agreement_map(self):
        self._update_agreement_map()
        return self._agreement_map.copy()  # return dict, not dictproxy

    def _update_agreement_map(self):
        """Return the dictionary mapping stack_ids to agreement_ids"""
        LOGGER.debug(
            'updating agreement map'
        )
        new_agreement_map = {}
        for resource in self._active_resources.itervalues():
            LOGGER.debug("Active Resource: {}".format(resource))
            agreement_id = resource.get('agreement_id', None)
            if agreement_id is not None:
                new_agreement_map[agreement_id] = {
                    'stack_id': resource.get('stack_id'),
                    'event': resource.get('event')
                }
                LOGGER.debug(
                    "New agreement map stack:{} agreement:{} event:{}".format(
                        resource.get('stack_id'),
                        agreement_id,
                        resource.get('event')
                    )
                )

        self._agreement_map.clear()
        self._agreement_map.update(new_agreement_map)

        LOGGER.debug('agreement map now: {}'.format(self._agreement_map))

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

                agreement_id = heat_msg_data.get('agreement_id', None)

                self._active_resources[resource_id] = {
                    'stack_id': stack_id,
                    'event': heat_msg_data['name'],
                    'agreement_id': agreement_id,
                    'actions': actions,
                    'embargo': heat_msg_data.get('embargo', 0),
                    'blacklist': heat_msg_data.get('blacklist', []),
                    'horizontal_scale_out': heat_msg_data.get(
                        'horizontal_scale_out',
                        None
                    ),
                }

                LOGGER.debug(
                    "Adding to active resources stack:{} "
                    "agreement:{} event:{}".format(
                        stack_id,
                        agreement_id,
                        heat_msg_data['name']
                    )
                )

                self._update_agreement_map()

                database.Database.update_stack_list(
                    self._active_vms,
                    delay=8,
                    create=True,
                    stack_id=stack_id
                )

                if agreement_id is not None:
                    try:
                        # try PUT at sla api to create 'statement'
                        base_url = cfg.sla_agreements__endpoint
                        end_url = "/enforcements/{}/start".format(agreement_id)
                        auth = (
                            cfg.sla_agreements__username,
                            cfg.sla_agreements__password
                        )
                        LOGGER.info(
                            "PUT-ting to {}{}".format(base_url, end_url)
                        )
                        response = requests.put(
                            "{}{}".format(base_url, end_url),
                            auth=auth,
                        )
                        LOGGER.info("Response: {:.90}".format(response.text))
                    except Exception, err:
                        LOGGER.info(
                            "Exception PUT-ting to sla api: {}".format(err)
                        )

                database.Database.log_adaptation_response_created(
                    stack_id=stack_id,
                    event_name=heat_msg_data['name'],
                    allowed_actions=actions,
                    horizontal_scale_out=heat_msg_data.get(
                        'horizontal_scale_out', {}
                    )
                )

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
                stack_id = None
                event_name = None
                try:
                    stack_id = self._active_resources[resource_id]['stack_id']
                    event_name = self._active_resources[resource_id]['event']
                    del self._active_resources[resource_id]
                    # update stacks in database
                    self._active_vms.pop(stack_id, None)
                    database.Database.update_stack_list(self._active_vms, 0)
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

                if stack_id and event_name:
                    database.Database.log_adaptation_response_deleted(
                        stack_id,
                        event_name
                    )

            elif heat_msg_type == 'heat_query':
                output_json = []

                for (event_resource_id, event) in (
                        self._active_resources.iteritems()
                ):
                    json_actions = []

                    for action in event['actions']:
                        json_actions.append(action.__dict__)

                    output_json.append({
                        'resource_id': event_resource_id,
                        'stack_id': event['stack_id'],
                        'agreement_id': event.get('agreement_id'),
                        'event_name': event['event'],
                        'embargo': event['embargo'],
                        'blacklist': event['blacklist'],
                        'actions': json_actions,
                        'horizontal_scale_out': event.get(
                            'horizontal_scale_out',
                            None
                        )
                    })

                LOGGER.info('Ouput: {0}'.format(output_json))

                self._mq_handler.publish_to_heat_resource(
                    resource_id=resource_id,
                    message=json.dumps({'resources': output_json})
                )
            else:
                raise Exception('invalid message: unrecognised heat type')

            LOGGER.info(
                'Current active resources: {0}'.format(self._active_resources)
            )

        except Exception, err:
            LOGGER.error(
                'There was an exception handling a message: [{0}]'.format(err)
            )
            LOGGER.exception(err)
