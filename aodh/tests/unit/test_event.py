#
# Copyright 2015 NEC Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import mock

from oslo_config import fixture as fixture_config
from oslo_messaging import server

from aodh import event
from aodh import service
from aodh.tests import base as tests_base


class TestEventAlarmEvaluationService(tests_base.BaseTestCase):

    def setUp(self):
        super(TestEventAlarmEvaluationService, self).setUp()

        conf = service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(fixture_config.Config(conf)).conf
        self.storage_conn = mock.MagicMock()
        self.setup_messaging(self.CONF)
        with mock.patch('aodh.storage.get_connection_from_config',
                        return_value=self.storage_conn):
            self.service = event.EventAlarmEvaluationService(self.CONF)

    def test_start_and_stop_service(self):
        self.service.start()
        self.assertIsInstance(self.service.listener,
                              server.MessageHandlingServer)
        self.service.stop()

    def test_listener_start_called(self):
        listener = mock.Mock()
        with mock.patch('aodh.messaging.get_notification_listener',
                        return_value=listener):
            self.service.start()
        self.assertTrue(listener.start.called)
