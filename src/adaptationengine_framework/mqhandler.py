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
import bz2
import datetime
import json
import logging
import pickle
import uuid

import pika

import adaptationengine_framework.configuration as cfg
import adaptationengine_framework.rabbitmq as rabbitmq


LOGGER = logging.getLogger('syslog')
HEALTHLOGGER = logging.getLogger('stdout')


class MQHandler:
    """
    Manage message queue connections and publishing
    """

    def __init__(self, msg_callback=None):
        """Basic setup, set callback function if supplied"""
        self._msg_callback = msg_callback

        self._mq_consumer = None
        self._adaptation_publisher = None
        self._os_publisher = None
        self._app_publisher = None
        self._heat_publisher = None

    def setup(self):
        """Create consumer and publisher connections"""
        self._mq_consumer = rabbitmq.RabbitConsumer(
            host=cfg.mq__host,
            port=cfg.mq__port,
            username=cfg.mq__username,
            password=cfg.mq__password,
            exchange=cfg.mq__exchange,
            key=cfg.mq__inbound,
            msg_callback=self._msg_callback,
        )

        self._adaptation_publisher = rabbitmq.RabbitPublisher(
            host=cfg.mq__host,
            port=cfg.mq__port,
            username=cfg.mq__username,
            password=cfg.mq__password,
            exchange=cfg.mq__exchange,
            key=cfg.mq__outbound,
        )

        # TODO: could probably be switched to QuickRabbit
        self._heat_publisher = rabbitmq.RabbitPublisher(
            host=cfg.heat_resource_mq__host,
            port=cfg.heat_resource_mq__port,
            username=cfg.heat_resource_mq__username,
            password=cfg.heat_resource_mq__password,
            exchange=cfg.heat_resource_mq__exchange,
            key=cfg.heat_resource_mq__key,
        )

    def publish(self, message):
        """Publish supplied message"""
        self._adaptation_publisher.publish(message)

    def publish_to_heat_resource(self, resource_id, message):
        """
        Publish supplied message with specified resource id to the
        custom heat resource listener
        """
        LOGGER.debug(
            'sending message [{0}] to [{1}]'.format(message, resource_id)
        )
        self._heat_publisher.publish(message=message, resource_id=resource_id)

    def healthcheck(self):
        """Execute message queue healthcheck connection"""
        try:
            LOGGER.debug('Healthcheck started')

            mq_tester = rabbitmq.RabbitHealthCheck(
                host=cfg.mq__host,
                port=cfg.mq__port,
                username=cfg.mq__username,
                password=cfg.mq__password,
                exchange=cfg.mq__exchange,
                key='cw-healthcheck.{0}'.format(uuid.uuid4()),
            )

            mq_tester.run_tests()
            while mq_tester.is_alive():
                pass

            LOGGER.debug('Healthcheck ends')
        except Exception, err:
            LOGGER.debug('Healthcheck failed: ' + str(err))
            HEALTHLOGGER.info("[FAIL] " + str(err))

    def run(self):
        """Executed on thread start. Setup, and start connection threads"""
        self.setup()
        self._mq_consumer.start()
        self._adaptation_publisher.start()
        self._heat_publisher.start()

    def stop(self):
        """Executed on thread stop. Halt connection threads"""
        self._mq_consumer.stop()
        self._adaptation_publisher.stop()
        self._heat_publisher.stop()


class QuickRabbit:
    """
    Convenient alternative to leaving a thread running when you're not
    listening for anything but need to publish multiple messages to
    the same broker
    """

    def __init__(
            self,
            host,
            port,
            username,
            password,
    ):
        """Setup the connection, channel, etc"""
        credentials = pika.PlainCredentials(
            username,
            password
        )
        self._connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=host,
                port=port,
                credentials=credentials
            )
        )
        self._channel = self._connection.channel()

    def _publish(self, exchange, key, message):
        """Publish a message using supplied details"""
        self._channel.exchange_declare(
            exchange=exchange,
            type='topic'
        )
        self._channel.basic_publish(
            exchange=exchange,
            routing_key=key,
            body=message
        )

    def disconnect(self):
        """Disconnect from the broker, close the channel and connection"""
        self._channel.close()
        self._connection.close()

    def publish_openstack_start_event(self, exchange, key, stack_id, name):
        """
        Publish an Openstack 'start' event notification JSON-format
        message using the supplied details
        """
        message = self._generate_openstack_event('start', stack_id, name)
        self._publish(exchange, key, message)

    def publish_openstack_complete_event(self, exchange, key, stack_id, name):
        """
        Publish an Openstack 'complete' event notification JSON-format
        message using the supplied details
        """
        message = self._generate_openstack_event('complete', stack_id, name)
        self._publish(exchange, key, message)

    def _generate_openstack_event(self, event_str, stack_id, name):
        """
        Create a JSON message using the supplied details to match the accepted
        Openstack Horizon custom notification format
        """
        ISO8601_time_format = '%Y-%m-%dT%H:%M:%SZ'

        # timestamp
        utc = datetime.datetime.utcnow()
        timestamp = utc.strftime(ISO8601_time_format)

        # generate message
        payload = {
            'priority': 'INFO',
            '_unique_id': uuid.uuid4().hex,
            'event_type': 'cw.{0}.adaptation-{1}'.format(stack_id, event_str),
            '_context_some': 'context',
            'publisher_id': 'test',
            'payload': {
                'cw_payload': json.dumps(
                    {'metrics': ['ACTIVE_CONN', 'VIDEO', 'vlan.bandwidth']}
                ),
                'cw_event_name': name,
                'cw_event_type': 'adaptation-{0}'.format(event_str),
                'timestamp': timestamp,
                'stack_id': stack_id,
            },
            'message_id': str(uuid.uuid4()),
        }

        return bz2.compress(
            pickle.dumps(
                json.dumps(payload)
            )
        )

    def publish_adaptation_request(
            self, exchange, key, adaptation_action, event
    ):
        """Publish a JSON adaptation request message"""
        self._publish(
            exchange,
            key,
            adaptation_action.generate_adaptation_request(
                event
            )
        )

    def publish_lowpower_request(
            self, exchange, key, adaptation_action, event
    ):
        """Publish a JSON lowpower request message"""
        # we need to redirect and rename the event before sending
        self._publish(
            exchange,
            key,
            adaptation_action.generate_adaptation_request(
                event,
                name='lowpower',
                stack_id=adaptation_action.application,
            )
        )

    def publish_app_feedback_start_event(
            self, exchange, key, stack_id, name, details
    ):
        """
        Publish a JSON application feedback 'start' notification message

        This indicates to an application that an adaptation on its stack
        has been started
        """
        message = self._generate_app_feedback_event(
            'start',
            stack_id,
            name,
            details
        )
        self._publish(exchange, key, message)

    def publish_app_feedback_complete_event(
            self, exchange, key, stack_id, name, details
    ):
        """
        Publish a JSON application feedback 'complete' notification message

        This indicates to an application that an adaptation on its stack
        has been completed
        """
        message = self._generate_app_feedback_event(
            'complete',
            stack_id,
            name,
            details
        )
        self._publish(exchange, key, message)

    def publish_app_feedback_failed_event(
            self, exchange, key, stack_id, name, details
    ):
        """
        Publish a JSON application feedback 'failed' notification message

        This indicates to an application that an adaptation on its stack
        has failed
        """
        message = self._generate_app_feedback_event(
            'failed',
            stack_id,
            name,
            details
        )
        self._publish(exchange, key, message)

    def _generate_app_feedback_event(self, event_str, stack_id, name, details):
        """
        Create a JSON message using the supplied details to match the accepted
        application feedback notification format
        """
        ISO8601_time_format = '%Y-%m-%dT%H:%M:%SZ'

        # timestamp
        utc = datetime.datetime.utcnow()
        timestamp = utc.strftime(ISO8601_time_format)

        # generate message
        payload = {
            'adaptation_event': {
                'event_type': '{0}.adaptation-{1}'.format(stack_id, event_str),
                'event_name': name,
                'timestamp': timestamp,
                'stack_id': stack_id,
                'id': str(uuid.uuid4()),
                'event_details': details,
            }
        }

        return json.dumps(payload)
