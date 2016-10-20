"""
Copyright 2016 INTEL RESEARCH AND INNOVATION IRELAND LIMITED

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
import datetime
import logging
import time
import threading

import pymongo

import adaptationengine_framework.openstack as openstack
import adaptationengine_framework.configuration as cfg


LOGGER = logging.getLogger('syslog')


class Database:
    """Interface to the adaptation engine mongodb database"""

    @staticmethod
    def _delete_collection(collection_name):
        """connect to database and delete a collection"""
        try:
            mongo_client = pymongo.MongoClient(
                cfg.database__host,
                int(cfg.database__port),
                serverSelectionTimeoutMS=5000
            )
            mongo_db = mongo_client[cfg.database__database_name]
            mongo_db.drop_collection(collection_name)
            mongo_client.close()
        except Exception, err:
            LOGGER.error(
                "Deleting database [{}] failed: [{}]".format(
                    collection_name, err
                )
            )

    @staticmethod
    def delete_db_log():
        """delete the collection where logging is stored"""
        Database._delete_collection(cfg.database__collection_log)

    @staticmethod
    def delete_db_cfg():
        """delete the collection where the config is stored"""
        Database._delete_collection(cfg.database__collection_config)

    @staticmethod
    def _post(entry):
        """post a json entry to the database"""
        try:
            mongo_client = pymongo.MongoClient(
                cfg.database__host,
                int(cfg.database__port),
                serverSelectionTimeoutMS=5000
            )
            mongo_db = mongo_client[cfg.database__database_name]
            mongo_collection = mongo_db[cfg.database__collection_log]
            mongo_collection.insert_one(entry)
            mongo_client.close()
        except Exception, err:
            LOGGER.error("Posting to database failed: [{}]".format(err))

    @staticmethod
    def _log(log_type, stack_id, log_details={}, location={}):
        """build the remaining JSON for a logging db entry"""
        _ISO8601_TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
        utc = datetime.datetime.utcnow()
        timestamp = utc.strftime(_ISO8601_TIME_FORMAT)
        #add the stacks current location
        try:
            location = Database.get_current_stack_location(stack_id)
        except Exception:
            pass
        output_json = {
            "log_stackid": stack_id,
            "log_timestamp": timestamp,
            "log_type": log_type,
            "log_details": log_details,
            "log_location": location
        }

        Database._post(output_json)

    @staticmethod
    def log_adaptation_response_created(
            stack_id, event_name, allowed_actions, horizontal_scale_out
    ):
        """log a preformatted json entry for an adaptation response creation"""
        allowed_actions = [
            action.to_dict() for action in allowed_actions
        ]
        log_details = {
            "name": event_name,
            "allowed_actions": allowed_actions,
            "horizontal_scale_out": horizontal_scale_out
        }
        Database._log('adaptation_response_created', stack_id, log_details)

    @staticmethod
    def log_adaptation_response_deleted(stack_id, event_name):
        """log a preformatted json entry for an adaptation response deletion"""
        log_details = {
            "name": event_name
        }
        Database._log('adaptation_response_deleted', stack_id, log_details)

    @staticmethod
    def log_event_received(stack_id, event):
        """log a preformatted json entry for a received event"""
        log_details = {
            "name": event.name,
            "value": event.value,
            "user_id": event.user_id,
            "tenant_id": event.tenant_id,
            "source": event.source,
            "severity": event.severity,
            "context": event.context,
            "data": event.data
        }
        Database._log('event_received', stack_id, log_details)

    @staticmethod
    def log_plugin_result(
            stack_id, plugin_name, plugin_weight, input_actions, output_actions
    ):
        """log a preformatted json entry for a plugin returning results"""
        input_actions = [action.to_dict() for action in input_actions]
        output_actions = [action.to_dict() for action in output_actions]
        log_details = {
            "name": plugin_name,
            "weight": plugin_weight,
            "input": input_actions,
            "output": output_actions
        }
        Database._log('plugin_result', stack_id, log_details)

    @staticmethod
    def log_consolidation(stack_id, consolidated_results):
        """log a preformatted json entry for a consolidation operation"""
        output_results = [action.to_dict() for action in consolidated_results]
        log_details = {
            # More Voting granularity?!?!
            "output": output_results
        }
        Database._log('consolidation', stack_id, log_details)

    @staticmethod
    def log_adaptation_started(stack_id, event_name, adaptation, consolidated_results=[]):
        """log a preformatted json entry for an adaptation being enacted"""

        c_res = []
        for res in consolidated_results:
            c_res.append([act.to_dict() for act in consolidated_results[res]])

        log_details = {
            "event_name": event_name,
            "adaptation": adaptation.to_dict(),
            "consolidated_results": c_res
        }
        Database._log('adaptation_started', stack_id, log_details)

    @staticmethod
    def log_adaptation_completed(stack_id, event_name, adaptation):
        """log a preformatted json entry for an adaptation completing"""
        log_details = {
            "event_name": event_name,
            "adaptation": adaptation.to_dict(),
        }
        Database._log('adaptation_completed', stack_id, log_details)

    @staticmethod
    def log_adaptation_failed(stack_id, event_name, adaptation):
        """log a preformatted json entry for an adaptation failure"""
        log_details = {
            "event_name": event_name,
            "adaptation": adaptation.to_dict(),
        }
        Database._log('adaptation_failed', stack_id, log_details)

    @staticmethod
    def load_config():
        """try and load the config from the database"""
        try:
            mongo_client = pymongo.MongoClient(
                cfg.database__host,
                int(cfg.database__port),
                serverSelectionTimeoutMS=5000
            )
            mongo_db = mongo_client[cfg.database__database_name]
            mongo_collection = mongo_db[cfg.database__collection_config]

            db_config = mongo_collection.find_one()

            if not db_config:
                LOGGER.warn(
                    "No config data found in database"
                )
            else:
                LOGGER.info("Parsing config from database")

                # Load available config from DB
                db_message_queues = db_config.get("message_queues", {})

                db_mq = db_message_queues.get("broker", {})
                cfg.mq__host = db_mq.get("host", cfg.mq__host)
                cfg.mq__port = db_mq.get("port", cfg.mq__port)
                cfg.mq__exchange = db_mq.get("exchange", cfg.mq__exchange)
                cfg.mq__inbound = db_mq.get("inbound", cfg.mq__inbound)
                cfg.mq__outbound = db_mq.get("outbound", cfg.mq__outbound)
                cfg.mq__username = db_mq.get("username", cfg.mq__username)
                cfg.mq__password = db_mq.get("password", cfg.mq__password)

                db_heat_res = db_message_queues.get("heat_resource", {})
                cfg.heat_resource_mq__host = db_heat_res.get(
                    "host", cfg.heat_resource_mq__host
                )
                cfg.heat_resource_mq__port = db_heat_res.get(
                    "port", cfg.heat_resource_mq__port
                )
                cfg.heat_resource_mq__username = db_heat_res.get(
                    "username", cfg.heat_resource_mq__username
                )
                cfg.heat_resource_mq__password = db_heat_res.get(
                    "password", cfg.heat_resource_mq__password
                )
                cfg.heat_resource_mq__exchange = db_heat_res.get(
                    "exchange", cfg.heat_resource_mq__exchange
                )
                cfg.heat_resource_mq__key = db_heat_res.get(
                    "key", cfg.heat_resource_mq__key
                )

                db_os_event = db_message_queues.get("openstack_event", {})
                cfg.openstack_event__host = db_os_event.get(
                    "host", cfg.openstack_event__host
                )
                cfg.openstack_event__port = db_os_event.get(
                    "port", cfg.openstack_event__port
                )
                cfg.openstack_event__username = db_os_event.get(
                    "username", cfg.openstack_event__username
                )
                cfg.openstack_event__password = db_os_event.get(
                    "password", cfg.openstack_event__password
                )
                cfg.openstack_event__exchange = db_os_event.get(
                    "exchange", cfg.openstack_event__exchange
                )
                cfg.openstack_event__key = db_os_event.get(
                    "key", cfg.openstack_event__key
                )

                db_app = db_message_queues.get("app_feedback", {})
                cfg.app_feedback__host = db_app.get(
                    "host", cfg.app_feedback__host
                )
                cfg.app_feedback__port = db_app.get(
                    "port", cfg.app_feedback__port
                )
                cfg.app_feedback__username = db_app.get(
                    "username", cfg.app_feedback__username
                )
                cfg.app_feedback__password = db_app.get(
                    "password", cfg.app_feedback__password
                )
                cfg.app_feedback__exchange = db_app.get(
                    "exchange", cfg.app_feedback__exchange
                )
                cfg.app_feedback__key = db_app.get(
                    "key", cfg.app_feedback__key
                )

                db_plugin = db_config.get("plugins", {})
                cfg.plugin_java = db_plugin.get("java", cfg.plugin_java)
                cfg.plugin_python = db_plugin.get("python", cfg.plugin_python)
                cfg.plugin_cpp = db_plugin.get("cpp", cfg.plugin_cpp)

                db_os = db_config.get("openstack", {})
                db_os_ks = db_os.get("keystone", {})
                cfg.openstack__auth_url = db_os_ks.get(
                    "endpoint", cfg.openstack__auth_url
                )
                cfg.openstack__username = db_os_ks.get(
                    "username", cfg.openstack__username
                )
                cfg.openstack__password = db_os_ks.get(
                    "password", cfg.openstack__password
                )
                cfg.openstack__tenant = db_os_ks.get(
                    "admin_tenant", cfg.openstack__tenant
                )

                db_objectmodel_res = db_message_queues.get(
					"objectmodel_endpoint", {}
				)
                cfg.objectmodel_endpoint__host = db_objectmodel_res.get(
					"host", cfg.objectmodel_endpoint__host
				)


            Database._post_config(mongo_client)

            mongo_client.close()
        except Exception, err:
            LOGGER.error(
                "Loading config from database failed: [{}]".format(err)
            )

    @staticmethod
    def _post_config(mongo_client):
        """
        try and delete old db config and then post
        current config to the database
        """
        try:
            LOGGER.info("Posting current config to database")
            mongo_db = mongo_client[cfg.database__database_name]
            mongo_db.drop_collection(cfg.database__collection_config)
            mongo_collection = mongo_db[cfg.database__collection_config]
            post_cfg = {
                "message_queues": {
                    "broker": {
                        "host": cfg.mq__host,
                        "port": cfg.mq__port,
                        "exchange": cfg.mq__exchange,
                        "inbound": cfg.mq__inbound,
                        "outbound": cfg.mq__outbound,
                        "username": cfg.mq__username,
                        "password": cfg.mq__password,
                    },
                    "heat_resource": {
                        "host": cfg.heat_resource_mq__host,
                        "port": cfg.heat_resource_mq__port,
                        "username": cfg.heat_resource_mq__username,
                        "password": cfg.heat_resource_mq__password,
                        "exchange": cfg.heat_resource_mq__exchange,
                        "key": cfg.heat_resource_mq__key,
                    },
                    "openstack_event": {
                        "host": cfg.openstack_event__host,
                        "port": cfg.openstack_event__port,
                        "username": cfg.openstack_event__username,
                        "password": cfg.openstack_event__password,
                        "exchange": cfg.openstack_event__exchange,
                        "key": cfg.openstack_event__key,
                    },
                    "app_feedback": {
                        "host": cfg.app_feedback__host,
                        "port": cfg.app_feedback__port,
                        "username": cfg.app_feedback__username,
                        "password": cfg.app_feedback__password,
                        "exchange": cfg.app_feedback__exchange,
                        "key": cfg.app_feedback__key,
                    },
                    "objectmodel_endpoint": {
                        "host": cfg.objectmodel_endpoint__host,
                    }
                },
                "plugins": {
                    "java": cfg.plugin_java,
                    "python": cfg.plugin_python,
                    "cpp": cfg.plugin_cpp,
                    "groupings": cfg.plugin__grouping,
                    "weightings": cfg.plugin__weightings,
                    "default_weightings": cfg.plugin__default_weighting,
                },
                "openstack": {
                    "keystone": {
                        "endpoint": cfg.openstack__auth_url,
                        "username": cfg.openstack__username,
                        "password": cfg.openstack__password,
                        "admin_tenant": cfg.openstack__tenant,
                    }
                },
            }
            mongo_collection.insert_one(post_cfg)
        except Exception, err:
            LOGGER.error(
                "Posting config to the database failed: [{}]".format(err)
            )

    @staticmethod
    def log_stack_created(stack_id):
        """log entry for stack creation"""
        log_details = {}
        Database._log('stack_created', stack_id, log_details)

    @staticmethod
    def get_current_stack_location(stack_id):
        """try and load the config from the database"""
        stack_pos = []
        try:
            mongo_client = pymongo.MongoClient(
                cfg.database__host,
                int(cfg.database__port),
                serverSelectionTimeoutMS=5000
            )
            mongo_db = mongo_client[cfg.database__database_name]
            mongo_collection = mongo_db[cfg.database__collection_stack]
            db_stack = mongo_collection.find_one()

            if db_stack:
                LOGGER.debug("Parsing config from database")
                stacks = db_stack.get("stacks", {})
                stack_pos = stacks.get(stack_id, [])
        except Exception:
            pass
        mongo_client.close()
        return stack_pos

    @staticmethod
    def update_stack_list(vm_list, delay=0, create=False, stack_id=None):
        """
        create or update the list of managed stacks
        """
        def update_stack_db_threaded(vm_list, delay, create, stack_id):
            mongo_client = pymongo.MongoClient(
                cfg.database__host,
                int(cfg.database__port),
                serverSelectionTimeoutMS=5000
            )
            mongo_db = mongo_client[cfg.database__database_name]
            mongo_collection = mongo_db[cfg.database__collection_stack]
            time.sleep(delay)
            vm_hype_mapping = openstack.OpenStackInterface().get_vm_hypervisor_mapping()

            #TODO: Refactor: repetition
            stacks = {}
            if create and stack_id:
                #create one
                db_stack = mongo_collection.find_one()
                if db_stack:
                    stacks = db_stack.get("stacks", {})
                    stacks[stack_id] = []
                    keystone_client = openstack.OpenStackClients.get_keystone_client()
                    heat_client = openstack.OpenStackClients.get_heat_client_for_stack(
                        keystone_client,
                        stack_id
                    )
                    vm_list = []
                    for resource in heat_client.resources.list(stack_id):
                        if resource.resource_type == 'OS::Nova::Server':
                            vm_list.append(resource.physical_resource_id)

                    for vmid in vm_list:
                        stacks[stack_id].append(
                            {
                                'vm_id': vmid,
                                'hypervisor_id': vm_hype_mapping.get(vmid, None)
                            })
            else:
                #complete update based on passed list of vms
                for stack_id in vm_list:
                    stacks[stack_id] = []
                    for vmid in vm_list[stack_id]:
                        stacks[stack_id].append(
                            {
                                'vm_id': vmid,
                                'hypervisor_id': vm_hype_mapping.get(vmid, None)
                            })
            post_stacks = {"stacks": stacks}
            mongo_db.drop_collection(cfg.database__collection_stack)
            mongo_collection.insert_one(post_stacks)

            if create:
                Database.log_stack_created(
                    stack_id=stack_id
                )


        thread = threading.Thread(
            target=update_stack_db_threaded,
            args=(copy.deepcopy(vm_list), delay, create, stack_id)
        )
        thread.start()
        return


