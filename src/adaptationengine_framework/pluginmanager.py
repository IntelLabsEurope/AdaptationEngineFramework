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
import logging
import os
import threading
import uuid

import jpype

import adaptationengine_framework.configuration as cfg
import adaptationengine_framework.plugins as plugins

LOGGER = logging.getLogger('syslog')


class PluginManager:
    """
    Handle information about plugins and their configuration, and manage JVM
    """

    def __init__(self):
        """
        Load configuration, setup Java Virtual Machine, find plugins, started
        JVM if we found Java plugins
        """
        # Load CFG
        self._plugin__grouping = cfg.plugin__grouping
        self._plugin__default_weighting = cfg.plugin__default_weighting

        # Build list of weightings
        self._plugin__weightings = {
            p.get('name'): p.get('weight') for p in cfg.plugin__weightings
        }

        # Java setup
        self._plugins = {}
        self._jvm_lock = threading.Lock()
        self.jvm_classpath = "{}/AdaptationEngine.jar".format(cfg.plugin_java)
        self.jvm_needed = self._scan_for_java_plugins()

        if self.jvm_needed:
            self._start_jvm()

        # Python setup
        self._scan_for_python_plugins()

    def _start_jvm(self):
        """
        Start JVM with necessary flags and classpath including all
        discovered plugins, if not already started
        """
        try:
            if not jpype.isJVMStarted() and self.jvm_needed:
                LOGGER.info("JVM is not started. Starting...")
                flag_list = [
                    '-Djava.class.path={}'.format(self.jvm_classpath)
                ]
                jpype.startJVM(
                    jpype.getDefaultJVMPath(),
                    *flag_list
                )
                LOGGER.info("JVM started")
            else:
                LOGGER.warn("JVM is already started or not needed")
        except OSError, err:
            raise Exception("Could not find/start JVM! [{}]".format(err))

    def get(self, plugin_name_list):
        """
        Get a new instance of all the plugins we have
        """
        LOGGER.info('Getting plugins {}'.format(plugin_name_list))
        plugin_instances = []
        for name in plugin_name_list:
            generator = self._plugins.get(name)
            if generator:
                plugin_instances.append(generator.next())
            else:
                LOGGER.error("could not get plugin {}".format(name))
        LOGGER.info('Returning plugins {}'.format(plugin_instances))
        return plugin_instances

    def _scan_for_python_plugins(self):
        """Find and store python plugins"""
        plugin_dir = cfg.plugin_python
        try:
            for dir_name in os.listdir(plugin_dir):
                full_dir_path = os.path.join(plugin_dir, dir_name)
                if os.path.isdir(full_dir_path):
                    # get a full path to the plugin file
                    full_module_path = os.path.join(
                        full_dir_path, '{}.py'.format(dir_name)
                    )
                    plugin_uuid = uuid.uuid4().hex
                    if os.path.isfile(full_module_path):
                        self._plugins[dir_name] = (
                            plugins.PythonPluginGenerator(
                                file_path=full_module_path,
                                info=imp.find_module(
                                    '{}'.format(dir_name), [full_dir_path]
                                ),
                                name=dir_name,
                                uuid=plugin_uuid,
                                weight=(
                                    self._plugin__weightings.get(
                                        dir_name,
                                        self._plugin__default_weighting
                                    )
                                )
                            )
                        )
                        LOGGER.info(
                            "Using a plugin called [{}] in "
                            "file [{}] with uuid [{}]".format(
                                dir_name,
                                full_module_path,
                                plugin_uuid,
                                # TODO: will need to tie this to
                                # weightings later
                            )
                        )
                    else:
                        raise OSError(
                            "Could not add a plugin called [{}] "
                            "in file [{}]. Doesn't exist!".format(
                                dir_name,
                                full_module_path,
                            )
                        )
        except OSError:
            LOGGER.warn(
                "Specified Python plugin directory doesn't "
                "seem to exist!"
                " [{}]".format(plugin_dir)
            )

    def _scan_for_java_plugins(self):
        """
        Find plugins in the configured Java plugin directory and add them
        to the list of plugins, and the JVM classpath. Set JVM as not needed if
        no plugins found.
        """
        plugin_dir = cfg.plugin_java
        jvm_needed = False
        try:
            for dir_name in os.listdir(plugin_dir):
                # list everything in plugin_dir
                full_dir_path = os.path.join(plugin_dir, dir_name)
                # check if directory
                if os.path.isdir(full_dir_path):
                    # get a full path to the main jar
                    full_jar_path = os.path.join(
                        full_dir_path, '{0}.jar'.format(dir_name)
                    )
                    plugin_uuid = uuid.uuid4().hex
                    if os.path.isfile(full_jar_path):
                        full_all_jars_path = full_jar_path
                        for item in os.listdir(full_dir_path):
                            if (
                                    item.endswith(".jar") and
                                    item != '{0}.jar'.format(dir_name)
                            ):
                                full_all_jars_path = (
                                    full_all_jars_path + ":" + os.path.join(
                                        full_dir_path, item
                                    )
                                )
                        self._plugins[dir_name] = (
                            plugins.JavaPluginGenerator(
                                file_path=full_jar_path,
                                lock=self._jvm_lock,
                                name=dir_name,
                                uuid=plugin_uuid,
                                weight=(
                                    self._plugin__weightings.get(
                                        dir_name,
                                        self._plugin__default_weighting
                                    )
                                )
                            )
                        )
                        jvm_needed = True
                        self.jvm_classpath += ":{}".format(full_all_jars_path)
                        LOGGER.info(
                            "Using a plugin called [{}] in "
                            "file [{}] with uuid [{}]".format(
                                dir_name,
                                full_jar_path,
                                plugin_uuid,
                                # TODO: will need to tie this to
                                # weightings later
                            )
                        )
                    else:
                        raise OSError(
                            "Could not add a plugin called [{}] "
                            "in file [{}]. Doesn't exist!".format(
                                dir_name,
                                full_jar_path,
                            )
                        )
                else:
                    LOGGER.warn(
                        "{} is not a directory!".format(full_dir_path)
                    )

            LOGGER.info("JVM classpath string [{}]".format(self.jvm_classpath))
        except OSError:
            LOGGER.warn(
                "Specified Java plugin directory doesn't "
                "seem to exist! Setting JVM to not-needed."
                " [{}]".format(plugin_dir)
            )
            return False
        else:
            if jvm_needed:
                return True
            else:
                return False
