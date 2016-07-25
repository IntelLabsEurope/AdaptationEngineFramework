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
import random

import heatclient.client as heatc
import keystoneclient.v2_0.client as keyc
import novaclient.client as novac

import adaptationengine_framework.configuration as cfg


LOGGER = logging.getLogger('syslog')


class OpenStackClients:
    """
    Interfaces to the Openstack keystone, nova, and heat APIs
    """

    @staticmethod
    def get_keystone_client(
            auth_url=None,
            username=None,
            password=None,
            tenant_name=None
    ):
        """Generate a keystone client"""
        LOGGER.debug("Generating keystone client")
        os_url = auth_url or cfg.openstack__auth_url
        os_user = username or cfg.openstack__username
        os_pass = password or cfg.openstack__password
        os_tenant = tenant_name or cfg.openstack__tenant

        keystone_client = keyc.Client(
            auth_url=os_url,
            username=os_user,
            password=os_pass,
            tenant_name=os_tenant
        )
        LOGGER.debug("Generated keystone client")

        return keystone_client

    @staticmethod
    def get_nova_client(
            api_version='2',
            username=None,
            password=None,
            tenant=None,
            auth_url=None,
            timeout=60
    ):
        """Generate a nova client"""
        LOGGER.debug("Generating nova client")
        os_url = auth_url or cfg.openstack__auth_url
        os_user = username or cfg.openstack__username
        os_pass = password or cfg.openstack__password
        os_tenant = tenant or cfg.openstack__tenant

        nova_client = novac.Client(
            api_version,
            os_user,
            os_pass,
            os_tenant,
            os_url,
            timeout=timeout,
        )
        LOGGER.debug("Generated nova client")

        return nova_client

    @staticmethod
    def get_heat_client(keystone_client, admin_ks_client=None):
        """Generate a heat client"""
        LOGGER.debug("Looking for heat endpoint")
        endpoint_ks_client = admin_ks_client or keystone_client
        heat_endpoint = OpenStackClients._find_endpoint(
            endpoint_ks_client, 'heat', keystone_client.project_id
        )
        LOGGER.debug("Generating heat client")
        heat_client = heatc.Client(
            "1",  # HEAT_API_VERSION
            endpoint=heat_endpoint,
            token=keystone_client.auth_token
        )
        LOGGER.debug("Generated heat client")

        return heat_client

    @staticmethod
    def _find_endpoint(keystone_client, wanted_service, tenant_id=None):
        """Return the endpoint url for a named openstack service"""
        if keystone_client is None:
            LOGGER.error("Invalid keystone client")
            return None

        LOGGER.debug(
            "Looking for endpoint for service [{}]".format(wanted_service)
        )
        endpoint = None
        service_id = None
        for ks_service in keystone_client.services.list():
            LOGGER.debug(
                "wanted:{},  name:{},  id:{}".format(
                    wanted_service, ks_service.name, ks_service.id
                )
            )
            if ks_service.name == wanted_service:
                service_id = ks_service.id
                break

        for ks_endpoint in keystone_client.endpoints.list():
            LOGGER.debug(
                "service_id:{},  endpoint.service_id:{},  "
                "endpoint.internalurl:{}".format(
                    service_id, ks_endpoint.service_id, ks_endpoint.internalurl
                )
            )
            if ks_endpoint.service_id == service_id:
                endpoint = ks_endpoint.internalurl
                break

        LOGGER.debug("Apparent endpoint url [{}]".format(endpoint))

        # openstack undocumented version difference #37891
        try:
            replacement_id = tenant_id or keystone_client.project_id
            endpoint = endpoint.replace(
                '%(tenant_id)s',
                replacement_id
            )
            endpoint = endpoint.replace(
                '$(tenant_id)s',
                replacement_id
            )
        except AttributeError:
            LOGGER.error(
                "No endpoint found for service [{}] in Keystone".format(
                    wanted_service
                )
            )

        LOGGER.debug(
            "Endpoint url with tenant id [{}]".format(endpoint)
        )

        return endpoint

    @staticmethod
    def get_heat_client_for_stack(admin_keystone_client, stack_id):
        """
        Generate a Heat client with persmissions to affect a particular stack

        Heat doesn't let you look at stacks for other tenants,
        so we need to keep trying tenants till we find the one who
        owns the stack and return a heat client that will have access.
        This all assumes that the keystone user is an admin with access
        to give auth tokens for every tenant
        """
        for tenant in admin_keystone_client.tenants.list():
            try:
                ks_tenant_client = OpenStackClients.get_keystone_client(
                    tenant_name=tenant.name
                )
                heat_client = OpenStackClients.get_heat_client(
                    ks_tenant_client,
                    admin_ks_client=admin_keystone_client
                )
                try:
                    heat_client.stacks.get(stack_id)
                    LOGGER.debug("Returning heat client")
                    return heat_client
                except Exception, err:
                    LOGGER.debug(
                        "Stack doesn't belong to tenant {} anyway".format(
                            tenant.name
                        )
                    )
            except Exception, err:
                LOGGER.error("Exception accessing stacks: {}".format(err))

        return None

    @staticmethod
    def get_openstack_clients():
        """Return keystone, heat, and nova clients"""
        keystone_client = OpenStackClients.get_keystone_client()
        heat_client = OpenStackClients.get_heat_client(keystone_client)
        nova_client = OpenStackClients.get_nova_client()

        return (keystone_client, nova_client, heat_client)


class OpenStackInterface:
    """An interface to perform some needed Openstack operations"""

    def __init__(self):
        """Generate a nova client for the interface"""
        LOGGER.debug("OpenStackInterface init")
        self._nova_client = OpenStackClients.get_nova_client()

    def get_migration_destination(self, vm_id):
        """get a random host id to move this vm to,
        so long as it's not the one it's already on
        """
        LOGGER.info("Looking for a host to move vm {} to...".format(vm_id))
        hypervisor_list = self._nova_client.hypervisors.list()
        valid_hypervisors = []

        for hypervisor in hypervisor_list:
            hypervisor_hosts = self._nova_client.hypervisors.search(
                hypervisor.hypervisor_hostname,
                servers=True
            )
            origin_hypervisor = False
            for hypervisor_host in hypervisor_hosts:
                try:
                    for server in hypervisor_host.servers:
                        if server.get('uuid', None) == vm_id:
                            origin_hypervisor = True
                except AttributeError:
                    LOGGER.warn("No servers on this hypervisor")
            if not origin_hypervisor:
                valid_hypervisors.append(hypervisor)

        if valid_hypervisors:
            LOGGER.info(
                "Found these hypervisors {}".format(valid_hypervisors)
            )
            rando_hype = random.choice(valid_hypervisors)
            LOGGER.info(
                "Returning this hypervisor [{}]".format(rando_hype)
            )
            return rando_hype.hypervisor_hostname
        else:
            LOGGER.warn("Could not find any other hypervisors")

        return None

    def get_migration_target(self, stack_id):
        """get a vm id from this stack"""
        keystone_client = OpenStackClients.get_keystone_client()
        heat_client = OpenStackClients.get_heat_client_for_stack(
            keystone_client,
            stack_id
        )

        LOGGER.info(
            "Looking for a vm that belongs to stack {}".format(stack_id)
        )
        the_vms = []
        for resource in heat_client.resources.list(stack_id):
            if resource.resource_type == "OS::Nova::Server":
                the_vms.append(resource.physical_resource_id)

        LOGGER.info("Found these vms {}".format(the_vms))
        rando_vm = random.choice(the_vms)
        LOGGER.info("Returning this vm [{}]".format(rando_vm))
        return rando_vm

    def get_scale_value(self, vm_id):
        """TODO: get the flavour 'up' from this vm's current one"""
        # TODO: actually get scale value
        tmp_flavour = "2"
        LOGGER.warn(
            "Returning fake flavour {} for VM uuid {}".format(
                tmp_flavour, vm_id
            )
        )
        return tmp_flavour


    def get_vm_hypervisor_mapping(self):
        server_list = {}
        hypvrs = self._nova_client.hypervisors.list()
        for hype in hypvrs:
            hype_obj = self._nova_client.hypervisors.search(
                hype.hypervisor_hostname,
                servers=True
            )
            for h in hype_obj:
                try:
                    for server in h.servers:
                        server_list[server.get('uuid', None)] = h.hypervisor_hostname
                except AttributeError:
                    pass
        return server_list

