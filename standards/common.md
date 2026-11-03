# Common rules (all languages)

## Never cut

A simplification that removes any of these is wrong, however short it makes
the code:

- validation of input that crosses a trust boundary (HTTP, CLI, files, env, queues)
- error handling that prevents data loss or corruption
- security checks: auth, permissions, escaping, secrets handling
- accessibility: labels, roles, keyboard handling
- behaviour the change was asked to add

## Rules

### CM-01 Dead code
**Flag when:** the change adds a function, branch, parameter, export or file
that nothing calls or reads.
**Not a finding when:** it is a public API, an entry point, or wired by a
framework (decorators, DI, reflection, routing by name).
**Fix:** delete it.

### CM-02 Speculative flexibility
**Flag when:** a new option, flag, config key, parameter with a default, or
hook that no caller sets to anything but the default.
**Not a finding when:** the task asked for it, or a caller in the same change
uses it.
**Fix:** hard-code the one value; add the option when a second caller appears.

### CM-03 Pass-through wrapper
**Flag when:** a function, class or module only forwards its arguments to
another one, adding no logic, validation or naming value.
**Not a finding when:** it is a seam the repo uses on purpose (a port to an
external service, a test double point documented as such).
**Fix:** call the wrapped thing directly.

### CM-04 Reinvented helper
**Flag when:** the change writes logic that already exists in the repo, the
standard library, or an already-installed dependency.
**Not a finding when:** the existing one has different semantics that matter
here (say which).
**Fix:** name the existing path/function and use it.

### CM-05 New dependency for a few lines
**Flag when:** the change adds a package to do what a few lines or the
standard library can do.
**Not a finding when:** the problem is genuinely hard (dates/time zones,
crypto, parsing a real grammar, HTML sanitising).
**Fix:** the stdlib call or the few lines.

### CM-06 Defensive checks on impossible states
**Flag when:** null/None/undefined checks, type checks or try/catch around
values the code or the type system already guarantees.
**Not a finding when:** the value crosses a trust boundary (see Never cut).
**Fix:** delete the check.

### CM-07 Catch that adds nothing
**Flag when:** a catch block only re-raises, logs and re-raises, or swallows
and returns a default that hides the failure.
**Not a finding when:** it converts the error into the type the caller
expects, adds context the caller needs, or is a top-level handler.
**Fix:** remove the try/catch, or let it propagate.

### CM-08 Comments that restate the code
**Flag when:** comments or docstrings say what the next line does, repeat the
function name, or narrate the change ("now we loop over items").
**Not a finding when:** they explain *why*, a non-obvious constraint, or a
public API contract.
**Fix:** delete; keep only the why.

### CM-09 Duplicated near-copies
**Flag when:** the change adds two or more blocks that differ only in a value
or two and must change together.
**Not a finding when:** they are expected to diverge (say why), or merging
them needs a flag parameter that makes the result harder to read.
**Fix:** one function or a loop over the varying values.

### CM-10 Abstraction with one user
**Flag when:** a new interface, base class, factory, registry, strategy or
generic type with exactly one implementation or call site.
**Not a finding when:** the repo's architecture requires it (documented layer
boundary), or a second implementation exists in tests as a real fake.
**Fix:** use the concrete thing.
