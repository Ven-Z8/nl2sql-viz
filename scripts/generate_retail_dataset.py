"""Generate a complex relational retail dataset (Olist-style, multi-table).

Schema: customers → orders → order_items → products, plus payments.
~950K rows total across 5 tables with foreign keys.
"""
import csv
import random
from datetime import date, timedelta

random.seed(11)

OUT = "data/datasets/retail"
N_CUSTOMERS = 50_000
N_PRODUCTS = 2_000
N_ORDERS = 200_000
ITEMS_PER_ORDER = (1, 5)  # 1-5 items per order

SEGMENTS = ["Consumer", "Corporate", "Home Office", "Small Business"]
REGIONS = ["North", "South", "East", "West", "Central"]
CHANNELS = ["Web", "Mobile", "Store", "Partner"]
STATUSES = ["completed", "completed", "completed", "completed", "refunded", "pending"]
CATEGORIES = ["Electronics", "Clothing", "Home", "Sports", "Beauty", "Books", "Toys", "Garden"]
PAY_METHODS = ["credit_card", "debit_card", "boleto", "voucher", "pix"]
START = date(2023, 1, 1)


def _date(days: int) -> str:
    return (START + timedelta(days=random.randint(0, days))).isoformat()


def _write(name: str, header: list[str], rows: list[list]) -> None:
    with open(f"{OUT}/{name}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  {name}.csv: {len(rows):,} rows")


def main() -> None:
    # customers
    customers = []
    for i in range(1, N_CUSTOMERS + 1):
        customers.append([
            f"C{i:06d}", f"Customer {i}", random.choice(SEGMENTS),
            random.choice(REGIONS), _date(700),
        ])
    _write("customers", ["customer_id", "name", "segment", "region", "signup_date"], customers)

    # products
    products = []
    for i in range(1, N_PRODUCTS + 1):
        products.append([
            f"P{i:05d}", f"Product {i}", random.choice(CATEGORIES),
            round(random.uniform(5, 500), 2), round(random.uniform(2, 200), 2),
        ])
    _write("products", ["product_id", "name", "category", "price", "cost"], products)

    # orders + order_items + payments
    orders = []
    order_items = []
    payments = []
    order_id = 1
    for _ in range(N_ORDERS):
        customer = random.choice(customers)[0]
        order_date = _date(700)
        status = random.choice(STATUSES)
        channel = random.choice(CHANNELS)
        orders.append([f"O{order_id:07d}", customer, order_date, status, channel])

        n_items = random.randint(*ITEMS_PER_ORDER)
        for _ in range(n_items):
            product = random.choice(products)
            qty = random.randint(1, 5)
            order_items.append([
                f"OI{len(order_items)+1:08d}", f"O{order_id:07d}",
                product[0], qty, product[3],
            ])

        # 1-2 payments per order
        n_pay = random.randint(1, 2)
        for _ in range(n_pay):
            payments.append([
                f"PAY{len(payments)+1:08d}", f"O{order_id:07d}",
                round(random.uniform(10, 2000), 2), random.choice(PAY_METHODS),
                _date(700),
            ])
        order_id += 1

    _write("orders", ["order_id", "customer_id", "order_date", "status", "channel"], orders)
    _write("order_items", ["order_item_id", "order_id", "product_id", "quantity", "unit_price"], order_items)
    _write("payments", ["payment_id", "order_id", "amount", "method", "payment_date"], payments)


if __name__ == "__main__":
    main()