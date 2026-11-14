"""
INF1103 Week 11 - Lab 9 automated tests (Strategy, Factory, validation, exceptions).
Run from the lab folder:   python -m unittest discover -v
"""
import ast
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import main
from digital_product import DigitalProduct
from discount_strategy import (BulkDiscount, DiscountStrategy, NoDiscount,
                               PercentageDiscount, StudentDiscount)
from file_handling import load_products
from inventory import Inventory
from order import Order
from order_line import OrderLine
from physical_product import PhysicalProduct
from product import Product
from product_factory import ProductFactory
from supplier import Supplier

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_supplier() -> Supplier:
    return Supplier("S001", "TechSource", "sales@techsource.sg")


def run_quietly(function, *args):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        function(*args)
    return buffer.getvalue()


def order_worth_250() -> Order:
    order = Order("O1")
    product = ProductFactory.create("physical", "P1", "Item", 125.0, 10, make_supplier(), 1.0)
    order.add_order_line(product, 2)           # 125 x 2 = 250
    return order


class TestStrategies(unittest.TestCase):
    def test_strategy_base_is_abstract(self):
        with self.assertRaises(TypeError):
            DiscountStrategy()  # type: ignore[abstract]

    def test_no_discount(self):
        self.assertEqual(NoDiscount().apply(250), 250)

    def test_percentage_discount(self):
        self.assertAlmostEqual(PercentageDiscount(10).apply(250), 225)

    def test_bulk_discount_at_and_around_threshold(self):
        self.assertEqual(BulkDiscount(200, 20).apply(250), 230)
        self.assertEqual(BulkDiscount(200, 20).apply(200), 180)   # 200 or more
        self.assertEqual(BulkDiscount(200, 20).apply(199.99), 199.99)

    def test_student_discount_is_five_percent(self):
        self.assertAlmostEqual(StudentDiscount().apply(200), 190)

    def test_all_strategies_are_discount_strategies(self):
        for strategy in (NoDiscount(), PercentageDiscount(10),
                         BulkDiscount(200, 20), StudentDiscount()):
            self.assertIsInstance(strategy, DiscountStrategy)

    def test_bad_strategy_values_rejected(self):
        with self.assertRaises(ValueError):
            PercentageDiscount(-1)
        with self.assertRaises(ValueError):
            PercentageDiscount(101)
        with self.assertRaises(ValueError):
            BulkDiscount(-1, 20)


class TestOrderUsesStrategy(unittest.TestCase):
    def test_default_is_no_discount(self):
        order = order_worth_250()
        self.assertIsInstance(order.get_discount(), NoDiscount)
        self.assertEqual(order.calculate_total(), 250)

    def test_strategy_given_at_creation(self):
        order = Order("O2", BulkDiscount(200, 20))
        self.assertIsInstance(order.get_discount(), BulkDiscount)

    def test_total_goes_through_strategy(self):
        order = order_worth_250()
        order.set_discount(BulkDiscount(200, 20))
        self.assertEqual(order.calculate_total(), 230)

    def test_set_discount_changes_existing_order(self):
        order = order_worth_250()
        order.set_discount(BulkDiscount(200, 20))
        self.assertEqual(order.calculate_total(), 230)
        order.set_discount(PercentageDiscount(10))
        self.assertAlmostEqual(order.calculate_total(), 225)

    def test_new_strategy_works_without_changing_order(self):
        class HalfPrice(DiscountStrategy):          # defined here, Order never saw it
            def apply(self, total: float) -> float:
                return total / 2
        order = order_worth_250()
        order.set_discount(HalfPrice())
        self.assertEqual(order.calculate_total(), 125)

    def test_two_orders_can_share_one_strategy(self):
        shared = PercentageDiscount(10)
        first, second = order_worth_250(), order_worth_250()
        first.set_discount(shared)
        second.set_discount(shared)
        self.assertIs(first.get_discount(), second.get_discount())

    def test_order_source_has_no_discount_if_elif_logic(self):
        with open(os.path.join(ROOT, "order.py")) as file:
            source = file.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.If):                 # every if in order.py
                condition = ast.unparse(node.test).lower()
                for word in ("discount", "percent", "bulk", "student", "type"):
                    self.assertNotIn(word, condition, "discount logic found in an if")
            if isinstance(node, ast.If):                 # an elif is an If inside orelse
                for child in node.orelse:
                    self.assertNotIsInstance(child, ast.If, "elif found in order.py")
        names = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)]
        for forbidden in ("PercentageDiscount", "BulkDiscount", "StudentDiscount"):
            self.assertNotIn(forbidden, names)


class TestFactory(unittest.TestCase):
    def test_creates_physical(self):
        product = ProductFactory.create("physical", "P1", "Lamp", 25.0, 10, make_supplier(), 1.5)
        self.assertIsInstance(product, PhysicalProduct)
        self.assertEqual(product.get_weight(), 1.5)  # type: ignore[attr-defined]

    def test_creates_digital(self):
        product = ProductFactory.create("digital", "D1", "App", 49.9, 5, make_supplier(), 300.0)
        self.assertIsInstance(product, DigitalProduct)

    def test_extra_value_defaults_to_zero(self):
        product = ProductFactory.create("physical", "P1", "Lamp", 25.0, 10, make_supplier())
        self.assertEqual(product.get_weight(), 0.0)  # type: ignore[attr-defined]

    def test_returns_product_type(self):
        self.assertIsInstance(
            ProductFactory.create("digital", "D1", "App", 1.0, 1, make_supplier()), Product)

    def test_unknown_type_raises_clear_value_error(self):
        with self.assertRaises(ValueError) as caught:
            ProductFactory.create("service", "S1", "Install", 30.0, 5, make_supplier())
        self.assertEqual(str(caught.exception), "Unknown product type: service")

    def test_create_is_a_static_method(self):
        self.assertIsInstance(ProductFactory.__dict__["create"], staticmethod)

    def test_products_are_created_through_the_factory(self):
        """No module except the factory itself builds PhysicalProduct/DigitalProduct."""
        allowed = {"product_factory.py", "physical_product.py", "digital_product.py"}
        for name in os.listdir(ROOT):
            if not name.endswith(".py") or name in allowed or name.startswith("demo_"):
                continue
            with open(os.path.join(ROOT, name)) as file:
                tree = ast.parse(file.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, ("PhysicalProduct", "DigitalProduct"),
                                     f"{name} creates a product directly")


class TestValidation(unittest.TestCase):
    def test_price_must_be_greater_than_zero(self):
        for bad_price in (0, -1, -0.01):
            with self.subTest(price=bad_price):
                with self.assertRaises(ValueError):
                    ProductFactory.create("physical", "P1", "X", bad_price, 1, make_supplier())

    def test_stock_cannot_be_negative(self):
        with self.assertRaises(ValueError):
            ProductFactory.create("digital", "D1", "X", 5.0, -1, make_supplier())

    def test_zero_stock_is_allowed(self):
        self.assertEqual(
            ProductFactory.create("digital", "D1", "X", 5.0, 0, make_supplier()).get_stock(), 0)

    def test_both_subclasses_enforce_the_rules(self):
        for kind in ("physical", "digital"):
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):
                    ProductFactory.create(kind, "X", "X", -5.0, 1, make_supplier())

    def test_update_stock_rejects_negative_and_keeps_old_value(self):
        product = ProductFactory.create("digital", "D1", "X", 5.0, 7, make_supplier())
        with self.assertRaises(ValueError):
            product.update_stock(-1)
        self.assertEqual(product.get_stock(), 7)

    def test_order_line_quantity_must_be_greater_than_zero(self):
        product = ProductFactory.create("digital", "D1", "X", 5.0, 7, make_supplier())
        for bad in (0, -3):
            with self.subTest(quantity=bad):
                with self.assertRaises(ValueError) as caught:
                    OrderLine(product, bad)
                self.assertEqual(str(caught.exception), "Quantity must be greater than zero.")

    def test_order_rejects_bad_quantity(self):
        order = Order("O1")
        product = ProductFactory.create("digital", "D1", "X", 5.0, 7, make_supplier())
        with self.assertRaises(ValueError):
            order.add_order_line(product, 0)
        self.assertEqual(len(order.get_order_lines()), 0)


class TestGetPositiveFloat(unittest.TestCase):
    def ask(self, typed):
        buffer = io.StringIO()
        with patch("builtins.input", side_effect=typed), redirect_stdout(buffer):
            value = main.get_positive_float("Price: ")
        return value, buffer.getvalue()

    def test_valid_first_time(self):
        value, output = self.ask(["12.50"])
        self.assertEqual(value, 12.5)
        self.assertEqual(output, "")

    def test_abc_then_minus_five_then_valid(self):
        value, output = self.ask(["abc", "-5", "12.50"])
        self.assertEqual(value, 12.5)
        self.assertEqual(output.splitlines(), [
            "Please enter a valid number, e.g. 12.50",
            "Please enter a number greater than zero.",
        ])

    def test_zero_is_rejected(self):
        value, output = self.ask(["0", "3"])
        self.assertEqual(value, 3.0)
        self.assertIn("greater than zero", output)

    def test_empty_input_is_rejected(self):
        value, _ = self.ask(["", "4"])
        self.assertEqual(value, 4.0)


class TestLoadProducts(unittest.TestCase):
    CSV_PATH = os.path.join(ROOT, "products.csv")

    def load(self, path):
        inventory = Inventory()
        output = run_quietly(load_products, path, inventory, make_supplier())
        return inventory, output

    def test_valid_rows_load_and_bad_rows_are_skipped(self):
        inventory, output = self.load(self.CSV_PATH)
        ids = [p.get_product_id() for p in inventory.get_all_products()]
        self.assertEqual(ids, ["P001", "D001", "P003"])
        self.assertIn("3 products loaded.", output)

    def test_bad_rows_are_reported(self):
        _, output = self.load(self.CSV_PATH)
        self.assertIn("Skipped row 4: Unknown product type: service", output)
        self.assertIn("Skipped row 5:", output)
        self.assertIn("'abc'", output)

    def test_message_order_and_finally(self):
        _, output = self.load(self.CSV_PATH)
        lines = output.splitlines()
        self.assertEqual(lines[-2:], ["3 products loaded.", "Load attempt finished."])

    def test_missing_file_is_handled(self):
        inventory, output = self.load("no_such_file.csv")
        self.assertEqual(output.splitlines(),
                         ["Products file not found: no_such_file.csv", "Load attempt finished."])
        self.assertEqual(len(inventory.get_all_products()), 0)

    def test_negative_stock_and_wrong_column_count_are_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "p.csv")
            with open(path, "w") as file:
                file.write("product_type,product_id,name,price,stock_quantity\n"
                           "physical,P1,A,5.00,-2\n"
                           "digital,D1,B,5.00\n"
                           "digital,D2,C,0,4\n"
                           "digital,D3,D,9.00,4\n")
            inventory, output = self.load(path)
        self.assertEqual([p.get_product_id() for p in inventory.get_all_products()], ["D3"])
        self.assertIn("1 products loaded.", output)

    def test_duplicate_id_is_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "p.csv")
            with open(path, "w") as file:
                file.write("h\ndigital,D1,A,5.00,1\ndigital,D1,B,6.00,2\n")
            inventory, output = self.load(path)
        self.assertEqual(len(inventory.get_all_products()), 1)
        self.assertIn("Duplicate product ID: D1", output)

    def test_header_only_file_loads_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "p.csv")
            with open(path, "w") as file:
                file.write("product_type,product_id,name,price,stock_quantity\n")
            _, output = self.load(path)
        self.assertIn("0 products loaded.", output)


class TestSpecificExceptions(unittest.TestCase):
    def test_no_bare_or_blanket_except_anywhere(self):
        for name in os.listdir(ROOT):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(ROOT, name)) as file:
                tree = ast.parse(file.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    self.assertIsNotNone(node.type, f"{name}: bare except")
                    if isinstance(node.type, ast.Name):
                        self.assertNotIn(node.type.id, ("Exception", "BaseException"),
                                         f"{name}: catches too much")


if __name__ == "__main__":
    unittest.main()
