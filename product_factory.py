"""
INF1103 Week 11 - Factory pattern: creating products
The factory owns the decision "which Product subclass do I build?".
The rest of the program asks the factory and only needs to know about Product.
ProductFactory creates products but does not store them: a dependency, not an association.
"""
from product import Product
from supplier import Supplier
from physical_product import PhysicalProduct
from digital_product import DigitalProduct


class ProductFactory:
    @staticmethod
    def create(product_type: str, product_id: str, name: str, price: float,
               stock_quantity: int, supplier: Supplier,
               extra_value: float = 0.0) -> Product:
        """
        extra_value is the type-specific number: weight (kg) for "physical",
        download size (MB) for "digital". It defaults to 0.0 because products.csv
        has no column for it.
        """
        if product_type == "physical":
            return PhysicalProduct(product_id, name, price, stock_quantity,
                                   supplier, extra_value)
        elif product_type == "digital":
            return DigitalProduct(product_id, name, price, stock_quantity,
                                  supplier, extra_value)
        else:
            raise ValueError(f"Unknown product type: {product_type}")
