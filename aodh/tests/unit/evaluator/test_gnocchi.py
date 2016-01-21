#
# Copyright 2015 eNovance
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

import datetime
import unittest
import uuid

from gnocchiclient import exceptions
import mock
from oslo_utils import timeutils
from oslotest import mockpatch
import pytz
import six
from six import moves

from aodh.evaluator import gnocchi
from aodh.storage import models
from aodh.tests import constants
from aodh.tests.unit.evaluator import base


class TestGnocchiThresholdEvaluate(base.TestEvaluatorBase):
    EVALUATOR = gnocchi.GnocchiThresholdEvaluator

    def setUp(self):
        self.client = self.useFixture(mockpatch.Patch(
            'aodh.evaluator.gnocchi.client'
        )).mock.Client.return_value
        super(TestGnocchiThresholdEvaluate, self).setUp()

    def prepare_alarms(self):
        self.alarms = [
            models.Alarm(name='instance_running_hot',
                         description='instance_running_hot',
                         type='gnocchi_resources_threshold',
                         enabled=True,
                         user_id='foobar',
                         project_id='snafu',
                         alarm_id=str(uuid.uuid4()),
                         state='insufficient data',
                         state_timestamp=constants.MIN_DATETIME,
                         timestamp=constants.MIN_DATETIME,
                         insufficient_data_actions=[],
                         ok_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         time_constraints=[],
                         rule=dict(
                             comparison_operator='gt',
                             threshold=80.0,
                             evaluation_periods=5,
                             aggregation_method='mean',
                             granularity=60,
                             metric='cpu_util',
                             resource_type='instance',
                             resource_id='my_instance')
                         ),
            models.Alarm(name='group_running_idle',
                         description='group_running_idle',
                         type='gnocchi_aggregation_by_metrics_threshold',
                         enabled=True,
                         user_id='foobar',
                         project_id='snafu',
                         state='insufficient data',
                         state_timestamp=constants.MIN_DATETIME,
                         timestamp=constants.MIN_DATETIME,
                         insufficient_data_actions=[],
                         ok_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         alarm_id=str(uuid.uuid4()),
                         time_constraints=[],
                         rule=dict(
                             comparison_operator='le',
                             threshold=10.0,
                             evaluation_periods=4,
                             aggregation_method='max',
                             granularity=300,
                             metrics=['0bb1604d-1193-4c0a-b4b8-74b170e35e83',
                                      '9ddc209f-42f8-41e1-b8f1-8804f59c4053']),
                         ),
            models.Alarm(name='instance_not_running',
                         description='instance_running_hot',
                         type='gnocchi_aggregation_by_resources_threshold',
                         enabled=True,
                         user_id='foobar',
                         project_id='snafu',
                         alarm_id=str(uuid.uuid4()),
                         state='insufficient data',
                         state_timestamp=constants.MIN_DATETIME,
                         timestamp=constants.MIN_DATETIME,
                         insufficient_data_actions=[],
                         ok_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         time_constraints=[],
                         rule=dict(
                             comparison_operator='gt',
                             threshold=80.0,
                             evaluation_periods=6,
                             aggregation_method='mean',
                             granularity=50,
                             metric='cpu_util',
                             resource_type='instance',
                             query='{"=": {"server_group": '
                             '"my_autoscaling_group"}}')
                         ),

        ]

    @staticmethod
    def _get_stats(granularity, values):
        now = timeutils.utcnow_ts()
        return [[six.text_type(now - len(values) * granularity),
                 granularity, value] for value in values]

    @staticmethod
    def _reason_data(disposition, count, most_recent):
        return {'type': 'threshold', 'disposition': disposition,
                'count': count, 'most_recent': most_recent}

    def _set_all_rules(self, field, value):
        for alarm in self.alarms:
            alarm.rule[field] = value

    def test_retry_transient_api_failure(self):
        means = self._get_stats(60, [self.alarms[0].rule['threshold'] - v
                                     for v in moves.xrange(5)])
        maxs = self._get_stats(300, [self.alarms[1].rule['threshold'] + v
                                     for v in moves.xrange(4)])
        avgs2 = self._get_stats(50, [self.alarms[2].rule['threshold'] - v
                                     for v in moves.xrange(6)])
        self.client.metric.get_measures.side_effect = [
            exceptions.ClientException(501, "error2"),
            means]
        self.client.metric.aggregation.side_effect = [
            Exception('boom'),
            exceptions.ClientException(500, "error"),
            maxs, avgs2]
        self._evaluate_all_alarms()
        self._assert_all_alarms('insufficient data')
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')

    def test_simple_insufficient(self):
        self._set_all_alarms('ok')
        self.client.metric.get_measures.return_value = []
        self.client.metric.aggregation.return_value = []
        self._evaluate_all_alarms()
        self._assert_all_alarms('insufficient data')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        expected = [mock.call(
            alarm,
            'ok',
            ('%d datapoints are unknown'
                % alarm.rule['evaluation_periods']),
            self._reason_data('unknown',
                              alarm.rule['evaluation_periods'],
                              None))
            for alarm in self.alarms]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    @mock.patch.object(timeutils, 'utcnow')
    def test_simple_alarm_trip(self, utcnow):
        utcnow.return_value = datetime.datetime(2015, 1, 26, 12, 57, 0, 0)
        self._set_all_alarms('ok')
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(1, 6)])
        maxs = self._get_stats(300, [self.alarms[1].rule['threshold'] - v
                                     for v in moves.xrange(4)])
        avgs2 = self._get_stats(50, [self.alarms[2].rule['threshold'] + v
                                     for v in moves.xrange(1, 7)])

        self.client.metric.get_measures.side_effect = [avgs]
        self.client.metric.aggregation.side_effect = [maxs, avgs2]
        self._evaluate_all_alarms()

        start_alarm1 = "2015-01-26T12:51:00"
        start_alarm2 = "2015-01-26T12:32:00"
        start_alarm3 = "2015-01-26T12:51:10"
        end = "2015-01-26T12:57:00"

        self.assertEqual([
            mock.call.get_measures(aggregation='mean', metric='cpu_util',
                                   resource_id='my_instance',
                                   start=start_alarm1, stop=end),
            mock.call.aggregation(aggregation='max',
                                  metrics=[
                                      '0bb1604d-1193-4c0a-b4b8-74b170e35e83',
                                      '9ddc209f-42f8-41e1-b8f1-8804f59c4053'],
                                  start=start_alarm2, stop=end),
            mock.call.aggregation(aggregation='mean', metrics='cpu_util',
                                  needed_overlap=0,
                                  query={"=": {"server_group":
                                               "my_autoscaling_group"}},
                                  resource_type='instance',
                                  start=start_alarm3, stop=end),
            ], self.client.metric.mock_calls)

        self._assert_all_alarms('alarm')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        reasons = ['Transition to alarm due to 5 samples outside'
                   ' threshold, most recent: %s' % avgs[-1][2],
                   'Transition to alarm due to 4 samples outside'
                   ' threshold, most recent: %s' % maxs[-1][2],
                   'Transition to alarm due to 6 samples outside'
                   ' threshold, most recent: %s' % avgs2[-1][2],
                   ]
        reason_datas = [self._reason_data('outside', 5, avgs[-1][2]),
                        self._reason_data('outside', 4, maxs[-1][2]),
                        self._reason_data('outside', 6, avgs2[-1][2])]
        expected = [mock.call(alarm, 'ok', reason, reason_data)
                    for alarm, reason, reason_data
                    in zip(self.alarms, reasons, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_simple_alarm_clear(self):
        self._set_all_alarms('alarm')
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] - v
                                    for v in moves.xrange(5)])
        maxs = self._get_stats(300, [self.alarms[1].rule['threshold'] + v
                                     for v in moves.xrange(1, 5)])
        avgs2 = self._get_stats(50, [self.alarms[2].rule['threshold'] - v
                                     for v in moves.xrange(6)])
        self.client.metric.get_measures.side_effect = [avgs]
        self.client.metric.aggregation.side_effect = [maxs, avgs2]
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        reasons = ['Transition to ok due to 5 samples inside'
                   ' threshold, most recent: %s' % avgs[-1][2],
                   'Transition to ok due to 4 samples inside'
                   ' threshold, most recent: %s' % maxs[-1][2],
                   'Transition to ok due to 6 samples inside'
                   ' threshold, most recent: %s' % avgs2[-1][2]]
        reason_datas = [self._reason_data('inside', 5, avgs[-1][2]),
                        self._reason_data('inside', 4, maxs[-1][2]),
                        self._reason_data('inside', 6, avgs2[-1][2])]
        expected = [mock.call(alarm, 'alarm', reason, reason_data)
                    for alarm, reason, reason_data
                    in zip(self.alarms, reasons, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_equivocal_from_known_state_ok(self):
        self._set_all_alarms('ok')
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(5)])
        maxs = self._get_stats(300, [self.alarms[1].rule['threshold'] - v
                                     for v in moves.xrange(-1, 3)])
        avgs2 = self._get_stats(50, [self.alarms[2].rule['threshold'] + v
                                     for v in moves.xrange(6)])
        self.client.metric.get_measures.side_effect = [avgs]
        self.client.metric.aggregation.side_effect = [maxs, avgs2]
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        self.assertEqual(
            [],
            self.storage_conn.update_alarm.call_args_list)
        self.assertEqual([], self.notifier.notify.call_args_list)

    def test_equivocal_ok_to_alarm(self):
        self.alarms = [self.alarms[1]]
        self._set_all_alarms('ok')
        # NOTE(sileht): we add one useless point (81.0) that will break
        # the test if the evaluator doesn't remove it.
        maxs = self._get_stats(300, [self.alarms[0].rule['threshold'] - v
                                     for v in moves.xrange(-1, 5)])
        self.client.metric.aggregation.side_effect = [maxs]
        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')

    def test_equivocal_from_known_state_and_repeat_actions(self):
        self._set_all_alarms('ok')
        self.alarms[1].repeat_actions = True
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(5)])
        maxs = self._get_stats(300, [self.alarms[1].rule['threshold'] - v
                                     for v in moves.xrange(-1, 3)])
        avgs2 = self._get_stats(50, [self.alarms[2].rule['threshold'] + v
                                     for v in moves.xrange(6)])
        self.client.metric.get_measures.side_effect = [avgs]
        self.client.metric.aggregation.side_effect = [maxs, avgs2]
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        self.assertEqual([], self.storage_conn.update_alarm.call_args_list)
        reason = ('Remaining as ok due to 4 samples inside'
                  ' threshold, most recent: 8.0')
        reason_datas = self._reason_data('inside', 4, 8.0)
        expected = [mock.call(self.alarms[1], 'ok', reason, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_unequivocal_from_known_state_and_repeat_actions(self):
        self._set_all_alarms('alarm')
        self.alarms[1].repeat_actions = True
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(1, 6)])
        maxs = self._get_stats(300, [self.alarms[1].rule['threshold'] - v
                                     for v in moves.xrange(4)])
        avgs2 = self._get_stats(50, [self.alarms[2].rule['threshold'] + v
                                     for v in moves.xrange(6)])
        self.client.metric.get_measures.side_effect = [avgs]
        self.client.metric.aggregation.side_effect = [maxs, avgs2]
        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')
        self.assertEqual([], self.storage_conn.update_alarm.call_args_list)
        reason = ('Remaining as alarm due to 4 samples outside'
                  ' threshold, most recent: 7.0')
        reason_datas = self._reason_data('outside', 4, 7.0)
        expected = [mock.call(self.alarms[1], 'alarm',
                              reason, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_state_change_and_repeat_actions(self):
        self._set_all_alarms('ok')
        self.alarms[0].repeat_actions = True
        self.alarms[1].repeat_actions = True
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(1, 6)])
        maxs = self._get_stats(300, [self.alarms[1].rule['threshold'] - v
                                     for v in moves.xrange(4)])
        avgs2 = self._get_stats(50, [self.alarms[2].rule['threshold'] + v
                                     for v in moves.xrange(1, 7)])
        self.client.metric.get_measures.side_effect = [avgs]
        self.client.metric.aggregation.side_effect = [maxs, avgs2]
        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        reasons = ['Transition to alarm due to 5 samples outside'
                   ' threshold, most recent: %s' % avgs[-1][2],
                   'Transition to alarm due to 4 samples outside'
                   ' threshold, most recent: %s' % maxs[-1][2],
                   'Transition to alarm due to 6 samples outside'
                   ' threshold, most recent: %s' % avgs2[-1][2]]
        reason_datas = [self._reason_data('outside', 5, avgs[-1][2]),
                        self._reason_data('outside', 4, maxs[-1][2]),
                        self._reason_data('outside', 6, avgs2[-1][2])]
        expected = [mock.call(alarm, 'ok', reason, reason_data)
                    for alarm, reason, reason_data
                    in zip(self.alarms, reasons, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    def test_equivocal_from_unknown(self):
        self._set_all_alarms('insufficient data')
        avgs = self._get_stats(60, [self.alarms[0].rule['threshold'] + v
                                    for v in moves.xrange(1, 6)])
        maxs = self._get_stats(300, [self.alarms[1].rule['threshold'] - v
                                     for v in moves.xrange(4)])
        avgs2 = self._get_stats(50, [self.alarms[2].rule['threshold'] + v
                                     for v in moves.xrange(1, 7)])
        self.client.metric.get_measures.side_effect = [avgs]
        self.client.metric.aggregation.side_effect = [maxs, avgs2]
        self._evaluate_all_alarms()
        self._assert_all_alarms('alarm')
        expected = [mock.call(alarm) for alarm in self.alarms]
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual(expected, update_calls)
        reasons = ['Transition to alarm due to 5 samples outside'
                   ' threshold, most recent: %s' % avgs[-1][2],
                   'Transition to alarm due to 4 samples outside'
                   ' threshold, most recent: %s' % maxs[-1][2],
                   'Transition to alarm due to 6 samples outside'
                   ' threshold, most recent: %s' % avgs2[-1][2]]
        reason_datas = [self._reason_data('outside', 5, avgs[-1][2]),
                        self._reason_data('outside', 4, maxs[-1][2]),
                        self._reason_data('outside', 6, avgs2[-1][2])]
        expected = [mock.call(alarm, 'insufficient data',
                              reason, reason_data)
                    for alarm, reason, reason_data
                    in zip(self.alarms, reasons, reason_datas)]
        self.assertEqual(expected, self.notifier.notify.call_args_list)

    @unittest.skipIf(six.PY3,
                     "the aodh base class is not python 3 ready")
    @mock.patch.object(timeutils, 'utcnow')
    def test_no_state_change_outside_time_constraint(self, mock_utcnow):
        self._set_all_alarms('ok')
        self.alarms[0].time_constraints = [
            {'name': 'test',
             'description': 'test',
             'start': '0 11 * * *',  # daily at 11:00
             'duration': 10800,  # 3 hours
             'timezone': 'Europe/Ljubljana'}
        ]
        self.alarms[1].time_constraints = self.alarms[0].time_constraints
        self.alarms[2].time_constraints = self.alarms[0].time_constraints
        dt = datetime.datetime(2014, 1, 1, 15, 0, 0,
                               tzinfo=pytz.timezone('Europe/Ljubljana'))
        mock_utcnow.return_value = dt.astimezone(pytz.UTC)
        self.client.metric.get_measures.return_value = []
        self.client.metric.aggregation.return_value = []
        self._evaluate_all_alarms()
        self._assert_all_alarms('ok')
        update_calls = self.storage_conn.update_alarm.call_args_list
        self.assertEqual([], update_calls,
                         "Alarm should not change state if the current "
                         " time is outside its time constraint.")
        self.assertEqual([], self.notifier.notify.call_args_list)
