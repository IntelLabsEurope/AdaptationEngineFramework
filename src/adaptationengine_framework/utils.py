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
import sys
import yaml

from pkg_resources import resource_string

import configuration as cfg
import database


def generic_logging(logger, handler, format_string, level):
    """Create a logger for this handler and return it"""
    loggo = logging.getLogger(logger)
    loggo.setLevel(level)
    h = handler
    h.setLevel(level)
    if isinstance(format_string, tuple):
        formatter = logging.Formatter(format_string[0], format_string[1])
    else:
        formatter = logging.Formatter(format_string)
    h.setFormatter(formatter)
    loggo.addHandler(h)
    return loggo


def syslog_logging(name='adaptation-engine', level=logging.DEBUG):
    """Set up logging to syslog and return a logger object"""
    handler = logging.handlers.SysLogHandler(address='/dev/log')
    # handler = logging.handlers.TimedRotatingFileHandler(
    #    filename='/tmp/adaptation_engine.log', when='midnight', backupCount=7
    # )
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
            cfg_string = resource_string(__name__, 'default-config.yaml')
            configfile = 'default'
        else:
            try:
                with open(configfile, 'r') as the_file:
                    cfg_string = the_file.read()
            except OSError, err:
                raise OSError("Could not open config file")

        yaml_config = yaml.load(cfg_string)

        cfg.database__host = yaml_config['adaptation_engine']['database']['host']
        cfg.database__port = yaml_config['adaptation_engine']['database']['port']
        cfg.database__database_name = yaml_config['adaptation_engine']['database']['database']
        cfg.database__collection_config = yaml_config['adaptation_engine']['database']['collections']['config']
        cfg.database__collection_log = yaml_config['adaptation_engine']['database']['collections']['log']

        cfg.mq__host = yaml_config['adaptation_engine']['mq_broker']['host']
        cfg.mq__port = yaml_config['adaptation_engine']['mq_broker']['port']
        cfg.mq__exchange = yaml_config['adaptation_engine']['mq_broker']['exchange']
        cfg.mq__inbound = yaml_config['adaptation_engine']['mq_broker']['routing_key']['inbound']
        cfg.mq__outbound = yaml_config['adaptation_engine']['mq_broker']['routing_key']['outbound']
        cfg.mq__username = yaml_config['adaptation_engine']['mq_broker']['username']
        cfg.mq__password = yaml_config['adaptation_engine']['mq_broker']['password']

        cfg.plugin_java = yaml_config['adaptation_engine']['plugins']['java']
        cfg.plugin_python = yaml_config['adaptation_engine']['plugins']['python']
        cfg.plugin_cpp = yaml_config['adaptation_engine']['plugins']['cpp']
        cfg.plugin__grouping = yaml_config['adaptation_engine']['plugins'].get('grouping', [])
        cfg.plugin__default_weighting = yaml_config['adaptation_engine']['plugins'].get('default_weighting', 1)
        cfg.plugin__weightings = yaml_config['adaptation_engine']['plugins'].get('weightings', [])

        cfg.heat_resource_mq__host = yaml_config['adaptation_engine']['heat_resource']['host']
        cfg.heat_resource_mq__port = yaml_config['adaptation_engine']['heat_resource']['port']
        cfg.heat_resource_mq__username = yaml_config['adaptation_engine']['heat_resource']['username']
        cfg.heat_resource_mq__password = yaml_config['adaptation_engine']['heat_resource']['password']
        cfg.heat_resource_mq__exchange = yaml_config['adaptation_engine']['heat_resource']['exchange']
        cfg.heat_resource_mq__key = yaml_config['adaptation_engine']['heat_resource']['key']

        cfg.openstack__auth_url = yaml_config['adaptation_engine']['openstack_polling']['auth_url']
        cfg.openstack__username = yaml_config['adaptation_engine']['openstack_polling']['username']
        cfg.openstack__password = yaml_config['adaptation_engine']['openstack_polling']['password']
        cfg.openstack__tenant = yaml_config['adaptation_engine']['openstack_polling']['tenant']

        cfg.openstack_event__host = yaml_config['adaptation_engine']['event']['host']
        cfg.openstack_event__port = yaml_config['adaptation_engine']['event']['port']
        cfg.openstack_event__username = yaml_config['adaptation_engine']['event']['username']
        cfg.openstack_event__password = yaml_config['adaptation_engine']['event']['password']
        cfg.openstack_event__exchange = yaml_config['adaptation_engine']['event']['exchange']
        cfg.openstack_event__key = yaml_config['adaptation_engine']['event']['key']

        cfg.app_feedback__host = yaml_config['adaptation_engine']['app_feedback']['host']
        cfg.app_feedback__port = yaml_config['adaptation_engine']['app_feedback']['port']
        cfg.app_feedback__username = yaml_config['adaptation_engine']['app_feedback']['username']
        cfg.app_feedback__password = yaml_config['adaptation_engine']['app_feedback']['password']
        cfg.app_feedback__exchange = yaml_config['adaptation_engine']['app_feedback']['exchange']
        cfg.app_feedback__key = yaml_config['adaptation_engine']['app_feedback']['key']

    except Exception, err:
        print "Exception loading config file [{0}]: ({1})".format(
            configfile,
            err
        )
        sys.exit(1)

    if clear_db_config:
        database.Database.delete_db_cfg()

    database.Database.load_config()
