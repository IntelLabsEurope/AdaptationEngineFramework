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

import threading
import json
import os

import jpype

import adaptationengine_framework.adaptationaction as ae_action
import adaptationengine_framework.output as output


class OpenStackAPI:

    def __init__(self, filename):
        if os.path.isfile(filename):
            self._text = open(filename).read()
            output.OUTPUT.info('Read API file [{}]'.format(filename))
        else:
            output.OUTPUT.error('Cannot find API file [{}]'.format(filename))
            self._text = None

    def get(self, url):
        output.OUTPUT.info('GET was called by plugin for url', url)
        output.OUTPUT.info('Returning text', str(self._text))
        return self._text


class Metrics(OpenStackAPI):

    def __init__(self, filename):
        OpenStackAPI.__init__(self, filename='metrics.json')


class Compute(OpenStackAPI):

    def __init__(self, filename):
        OpenStackAPI.__init__(self, filename='nova.json')


class Orchestration(OpenStackAPI):

    def __init__(self, filename):
        OpenStackAPI.__init__(self, filename='orchestration.json')


class JLogger:

    def __init__(self):
        pass

    def log(self, message):
        output.OUTPUT.info(message)


class Plugin(threading.Thread):

    def __init__(self, name, uuid, initial_actions, event, results, metrics, compute, orchestration):
        output.OUTPUT.info("Plugin", name)

        self._name = name
        self._uuid = uuid
        self._initial_actions = initial_actions
        self._event = event
        self._results = results

        self._json_metrics = metrics
        self._json_compute = compute
        self._json_orchestration = orchestration

        threading.Thread.__init__(self)


class JavaPlugin(Plugin):

    def __init__(self, lock, name, uuid, initial_actions, event, results, metrics, compute, orchestration):
        self._lock = lock

        Plugin.__init__(self, name, uuid, initial_actions, event, results, metrics, compute, orchestration)

    def run(self):
        output.OUTPUT.info("Acquiring JVM lock...")
        self._lock.acquire()
        output.OUTPUT.info("JVM lock acquired")
        output.OUTPUT.info("Attaching thread to JVM...")
        jpype.attachThreadToJVM()
        output.OUTPUT.info("Thread attached to JVM")

        # interfaces
        metrics = Metrics(self._json_metrics)
        j_metrics = jpype.JProxy("cloudwave.adaptationengine.Metrics", inst=metrics)

        compute = Compute(self._json_compute)
        j_compute = jpype.JProxy("cloudwave.adaptationengine.Compute", inst=compute)

        orchestration = Orchestration(self._json_orchestration)
        j_orchestration = jpype.JProxy("cloudwave.adaptationengine.Orchestration", inst=orchestration)

        # event
        JCloudWaveEvent = jpype.JClass("cloudwave.adaptationengine.CloudWaveEvent")

        # log
        the_logging = JLogger()
        j_logger = jpype.JProxy("cloudwave.adaptationengine.Logger", inst=the_logging)


        #output.OUTPUT.info('CloudWaveEvent.data' + json.dumps(self._event.data))

        j_cwevent = JCloudWaveEvent(
            self._event.user_id,
            self._event.tenant_id,
            self._event.stack_id,
            self._event.instance_id,
            self._event.name,
            str(self._event.value), # mite be a float, int, or string
            json.dumps(self._event.data) # is a list of dictionaries
        )

        # translate actions in java objects
        JAdaptationType = jpype.JClass("cloudwave.adaptationengine.AdaptationType")
        JAdaptationAction = jpype.JClass("cloudwave.adaptationengine.AdaptationAction")
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

        # execute
        plugin_class_name = "cloudwave.adaptationengine.plugins.{}".format(self._name)
        j_ae_plugin = jpype.JClass(plugin_class_name)
        j_ae = j_ae_plugin()

        output.OUTPUT.info("Executing plugin")

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
            output.OUTPUT.info("Plugin returned responses", len(response_actions))
        except Exception, err:
            output.OUTPUT.error("Problem with plugin response: {}".format(err))
            output.OUTPUT.error(err)

        # translate actions back into python AdaptationActions
        output.OUTPUT.info("Translating response actions into python AdaptationActions")

        try:
            output_actions = []
            if response_actions:
                for i, j_action in enumerate(response_actions):
                    j_type = j_action.getType()
                    p_action = ae_action.AdaptationAction(j_type.ordinal())
                    p_action.target = j_action.getTarget()
                    p_action.destination = j_action.getDestination()
                    p_action.scale_value = j_action.getScaleValue()
                    p_action.score = j_action.getScore()
                    output.OUTPUT.info("[Action {} type]".format(i), p_action)
                    output.OUTPUT.info("[Action {} target]".format(i), (p_action.target or 'None'))
                    output.OUTPUT.info("[Action {} destination]".format(i), (p_action.destination or 'None'))
                    output.OUTPUT.info("[Action {} scale_value]".format(i), (p_action.scale_value or 'None'))
                    output.OUTPUT.info("[Action {} score]".format(i), (p_action.score or 'None'))
                    output_actions.append(p_action)
            else:
                raise Exception('No actions to translate')
        except Exception, err:
            output.OUTPUT.error("Problem with python translation: {}".format(err))
            output.OUTPUT.error(err)

        self._results[self._uuid] = output_actions

        output.OUTPUT.info("Detaching thread from JVM...")
        jpype.detachThreadFromJVM()
        output.OUTPUT.info("Thread detached from JVM")

        output.OUTPUT.info("Releasing JVM lock...")
        self._lock.release()
        output.OUTPUT.info("JVM lock released")
