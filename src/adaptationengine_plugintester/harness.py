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
import multiprocessing
import optparse
import os
import sys
import threading
import uuid

import jpype

import adaptationengine_framework.adaptationaction as ae_action
import adaptationengine_framework.event as ae_event
import adaptationengine_framework.output as output

import plugins


def generate_initial_actions(actions_json):
    action_list = json.loads(actions_json)
    initial_actions = []

    for action in action_list:
        x = ae_action.AdaptationAction(action['type'])
        x.target = action['target']
        x.destination = action['destination']
        x.scale_value = action['scale_value']
        x.score = action['score']
        initial_actions.append(x)

    return initial_actions


def main():
    # setup
    usage = "usage: %prog <PLUGIN.jar> <CWEVENT.json> <ACTIONS.json> [options]"
    description = "CloudWave adaptation engine plugin test utility"
    version = "%prog 0.4"

    opt_parser = optparse.OptionParser(
        usage=usage, version=version, description=description
    )

    opt_parser.add_option(
        "-d",
        "--dependency-jar",
        action="append",
        type="string",
        help="Additional JARs required by plugin. One per flag.",
        dest="dependency_jars",
        default=[]
    )
    opt_parser.add_option(
        "--dependency-dir",
        action="store",
        type="string",
        help="For people with too many jars",
        dest="dependency_dir",
        default=None
    )
    opt_parser.add_option(
        "-j",
        "--java-flags",
        action="append",
        type="string",
        help="Additional flags to be passed to JVM. One per flag.",
        dest="env_vars",
        default=[]
    )
    opt_parser.add_option(
        "-m",
        "--metrics-json",
        action="store",
        type="string",
        help="JSON file to be used as return value for all get requests",
        dest="metrics_json",
        default="metrics.json"
    )
    opt_parser.add_option(
        "-c",
        "--compute-json",
        action="store",
        type="string",
        help="JSON file to be used as return value for all get requests",
        dest="compute_json",
        default="compute.json"
    )
    opt_parser.add_option(
        "-o",
        "--orchestration-json",
        action="store",
        type="string",
        help="JSON file to be used as return value for all get requests",
        dest="orchestration_json",
        default="orchestration.json"
    )
    opt_parser.add_option(
        "--plugin-timeout",
        action="store",
        type="int",
        help="Amount of seconds to wait for plugin to finish executing",
        dest="timeout",
        default=30
    )
    opt_parser.add_option(
        "--cloudwave-jar",
        action="store",
        type="string",
        help="Path to CloudWave.jar if not in local directory",
        dest="cloudwave_jar"
    )

    (options, args) = opt_parser.parse_args()

    # setup done
    manager = multiprocessing.Manager()
    plugin_results = manager.dict()
    jre_lock = threading.Lock()

    if len(args) == 3:
        if (
            not os.path.isfile(args[0]) and
            not os.path.isfile(args[1]) and
            not os.path.isfile(args[2])
        ):
            raise Exception('You should probably correct a file name')

        # event and actions
        cw_event = open(args[1]).read()
        initial_actions = generate_initial_actions(open(args[2]).read())

        # execute plugin
        if options.cloudwave_jar:
            cloudwave_jar = options.cloudwave_jar
        else:
            cloudwave_jar = 'CloudWave.jar'
        jre_classpath = cloudwave_jar + ":" + args[0]
        print jre_classpath
        for jar in options.dependency_jars:
            jre_classpath += ":{}".format(jar)

        if options.dependency_dir:
            even_more_jars = []
            print str(options.dependency_dir)
            for (dirpath, dirnames, filenames) in os.walk(
                options.dependency_dir
            ):
                for probable_jar in filenames:
                    (head, tail) = os.path.split(probable_jar)
                    if tail.endswith('.jar'):
                        even_more_jars.append(
                            os.path.join(options.dependency_dir, probable_jar)
                        )
            for jar in even_more_jars:
                jre_classpath += ":{}".format(jar)

        # output.OUTPUT.info("JRE Classpath", jre_classpath)

        # start JVM
        if not jpype.isJVMStarted():
            output.OUTPUT.info("JVM is not started. Starting...")
            try:
                flag_string = ""
                for x in options.env_vars:
                    flag_string = flag_string + " " + x
                output.OUTPUT.info(
                    "passed to java",
                    '-Djava.class.path={} {}'.format(
                        jre_classpath,
                        flag_string
                    )
                )
                flag_list = options.env_vars
                jpype.startJVM(
                    jpype.getDefaultJVMPath(),
                    '-Djava.class.path={}'.format(jre_classpath),
                    *flag_list
                )
                output.OUTPUT.info("JVM started")
            except Exception, err:
                output.OUTPUT.error(err)
        else:
            output.OUTPUT.warn("JVM is already started")

        # start plugin
        plugin_name = args[0]
        (head, tail) = os.path.split(plugin_name)
        if tail.endswith('.jar'):
            tail = tail[:-4]

        plugin = plugins.JavaPlugin(
            lock=jre_lock,
            name=tail,
            uuid=uuid.uuid4().hex,
            initial_actions=initial_actions,
            event=ae_event.Event(cw_event),
            results=plugin_results,
            metrics=options.metrics_json,
            compute=options.compute_json,
            orchestration=options.orchestration_json
        )

        try:
            plugin.start()
            output.OUTPUT.info("Started plugin", plugin._name)
        except Exception, err:
            output.OUTPUT.error(err)

        output.OUTPUT.info("Done")
        # wait for them to finish (for a while)
        plugin.join(options.timeout)
        output.OUTPUT.info("Done")
        sys.exit(0)
    else:
        opt_parser.error(
            "incorrect number of arguments. you need to specify a JAR file."
        )
        sys.exit(2)


def __main__():
    main()

if __name__ == "__main__":
    main()
