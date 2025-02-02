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

"""Util functions."""

import functools
import json
import re
import sys
from pathlib import Path
from random import Random
from types import SimpleNamespace
from urllib.parse import urlparse, urlunparse

from . import dirs, epr
from .dirs import tempdir as tempdir
from .resource import resource as resource

random = Random()
wc_re = re.compile(r"\*|\?")


def has_wildcards(s):
    if isinstance(s, str):
        return bool(wc_re.search(s))


def expand_wildcards(s, alphabet, min_star_len, max_star_len):
    if not isinstance(s, str):
        return s
    chars = []
    for c in s:
        if c == "?":
            chars.append(random.choice(alphabet))
        elif c == "*":
            chars.extend(random.choices(alphabet, k=random.randint(min_star_len, max_star_len)))
        else:
            chars.append(c)
    return "".join(chars)


@functools.lru_cache
def load_schema(uri, path, basedir=None):
    from ruamel.yaml import YAML

    with resource(uri, basedir=basedir, cachedir=dirs.cache) as resource_dir:
        with open(resource_dir / path) as f:
            yaml = YAML(typ="safe")
            return yaml.load(f)


def load_integration_schema(name, kibana_version):
    from ruamel.yaml import YAML

    conditions = {}
    if kibana_version and str(kibana_version) != "serverless":
        if str(kibana_version).endswith("-SNAPSHOT"):
            kibana_version = str(kibana_version)[: -len("-SNAPSHOT")]
        conditions["kibana.version"] = kibana_version

    e = epr.EPR(timeout=17, tries=3)
    res = e.search_package(name, **conditions)
    uri = urlunparse(urlparse(e.url)._replace(path=res[0]["download"]))

    def is_array(tree):
        return "example" in tree and isinstance(json.loads(tree["example"]), list)

    def field_schema(tree, path=()):
        path = path + (tree["name"],)
        if tree["type"] == "group":
            try:
                fields = tree["fields"]
            except KeyError:
                fields = tree["field"]
            for tree in fields:
                yield from field_schema(tree, path)
        else:
            schema = {"type": tree["type"]}
            if is_array(tree):
                schema["normalize"] = ["array"]
            yield ".".join(path), schema

    schema = {}
    with resource(uri, cachedir=dirs.cache) as resource_dir:
        for fields_yml in resource_dir.glob("**/fields.yml"):
            with open(fields_yml) as f:
                schema.update({field: schema for tree in YAML(typ="safe").load(f) for field, schema in field_schema(tree)})
    return schema


@functools.lru_cache
def load_rules(uri, paths=None, basedir=None, *, timeout=17, tries=3):
    version = None
    uri_parts = urlparse(uri)
    if uri_parts.hostname == "epr.elastic.co":
        import requests

        for n in range(tries):
            try:
                res = requests.get(uri, timeout=timeout)
                break
            except requests.exceptions.ConnectTimeout:
                if n == tries - 1:
                    raise

        res.raise_for_status()
        res = res.json()

        if uri_parts.path == "/search":
            if len(res) != 1:
                raise ValueError(f"Wrong number of packages: {len(res)}")
            uri_parts = uri_parts._replace(path=res[0]["download"], query="")
            uri = urlunparse(uri_parts)
            version = res[0]["version"]
        elif uri_parts.path.startswith("/package/security_detection_engine/"):
            uri_parts = uri_parts._replace(path=res["download"], query="")
            uri = urlunparse(uri_parts)
            version = res["version"]

    with resource(uri, basedir=basedir, cachedir=dirs.cache) as resource_dir:
        is_package = (resource_dir / "manifest.yml").exists()

        if paths is None:
            paths = "kibana/security_rule/*.json" if is_package else "rules/**/*.toml"
        if isinstance(paths, str):
            paths = (paths,)

        if is_package:
            files = {}
            for path in paths:
                for filepath in resource_dir.glob(path):
                    rule_id, *rule_rev = filepath.stem.split("_")
                    rule_rev = int(rule_rev[0]) if rule_rev else 0
                    try:
                        if rule_rev > files[rule_id][0]:
                            files[rule_id] = (rule_rev, filepath)
                    except KeyError:
                        files[rule_id] = (rule_rev, filepath)
            filenames = (filename for _, filename in files.values())
            import json
        else:
            filenames = (filename for path in paths for filename in resource_dir.glob(path))
            import pytoml

        rules = []
        for filename in filenames:
            with open(filename) as f:
                if is_package:
                    rule = json.load(f)["attributes"]
                else:
                    rule = pytoml.load(f)["rule"]
            rule["path"] = Path(".").joinpath(*Path(filename).relative_to(resource_dir).parts[1:])
            rules.append(SimpleNamespace(**rule))
    return version, rules


def deep_merge(a, b, path=None, *, overwrite=False):
    """Recursively merge two dictionaries"""

    for key in b:
        if key in a:
            path = (path or []) + [str(key)]
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                deep_merge(a[key], b[key], path, overwrite=overwrite)
            elif isinstance(a[key], list) and isinstance(b[key], list):
                a[key].extend(x for x in b[key] if x not in a[key])
            elif overwrite:
                a[key] = b[key]
            elif a[key] != b[key]:
                raise ValueError(f"Destination field already exists: {'.'.join(path)} ('{a[key]}' != '{b[key]}')")
        else:
            a[key] = b[key]
    return a


def remove_none_fields(doc):
    for field, value in list(doc.items()):
        if isinstance(value, dict):
            remove_none_fields(value)
            if not value:
                del doc[field]
        elif value is None:
            del doc[field]


class TreeTraverser:
    """Automatic dispatching of node accessors."""

    def __init__(self):
        self.traversers = {}

    class NodeTraverser:
        def __init__(self, traversers, node_type):
            self.traversers = traversers
            self.node_type = node_type
            self.successful = 0
            self.total = 0

        def __call__(self, func):
            if self.node_type in self.traversers:
                raise ValueError(f"Duplicate traverser for {self.node_type}: {func.__name__}")
            self.traversers[self.node_type] = self

            @functools.wraps(func)
            def traverse(*args, **kwargs):
                self.total += 1
                ret = func(*args, **kwargs)
                self.successful += 1
                return ret

            self.traverse = traverse
            return traverse

    def __call__(self, node_type):
        return self.NodeTraverser(self.traversers, node_type)

    def traverse(self, node, *args, **kwargs):
        return self.traversers[type(node)].traverse(node, *args, **kwargs)

    def get_stats(self):
        return {k.__name__: (v.successful, v.total) for k, v in self.traversers.items()}


def split_path(field):
    return list(p[1:-1] if len(p) > 1 and p.startswith("`") and p.endswith("`") else p for p in field.split("."))


if sys.version_info >= (3, 12):
    from itertools import batched
else:
    from itertools import islice

    def batched(iterable, chunk_size):
        iterator = iter(iterable)
        while chunk := list(islice(iterator, chunk_size)):
            yield chunk


def str_to_bool(s):
    ls = s.lower()
    if ls in ("true", "yes", "on", "1"):
        return True
    if ls in ("false", "no", "off", "0"):
        return False
    raise ValueError(f"Invalid boolean string: {s}")
