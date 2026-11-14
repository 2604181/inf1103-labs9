"""
INF1103 Week 11 - Order class
Composition: an Order CREATES and MANAGES its own OrderLine objects.
Association: an Order USES a DiscountStrategy (it does not own it). Strategies are
created outside, can be changed with set_discount(), and may be shared by orders.
Order contains NO if/elif about discount types (Strategy pattern, OCP).
"""
from discount_strategy import DiscountStrategy, NoDiscount
from order_line import OrderLine
from product import Product


class Order:
    def __init__(self, order_id: str, discount: DiscountStrategy | None = None) -> None:
        self.__order_id: str = order_id
        self.__order_lines: list[OrderLine] = []
        self.__discount: DiscountStrategy = discount if discount is not None else NoDiscount()

    def get_order_id(self) -> str:
        return self.__order_id

    def set_discount(self, discount: DiscountStrategy) -> None:
        self.__discount = discount

    def get_discount(self) -> DiscountStrategy:
        return self.__discount

    def add_order_line(self, product: Product, quantity: int) -> None:
        # The Order creates the OrderLine itself (this is what makes it composition)
        order_line: OrderLine = OrderLine(product, quantity)
        self.__order_lines.append(order_line)

    def remove_order_line(self, index: int) -> None:
        if index < 0 or index >= len(self.__order_lines):
            raise IndexError("No order line at that position.")
        del self.__order_lines[index]

    def get_order_lines(self) -> tuple[tuple[Product, int, float], ...]:
        # Plain values only: the OrderLine objects themselves never leave the Order
        lines: list[tuple[Product, int, float]] = []
        for order_line in self.__order_lines:
            lines.append((
                order_line.get_product(),
                order_line.get_quantity(),
                order_line.calculate_subtotal()
            ))
        return tuple(lines)

    def calculate_total(self) -> float:
        total: float = sum(line.calculate_subtotal() for line in self.__order_lines)
        return self.__discount.apply(total)
