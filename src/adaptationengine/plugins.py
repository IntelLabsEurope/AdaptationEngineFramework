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
import requests
import threading

import jpype

import adaptationaction
import openstack


LOGGER = logging.getLogger('syslog')


class OpenStackAPI:
    """
    Allow access for plugins to openstack apis
    without knowing where they are
    """

    def __init__(self):
        """Connect to keystone and get authentication for later queries"""
        LOGGER.info("Getting keystone auth token for REST API")
        self._keystone = openstack.OpenStackClients.get_keystone_client()

        self._token = self._keystone.auth_ref['token']['id']
        LOGGER.info("Got auth token")
        self._tenant_id = self._keystone.auth_ref['token']['tenant']['id']
        LOGGER.info("Got tenant id")
        self._headers = {"X-Auth-Token": self._token}

    def _find_endpoint(self, keystone_client, service):
        """Return the endpoint url for a named openstack service"""
        LOGGER.info("Looking for endpoint for service [{}]".format(service))
        endpoint = None
        service_id = None
        for y in keystone_client.services.list():
            if y.name == service:
                service_id = y.id

        for z in keystone_client.endpoints.list():
            if z.service_id == service_id:
                endpoint = z.internalurl

        LOGGER.info("Apparent endpoint url [{}]".format(endpoint))
        # openstack undocumented version difference #37891
        try:
            endpoint = endpoint.replace(
                '%(tenant_id)s',
                keystone_client.project_id
            )
            endpoint = endpoint.replace(
                '$(tenant_id)s',
                keystone_client.project_id
            )
        except AttributeError:
            LOGGER.error(
                'No endpoint found for service [{}] in Keystone'.format(
                    service
                )
            )

        LOGGER.info("Endpoint url with tenant id [{}]".format(endpoint))

        return endpoint

    def get(self, url):
        """Return the results (JSON) of a GET request to url"""
        LOGGER.info("Plugin requested openstack api url: {}".format(url))
        if not self._endpoint:
            LOGGER.error("No endpoint for this API call")
            return None
        try:
            final_url = self._endpoint + url
            r = requests.get(final_url, headers=self._headers)
            LOGGER.info("API resonse: {}".format(r))
            LOGGER.info("Response body: {}".format(r.text))
            return r.text
        except Exception, err:
            LOGGER.error("Exception while querying openstack api")
            LOGGER.exception(err)
            return None


class Metrics(OpenStackAPI):
    """Provide access to OpenStack metric api (ceilometer)"""

    def __init__(self):
        """Find endpoint url"""
        OpenStackAPI.__init__(self)
        self._endpoint = self._find_endpoint(self._keystone, 'ceilometer')
        LOGGER.info("Found endpoint {}".format(self._endpoint))


class Compute(OpenStackAPI):
    """Provide access to OpenStack compute api (nova)"""

    def __init__(self):
        """Find endpoint url"""
        OpenStackAPI.__init__(self)
        self._endpoint = self._find_endpoint(self._keystone, 'nova')
        LOGGER.info("Found endpoint {}".format(self._endpoint))


class Orchestration(OpenStackAPI):
    """Provide access to OpenStack orchestration api (heat)"""

    def __init__(self):
        """Find endpoint url"""
        OpenStackAPI.__init__(self)
        self._endpoint = self._find_endpoint(self._keystone, 'heat')
        LOGGER.info("Found endpoint {}".format(self._endpoint))


class JLogger:

    def __init__(self):
        pass

    def log(self, message):
        """Allow a plugin to log to the usual adaptation engine log file"""
        LOGGER.info("JAVA LOG: {}".format(message))


class Plugin(threading.Thread):

    def __init__(self, file_path, name, uuid, weight):
        LOGGER.info("[{}] Plugin init".format(name))

        self.plugin_name = name
        self.file_path = file_path
        self._uuid = uuid
        self.weight = weight

        LOGGER.info("[{}] Plugin init complete".format(name))

        threading.Thread.__init__(self)

    def _log_info(self, msg):
        LOGGER.info("[{}] {}".format(self.plugin_name, msg))

    def _log_error(self, msg):
        LOGGER.error("[{}] {}".format(self.plugin_name, msg))


class PyPlugin(Plugin):

    def run(self):
        pass


class JavaPluginGenerator:

    def __init__(self, file_path, lock, name, uuid, weight):
        self._file_path = file_path
        self._lock = lock
        self._name = name
        self._uuid = uuid
        self._weight = weight

    def next(self):
        return JavaPlugin(
            self._file_path,
            self._lock,
            self._name,
            self._uuid,
            self._weight
        )


class JavaPlugin(Plugin):

    def __init__(self, file_path, lock, name, uuid, weight):
        self._lock = lock
        self._event = None
        self._initial_actions = None
        self._results = None

        Plugin.__init__(self, file_path, name, uuid, weight)

    def setup(self, event, initial_actions, results):
        self._event = event
        self._initial_actions = initial_actions
        self._results = results

    def run(self):
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
            metrics = Metrics()
            j_metrics = jpype.JProxy(
                "intel.adaptationengine.Metrics",
                inst=metrics
            )
        except Exception, err:
            LOGGER.err("Error initialising OpenStackAPI interface (Metrics)")
            LOGGER.exception(err)

        try:
            compute = Compute()
            j_compute = jpype.JProxy(
                "intel.adaptationengine.Compute",
                inst=compute
            )
        except Exception, err:
            LOGGER.err("Error initialising OpenStackAPI interface (Compute)")
            LOGGER.exception(err)

        try:
            orchestration = Orchestration()
            j_orchestration = jpype.JProxy(
                "intel.adaptationengine.Orchestration",
                inst=orchestration
            )
        except Exception, err:
            LOGGER.err(
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
        the_logging = JLogger()
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

        self._log_info("Detaching thread from JVM...")
        jpype.detachThreadFromJVM()
        self._log_info("Thread detached from JVM")

        self._log_info("Releasing JVM lock...")
        self._lock.release()
        self._log_info("JVM lock released")
