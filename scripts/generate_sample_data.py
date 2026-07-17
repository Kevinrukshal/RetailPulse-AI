"""Generate deterministic demonstration datasets for RetailPulse AI."""

import csv
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

SEED = 20260717
SAMPLE_ROW_COUNT = 750
ROOT = Path(__file__).resolve().parents[1]
FIELDNAMES = [
    "order_id",
    "order_date",
    "ship_date",
    "customer_id",
    "customer_name",
    "segment",
    "country",
    "city",
    "state",
    "region",
    "product_id",
    "product_name",
    "category",
    "subcategory",
    "sales",
    "quantity",
    "discount",
    "profit",
]

PRODUCTS = [
    ("P-001", "Ergonomic Office Chair", "Furniture", "Chairs", "249.00", "142.00"),
    ("P-002", "Standing Desk", "Furniture", "Tables", "489.00", "315.00"),
    ("P-003", "Five Shelf Bookcase", "Furniture", "Bookcases", "179.00", "111.00"),
    ("P-004", "Storage Cabinet", "Furniture", "Storage", "219.00", "137.00"),
    ("P-005", "LED Desk Lamp", "Furniture", "Furnishings", "59.00", "27.00"),
    ("P-006", "Wireless Keyboard", "Technology", "Accessories", "79.00", "38.00"),
    ("P-007", "Noise Cancelling Headset", "Technology", "Accessories", "159.00", "82.00"),
    ("P-008", "Business Laptop", "Technology", "Computers", "1249.00", "930.00"),
    ("P-009", "Laser Printer", "Technology", "Machines", "399.00", "278.00"),
    ("P-010", "27 Inch Monitor", "Technology", "Displays", "329.00", "224.00"),
    ("P-011", "USB-C Dock", "Technology", "Accessories", "139.00", "76.00"),
    ("P-012", "A4 Copy Paper", "Office Supplies", "Paper", "12.50", "6.20"),
    ("P-013", "Permanent Marker Set", "Office Supplies", "Art", "18.00", "7.40"),
    ("P-014", "Heavy Duty Stapler", "Office Supplies", "Binders", "36.00", "18.50"),
    ("P-015", "Archive Box Pack", "Office Supplies", "Storage", "42.00", "22.00"),
    ("P-016", "Shipping Label Roll", "Office Supplies", "Labels", "24.00", "10.50"),
    ("P-017", "Executive Notebook", "Office Supplies", "Paper", "21.00", "8.50"),
    ("P-018", "Desk Organizer", "Office Supplies", "Storage", "31.00", "14.00"),
    ("P-019", "Web Conference Camera", "Technology", "Accessories", "129.00", "69.00"),
    ("P-020", "Mobile File Pedestal", "Furniture", "Storage", "199.00", "126.00"),
]

LOCATIONS = [
    ("New York", "New York", "East"),
    ("Boston", "Massachusetts", "East"),
    ("Chicago", "Illinois", "Central"),
    ("Dallas", "Texas", "Central"),
    ("Atlanta", "Georgia", "South"),
    ("Miami", "Florida", "South"),
    ("Seattle", "Washington", "West"),
    ("San Francisco", "California", "West"),
]


def money(value: Decimal) -> str:
    """Render monetary values with two deterministic decimal places."""
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_sample_rows() -> list[dict[str, Any]]:
    """Build stable, plausible retail order-line records using a fixed seed."""
    randomizer = random.Random(SEED)
    customers = [
        (
            f"C-{index:04d}",
            f"Demo Customer {index:03d}",
            ("Consumer", "Corporate", "Home Office")[index % 3],
            LOCATIONS[index % len(LOCATIONS)],
        )
        for index in range(1, 81)
    ]
    discounts = [
        Decimal("0"),
        Decimal("0.05"),
        Decimal("0.10"),
        Decimal("0.15"),
        Decimal("0.20"),
        Decimal("0.30"),
    ]
    rows: list[dict[str, Any]] = []
    order_number = 1

    while len(rows) < SAMPLE_ROW_COUNT:
        customer_id, customer_name, segment, location = randomizer.choice(customers)
        city, state, region = location
        order_date = date(2023, 1, 1) + timedelta(days=randomizer.randrange(0, 1095))
        ship_date = order_date + timedelta(days=randomizer.randint(1, 7))
        line_count = min(randomizer.randint(1, 4), SAMPLE_ROW_COUNT - len(rows))
        selected_products = randomizer.sample(PRODUCTS, k=line_count)
        order_id = f"RP-{order_date.year}-{order_number:05d}"

        for product in selected_products:
            product_id, product_name, category, subcategory, price_text, cost_text = product
            quantity = randomizer.randint(1, 8)
            discount = randomizer.choices(discounts, weights=[34, 18, 18, 14, 10, 6], k=1)[0]
            price = Decimal(price_text)
            cost = Decimal(cost_text)
            sales = price * quantity * (Decimal("1") - discount)
            shipping_allocation = Decimal("2.50") + Decimal(str(quantity)) * Decimal("0.75")
            profit = sales - (cost * quantity) - shipping_allocation
            rows.append(
                {
                    "order_id": order_id,
                    "order_date": order_date.isoformat(),
                    "ship_date": ship_date.isoformat(),
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "segment": segment,
                    "country": "United States",
                    "city": city,
                    "state": state,
                    "region": region,
                    "product_id": product_id,
                    "product_name": product_name,
                    "category": category,
                    "subcategory": subcategory,
                    "sales": money(sales),
                    "quantity": quantity,
                    "discount": str(discount),
                    "profit": money(profit),
                }
            )
        order_number += 1

    return rows


def build_invalid_rows(valid_row: dict[str, Any]) -> list[dict[str, Any]]:
    """Create fixtures containing each intentional validation problem."""

    def changed(**values: Any) -> dict[str, Any]:
        return {**valid_row, **values}

    duplicate = changed(order_id="RP-DUPLICATE")
    return [
        changed(order_id=""),
        changed(order_id="RP-BAD-0002", customer_id=""),
        changed(order_id="RP-BAD-0003", product_id=""),
        changed(order_id="RP-BAD-0004", order_date="not-a-date"),
        changed(order_id="RP-BAD-0005", order_date="2025-04-10", ship_date="2025-04-01"),
        changed(order_id="RP-BAD-0006", sales="-25.00"),
        changed(order_id="RP-BAD-0007", quantity="0"),
        changed(order_id="RP-BAD-0008", discount="1.25"),
        changed(order_id="RP-BAD-0009", region="North"),
        changed(order_id="RP-BAD-0010", sales="many", quantity="several", profit="unknown"),
        duplicate,
        duplicate.copy(),
    ]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write rows with stable field order and UTF-8 encoding."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Generate the sample and test fixture CSV files."""
    sample_rows = build_sample_rows()
    write_csv(ROOT / "data" / "sample" / "sample_sales.csv", sample_rows)
    write_csv(ROOT / "tests" / "fixtures" / "valid_sales.csv", sample_rows[:12])
    write_csv(
        ROOT / "tests" / "fixtures" / "invalid_sales.csv",
        build_invalid_rows(sample_rows[0]),
    )
    print(f"Generated {len(sample_rows)} deterministic sample rows with seed {SEED}.")


if __name__ == "__main__":
    main()
