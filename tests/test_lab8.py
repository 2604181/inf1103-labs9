"""
INF1103 Week 10 - Tests for the Lab 8 testing requirements (Section 9).
Run with:  python test_lab8.py
(JSON tests use a temporary file, so your real inventory.json is not touched.)
"""
import contextlib
import inspect
import io
import json
import os
import tempfile
import typing
import unittest

import file_handling
import inventory as inventory_module
import order as order_module
import order_line as order_line_module
import product as product_module
import supplier as supplier_module
import physical_product as physical_module
import digital_product as digital_module
from can_be_shipped import CanBeShipped
from digital_product import DigitalProduct
from file_handling import load_inventory, save_inventory
from inventory import Inventory
from order import Order
from order_line import OrderLine
from physical_product import PhysicalProduct
from product import Product
from supplier import Supplier


def capture_output(function) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        function()
    return buffer.getvalue()


def show_product_details(product: Product) -> None:
    """The substitutability test function from Section 6.2."""
    product.display_information()
    print(product.get_fulfilment_info())


class BadDigitalProduct(DigitalProduct):
    """The teammate's design from the Diagnose question (violates LSP)."""
    def update_stock(self, quantity: int) -> None:
        raise NotImplementedError("Digital products have no stock")


class RelationshipTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.supplier = Supplier("S001", "TechSource Pte Ltd", "sales@techsource.sg")
        self.laptop = PhysicalProduct("P001", "Laptop", 1200.00, 15, self.supplier, 2.5)
        self.antivirus = DigitalProduct("D001", "Antivirus", 29.99, 100, self.supplier, 350.0)


class TestAssociation(RelationshipTestCase):
    # Supplier and Product have an association and can exist independently
    def test_supplier_exists_without_any_product(self):
        lonely = Supplier("S9", "Lonely Ltd", "a@b.sg")
        self.assertEqual(lonely.get_name(), "Lonely Ltd")
        self.assertFalse(hasattr(lonely, "get_products"))     # supplier does not track products

    def test_product_stores_reference_to_its_supplier(self):
        self.assertIs(self.laptop.get_supplier(), self.supplier)
        self.assertIs(self.antivirus.get_supplier(), self.supplier)

    def test_one_supplier_shared_by_both_product_types(self):
        self.assertIs(self.laptop.get_supplier(), self.antivirus.get_supplier())

    def test_products_still_reach_supplier_after_variable_deleted(self):
        del self.supplier
        self.assertEqual(self.laptop.get_supplier().get_name(), "TechSource Pte Ltd")
        self.assertEqual(self.antivirus.get_supplier().get_contact_email(), "sales@techsource.sg")

    def test_supplier_display_information(self):
        output = capture_output(self.laptop.get_supplier().display_information)
        self.assertIn("Supplier ID: S001", output)
        self.assertIn("TechSource Pte Ltd", output)
        self.assertIn("sales@techsource.sg", output)


class TestAggregation(RelationshipTestCase):
    # Inventory aggregates Product objects; products survive removal / transfer
    def test_product_exists_before_any_inventory(self):
        self.assertEqual(self.laptop.get_name(), "Laptop")

    def test_remove_does_not_destroy_product(self):
        inventory_a = Inventory()
        inventory_a.add_product(self.laptop)
        self.assertTrue(inventory_a.remove_product("P001"))
        self.assertIsNone(inventory_a.find_product("P001"))
        self.laptop.update_stock(40)                         # still fully usable
        self.assertEqual(self.laptop.get_stock(), 40)

    def test_transfer_between_inventories_keeps_same_object(self):
        inventory_a, inventory_b = Inventory(), Inventory()
        inventory_a.add_product(self.laptop)
        inventory_a.remove_product("P001")
        inventory_b.add_product(self.laptop)
        self.assertIs(inventory_b.find_product("P001"), self.laptop)

    def test_one_product_can_sit_in_two_inventories(self):
        inventory_a, inventory_b = Inventory(), Inventory()
        inventory_a.add_product(self.laptop)
        inventory_b.add_product(self.laptop)
        inventory_a.remove_product("P001")
        self.assertIs(inventory_b.find_product("P001"), self.laptop)

    def test_emptied_inventory_does_not_destroy_products(self):
        inventory = Inventory()
        inventory.add_product(self.laptop)
        inventory.add_product(self.antivirus)
        inventory.remove_product("P001")
        inventory.remove_product("D001")
        self.assertEqual(len(inventory.products), 0)
        self.assertEqual(self.laptop.get_name(), "Laptop")
        self.assertEqual(self.antivirus.get_name(), "Antivirus")

    def test_find_remove_missing_product(self):
        inventory = Inventory()
        self.assertIsNone(inventory.find_product("NOPE"))
        self.assertFalse(inventory.remove_product("NOPE"))

    def test_products_view_cannot_change_inventory(self):
        inventory = Inventory()
        inventory.add_product(self.laptop)
        self.assertIsInstance(inventory.products, tuple)
        self.assertEqual(len(inventory.get_all_products()), 1)


class TestComposition(RelationshipTestCase):
    # Order creates and manages its own OrderLines; OrderLine refers to, but does not own, a Product
    def test_order_creates_its_own_order_lines(self):
        order = Order("O001")
        order.add_order_line(self.laptop, 1)
        lines = order._Order__order_lines                    # peek inside for the test only
        self.assertEqual(len(lines), 1)
        self.assertIsInstance(lines[0], OrderLine)

    def test_add_order_line_takes_product_and_quantity_not_an_orderline(self):
        names = list(inspect.signature(Order.add_order_line).parameters)
        self.assertEqual(names, ["self", "product", "quantity"])

    def test_same_product_in_two_orders_gives_two_lines_one_product(self):
        order_1, order_2 = Order("O001"), Order("O002")
        order_1.add_order_line(self.laptop, 1)
        order_2.add_order_line(self.laptop, 3)
        line_1 = order_1._Order__order_lines[0]
        line_2 = order_2._Order__order_lines[0]
        self.assertIsNot(line_1, line_2)                     # 2 OrderLine objects
        self.assertIs(line_1.get_product(), line_2.get_product())   # 1 Product object

    def test_order_total_uses_order_lines(self):
        order = Order("O001")
        order.add_order_line(self.laptop, 1)
        order.add_order_line(self.antivirus, 2)
        self.assertAlmostEqual(order.calculate_total(), 1200.00 + 2 * 29.99)

    def test_order_line_subtotal(self):
        line = OrderLine(self.antivirus, 3)
        self.assertAlmostEqual(line.calculate_subtotal(), 3 * 29.99)
        self.assertEqual(line.get_quantity(), 3)

    def test_get_order_lines_returns_values_not_orderline_objects(self):
        order = Order("O001")
        order.add_order_line(self.laptop, 2)
        (product, quantity, subtotal), = order.get_order_lines()
        self.assertIs(product, self.laptop)
        self.assertEqual(quantity, 2)
        self.assertAlmostEqual(subtotal, 2400.00)

    def test_remove_order_line(self):
        order = Order("O001")
        order.add_order_line(self.laptop, 1)
        order.add_order_line(self.antivirus, 1)
        order.remove_order_line(0)
        self.assertEqual(len(order.get_order_lines()), 1)
        self.assertAlmostEqual(order.calculate_total(), 29.99)
        with self.assertRaises(IndexError):
            order.remove_order_line(5)

    def test_order_line_does_not_own_the_product(self):
        inventory = Inventory()
        inventory.add_product(self.laptop)
        order = Order("O001")
        order.add_order_line(self.laptop, 1)
        del order                                            # order (and its lines) gone
        self.assertIs(inventory.find_product("P001"), self.laptop)
        self.assertEqual(self.laptop.get_name(), "Laptop")

    def test_invalid_quantity_rejected(self):
        with self.assertRaises(ValueError):
            OrderLine(self.laptop, 0)


class TestTypeHints(unittest.TestCase):
    MODULES = [supplier_module, product_module, physical_module, digital_module,
               inventory_module, order_line_module, order_module, file_handling]

    def test_every_function_and_method_is_fully_annotated(self):
        problems = []
        for module in self.MODULES:
            callables = []
            for name, member in inspect.getmembers(module):
                # Python 3.14 adds a hidden compiler helper called __annotate__; skip it
                if name.startswith("__annotate"):
                    continue
                if inspect.isfunction(member) and member.__module__ == module.__name__:
                    callables.append((name, member))
                elif inspect.isclass(member) and member.__module__ == module.__name__:
                    for method_name, method in vars(member).items():
                        if method_name.startswith("__annotate"):
                            continue
                        if isinstance(method, property):
                            method = method.fget
                        if inspect.isfunction(method):
                            callables.append((f"{name}.{method_name}", method))
            for label, function in callables:
                signature = inspect.signature(function)
                for parameter in signature.parameters.values():
                    if parameter.name != "self" and parameter.annotation is inspect.Parameter.empty:
                        problems.append(f"{module.__name__}.{label}: parameter '{parameter.name}'")
                if signature.return_annotation is inspect.Signature.empty:
                    problems.append(f"{module.__name__}.{label}: return type")
        self.assertEqual(problems, [])

    def test_key_hints_match_the_uml_design(self):
        hints = typing.get_type_hints(Product.__init__)
        self.assertIs(hints["supplier"], Supplier)
        self.assertIs(hints["price"], float)
        self.assertEqual(typing.get_type_hints(Inventory.add_product)["product"], Product)
        self.assertEqual(typing.get_type_hints(Inventory.find_product)["return"], Product | None)
        self.assertEqual(typing.get_type_hints(Inventory.remove_product)["product_id"], str)
        self.assertEqual(typing.get_type_hints(Order.add_order_line)["product"], Product)
        self.assertEqual(typing.get_type_hints(Order.add_order_line)["return"], type(None))
        self.assertEqual(typing.get_type_hints(OrderLine.calculate_subtotal)["return"], float)
        self.assertEqual(typing.get_type_hints(Inventory.get_all_products)["return"],
                         tuple[Product, ...])
        self.assertEqual(typing.get_type_hints(Order.get_order_lines)["return"],
                         tuple[tuple[Product, int, float], ...])


class TestLspAndPolymorphism(RelationshipTestCase):
    def test_show_product_details_works_for_both_subclasses(self):
        for product in (self.laptop, self.antivirus):
            output = capture_output(lambda p=product: show_product_details(p))
            self.assertIn(f"Name: {product.get_name()}", output)
            self.assertIn(product.get_fulfilment_info(), output)

    def test_inventory_stores_both_types_through_product(self):
        inventory = Inventory()
        self.assertTrue(inventory.add_product(self.laptop))
        self.assertTrue(inventory.add_product(self.antivirus))
        for product in inventory.products:
            self.assertIsInstance(product, Product)
        output = capture_output(inventory.display_all)
        self.assertIn("Weight: 2.50 kg", output)
        self.assertIn("Download Size: 350.00 MB", output)

    def test_both_subclasses_preserve_update_stock_contract(self):
        for product in (self.laptop, self.antivirus):
            with self.subTest(product=product.get_name()):
                self.assertIsNone(product.update_stock(60))
                self.assertEqual(product.get_stock(), 60)
                self.assertIsNone(product.update_stock(0))      # valid input accepted
                self.assertEqual(product.get_stock(), 0)
                product.update_stock(-5)                         # invalid ignored, no crash
                self.assertEqual(product.get_stock(), 0)

    def test_subclasses_do_not_override_update_stock(self):
        self.assertIs(PhysicalProduct.update_stock, Product.update_stock)
        self.assertIs(DigitalProduct.update_stock, Product.update_stock)

    def test_get_price_keeps_numeric_contract(self):
        for product in (self.laptop, self.antivirus):
            self.assertIsInstance(product.get_price(), float)
            self.assertIsInstance(product.get_price() * 2, float)

    def test_polymorphic_calls_run_the_subclass_implementation(self):
        products: list[Product] = [self.laptop, self.antivirus]
        results = [product.get_fulfilment_info() for product in products]
        self.assertEqual(results, ["Requires physical shipping.",
                                   "Delivered digitally via download link."])

    def test_inventory_never_checks_for_subclasses(self):
        source = inspect.getsource(inventory_module)
        self.assertNotIn("isinstance", source)
        self.assertNotIn("PhysicalProduct", source)
        self.assertNotIn("DigitalProduct", source)

    def test_digital_is_still_not_shippable(self):
        self.assertIsInstance(self.laptop, CanBeShipped)
        self.assertNotIsInstance(self.antivirus, CanBeShipped)

    def test_diagnose_example_breaks_lsp(self):
        # A subclass that raises NotImplementedError cannot stand in for Product
        bad = BadDigitalProduct("D2", "Bad", 1.0, 1, self.supplier, 1.0)
        with self.assertRaises(NotImplementedError):
            bad.update_stock(10)


class TestPersistenceWithSuppliers(RelationshipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, "inventory.json")

    def tearDown(self) -> None:
        self.folder.cleanup()

    def test_round_trip_keeps_types_suppliers_and_sharing(self):
        other = Supplier("S002", "BookWorks LLP", "hello@bookworks.sg")
        ebook = DigitalProduct("D002", "E-Book", 9.99, 500, other, 12.5)
        save_inventory([self.laptop, self.antivirus, ebook], self.path)

        loaded, status = load_inventory(self.path)
        self.assertEqual(status, "loaded")
        self.assertIsInstance(loaded[0], PhysicalProduct)
        self.assertIsInstance(loaded[1], DigitalProduct)
        self.assertEqual(loaded[2].get_supplier().get_name(), "BookWorks LLP")
        # products with the same supplier id share ONE Supplier object again
        self.assertIs(loaded[0].get_supplier(), loaded[1].get_supplier())
        self.assertIsNot(loaded[0].get_supplier(), loaded[2].get_supplier())

    def test_lab7_file_without_supplier_is_rejected_gracefully(self):
        with open(self.path, "w") as file:
            json.dump([{"id": "P1", "name": "N", "price": 1, "stock": 1,
                        "type": "physical", "weight": 1}], file)
        self.assertEqual(load_inventory(self.path), ([], "error"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
