# Java rules

Out of scope (compiler, checkstyle, PMD, SpotBugs, IDE inspections cover
these): unused imports, formatting, naming style, raw types.

### JV-01 Interface with one implementation
**Flag when:** a new `FooService` interface plus `FooServiceImpl`, and
nothing else implements it.
**Not a finding when:** it is a module/API boundary, a framework needs a
proxy interface, or a test provides a real second implementation.
**Fix:** one concrete class.

### JV-02 Factory, builder or manager for a simple object
**Flag when:** a `Factory`, hand-written `Builder`, `Manager` or `Helper`
class that only calls one constructor or holds static methods for one caller.
**Not a finding when:** construction has real choices or many optional
parameters used by several callers.
**Fix:** the constructor, a static factory method, or a record.

### JV-03 Data class that should be a record
**Flag when:** a class with private final fields, a constructor, getters,
`equals`/`hashCode`/`toString`, and no behaviour (Java 16+).
**Not a finding when:** a framework needs a mutable bean (JPA entity,
some serialisers) or the project targets Java < 16.
**Fix:** `record`. (Lombok `@Value` if the repo already uses Lombok.)

### JV-04 Hand-rolled stdlib
**Flag when:** loops that rebuild `Collectors.groupingBy/toMap/joining`,
`Map.computeIfAbsent/merge/getOrDefault`, `List.of`, `Objects.equals/hash/
requireNonNullElse`, `Optional.map/orElse`, `String.join`, `Files.readString`.
**Not a finding when:** the loop is clearer than the stream (several
side effects, checked exceptions per item).
**Fix:** the library call.
```java
// before
Map<String, List<Order>> byUser = new HashMap<>();
for (Order o : orders) {
    byUser.computeIfAbsent(o.user(), k -> new ArrayList<>()).add(o);
}
// after
var byUser = orders.stream().collect(groupingBy(Order::user));
```

### JV-05 Optional misuse
**Flag when:** `Optional` as a field or parameter, `isPresent()` + `get()`,
or wrapping a value only to unwrap it on the next line.
**Not a finding when:** it is a return type of a lookup that can miss.
**Fix:** `map`/`orElse`/`ifPresent`, or a plain nullable with a check.

### JV-06 Checked exception wrapping chain
**Flag when:** catch-and-rethrow as a new custom exception at every layer
with no added context.
**Not a finding when:** the layer translates to an API error type or adds
context (ids, operation).
**Fix:** let it propagate, or one translation at the boundary.

### JV-07 Constants class and enums for one value
**Flag when:** a `Constants` class or enum created for a value used once.
**Not a finding when:** the value is shared or is a closed set used in a
`switch`.
**Fix:** inline it, or a `private static final` next to its use.

### JV-08 Javadoc that restates signatures
**Flag when:** `@param id the id`, `@return the result`, or Javadoc on
private methods that repeats the name.
**Not a finding when:** public API docs that state contracts (nullability,
thread safety, units, exceptions).
**Fix:** delete.

### JV-09 Spring/DI ceremony
**Flag when:** a `@Configuration` bean method that only calls `new` for a
class that could be `@Component`, or field injection plus setters added
alongside constructor injection.
**Not a finding when:** the bean needs third-party construction or the repo
standardises on explicit config.
**Fix:** annotate the class, use constructor injection only.
