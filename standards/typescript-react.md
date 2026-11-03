# TypeScript and React rules

Out of scope (tsc, eslint, eslint-plugin-react-hooks, prettier cover these):
unused vars/imports, formatting, missing hook deps, `any` where lint bans it.

## TypeScript

### TS-01 Types that repeat inference or other types
**Flag when:** explicit annotations on values TS infers exactly, or a new
interface that copies fields of an existing type.
**Not a finding when:** it is an exported function's return type, or the
annotation narrows/widens on purpose.
**Fix:** drop the annotation; derive with `Pick`/`Omit`/`typeof`/`ReturnType`.

### TS-02 Enum or class where a union or object works
**Flag when:** a new `enum` used only as string values, or a class with only
static members.
**Not a finding when:** the repo standardises on enums.
**Fix:** a string literal union, or plain functions in a module.

### TS-03 Hand-rolled platform or stdlib
**Flag when:** code rebuilding `structuredClone`, `URLSearchParams`, `Intl`
formatting, `Array.prototype.flatMap/at/findLast`, `Object.groupBy`,
`AbortController` timeouts, or a lodash-style util the repo already has.
**Not a finding when:** the target runtime lacks it (check browserslist /
`tsconfig` lib).
**Fix:** the built-in.

### TS-04 Casts and non-null assertions to silence the compiler
**Flag when:** `as Foo`, `as unknown as`, or `!` added where a narrowing
check or a correct type would do.
**Not a finding when:** data from outside the program right after runtime
validation (zod etc.).
**Fix:** narrow or fix the type at the source.

## React

### RE-01 Derived state in useState + useEffect
**Flag when:** state that is computed from props or other state and kept in
sync by an effect.
**Not a finding when:** the value is expensive *and* measured slow, or must
persist across prop changes on purpose.
**Fix:** compute during render.
```tsx
// before
const [fullName, setFullName] = useState("");
useEffect(() => setFullName(`${first} ${last}`), [first, last]);
// after
const fullName = `${first} ${last}`;
```

### RE-02 Effect used as an event handler
**Flag when:** a `useEffect` that reacts to a state flag set by a click or
submit (`if (submitted) { post(); }`).
**Not a finding when:** syncing with an external system (subscription, DOM
API, timer) that is not tied to one event.
**Fix:** do the work in the handler.

### RE-03 Reflexive memoisation
**Flag when:** `useMemo`/`useCallback`/`React.memo` around cheap work or for
a child that is not memoised. (Also when the repo uses the React Compiler.)
**Not a finding when:** a measured hot path, or the value is a dependency of
an effect/memoised child that must stay stable.
**Fix:** plain value or function.

### RE-04 Wrapper component that only forwards props
**Flag when:** a component that renders one other component and passes its
props through unchanged or with a fixed value.
**Not a finding when:** it is the repo's design-system layer or adds
behaviour (a11y, error boundary).
**Fix:** use the inner component directly.

### RE-05 Custom hook with one caller and no logic
**Flag when:** `useFoo()` that wraps a single `useState`/`useContext` or is
used by one component.
**Not a finding when:** it hides real logic or is shared.
**Fix:** inline into the component.

### RE-06 Hand-built native control
**Flag when:** custom dropdown/date picker/modal/tooltip when `<select>`,
`<input type="date">`, `<dialog>` or the repo's component library does it.
**Not a finding when:** the design requirement cannot be met natively (say
which).
**Fix:** the native element or the house component.

### RE-07 Fetch logic duplicated in components
**Flag when:** loading/error/data state and `fetch` written by hand in a
component when the repo has an API client or a data hook (React Query, SWR,
a `useApi` helper).
**Not a finding when:** the repo has no such layer.
**Fix:** the existing client/hook.
