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
import imp
import json
import logging
import threading

import jpype
import requests

import adaptationengine_framework.adaptationaction as adaptationaction
import adaptationengine_framework.configuration as cfg
import adaptationengine_framework.openstack as openstack


LOGGER = logging.getLogger('syslog')


class OpenStackAPI:
    """
    Allow access for plugins to openstack apis
    without knowing where they are
    """

    def __init__(self, plugin_name):
        """Connect to keystone and get authentication for later queries"""
        self._plugin_name = plugin_name
        self._service_name = None
        self._endpoint = None
        self._headers = {}
        self._auth = None
        self._keystone = None

        LOGGER.debug(
            "[{}] Getting keystone auth token for REST API".format(
                self._plugin_name
            )
        )
        try:
            self._keystone = openstack.OpenStackClients.get_keystone_client()

            self._token = self._keystone.auth_ref['token']['id']
            LOGGER.debug("[{}] Got auth token".format(self._plugin_name))
            self._tenant_id = self._keystone.auth_ref['token']['tenant']['id']
            LOGGER.debug("[{}] Got tenant id".format(self._plugin_name))
            self._headers = {"X-Auth-Token": self._token}
        except Exception, err:
            LOGGER.error(
                "[{}] Could not get keystone client [{}]".format(
                    self._plugin_name, err
                )
            )
            self._keystone = None
            self._token = None
            self._auth = None
            self._headers = None

    def get(self, url, tenant_id=None):
        """Return the results (JSON) of a GET request to url"""
        use_headers = self._headers
        use_endpoint = self._endpoint

        if tenant_id:
            LOGGER.info(
                "[{}] Plugin requested new tenant id: {}".format(
                    self._plugin_name, tenant_id
                )
            )
            try:
                use_headers = None
                use_endpoint = None
                desired_tenant = self._keystone.tenants.get(tenant_id)
                tenant_keystone = (
                    openstack.OpenStackClients.get_keystone_client(
                        tenant_name=desired_tenant.name
                    )
                )
                use_endpoint = openstack.OpenStackClients._find_endpoint(
                    tenant_keystone, self._service_name
                )
                tenant_token = tenant_keystone.auth_ref['token']['id']
                LOGGER.info("[{}] Got auth token".format(self._plugin_name))
                use_headers = {"X-Auth-Token": tenant_token}
            except Exception, err:
                LOGGER.error(
                    "[{}] Could not get keystone client [{}]".format(
                        self._plugin_name, err
                    )
                )

        LOGGER.info(
            "[{}] Plugin requested API url: {}".format(
                self._plugin_name, url
            )
        )
        if use_endpoint is None:
            LOGGER.error(
                "[{}] No endpoint for this API call for this tenant".format(
                    self._plugin_name
                )
            )
            return None

        try:
            final_url = use_endpoint + url
            response = requests.get(
                final_url, auth=self._auth, headers=use_headers
            )
            LOGGER.info(
                "[{}] Final requested API url: {}".format(
                    self._plugin_name, final_url
                )
            )
            LOGGER.info(
                "[{}] API resonse: {}".format(self._plugin_name, response)
            )

            return response.text
        except Exception, err:
            LOGGER.error(
                "[{}] Exception while querying API".format(
                    self._plugin_name
                )
            )
            LOGGER.exception(err)
            return None


class Metrics(OpenStackAPI):
    """Provide access to OpenStack metric api (ceilometer)"""

    def __init__(self, plugin_name="NoName"):
        """Find endpoint url"""
        OpenStackAPI.__init__(self, plugin_name)
        self._service_name = 'ceilometer'
        self._endpoint = openstack.OpenStackClients._find_endpoint(
            self._keystone, self._service_name
        )


class Compute(OpenStackAPI):
    """Provide access to OpenStack compute api (nova)"""

    def __init__(self, plugin_name="NoName"):
        """Find endpoint url"""
        OpenStackAPI.__init__(self, plugin_name)
        self._service_name = 'nova'
        self._endpoint = openstack.OpenStackClients._find_endpoint(
            self._keystone, self._service_name
        )


class Orchestration(OpenStackAPI):
    """Provide access to OpenStack orchestration api (heat)"""

    def __init__(self, plugin_name="NoName"):
        """Find endpoint url"""
        OpenStackAPI.__init__(self, plugin_name)
        self._service_name = 'heat'
        self._endpoint = openstack.OpenStackClients._find_endpoint(
            self._keystone, self._service_name
        )


class Agreements(OpenStackAPI):
    """Provide access to SLA api"""

    def __init__(self, agreement_map, plugin_name="NoName"):
        """Skip OpenStackAPI init and do our own"""
        self._keystone = None
        self._plugin_name = plugin_name
        self._agreement_map = agreement_map
        self._endpoint = cfg.sla_agreements__endpoint
        self._auth = (
            cfg.sla_agreements__username,
            cfg.sla_agreements__password
        )
        self._headers = {'Accept': 'application/json'}

    def get_agreement_id(self, stack_id):
        """"""
        for k, v in self._agreement_map.iteritems():
            if v.get('stack_id') == stack_id:
                return k


class PluginLogger:
    """Allows plugins to log to normal adaptation engine log"""

    def __init__(self, plugin_name="NoName"):
        """Name the plugin that will be using the logger"""
        self._name = plugin_name

    def log(self, message):
        """Allow a plugin to log to the usual adaptation engine log file"""
        LOGGER.info("[{}] LOG: {}".format(self._name, message))


class Plugin(threading.Thread):
    """An adaptation engine plugin"""

    def __init__(self, file_path, name, uuid, weight):
        """Initialise and setup thread"""
        LOGGER.debug("[{}] Plugin init".format(name))

        self.plugin_name = name
        self.file_path = file_path
        self._uuid = uuid
        self.weight = weight

        self._event = None
        self._initial_actions = None
        self._agreement_map = None
        self._results = None

        LOGGER.debug("[{}] Plugin init complete".format(name))

        threading.Thread.__init__(self)

    def setup(self, event, initial_actions, results, agreement_map=None):
        """
        Additional setup used when plugin instance is created by generator
        """
        self._event = event
        self._initial_actions = initial_actions
        self._agreement_map = agreement_map
        self._results = results

    def _log_info(self, msg):
        """Plugin logs to log level INFO"""
        LOGGER.info("[{}] {}".format(self.plugin_name, msg))

    def _log_debug(self, msg):
        """Plugin logs to log level DEBUG"""
        LOGGER.info("[{}] {}".format(self.plugin_name, msg))

    def _log_error(self, msg):
        """Plugin logs to log level ERROR"""
        LOGGER.error("[{}] {}".format(self.plugin_name, msg))


class PythonPlugin(Plugin):
    """Python-specific sub-class of Plugin"""

    def __init__(self, file_path, info, name, uuid, weight):
        """Python-specific Plugin intialisation"""
        self._plugin = imp.load_module('{}.py'.format(name), *info)

        Plugin.__init__(self, file_path, name, uuid, weight)

        self._log_debug(
            "initialising plugin [{}] [{}]".format(file_path, info)
        )

    def run(self):
        """Execute a python plugin instance and collect results"""
        api_metrics = Metrics(self.plugin_name)
        api_compute = Compute(self.plugin_name)
        api_orchestration = Orchestration(self.plugin_name)
        api_sla = Agreements(self._agreement_map, self.plugin_name)
        plugin_logger = PluginLogger(self.plugin_name)

        self._log_debug("Executing Python plugin")
        self._results[self.plugin_name] = {
            'results': self._plugin.run(
                self._event,
                self._initial_actions,
                api_metrics,
                api_compute,
                api_orchestration,
                api_sla,
                plugin_logger
            ),
            'weight': self.weight
        }


class PythonPluginGenerator:
    """Generate a new instance of a specific python plugin"""

    def __init__(self, file_path, info, name, uuid, weight):
        """Initialise vars"""
        self._file_path = file_path
        self._info = info
        self._name = name
        self._uuid = uuid
        self._weight = weight

    def next(self):
        """Generate a new instance"""
        return PythonPlugin(
            self._file_path,
            self._info,
            self._name,
            self._uuid,
            self._weight
        )


class JavaPluginGenerator:
    """Generate a new instance of a specific java plugin"""

    def __init__(self, file_path, lock, name, uuid, weight):
        """Initialise vars"""
        self._file_path = file_path
        self._lock = lock
        self._name = name
        self._uuid = uuid
        self._weight = weight

    def next(self):
        """Generate a new instance"""
        return JavaPlugin(
            self._file_path,
            self._lock,
            self._name,
            self._uuid,
            self._weight
        )


class JavaPlugin(Plugin):
    """Java-specific sub-class of Plugin"""

    def __init__(self, file_path, lock, name, uuid, weight):
        """Java-specific Plugin intialisation"""
        self._lock = lock

        Plugin.__init__(self, file_path, name, uuid, weight)

    def run(self):
        """Execute a java plugin instance and collect results"""
        self._log_info("Acquiring JVM lock...")
        self._lock.acquire()
        self._log_info("JVM lock acquired")
        self._log_info("Attaching thread to JVM...")
        jpype.attachThreadToJVM()
        self._log_info("Thread attached to JVM")

        for action in self._initial_actions:
            self._log_info(
                "Initial action passed to plugin: {}".format(action)
            )

        self._log_info("Initialising OpenStackAPI interfaces")

        # interfaces
        try:
            metrics = Metrics(self.plugin_name)
            j_metrics = jpype.JProxy(
                "intel.adaptationengine.Metrics",
                inst=metrics
            )
        except Exception, err:
            LOGGER.error("Error initialising OpenStackAPI interface (Metrics)")
            LOGGER.exception(err)

        try:
            compute = Compute(self.plugin_name)
            j_compute = jpype.JProxy(
                "intel.adaptationengine.Compute",
                inst=compute
            )
        except Exception, err:
            LOGGER.error("Error initialising OpenStackAPI interface (Compute)")
            LOGGER.exception(err)

        try:
            orchestration = Orchestration(self.plugin_name)
            j_orchestration = jpype.JProxy(
                "intel.adaptationengine.Orchestration",
                inst=orchestration
            )
        except Exception, err:
            LOGGER.error(
                "Error initialising OpenStackAPI interface (Orchestration)"
            )
            LOGGER.exception(err)

        # event
        self._log_info("Initialising Event interfaces")
        JEvent = jpype.JClass(
            "intel.adaptationengine.Event"
        )

        # log
        self._log_info("Initialising Logging interfaces")
        the_logging = PluginLogger(self.plugin_name)
        j_logger = jpype.JProxy(
            "intel.adaptationengine.Logger",
            inst=the_logging
        )

        self._log_info(
            'Event.data: ' + json.dumps(self._event.data)
        )

        self._log_info("Initialising Event object")
        j_cwevent = JEvent(
            self._event.user_id,
            self._event.tenant_id,
            self._event.stack_id,
            self._event.instance_id,
            self._event.name,
            str(self._event.value),  # mite be a float, int, or string
            json.dumps(self._event.data)  # is a list of dictionaries
        )

        # translate actions in java objects
        self._log_info("Translating initial AdaptationActions to java")
        try:
            JAdaptationType = jpype.JClass(
                "intel.adaptationengine.AdaptationType"
            )
            JAdaptationAction = jpype.JClass(
                "intel.adaptationengine.AdaptationAction"
            )
            j_action_list = []
            for action in self._initial_actions:
                j_action_list.append(
                    JAdaptationAction(
                        JAdaptationType.values()[action.adaptation_type],
                        action.target,
                        action.destination,
                        action.scale_value,
                        action.score
                    )
                )

            j_action_array = jpype.JArray(JAdaptationAction)(j_action_list)
        except Exception, err:
            LOGGER.error('Problem translating actions to java')
            LOGGER.exception(err)

        # execute
        self._log_info("Executing plugin...")
        plugin_class_name = "intel.adaptationengine.plugins.{}".format(
            self.plugin_name
        )
        j_ae_plugin = jpype.JClass(plugin_class_name)
        j_ae = j_ae_plugin()

        self._log_info("Checking plugin response")

        response_actions = None

        try:
            response_actions = j_ae.run(
                j_cwevent,
                j_action_array,
                j_metrics,
                j_compute,
                j_orchestration,
                j_logger
            )
        except Exception, err:
            LOGGER.error("Problem with plugin response: {}".format(err))
            LOGGER.exception(err)

        self._log_info('response_actions: {}'.format(response_actions))

        # translate actions back into python AdaptationActions
        self._log_info(
            "translating actions back into python AdaptationActions"
        )

        output_actions = []
        try:
            if response_actions:
                for j_action in response_actions:
                    if j_action:
                        j_type = j_action.getType()
                        p_action = adaptationaction.AdaptationAction(
                            j_type.ordinal()
                        )
                        p_action.target = j_action.getTarget()
                        p_action.destination = j_action.getDestination()
                        p_action.scale_value = j_action.getScaleValue()
                        p_action.score = j_action.getScore()
                        output_actions.append(p_action)
            else:
                raise Exception('No actions to translate')
        except Exception, err:
            LOGGER.error("Problem with python translation: {}".format(err))
            LOGGER.exception(err)
            LOGGER.warn(
                "Returning original initial actions becuase of plugin error"
            )
            self._results[self.plugin_name] = self._initial_actions
        else:

            for action in output_actions:
                self._log_info(
                    "Result action from plugin: {}".format(action)
                )

            self._results[self.plugin_name] = output_actions
            self._results[self.plugin_name] = {
                'results': output_actions,
                'weight': self.weight
            }

        self._log_info("Detaching thread from JVM...")
        jpype.detachThreadFromJVM()
        self._log_info("Thread detached from JVM")

        self._log_info("Releasing JVM lock...")
        self._lock.release()
        self._log_info("JVM lock released")
