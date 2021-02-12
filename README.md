# Configuration generator
This Python package lets you quickly generate non-trivial matrices of configuration parameters
from a declarative description (think cartesian product on steroids). It enables you to build
complex Python objects from a simple declarative description. It's useful for generating configuration
inputs for hyperparameter search, complex experiments with lots of input parameters, etc.

## Installation
```bash
$ pip3 install .
```

## Usage
You provide a dictionary containing JSON-like objects (numbers, strings, bools,
lists, tuples and dictionaries are allowed), called a template. `cfggen` will then process the
template and generate a Python object.

The main function that builds templates is called `build_template`. Often you may want to write
the template in a JSON(5) or YAML file, in that case you can use `build_template_from_file`.

By default, the function it will simply return the input template:

```python
from cfggen import build_template

configurations = build_template({
    "batch_size": 128,
    "learning_rate": 0.1
})
# { "batch_size": 128, "learning_rate": 0.1 }
```

To build more complex combinations, the builder supports special **operators**
(similar to [MongoDB operators](https://docs.mongodb.com/manual/reference/operator/query/)).

An operator is a dictionary with a single key starting with `$`. The value associated with the
key contains parameters for the operator. The operator will return a Python object after it is
evaluated by the builder. Operators can be arbitrarily nested.

### Integer range
`$range: int | list[int]`
  
Evaluates to a list of numbers, similarly to the built-in `range` function.
```python
build_template({"$range": 3})         # [0, 1, 2]
build_template({"$range": [1, 7, 2]}) # [1, 3, 5]
```

### Reference to another key
`$ref: str`

Evaluates to the value of a top level key in the input template. It is useful when you want
to use a specific key multiple times, but you want to define it only once.
```python
build_template({
    "graphs": ["a", "b", "c"],
    "bfs": {
        "algorithm": "bfs",
        "graphs": {"$ref": "graphs"}
    },
    "dijkstra": {
        "algorithm": "dijkstra",
        "graphs": {"$ref": "graphs"}
    }
})
"""
{
    "graphs": ["a", "b", "c"],
    "bfs": {
        "algorithm": "bfs",
        "graphs": ["a", "b", "c"]
    },
    "dijkstra": {
        "algorithm": "dijkstra",
        "graphs": ["a", "b", "c"]
    }
}
"""
```

### Cartesian product
`$product: dict[str, iterable] | list[iterable]`

Evaluates to a list containing a cartesian product of the input parameters.
If the input parameter is a list of iterables, it behaves like `list(itertools.product(*params))`.
You can combine this with other operators to e.g. build cartesian products with "holes" (i.e. some
combinations might be missing).

```python
build_template({
    "$product": [[1, 2], ["a", "b"]]
})
# [(1, "a"), (1, "b"), (2, "a"), (2, "b")]
```

If the value is a dictionary, it will evaluate to a list of dictionaries with the same
keys, with the values forming the cartesian product:
```python
build_template({
    "$product": {
        "batch_size": [32, 64],
        "learning_rate": [0.01, 0.1]
    }
})
"""
[
    {"batch_size": 32, "learning_rate": 0.01},
    {"batch_size": 32, "learning_rate": 0.1},
    {"batch_size": 64, "learning_rate": 0.01},
    {"batch_size": 64, "learning_rate": 0.1}
]
"""
```

When you nest other operators inside a `$product`, each element of the inner operator will be
evaluated as a single element of the outer product:
```python
build_template({
    "$product": {
        "a": {
            "$product": {
                "x": [3, 4],
                "y": [5, 6]
            }
        },
        "b": [1, 2]
    }
})
"""
[
    {"a": {"x": 3, "y": 5}, "b": 1},
    {"a": {"x": 3, "y": 5}, "b": 2},
    {"a": {"x": 3, "y": 6}, "b": 1},
    {"a": {"x": 3, "y": 6}, "b": 2},
    {"a": {"x": 4, "y": 5}, "b": 1},
    {"a": {"x": 4, "y": 5}, "b": 2},
    {"a": {"x": 4, "y": 6}, "b": 1},
    {"a": {"x": 4, "y": 6}, "b": 2}
]
"""
```

If you instead want to materialize the inner operator first and use its final value as a single
element of the product, simply wrap the nested operator in a list:

```python
build_config({
    "$product": {
        "a": [{
            "$product": {
                "x": [3, 4],
                "y": [5, 6]
            }
        }],
        "b": [1, 2]
    }
})
"""
[
    {"a": [{"x": 3, "y": 5}, {"x": 3, "y": 6}, {"x": 4, "y": 5}, {"x": 4, "y": 6}], "b": 1},
    {"a": [{"x": 3, "y": 5}, {"x": 3, "y": 6}, {"x": 4, "y": 5}, {"x": 4, "y": 6}], "b": 2}
]
"""
```

### Variable interpolation
```
$env: {
    name: str,
    default: any,                           (optional)
    type: "int" | "float" | "str" | "bool"  (optional)
}
```

The `build_template` function takes an environment parameter, which should be a dictionary. If
nothing is passed to it, it will use environment variables (`os.environ`) as the environment.

This operator evalutes to a variable with the given key from the input environment. You can specify
a `default` value if the key is missing, and a type constructor to convert the value to the target
type (useful especially if environment variables are used as the input environment).

```python
build_template({
    "a": {"$env": { "name": "FOO", "type": "int" }},
    "b": {"$env": { "name": "BAR", "default": 42 }}
}, environment={"FOO": "1"})
# { "a": 1, "b": 42 }
```

### List concatenation
`$+: list[iterable]`

Evaluates to a concatenation of its input parameters (i.e. behaves like
`list(itertools.chain.from_iterable(params))`). It is useful to concatenate output which is
dynamically generated by other operators.

In this example you can see how it can be combined with a nested `$ref` operator.
```python
build_template({
    "small_graphs": ["a", "b"],
    "large_graphs": ["c", "d"],
    "graphs": {"$+": [{"$ref": "small_graphs"}, {"$ref": "large_graphs"}]}
})
"""
{
    "small_graphs": ["a", "b"],
    "large_graphs": ["c", "d"],
    "graphs": ["a", "b", "c", "d"]
}
"""
```

### Zip
`$zip: list[iterable]`

Evaluates to a list of zipped values from the input parameters, i.e. behaves like `list(zip(*params))`.
```python
build_template({
    "a": {"$zip": [[1, 2], ["a", "b"]]}
})
"""
{
    "a": [(1, "a"), (2, "b")]
}
```

## Merging multiple templates
Often it is useful to define your parametrization in multiple templates (files) and combine them
together to avoid frequently changing a single large template file. You can use the function
`merge_templates` to merge several templates together. A template which appears later in the list
will overwrite the top-level keys of the templates that precede it. Note that merging happens on the
level of templates, i.e. before operators are evaluated.

```python
from cfggen import merge_templates

inputs_template = {
    "inputs": [1, 2],
    "experiments": {
        "$product": {
            "inputs": {"$ref": "inputs"},
            "machines": {"$ref": "machines"}
        }
    }
}
small_machines_template = {"machines": [{"cpus": 4}]}
large_machines_template = {"machines": [{"cpus": 24}]}

conf_a = merge_templates([inputs_template, small_machines_template])
"""
{
    "inputs": [1, 2],
    "experiments": [{
        "inputs": 1,
        "machines": {"cpus": 4}
    }, {
        "inputs": 2,
        "machines": {"cpus": 4}
    }],
    "machines": [{"cpus": 4}]
}
"""

conf_b = merge_templates([inputs_template, large_machines_template])
"""
{
    "inputs": [1, 2],
    "experiments": [{
        "inputs": 1,
        "machines": {"cpus": 24}
    }, {
        "inputs": 2,
        "machines": {"cpus": 24}
    }],
    "machines": [{"cpus": 24}]
}
"""
```
