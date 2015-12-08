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

from oslo_serialization import jsonutils
import pecan
import requests
import wsme
from wsme import types as wtypes

from aodh.api.controllers.v2 import base
from aodh.api.controllers.v2 import utils as v2_utils
from aodh import keystone_client


class GnocchiUnavailable(Exception):
    code = 503


class AlarmGnocchiThresholdRule(base.AlarmRule):
    comparison_operator = base.AdvEnum('comparison_operator', str,
                                       'lt', 'le', 'eq', 'ne', 'ge', 'gt',
                                       default='eq')
    "The comparison against the alarm threshold"

    threshold = wsme.wsattr(float, mandatory=True)
    "The threshold of the alarm"

    aggregation_method = wsme.wsattr(wtypes.text, mandatory=True)
    "The aggregation_method to compare to the threshold"

    evaluation_periods = wsme.wsattr(wtypes.IntegerType(minimum=1), default=1)
    "The number of historical periods to evaluate the threshold"

    granularity = wsme.wsattr(wtypes.IntegerType(minimum=1), default=60)
    "The time range in seconds over which query"

    @classmethod
    def validate_alarm(cls, alarm):
        alarm_rule = getattr(alarm, "%s_rule" % alarm.type)
        aggregation_method = alarm_rule.aggregation_method
        if aggregation_method not in cls._get_aggregation_methods():
            raise base.ClientSideError(
                'aggregation_method should be in %s not %s' % (
                    cls._get_aggregation_methods(), aggregation_method))

    # NOTE(sileht): once cachetools is in the requirements
    # enable it
    # @cachetools.ttl_cache(maxsize=1, ttl=600)
    @staticmethod
    def _get_aggregation_methods():
        ks_client = keystone_client.get_client(pecan.request.cfg)
        gnocchi_url = pecan.request.cfg.gnocchi_url
        headers = {'Content-Type': "application/json",
                   'X-Auth-Token': ks_client.auth_token}
        try:
            r = requests.get("%s/v1/capabilities" % gnocchi_url,
                             headers=headers)
        except requests.ConnectionError as e:
            raise GnocchiUnavailable(e)
        if r.status_code // 200 != 1:
            raise GnocchiUnavailable(r.text)

        return jsonutils.loads(r.text).get('aggregation_methods', [])


class MetricOfResourceRule(AlarmGnocchiThresholdRule):
    metric = wsme.wsattr(wtypes.text, mandatory=True)
    "The name of the metric"

    resource_id = wsme.wsattr(wtypes.text, mandatory=True)
    "The id of a resource"

    resource_type = wsme.wsattr(wtypes.text, mandatory=True)
    "The resource type"

    def as_dict(self):
        rule = self.as_dict_from_keys(['granularity', 'comparison_operator',
                                       'threshold', 'aggregation_method',
                                       'evaluation_periods',
                                       'metric',
                                       'resource_id',
                                       'resource_type'])
        return rule

    @classmethod
    def validate_alarm(cls, alarm):
        super(MetricOfResourceRule,
              cls).validate_alarm(alarm)

        rule = alarm.gnocchi_resources_threshold_rule
        ks_client = keystone_client.get_client(pecan.request.cfg)
        gnocchi_url = pecan.request.cfg.gnocchi_url
        headers = {'Content-Type': "application/json",
                   'X-Auth-Token': ks_client.auth_token}
        try:
            r = requests.get("%s/v1/resource/%s/%s" % (
                gnocchi_url, rule.resource_type,
                rule.resource_id),
                headers=headers)
        except requests.ConnectionError as e:
            raise GnocchiUnavailable(e)
        if r.status_code == 404:
            raise base.EntityNotFound('gnocchi resource',
                                      rule.resource_id)
        elif r.status_code // 200 != 1:
            raise base.ClientSideError(r.content, status_code=r.status_code)


class AggregationMetricByResourcesLookupRule(AlarmGnocchiThresholdRule):
    metric = wsme.wsattr(wtypes.text, mandatory=True)
    "The name of the metric"

    query = wsme.wsattr(wtypes.text, mandatory=True)
    ('The query to filter the metric, Don\'t forget to filter out '
     'deleted resources (example: {"and": [{"=": {"ended_at": null}}, ...]}), '
     'Otherwise Gnocchi will try to create the aggregate against obsolete '
     'resources')

    resource_type = wsme.wsattr(wtypes.text, mandatory=True)
    "The resource type"

    def as_dict(self):
        rule = self.as_dict_from_keys(['granularity', 'comparison_operator',
                                       'threshold', 'aggregation_method',
                                       'evaluation_periods',
                                       'metric',
                                       'query',
                                       'resource_type'])
        return rule

    @classmethod
    def validate_alarm(cls, alarm):
        super(AggregationMetricByResourcesLookupRule,
              cls).validate_alarm(alarm)

        rule = alarm.gnocchi_aggregation_by_resources_threshold_rule

        # check the query string is a valid json
        try:
            query = jsonutils.loads(rule.query)
        except ValueError:
            raise wsme.exc.InvalidInput('rule/query', rule.query)

        # Scope the alarm to the project id if needed
        auth_project = v2_utils.get_auth_project(alarm.project_id)
        if auth_project:
            rule.query = jsonutils.dumps({
                "and": [{"=": {"created_by_project_id": auth_project}},
                        query]})

        # Delegate the query validation to gnocchi
        ks_client = keystone_client.get_client(pecan.request.cfg)
        request = {
            'url': "%s/v1/aggregation/resource/%s/metric/%s" % (
                pecan.request.cfg.gnocchi_url,
                rule.resource_type,
                rule.metric),
            'headers': {'Content-Type': "application/json",
                        'X-Auth-Token': ks_client.auth_token},
            'params': {'aggregation': rule.aggregation_method,
                       'needed_overlap': 0},
            'data': rule.query,
        }

        try:
            r = requests.post(**request)
        except requests.ConnectionError as e:
            raise GnocchiUnavailable(e)
        if r.status_code // 200 != 1:
            raise base.ClientSideError(r.content, status_code=r.status_code)


class AggregationMetricsByIdLookupRule(AlarmGnocchiThresholdRule):
    metrics = wsme.wsattr([wtypes.text], mandatory=True)
    "A list of metric Ids"

    def as_dict(self):
        rule = self.as_dict_from_keys(['granularity', 'comparison_operator',
                                       'threshold', 'aggregation_method',
                                       'evaluation_periods',
                                       'metrics'])
        return rule
