type Item = { name: string; price: number; qty: number };

export function App({ items }: { items: Item[] }) {
  return (
    <ul>
      {items.map((i) => (
        <li key={i.name}>
          {i.name} × {i.qty}
        </li>
      ))}
    </ul>
  );
}
