# Licensed to Elasticsearch B.V. under one or more contributor
# license agreements. See the NOTICE file distributed with
# this work for additional information regarding copyright
# ownership. Elasticsearch B.V. licenses this file to you under
# the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# 	http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""Test emitter with rules."""

import os
import unittest

import tests.utils as tu
from geneve.events_emitter import SourceEvents, ast_from_rule

from . import jupyter


class TestRules(tu.QueryTestCase, tu.SeededTestCase, unittest.TestCase):
    maxDiff = None
    nb = jupyter.Notebook()
    nb.cells.append(
        jupyter.Markdown(
            """
        # Documents generation from detection rules

        This report captures the error reported while generating documents from detection rules. Here you
        can learn what rules are still problematic and for which no documents can be generated at the moment.

        Curious about the inner workings? Read [here](signals_generation.md).
    """
        )
    )

    def parse_from_collection(self, collection):
        asts = []
        rules = []
        errors = {}
        for rule in collection:
            try:
                asts.append(ast_from_rule(rule))
                rules.append(rule)
            except Exception as e:
                errors.setdefault(str(e), []).append(rule)
                continue

        with self.nb.chapter("## Skipped rules") as cells:
            cells.append(None)
            for err in sorted(sorted(errors), key=lambda e: len(errors[e]), reverse=True):
                heading = [f"{len(errors[err])} rules:", ""]
                bullets = []
                for rule in sorted(errors[err], key=lambda r: r.name):
                    bullets.append(f"* {rule.name} ({rule.path})")
                with self.nb.chapter(f"### {err} ({len(errors[err])})") as cells:
                    cells.append(jupyter.Markdown(heading + sorted(bullets)))

        return rules, asts

    def generate_docs(self, rules, asts):
        errors = {}
        for rule, ast in zip(rules, asts):
            try:
                se = SourceEvents(self.schema)
                se.add_ast(ast)
                _ = se.emit(timestamp=False, complete=True)
            except Exception as e:
                errors.setdefault(str(e), []).append(rule)
                continue

        with self.nb.chapter("## Generation errors") as cells:
            cells.append(None)
            for err in sorted(sorted(errors), key=lambda e: len(errors[e]), reverse=True):
                heading = [f"{len(errors[err])} rules:"]
                bullets = []
                for rule in sorted(errors[err], key=lambda r: r.name):
                    bullets.append(f"* {rule.name} ({rule.path})")
                with self.nb.chapter(f"### {err} ({len(errors[err])})") as cells:
                    cells.append(jupyter.Markdown(heading + sorted(bullets)))

    def test_rules_collection(self):
        collection = sorted(tu.load_test_rules(), key=lambda x: x.name)
        rules, asts = self.parse_from_collection(collection)
        self.generate_docs(rules, asts)

    def test_unchanged(self):
        tu.assertReportUnchanged(self, self.nb, "documents_from_rules.md")


@unittest.skipIf(os.getenv("TEST_SIGNALS_RULES", "0").lower() in ("0", "false", "no", ""), "Slow online test")
class TestSignalsRules(tu.SignalsTestCase, tu.OnlineTestCase, tu.SeededTestCase, unittest.TestCase):
    maxDiff = None
    nb = jupyter.Notebook()
    nb.cells.append(
        jupyter.Markdown(
            """
        # Alerts generation from detection rules

        This report captures the detection rules signals generation coverage. Here you can
        learn what rules are supported and what not and why.

        Curious about the inner workings? Read [here](signals_generation.md).
    """
        )
    )

    def parse_from_collection(self, collection):
        rules = []
        asts = []
        for i, rule in enumerate(collection):
            index_name = "{:s}-{:03d}".format(self.index_template, i)
            test_rule = {
                "rule_id": rule.rule_id,
                "risk_score": rule.risk_score,
                "description": rule.description,
                "name": rule.name,
                "index": [index_name],
                "interval": "3s",
                "from": "now-2h",
                "severity": rule.severity,
                "type": rule.type,
                "query": rule.query,
                "language": rule.language,
                "max_signals": 200,
                "enabled": True,
                ".test_private": {
                    "index": index_name,
                },  # private test data, not sent to Kibana
            }
            try:
                asts.append(ast_from_rule(test_rule))
            except Exception:
                continue
            rules.append(test_rule)
        return rules, asts

    ack_no_signals = 5

    def test_rules(self):
        if self.get_version() < "8.2.0":
            self.ack_too_few_signals = 1  # https://github.com/elastic/kibana/issues/126822
            pre_8_2_ext = "_pre-8.2"
        else:
            pre_8_2_ext = ""

        mf_ext = f"_{self.multiplying_factor}x" if self.multiplying_factor > 1 else ""
        collection = sorted(tu.load_test_rules(), key=lambda x: x.name)
        rules, asts = self.parse_from_collection(collection)
        pending = self.load_rules_and_docs(rules, asts)
        self.check_signals(rules, pending)
        tu.assertReportUnchanged(self, self.nb, f"alerts_from_rules{pre_8_2_ext}{mf_ext}.md")
