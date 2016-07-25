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
import logging.config
import pkg_resources
import sys
import yaml

import adaptationengine_framework.configuration as cfg
import adaptationengine_framework.database as database


def generic_logging(logger, handler, format_string, level):
    """Create a logger for this handler and return it"""
    loggo = logging.getLogger(logger)
    loggo.setLevel(level)
    our_handler = handler
    our_handler.setLevel(level)
    if isinstance(format_string, tuple):
        formatter = logging.Formatter(format_string[0], format_string[1])
    else:
        formatter = logging.Formatter(format_string)
    our_handler.setFormatter(formatter)
    loggo.addHandler(our_handler)
    return loggo


def syslog_logging(name='adaptationengine', level=logging.DEBUG):
    """Set up logging to syslog and return a logger object"""
    handler = logging.handlers.SysLogHandler(address='/dev/log')
    return generic_logging(
        'syslog',
        handler,
        name + "(%(levelname)s) [%(process)d/%(thread)d]: "
        "(%(module)s.%(funcName)s) %(message)s",
        level
    )


def health_logging():
    """
    Set up logging to stdout in the healthcheck format
    and return a logger object
    """
    handler = logging.StreamHandler(sys.stdout)
    return generic_logging(
        'stdout',
        handler,
        ('%(asctime)s %(message)s', '%Y/%m/%d %H:%M:%S'),
        logging.INFO
    )


def std_logging():
    """Set up logging to stdout and return a logger object"""
    handler = logging.StreamHandler(sys.stdout)
    return generic_logging('stdout', handler, '%(message)s', logging.INFO)


def load_config(configfile, clear_db_config):
    """
    Load a YAML config file and parse it into the
    configuration module for global access
    """
    yaml_config = None

    try:
        if configfile is None:
            cfg_string = pkg_resources.resource_string(
                __name__, 'default-config.yaml'
            )
            configfile = 'default'
        else:
            try:
                with open(configfile, 'r') as the_file:
                    cfg_string = the_file.read()
            except OSError, err:
                raise OSError("Could not open config file")

        yaml_config = yaml.load(cfg_string)

        # webbo
        yml_webbo = yaml_config['adaptation_engine'].get('webbo', {})
        cfg.webbo__port = yml_webbo.get('port', 8888)

        # database config
        yml_database = yaml_config['adaptation_engine']['database']
        cfg.database__host = yml_database['host']
        cfg.database__port = yml_database['port']
        cfg.database__database_name = yml_database['database']
        cfg.database__collection_config = yml_database['collections']['config']
        cfg.database__collection_log = yml_database['collections']['log']
        cfg.database__collection_stack = yml_database['collections']['stack']

        # message queue config
        yml_mq = yaml_config['adaptation_engine']['mq_broker']
        cfg.mq__host = yml_mq['host']
        cfg.mq__port = yml_mq['port']
        cfg.mq__exchange = yml_mq['exchange']
        cfg.mq__inbound = yml_mq['routing_key']['inbound']
        cfg.mq__outbound = yml_mq['routing_key']['outbound']
        cfg.mq__username = yml_mq['username']
        cfg.mq__password = yml_mq['password']

        # plugin config
        yml_plugin = yaml_config['adaptation_engine']['plugins']
        cfg.plugin__timeout = yml_plugin.get('timeout', 30)
        cfg.plugin_java = yml_plugin['java']
        cfg.plugin_python = yml_plugin['python']
        cfg.plugin_cpp = yml_plugin['cpp']
        cfg.plugin__grouping = yml_plugin.get('grouping', [])
        cfg.plugin__default_weighting = yml_plugin.get('default_weighting', 1)
        cfg.plugin__weightings = yml_plugin.get('weightings', [])

        # heat resource config
        yml_heat = yaml_config['adaptation_engine']['heat_resource']
        cfg.heat_resource_mq__host = yml_heat['host']
        cfg.heat_resource_mq__port = yml_heat['port']
        cfg.heat_resource_mq__username = yml_heat['username']
        cfg.heat_resource_mq__password = yml_heat['password']
        cfg.heat_resource_mq__exchange = yml_heat['exchange']
        cfg.heat_resource_mq__key = yml_heat['key']

        # openstack message queue config
        yml_opstk = yaml_config['adaptation_engine']['openstack_polling']
        cfg.openstack__auth_url = yml_opstk['auth_url']
        cfg.openstack__username = yml_opstk['username']
        cfg.openstack__password = yml_opstk['password']
        cfg.openstack__tenant = yml_opstk['tenant']

        # event message queue config
        yml_event = yaml_config['adaptation_engine']['event']
        cfg.openstack_event__host = yml_event['host']
        cfg.openstack_event__port = yml_event['port']
        cfg.openstack_event__username = yml_event['username']
        cfg.openstack_event__password = yml_event['password']
        cfg.openstack_event__exchange = yml_event['exchange']
        cfg.openstack_event__key = yml_event['key']

        # feedback message queue config
        yml_feedbk = yaml_config['adaptation_engine']['app_feedback']
        cfg.app_feedback__host = yml_feedbk['host']
        cfg.app_feedback__port = yml_feedbk['port']
        cfg.app_feedback__username = yml_feedbk['username']
        cfg.app_feedback__password = yml_feedbk['password']
        cfg.app_feedback__exchange = yml_feedbk['exchange']
        cfg.app_feedback__key = yml_feedbk['key']

        cfg.objectmodel_endpoint__host = yaml_config['adaptation_engine']['objectmodel_endpoint']['host']

        # sla agreements config
        yml_sla = yaml_config['adaptation_engine']['sla_agreements']
        cfg.sla_agreements__endpoint = yml_sla['endpoint']
        cfg.sla_agreements__username = yml_sla['username']
        cfg.sla_agreements__password = yml_sla['password']

    except (KeyError, OSError), err:
        print "Exception loading config file [{0}]: ({1})".format(
            configfile,
            err
        )
        sys.exit(1)

    if clear_db_config:
        database.Database.delete_db_cfg()

    database.Database.load_config()
