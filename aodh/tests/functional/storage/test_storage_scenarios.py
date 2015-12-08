#
# Copyright 2013 Intel Corp.
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
""" Base classes for DB backend implementation test
"""

import datetime

import mock
from oslo_utils import timeutils

from aodh.storage import models as alarm_models
from aodh.tests import constants
from aodh.tests.functional import db as tests_db


class DBTestBase(tests_db.TestBase):
    @staticmethod
    def create_side_effect(method, exception_type, test_exception):
        def side_effect(*args, **kwargs):
            if test_exception.pop():
                raise exception_type
            else:
                return method(*args, **kwargs)
        return side_effect

    def setUp(self):
        super(DBTestBase, self).setUp()
        patcher = mock.patch.object(timeutils, 'utcnow')
        self.addCleanup(patcher.stop)
        self.mock_utcnow = patcher.start()
        self.mock_utcnow.return_value = datetime.datetime(2015, 7, 2, 10, 39)


class AlarmTestBase(DBTestBase):
    def add_some_alarms(self):
        alarms = [alarm_models.Alarm(alarm_id='r3d',
                                     enabled=True,
                                     type='threshold',
                                     name='red-alert',
                                     description='my red-alert',
                                     timestamp=datetime.datetime(2015, 7,
                                                                 2, 10, 25),
                                     user_id='me',
                                     project_id='and-da-boys',
                                     state="insufficient data",
                                     state_timestamp=constants.MIN_DATETIME,
                                     ok_actions=[],
                                     alarm_actions=['http://nowhere/alarms'],
                                     insufficient_data_actions=[],
                                     repeat_actions=False,
                                     time_constraints=[dict(name='testcons',
                                                            start='0 11 * * *',
                                                            duration=300)],
                                     rule=dict(comparison_operator='eq',
                                               threshold=36,
                                               statistic='count',
                                               evaluation_periods=1,
                                               period=60,
                                               meter_name='test.one',
                                               query=[{'field': 'key',
                                                       'op': 'eq',
                                                       'value': 'value',
                                                       'type': 'string'}]),
                                     ),
                  alarm_models.Alarm(alarm_id='0r4ng3',
                                     enabled=True,
                                     type='threshold',
                                     name='orange-alert',
                                     description='a orange',
                                     timestamp=datetime.datetime(2015, 7,
                                                                 2, 10, 40),
                                     user_id='me',
                                     project_id='and-da-boys',
                                     state="insufficient data",
                                     state_timestamp=constants.MIN_DATETIME,
                                     ok_actions=[],
                                     alarm_actions=['http://nowhere/alarms'],
                                     insufficient_data_actions=[],
                                     repeat_actions=False,
                                     time_constraints=[],
                                     rule=dict(comparison_operator='gt',
                                               threshold=75,
                                               statistic='avg',
                                               evaluation_periods=1,
                                               period=60,
                                               meter_name='test.forty',
                                               query=[{'field': 'key2',
                                                       'op': 'eq',
                                                       'value': 'value2',
                                                       'type': 'string'}]),
                                     ),
                  alarm_models.Alarm(alarm_id='y3ll0w',
                                     enabled=False,
                                     type='threshold',
                                     name='yellow-alert',
                                     description='yellow',
                                     timestamp=datetime.datetime(2015, 7,
                                                                 2, 10, 10),
                                     user_id='me',
                                     project_id='and-da-boys',
                                     state="insufficient data",
                                     state_timestamp=constants.MIN_DATETIME,
                                     ok_actions=[],
                                     alarm_actions=['http://nowhere/alarms'],
                                     insufficient_data_actions=[],
                                     repeat_actions=False,
                                     time_constraints=[],
                                     rule=dict(comparison_operator='lt',
                                               threshold=10,
                                               statistic='min',
                                               evaluation_periods=1,
                                               period=60,
                                               meter_name='test.five',
                                               query=[{'field': 'key2',
                                                       'op': 'eq',
                                                       'value': 'value2',
                                                       'type': 'string'},
                                                      {'field':
                                                       'user_metadata.key3',
                                                       'op': 'eq',
                                                       'value': 'value3',
                                                       'type': 'string'}]),
                                     )]

        for a in alarms:
            self.alarm_conn.create_alarm(a)


class AlarmTest(AlarmTestBase):

    def test_empty(self):
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual([], alarms)

    def test_list(self):
        self.add_some_alarms()
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_list_ordered_by_timestamp(self):
        self.add_some_alarms()
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(len(alarms), 3)
        alarm_l = [a.timestamp for a in alarms]
        alarm_l_ordered = [datetime.datetime(2015, 7, 2, 10, 40),
                           datetime.datetime(2015, 7, 2, 10, 25),
                           datetime.datetime(2015, 7, 2, 10, 10)]
        self.assertEqual(alarm_l_ordered, alarm_l)

    def test_list_enabled(self):
        self.add_some_alarms()
        alarms = list(self.alarm_conn.get_alarms(enabled=True))
        self.assertEqual(2, len(alarms))

    def test_list_disabled(self):
        self.add_some_alarms()
        alarms = list(self.alarm_conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))

    def test_list_by_type(self):
        self.add_some_alarms()
        alarms = list(self.alarm_conn.get_alarms(alarm_type='threshold'))
        self.assertEqual(3, len(alarms))
        alarms = list(self.alarm_conn.get_alarms(alarm_type='combination'))
        self.assertEqual(0, len(alarms))

    def test_list_excluded_by_name(self):
        self.add_some_alarms()
        exclude = {'name': 'yellow-alert'}
        alarms = list(self.alarm_conn.get_alarms(exclude=exclude))
        self.assertEqual(2, len(alarms))
        alarm_names = sorted([a.name for a in alarms])
        self.assertEqual(['orange-alert', 'red-alert'], alarm_names)

    def test_add(self):
        self.add_some_alarms()
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))

        meter_names = sorted([a.rule['meter_name'] for a in alarms])
        self.assertEqual(['test.five', 'test.forty', 'test.one'], meter_names)

    def test_update(self):
        self.add_some_alarms()
        orange = list(self.alarm_conn.get_alarms(name='orange-alert'))[0]
        orange.enabled = False
        orange.state = alarm_models.Alarm.ALARM_INSUFFICIENT_DATA
        query = [{'field': 'metadata.group',
                  'op': 'eq',
                  'value': 'test.updated',
                  'type': 'string'}]
        orange.rule['query'] = query
        orange.rule['meter_name'] = 'new_meter_name'
        updated = self.alarm_conn.update_alarm(orange)
        self.assertEqual(False, updated.enabled)
        self.assertEqual(alarm_models.Alarm.ALARM_INSUFFICIENT_DATA,
                         updated.state)
        self.assertEqual(query, updated.rule['query'])
        self.assertEqual('new_meter_name', updated.rule['meter_name'])

    def test_update_llu(self):
        llu = alarm_models.Alarm(alarm_id='llu',
                                 enabled=True,
                                 type='threshold',
                                 name='llu',
                                 description='llu',
                                 timestamp=constants.MIN_DATETIME,
                                 user_id='bla',
                                 project_id='ffo',
                                 state="insufficient data",
                                 state_timestamp=constants.MIN_DATETIME,
                                 ok_actions=[],
                                 alarm_actions=[],
                                 insufficient_data_actions=[],
                                 repeat_actions=False,
                                 time_constraints=[],
                                 rule=dict(comparison_operator='lt',
                                           threshold=34,
                                           statistic='max',
                                           evaluation_periods=1,
                                           period=60,
                                           meter_name='llt',
                                           query=[])
                                 )
        updated = self.alarm_conn.update_alarm(llu)
        updated.state = alarm_models.Alarm.ALARM_OK
        updated.description = ':)'
        self.alarm_conn.update_alarm(updated)

        all = list(self.alarm_conn.get_alarms())
        self.assertEqual(1, len(all))

    def test_delete(self):
        self.add_some_alarms()
        victim = list(self.alarm_conn.get_alarms(name='orange-alert'))[0]
        self.alarm_conn.delete_alarm(victim.alarm_id)
        survivors = list(self.alarm_conn.get_alarms())
        self.assertEqual(2, len(survivors))
        for s in survivors:
            self.assertNotEqual(victim.name, s.name)


@tests_db.run_with('sqlite', 'mysql', 'pgsql', 'hbase')
class AlarmHistoryTest(AlarmTestBase):

    def setUp(self):
        super(AlarmTestBase, self).setUp()
        self.add_some_alarms()
        self.prepare_alarm_history()

    def prepare_alarm_history(self):
        alarms = list(self.alarm_conn.get_alarms())
        for alarm in alarms:
            i = alarms.index(alarm)
            alarm_change = {
                "event_id": "3e11800c-a3ca-4991-b34b-d97efb6047d%s" % i,
                "alarm_id": alarm.alarm_id,
                "type": alarm_models.AlarmChange.CREATION,
                "detail": "detail %s" % alarm.name,
                "user_id": alarm.user_id,
                "project_id": alarm.project_id,
                "on_behalf_of": alarm.project_id,
                "timestamp": datetime.datetime(2014, 4, 7, 7, 30 + i)
            }
            self.alarm_conn.record_alarm_change(alarm_change=alarm_change)

    def _clear_alarm_history(self, utcnow, ttl, count):
        self.mock_utcnow.return_value = utcnow
        self.alarm_conn.clear_expired_alarm_history_data(ttl)
        history = list(self.alarm_conn.query_alarm_history())
        self.assertEqual(count, len(history))

    def test_clear_alarm_history_no_data_to_remove(self):
        utcnow = datetime.datetime(2013, 4, 7, 7, 30)
        self._clear_alarm_history(utcnow, 1, 3)

    def test_clear_some_alarm_history(self):
        utcnow = datetime.datetime(2014, 4, 7, 7, 35)
        self._clear_alarm_history(utcnow, 3 * 60, 1)

    def test_clear_all_alarm_history(self):
        utcnow = datetime.datetime(2014, 4, 7, 7, 45)
        self._clear_alarm_history(utcnow, 3 * 60, 0)

    def test_delete_history_when_delete_alarm(self):
        alarms = list(self.alarm_conn.get_alarms())
        self.assertEqual(3, len(alarms))
        history = list(self.alarm_conn.query_alarm_history())
        self.assertEqual(3, len(history))
        for alarm in alarms:
            self.alarm_conn.delete_alarm(alarm.alarm_id)
        self.assertEqual(3, len(alarms))
        history = list(self.alarm_conn.query_alarm_history())
        self.assertEqual(0, len(history))


class ComplexAlarmQueryTest(AlarmTestBase):

    def test_no_filter(self):
        self.add_some_alarms()
        result = list(self.alarm_conn.query_alarms())
        self.assertEqual(3, len(result))

    def test_no_filter_with_limit(self):
        self.add_some_alarms()
        result = list(self.alarm_conn.query_alarms(limit=2))
        self.assertEqual(2, len(result))

    def test_filter(self):
        self.add_some_alarms()
        filter_expr = {"and":
                       [{"or":
                        [{"=": {"name": "yellow-alert"}},
                         {"=": {"name": "red-alert"}}]},
                        {"=": {"enabled": True}}]}

        result = list(self.alarm_conn.query_alarms(filter_expr=filter_expr))

        self.assertEqual(1, len(result))
        for a in result:
            self.assertIn(a.name, set(["yellow-alert", "red-alert"]))
            self.assertTrue(a.enabled)

    def test_filter_with_regexp(self):
        self.add_some_alarms()
        filter_expr = {"and":
                       [{"or": [{"=": {"name": "yellow-alert"}},
                                {"=": {"name": "red-alert"}}]},
                        {"=~": {"description": "yel.*"}}]}

        result = list(self.alarm_conn.query_alarms(filter_expr=filter_expr))

        self.assertEqual(1, len(result))
        for a in result:
            self.assertEqual("yellow", a.description)

    def test_filter_for_alarm_id(self):
        self.add_some_alarms()
        filter_expr = {"=": {"alarm_id": "0r4ng3"}}

        result = list(self.alarm_conn.query_alarms(filter_expr=filter_expr))

        self.assertEqual(1, len(result))
        for a in result:
            self.assertEqual("0r4ng3", a.alarm_id)

    def test_filter_and_orderby(self):
        self.add_some_alarms()
        result = list(self.alarm_conn.query_alarms(filter_expr=(
            {"=": {"enabled": True}}),
            orderby=[{"name": "asc"}]))
        self.assertEqual(2, len(result))
        self.assertEqual(["orange-alert", "red-alert"],
                         [a.name for a in result])
        for a in result:
            self.assertTrue(a.enabled)


class ComplexAlarmHistoryQueryTest(AlarmTestBase):
    def setUp(self):
        super(DBTestBase, self).setUp()
        self.filter_expr = {"and":
                            [{"or":
                              [{"=": {"type": "rule change"}},
                               {"=": {"type": "state transition"}}]},
                             {"=": {"alarm_id": "0r4ng3"}}]}
        self.add_some_alarms()
        self.prepare_alarm_history()

    def prepare_alarm_history(self):
        alarms = list(self.alarm_conn.get_alarms())
        name_index = {
            'red-alert': 0,
            'orange-alert': 1,
            'yellow-alert': 2
        }

        for alarm in alarms:
            i = name_index[alarm.name]
            alarm_change = dict(event_id=(
                                "16fd2706-8baf-433b-82eb-8c7fada847c%s" % i),
                                alarm_id=alarm.alarm_id,
                                type=alarm_models.AlarmChange.CREATION,
                                detail="detail %s" % alarm.name,
                                user_id=alarm.user_id,
                                project_id=alarm.project_id,
                                on_behalf_of=alarm.project_id,
                                timestamp=datetime.datetime(2012, 9, 24,
                                                            7 + i,
                                                            30 + i))
            self.alarm_conn.record_alarm_change(alarm_change=alarm_change)

            alarm_change2 = dict(event_id=(
                                 "16fd2706-8baf-433b-82eb-8c7fada847d%s" % i),
                                 alarm_id=alarm.alarm_id,
                                 type=alarm_models.AlarmChange.RULE_CHANGE,
                                 detail="detail %s" % i,
                                 user_id=alarm.user_id,
                                 project_id=alarm.project_id,
                                 on_behalf_of=alarm.project_id,
                                 timestamp=datetime.datetime(2012, 9, 25,
                                                             10 + i,
                                                             30 + i))
            self.alarm_conn.record_alarm_change(alarm_change=alarm_change2)

            alarm_change3 = dict(
                event_id="16fd2706-8baf-433b-82eb-8c7fada847e%s" % i,
                alarm_id=alarm.alarm_id,
                type=alarm_models.AlarmChange.STATE_TRANSITION,
                detail="detail %s" % (i + 1),
                user_id=alarm.user_id,
                project_id=alarm.project_id,
                on_behalf_of=alarm.project_id,
                timestamp=datetime.datetime(2012, 9, 26, 10 + i, 30 + i)
            )

            if alarm.name == "red-alert":
                alarm_change3['on_behalf_of'] = 'and-da-girls'

            self.alarm_conn.record_alarm_change(alarm_change=alarm_change3)

    def test_alarm_history_with_no_filter(self):
        history = list(self.alarm_conn.query_alarm_history())
        self.assertEqual(9, len(history))

    def test_alarm_history_with_no_filter_and_limit(self):
        history = list(self.alarm_conn.query_alarm_history(limit=3))
        self.assertEqual(3, len(history))

    def test_alarm_history_with_filter(self):
        history = list(
            self.alarm_conn.query_alarm_history(filter_expr=self.filter_expr))
        self.assertEqual(2, len(history))

    def test_alarm_history_with_regexp(self):
        filter_expr = {"and":
                       [{"=~": {"type": "(rule)|(state)"}},
                        {"=": {"alarm_id": "0r4ng3"}}]}
        history = list(
            self.alarm_conn.query_alarm_history(filter_expr=filter_expr))
        self.assertEqual(2, len(history))

    def test_alarm_history_with_filter_and_orderby(self):
        history = list(
            self.alarm_conn.query_alarm_history(filter_expr=self.filter_expr,
                                                orderby=[{"timestamp":
                                                          "asc"}]))
        self.assertEqual([alarm_models.AlarmChange.RULE_CHANGE,
                          alarm_models.AlarmChange.STATE_TRANSITION],
                         [h.type for h in history])

    def test_alarm_history_with_filter_and_orderby_and_limit(self):
        history = list(
            self.alarm_conn.query_alarm_history(filter_expr=self.filter_expr,
                                                orderby=[{"timestamp":
                                                          "asc"}],
                                                limit=1))
        self.assertEqual(alarm_models.AlarmChange.RULE_CHANGE, history[0].type)

    def test_alarm_history_with_on_behalf_of_filter(self):
        filter_expr = {"=": {"on_behalf_of": "and-da-girls"}}
        history = list(self.alarm_conn.query_alarm_history(
            filter_expr=filter_expr))
        self.assertEqual(1, len(history))
        self.assertEqual("16fd2706-8baf-433b-82eb-8c7fada847e0",
                         history[0].event_id)

    def test_alarm_history_with_alarm_id_as_filter(self):
        filter_expr = {"=": {"alarm_id": "r3d"}}
        history = list(self.alarm_conn.query_alarm_history(
            filter_expr=filter_expr, orderby=[{"timestamp": "asc"}]))
        self.assertEqual(3, len(history))
        self.assertEqual([alarm_models.AlarmChange.CREATION,
                          alarm_models.AlarmChange.RULE_CHANGE,
                          alarm_models.AlarmChange.STATE_TRANSITION],
                         [h.type for h in history])
