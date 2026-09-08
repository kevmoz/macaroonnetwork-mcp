"""Acceptance predicate language (see specs/S2.2-predicate-language.md).

Pure and deterministic: no network, no filesystem, no `datetime.now()` in
`evaluate()` — `as_of` is the only time source, ever. This is load-bearing
for S2.3, which commits to a `predicate_hash` before paying; a non-
deterministic evaluator would make that commitment meaningless.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from hashlib import sha256
from numbers import Number
from typing import Any

from jsonpath_ng.ext import parse as jsonpath_parse

MAX_DEPTH = 8
MAX_NODES = 64
MAX_RESULT_SET = 10_000

_LEAF_TYPES = {"count_gte", "contains_all", "within", "field_changed"}
_COMPOSITE_TYPES = {"all", "any", "not"}
_COMPARATORS = {"eq", "lt", "lte", "gt", "gte", "in"}


class PredicateTooComplex(Exception):
    """Raised when a predicate exceeds MAX_DEPTH, MAX_NODES, or a JSONPath
    result set exceeds MAX_RESULT_SET. Never evaluated in this case."""


def _jsonpath_values(payload: dict, field: str) -> list[Any]:
    matches = jsonpath_parse(field).find(payload)
    if len(matches) > MAX_RESULT_SET:
        raise PredicateTooComplex(f"JSONPath {field!r} matched more than {MAX_RESULT_SET} items")
    return [match.value for match in matches]


def _check_complexity(predicate: dict, depth: int, node_count: list[int]) -> None:
    if depth > MAX_DEPTH:
        raise PredicateTooComplex(f"predicate depth exceeds {MAX_DEPTH}")
    node_count[0] += 1
    if node_count[0] > MAX_NODES:
        raise PredicateTooComplex(f"predicate has more than {MAX_NODES} nodes")

    node_type = predicate.get("type")
    if node_type == "all" or node_type == "any":
        for condition in predicate.get("conditions", []):
            _check_complexity(condition, depth + 1, node_count)
    elif node_type == "not":
        _check_complexity(predicate.get("condition", {}), depth + 1, node_count)


def _eval_count_gte(predicate: dict, payload: dict, as_of: datetime) -> bool:
    values = _jsonpath_values(payload, predicate["field"])
    if not values:
        return False
    # A single JSONPath match on an array field returns that array itself.
    items = values[0] if len(values) == 1 and isinstance(values[0], list) else values
    return len(items) >= predicate["value"]


def _eval_contains_all(predicate: dict, payload: dict, as_of: datetime) -> bool:
    required = predicate["values"]
    if not required:
        return True  # vacuously true
    values = _jsonpath_values(payload, predicate["field"])
    if not values:
        return False
    return all(item in values for item in required)


def _eval_within(predicate: dict, payload: dict, as_of: datetime) -> bool:
    values = _jsonpath_values(payload, predicate["field"])
    if not values:
        return False
    try:
        field_time = datetime.fromisoformat(str(values[0]).replace("Z", "+00:00"))
    except ValueError:
        return False
    if field_time.tzinfo is None:
        field_time = field_time.replace(tzinfo=as_of.tzinfo)
    return abs(as_of - field_time) <= timedelta(hours=predicate["duration_hours"])


def _compare(operator: str, field_value: Any, target: Any) -> bool:
    if operator == "eq":
        return field_value == target
    if operator == "in":
        return field_value in target
    if operator in {"lt", "lte", "gt", "gte"}:
        if not isinstance(field_value, Number) or isinstance(field_value, bool):
            return False
        if not isinstance(target, Number) or isinstance(target, bool):
            return False
        if operator == "lt":
            return field_value < target
        if operator == "lte":
            return field_value <= target
        if operator == "gt":
            return field_value > target
        return field_value >= target
    raise ValueError(f"unsupported operator: {operator}")


def _eval_field_changed(predicate: dict, payload: dict, as_of: datetime) -> bool:
    values = _jsonpath_values(payload, predicate["field"])
    if not values:
        return False
    return _compare(predicate["operator"], values[0], predicate["value"])


_LEAF_EVALUATORS = {
    "count_gte": _eval_count_gte,
    "contains_all": _eval_contains_all,
    "within": _eval_within,
    "field_changed": _eval_field_changed,
}


def _eval(predicate: dict, payload: dict, as_of: datetime) -> bool:
    node_type = predicate.get("type")

    if node_type == "all":
        return all(_eval(cond, payload, as_of) for cond in predicate.get("conditions", []))
    if node_type == "any":
        return any(_eval(cond, payload, as_of) for cond in predicate.get("conditions", []))
    if node_type == "not":
        return not _eval(predicate["condition"], payload, as_of)

    evaluator = _LEAF_EVALUATORS.get(node_type)
    if evaluator is None:
        raise ValueError(f"unknown predicate type: {node_type!r}")
    return evaluator(predicate, payload, as_of)


def evaluate(predicate: dict, payload: dict, as_of: datetime) -> bool:
    """Evaluate `predicate` against `payload` as of `as_of`. Pure + deterministic."""
    _check_complexity(predicate, depth=0, node_count=[0])
    return _eval(predicate, payload, as_of)


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def predicate_hash(predicate: dict) -> str:
    """SHA-256 hex of the canonical (sorted-keys, no-whitespace) serialisation.

    Order-insensitive: semantically identical predicates with differently
    ordered keys hash identically.
    """
    canonical = json.dumps(_canonicalize(predicate), sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()
