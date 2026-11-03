# Python rules

Out of scope (ruff, mypy/pyright cover these): unused imports, formatting,
naming style, bare `except`, mutable default arguments.

### PY-01 Class that should be a function
**Flag when:** a class has `__init__` plus one method, or only static methods.
**Not a finding when:** it holds state across calls, or a framework needs a
class (Pydantic model, Django view, pytest class grouping used in the repo).
**Fix:** a module-level function.

### PY-02 Hand-rolled stdlib
**Flag when:** loops that rebuild `collections.Counter`, `defaultdict`,
`itertools.groupby/chain/batched`, `functools.cache`, `pathlib`,
`dataclasses`, `enumerate`, `zip`, `any`/`all`, `sum`, `sorted(key=...)`.
**Not a finding when:** the loop does something the builtin cannot (early
exit with side effects, custom error per item).
**Fix:** the builtin.
```python
# before
counts = {}
for w in words:
    counts[w] = counts.get(w, 0) + 1
# after
counts = Counter(words)
```

### PY-03 Manual boilerplate a dataclass/model already gives
**Flag when:** hand-written `__init__`, `__eq__`, `__repr__` or `to_dict` on
a plain data holder.
**Not a finding when:** the method does real work (validation, derived
fields not expressible with `field`/validators).
**Fix:** `@dataclass` or the repo's Pydantic model.

### PY-04 Getters and setters
**Flag when:** `get_x()`/`set_x()` methods or a `@property` that only returns
`self._x`.
**Not a finding when:** the property computes, validates, or is part of a
public API that must stay stable.
**Fix:** a plain attribute.

### PY-05 Redundant conversions
**Flag when:** `list(...)` around something only iterated once, `str()` on a
str, `dict(**d)` copies nobody mutates, `bool(x)` in an `if`.
**Not a finding when:** the copy prevents mutation of shared data.
**Fix:** drop the conversion.

### PY-06 Exception class per call site
**Flag when:** the change adds a custom exception used in one place and
caught nowhere specifically.
**Not a finding when:** a caller catches it by type, or it maps to an API
error code.
**Fix:** raise the closest builtin (`ValueError`, `LookupError`, ...).

### PY-07 Over-typed internals
**Flag when:** `TypeVar`/`Generic`/`Protocol` or `TypedDict` introduced for a
helper with one caller and one concrete type.
**Not a finding when:** it is a public or shared API, or the repo's typing
policy requires it.
**Fix:** the concrete type.

### PY-08 Logging noise
**Flag when:** log lines at entry/exit of functions, or logging values the
caller already logs.
**Not a finding when:** it records a decision, a retry, or a failure that is
otherwise silent.
**Fix:** delete.

### PY-09 Async for nothing
**Flag when:** `async def` with no `await` inside, called only from sync code
via `asyncio.run`, or `await` on a function that is sync work.
**Not a finding when:** the framework requires the signature (FastAPI
dependency style chosen by the repo).
**Fix:** a plain `def`.
