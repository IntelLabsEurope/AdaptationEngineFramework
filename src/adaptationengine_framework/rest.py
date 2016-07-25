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
import json
import logging
import threading

import web

import adaptationengine_framework.configuration as cfg


LOGGER = logging.getLogger('syslog')


class WebboNoPrinto:
    """Suppress most of web.py's output"""

    def write(self, data):
        """Nobody cares"""
        pass

    def flush(self):
        """Still don't care"""
        pass


class Webbo(threading.Thread):
    """Run a webserver"""

    def __init__(self, get_agreement_map_function):
        """Initialise the server, setup the thread"""
        LOGGER.info("Making a webbo")
        self._get_agreement_map = get_agreement_map_function
        self._app = None

        threading.Thread.__init__(self)

    def load_agreements(self, handler):
        """Pass the agreement map into the request class"""
        web.ctx.agreements = self._get_agreement_map()
        return handler()

    def run(self):
        """Setup and start the webserver"""
        LOGGER.info("Doing a webbo")
        try:
            urls = (
                '/agreements', 'RESTAgreements',
                '/(.*)', 'RESTRoot',
            )
            # suppress most of webpy's output
            web.httpserver.sys.stderr = WebboNoPrinto()

            self._app = web.application(urls, globals())
            self._app.add_processor(self.load_agreements)
            web.httpserver.runsimple(
                self._app.wsgifunc(),
                ("0.0.0.0", cfg.webbo__port)
            )

        except Exception, err:
            LOGGER.exception(err)
            LOGGER.error("Could not start web server")

    def stop(self):
        """Stop the webserver"""
        LOGGER.info("So long webbo")
        self._app.stop()


class RESTRoot:
    """Handles the root directory of the webserver"""

    def GET(self, *args):
        """Just return a message"""
        return "No"


class RESTAgreements:
    """
    Handles presenting agreementid to stackid mappings to the world as json
    """

    def GET(self, *args):
        """dump"""
        return json.dumps(web.ctx.agreements)
