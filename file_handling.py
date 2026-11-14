"""
INF1103 Week 11 - File handling
Responsibility: load and save inventory data (JSON). No menus, no prompts.
Each saved product has a "type" ("physical" or "digital") and a "supplier".
Products with the same supplier id share ONE Supplier object when loaded.
"""
import csv
import json
from collections.abc import Sequence
from typing import Any

from product import Product
from supplier import Supplier
from physical_product import PhysicalProduct
from digital_product import DigitalProduct
from product_factory import ProductFactory
from inventory import Inventory

# Global Constant
INVENTORY_FILE: str = "inventory.json"


def supplier_from_dict(data: dict[str, Any], suppliers: dict[str, Supplier]) -> Supplier:
    """Reuse an existing Supplier object if this supplier id was already loaded."""
    supplier_id: str = data["id"]
    if supplier_id not in suppliers:
        suppliers[supplier_id] = Supplier(supplier_id, data["name"], data["email"])
    return suppliers[supplier_id]


# Which JSON field holds the type-specific value for each product type
EXTRA_FIELD_NAMES: dict[str, str] = {"physical": "weight", "digital": "download_size"}


def product_from_dict(item: dict[str, Any], suppliers: dict[str, Supplier]) -> Product:
    """Read the fields, then let the ProductFactory build the right subclass."""
    supplier: Supplier = supplier_from_dict(item["supplier"], suppliers)
    product_type: str = item["type"]

    extra_field: str | None = EXTRA_FIELD_NAMES.get(product_type)
    extra_value: float = float(item[extra_field]) if extra_field is not None else 0.0

    # An unknown type reaches the factory, which raises the ValueError
    return ProductFactory.create(
        product_type,
        item["id"],
        item["name"],
        float(item["price"]),
        int(item["stock"]),
        supplier,
        extra_value
    )


def product_to_dict(product: Product) -> dict[str, Any]:
    """Turn a Product object into a dictionary that can be saved as JSON."""
    supplier: Supplier = product.get_supplier()
    item: dict[str, Any] = {
        "id": product.get_product_id(),
        "name": product.get_name(),
        "price": product.get_price(),
        "stock": product.get_stock(),
        "supplier": {
            "id": supplier.get_supplier_id(),
            "name": supplier.get_name(),
            "email": supplier.get_contact_email()
        }
    }

    if isinstance(product, PhysicalProduct):
        item["type"] = "physical"
        item["weight"] = product.get_weight()
    elif isinstance(product, DigitalProduct):
        item["type"] = "digital"
        item["download_size"] = product.get_download_size()
    else:
        raise ValueError("Unsupported product type.")

    return item


def load_inventory(filename: str = INVENTORY_FILE) -> tuple[list[Product], str]:
    products: list[Product] = []
    suppliers: dict[str, Supplier] = {}
    status: str = "not_found"

    try:
        with open(filename, "r") as file:
            data: Any = json.load(file)

        if not isinstance(data, list):
            return [], "error"

        for item in data:
            products.append(product_from_dict(item, suppliers))
        status = "loaded"

    except FileNotFoundError:
        products = []
        status = "not_found"
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        products = []
        status = "error"

    return products, status


def save_inventory(products: Sequence[Product], filename: str = INVENTORY_FILE) -> None:
    data: list[dict[str, Any]] = []
    for product in products:
        data.append(product_to_dict(product))

    with open(filename, "w") as file:
        json.dump(data, file, indent=4)


def load_products(path: str, inventory: Inventory, supplier: Supplier) -> None:
    """
    Load products from a CSV file (header row, then one product per row).
    - FileNotFoundError  -> simple message, program carries on
    - else               -> read the rows; each row has its OWN try/except ValueError
    - finally            -> always prints "Load attempt finished."
    """
    try:
        file = open(path, newline="")
    except FileNotFoundError:
        print(f"Products file not found: {path}")
    else:
        loaded: int = 0
        with file:
            reader = csv.reader(file)
            next(reader, None)  # skip the header row
            for row_number, row in enumerate(reader, start=2):
                try:
                    product_type, product_id, name, price, stock = row
                    product: Product = ProductFactory.create(
                        product_type, product_id, name,
                        float(price), int(stock), supplier
                    )
                    if not inventory.add_product(product):
                        raise ValueError(f"Duplicate product ID: {product_id}")
                    loaded += 1
                except ValueError as error:
                    print(f"Skipped row {row_number}: {error}")
        print(f"{loaded} products loaded.")
    finally:
        print("Load attempt finished.")
