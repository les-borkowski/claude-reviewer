package shop;

import java.util.List;

public class Checkout {
    public long total(List<Order> orders) {
        return orders.stream().mapToLong(Order::totalCents).sum();
    }
}
