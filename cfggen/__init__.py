import collections
import itertools
import logging
import os
from collections.abc import Iterable

_State = collections.namedtuple("State", ["toplevel", "computed", "resolving", "environment"])


def _check_type_all(iterable, type):
    for item in iterable:
        if not isinstance(item, type):
            return False
    return True


def _is_list_like(item):
    return isinstance(item, list) or isinstance(item, tuple)


def _resolve_ref(state, key):
    assert isinstance(key, str)
    value = state.computed.get(key)
    if value is None:
        if key in state.resolving:
            raise Exception("Ref cycle detected: {}".format(key))
        state.resolving.add(key)
        value = _resolve(state, state.toplevel[key])
        state.resolving.remove(key)
        state.computed[key] = value
    return value


def _resolve_range(state, args):
    if isinstance(args, int):
        return list(range(args))
    elif _is_list_like(args) and 2 <= len(args) <= 3:
        return list(range(*args))
    raise Exception("Invalid argument for range")


def _map_list_like(state, iterable):
    assert _is_list_like(iterable)
    constructor = type(iterable)
    return constructor((_resolve(state, item) for item in iterable))


def _resolve_concat(state, args):
    assert isinstance(args, Iterable)
    items = _map_list_like(state, args)
    assert _check_type_all(items, Iterable)
    return type(items)(itertools.chain.from_iterable(items))


def _resolve_product(state, args):
    args = _resolve(state, args)
    if _is_list_like(args):
        args = _map_list_like(state, args)
        assert _check_type_all(args, list) or _check_type_all(args, tuple)
        return list(itertools.product(*args))
    elif isinstance(args, dict):
        values = _map_list_like(state, tuple(args.values()))
        assert _check_type_all(values, Iterable)
        return [dict(zip(args.keys(), items)) for items in itertools.product(*values)]
    else:
        raise Exception("Invalid argument of product")


def _resolve_zip(state, args):
    assert _is_list_like(args)

    items = [_resolve(state, item) for item in args]
    assert _check_type_all(items, list) or _check_type_all(items, tuple)
    return list(zip(*items))


ENV_CONSTRUCTORS = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool
}


def _resolve_env(state, args):
    default = None
    constructor = "str"

    if isinstance(args, str):
        key = args
    elif isinstance(args, dict):
        key = args["name"]
        default = args.get("default")
        constructor = args.get("type", constructor)
        if constructor not in ENV_CONSTRUCTORS:
            raise Exception(f"Unknown type {constructor}")
    else:
        raise Exception("Invalid $env parameter, use string or a dictionary")

    value = state.environment.get(key)
    if value is None:
        if default is not None:
            return default
        raise Exception(f"Key {key} not found in environment and no default was provided")

    return ENV_CONSTRUCTORS[constructor](value)


OPS_SWITCH = {
    "$ref": _resolve_ref,
    "$range": _resolve_range,
    "$+": _resolve_concat,
    "$product": _resolve_product,
    "$zip": _resolve_zip,
    "$env": _resolve_env,
}


def _resolve(state, value):
    if isinstance(value, dict) and len(value) == 1:
        key = tuple(value.keys())[0]
        fn = OPS_SWITCH.get(key)
        if fn is not None:
            return fn(state, value[key])

    if _is_list_like(value):
        return [_resolve(state, item) for item in value]
    elif isinstance(value, dict):
        return {key: _resolve(state, item) for (key, item) in value.items()}
    return value


def build_template(template, environment=None):
    env = environment or os.environ.copy()
    state = _State(template, {}, set(), env)
    return _resolve(state, template)


def merge_templates(templates, environment=None):
    base_template = templates[0]
    for template in templates[1:]:
        base_template.update(template)
    return build_template(base_template, environment=environment)


def build_template_from_file(path: str, environment=None):
    data = load_template_from_file(path)
    return build_template(data, environment=environment)


def load_template_from_file(path: str):
    extension = os.path.splitext(path)[1]
    with open(path) as f:
        if extension in (".json", ".json5"):
            try:
                import json5 as json
            except ImportError:
                logging.warning("json5 could not be imported, defaulting to json")
                import json
            return json.load(f)
        elif extension in (".yml", ".yaml"):
            import yaml
            return yaml.safe_load(f)
        else:
            raise Exception(f"Invalid extension {extension}")
