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
import threading
import time

import pika

import healthcheck

LOGGER = logging.getLogger('syslog')


class RabbitMQ(threading.Thread):
    """
    A generic RabbitMQ connection to run in a seperate thread
    """

    def __init__(
        self,
        host,
        port,
        username,
        password,
        exchange,
        key,
    ):
        """Create the connection and execute thread setup"""
        self._EXCHANGE = exchange
        self._KEY = key
        self._CONNECTION = None
        self._CHANNEL = None
        self._CLOSING = False

        self._HOST = host
        self._PORT = port

        credentials = pika.PlainCredentials(username, password)
        self._CONNECTION_PARAMETERS = pika.ConnectionParameters(
            host=host,
            port=port,
            credentials=credentials
        )

        LOGGER.info(
            'RabbitMQ connection to {0}:{1} initialised'.format(host, port)
        )

        threading.Thread.__init__(self)

    def _connect(self):
        """
        Connect to the broker, unless we're intentionally closing the
        connection. Try to reconnect every 5 seconds if needed. Start
        the pika ioloop.
        """
        while not self._CLOSING:
            LOGGER.info(
                'Connecting to [{0}:{1}]'.format(self._HOST, self._PORT)
            )
            try:
                self._CONNECTION = pika.SelectConnection(
                    parameters=self._CONNECTION_PARAMETERS,
                    on_open_callback=self._on_connection_open,
                    stop_ioloop_on_close=False
                )
                self._CONNECTION.ioloop.start()
                break
            except Exception:
                # wait for 5 seconds and try again
                LOGGER.info(
                    "Could not connect to [{0}:{1}]."
                    " Waiting 5 seconds and trying again.".format(
                        self._HOST,
                        self._PORT
                    )
                )
                time.sleep(5)

    def _reconnect(self):
        """Stop the ioloop, and re-execute the connection"""
        self._CONNECTION.ioloop.stop()
        self._connect()

    def _on_connection_open(self, connection):
        """
        Callback executed when there is a successfull connection to the broker

        Create the channel and add disconnection callback
        """
        LOGGER.info('Connected to [{0}:{1}]'.format(self._HOST, self._PORT))
        connection.channel(self._on_channel_open)
        connection.add_on_close_callback(self._on_connection_closed)

    def _on_connection_closed(self, connection, reply_code, reply_text):
        """
        Callback executed when the connection to the broker is closed, whether
        intentionally or not

        If not intentionally closing the connection, try reconnecting
        """
        self._CHANNEL = None
        if not self._CLOSING:
            LOGGER.error(
                'Connection to [{0}:{1}] closed'.format(self._HOST, self._PORT)
            )
            self._CONNECTION.add_timeout(5, self._reconnect)
        LOGGER.info('Connection closed')

    def _on_channel_open(self, channel):
        """
        Callback executed when a channel is opened on the connection

        Add channel close callback, declare exchange
        """
        LOGGER.info('Channel opened')
        self._CHANNEL = channel
        self._CHANNEL.add_on_close_callback(self._on_channel_closed)
        self._CHANNEL.exchange_declare(
            self._on_exchange_declared,
            self._EXCHANGE,
            'topic'
        )

    def _on_channel_closed(self, channel, reply_code, reply_text):
        """
        Callback executed when the channel is closed

        If intentionally disconnecting from the broker, close the connection
        """
        LOGGER.warning(
            'Channel %i was closed: (%s) %s', channel, reply_code, reply_text
        )
        if self._CLOSING:
            self._CONNECTION.close()

    def _on_exchange_declared(self, response):
        """
        Callback executed when the exchange is delared
        """
        LOGGER.info('Exchange declared')
        pass

    def run(self):
        """
        Executed on thread start

        Connect to broker
        """
        self._connect()

    def stop(self):
        """
        Executed on thread stop

        Set intentional connection closing flag, close connection and stop
        ioloop
        """
        try:
            self._CLOSING = True
            self._CONNECTION.close()
            self._CONNECTION.ioloop.stop()
            LOGGER.info('Stopped')
        except Exception, err:
            LOGGER.error(
                'Exception stopping rabbitmq connection: [{0}]'.format(err)
            )


class RabbitConsumer(RabbitMQ):
    """
    A Rabbit consumer sub-class for reading incoming messages
    """

    def __init__(
        self,
        host,
        port,
        username,
        password,
        exchange,
        key,
        queue=None,
        msg_callback=None,
    ):
        """Basic setup, execute parent init"""
        self._QUEUE = queue
        self._MSG_CALLBACK = msg_callback
        self._CONSUMER = None

        RabbitMQ.__init__(self, host, port, username, password, exchange, key)

    def _on_exchange_declared(self, response):
        """
        Callback executed when an exchange is declared

        Declare queue, either with an auto-generated name, or a supplied one
        """
        LOGGER.info('Exchange declared')
        if not self._QUEUE:
            self._CHANNEL.queue_declare(
                self._on_queue_declared,
                auto_delete=True
            )
        else:
            self._CHANNEL.queue_declare(
                self._on_queue_declared,
                self._QUEUE,
                auto_delete=True
            )

    def _on_queue_declared(self, response):
        """
        Callback executed when a queue is declared

        Bind queue to channel
        """
        LOGGER.info('Queue declared')
        self._QUEUE = response.method.queue
        self._CHANNEL.queue_bind(
            self._on_queue_bound,
            self._QUEUE,
            self._EXCHANGE,
            self._KEY
        )

    def _on_queue_bound(self, response):
        """
        Callback executed when a queue is bound to a channel

        Create a consumer and start it consuming
        """
        LOGGER.info('Queue bound')
        self._CONSUMER = self._CHANNEL.basic_consume(
            self._on_message_received,
            self._QUEUE,
            no_ack=True
        )

    def _on_message_received(self, channel, basic_deliver, properties, body):
        """
        Callback executed on receipt of message

        Pass message to the callback function specified on initialisation, if
        there was one
        """
        LOGGER.info('Message received')
        try:
            if self._MSG_CALLBACK is not None:
                self._MSG_CALLBACK(body)
        except Exception, err:
            LOGGER.error(
                "Message could not be handled "
                "properly (exception: [{0}])".format(err)
            )


class RabbitPublisher(RabbitMQ):
    """
    A Rabbit publisher sub-class for reading incoming messages
    """

    def __init__(
        self,
        host,
        port,
        username,
        password,
        exchange,
        key,
    ):
        """Execute parent init"""
        RabbitMQ.__init__(self, host, port, username, password, exchange, key)

    def publish(self, message, resource_id=None):
        """
        Publish a provided message, optionally appending a resource_id
        to the existing configured routing key
        """
        LOGGER.info('Publishing a message...')
        LOGGER.info('existing key [{0}]'.format(self._KEY))
        if resource_id:
            try:
                respond_key = self._KEY.format(resource_id=resource_id)
            except Exception, err:
                LOGGER.error(
                    "Improper resource id formatting"
                    " in routing key (exception: [{0}])".format(err)
                )
        else:
            respond_key = self._KEY

        LOGGER.info('response key [{0}]'.format(respond_key))
        LOGGER.info("response: {0}".format(message))

        try:
            self._CHANNEL.basic_publish(
                exchange=self._EXCHANGE,
                routing_key=respond_key,
                body=message
            )
        except Exception, err:
            LOGGER.error(
                "Exception while publishing message: [{0}]".format(err)
            )
        else:
            LOGGER.info('Message published')


class RabbitHealthCheck(RabbitMQ):
    """
    A Rabbit sub-class for performaing message queue health checks

    Mostly a bridge between RabbitMQ interfaces and HealthCheck logic
    """

    def __init__(
        self,
        host,
        port,
        username,
        password,
        exchange,
        key,
        name='RabbitMQ Broker',
    ):
        """Basic setup, create health checker, setup thread"""
        self._CONSUMER = None
        self._QUEUE = None
        self.test_name = name

        self._HEALTHCHECKER = healthcheck.HealthCheck(self)

        self._HEALTHCHECKER.log(
            'Using Connection [{0}:{1}]'.format(host, port)
        )
        self._HEALTHCHECKER.log('Using Exchange [{0}]'.format(exchange))
        self._HEALTHCHECKER.log('Using Routing Key [{0}]'.format(key))

        RabbitMQ.__init__(self, host, port, username, password, exchange, key)

    def _on_connection_open(self, connection):
        """
        Callback executed when there is a successfull connection to the broker
        """
        self._HEALTHCHECKER.log('Connected', 2)
        RabbitMQ._on_connection_open(self, connection)

    def _on_exchange_declared(self, response):
        """
        Callback executed when the exchange is delared
        """
        self._HEALTHCHECKER.log('Exchange declared', 2)
        self._CHANNEL.queue_declare(self._on_queue_declared, auto_delete=True)

    def _on_queue_declared(self, response):
        """Callback executed when a queue is declared"""
        self._HEALTHCHECKER.log('Queue declared', 2)
        self._QUEUE = response.method.queue
        self._CHANNEL.queue_bind(
            self._on_queue_bound, self._QUEUE, self._EXCHANGE, self._KEY
        )

    def _on_queue_bound(self, response):
        """Callback executed when a queue is bound to a channel"""
        self._HEALTHCHECKER.log('Queue bound', 2)
        self._CONSUMER = self._CHANNEL.basic_consume(
            self._on_message_received, self._QUEUE, no_ack=True
        )
        self._HEALTHCHECKER.publish_messages()

    def _on_message_received(self, channel, basic_deliver, properties, body):
        """Callback executed on receipt of message"""
        self._HEALTHCHECKER.received_msg(body)

    def publish(self, msg):
        """Publish a provided message"""
        self._CHANNEL.basic_publish(
            exchange=self._EXCHANGE, routing_key=self._KEY, body=msg
        )

    def run_tests(self):
        """Execute the tests suite"""
        self._HEALTHCHECKER.run_tests(
            import_exception=pika.exceptions.IncompatibleProtocolError
        )
