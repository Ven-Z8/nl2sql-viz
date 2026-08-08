"""Generate a realistic retail orders sample dataset (schema-agnostic demo data)."""
import csv
import random
from datetime import date, timedelta

random.seed(42)

OUT = "data/samples/retail_orders.csv"
N = 2000

CUSTOMERS = [f"C{1000 + i}" for i in range(300)]
REGIONS = ["North", "South", "East", "West", "Central"]
CATEGORIES = ["Electronics", "Clothing", "Home", "Sports", "Beauty", "Books"]
PRODUCTS = {
    "Electronics": ["Headphones", "Smartwatch", "Speaker", "Charger", "Keyboard"],
    "Clothing": ["T-Shirt", "Jeans", "Jacket", "Sneakers", "Dress"],
    "Home": ["Lamp", "Pillow", "Mug Set", "Blanket", "Candle"],
    "Sports": ["Yoga Mat", "Dumbbells", "Water Bottle", "Resistance Band", "Jump Rope"],
    "Beauty": ["Serum", "Moisturizer", "Sunscreen", "Shampoo", "Lip Balm"],
    "Books": ["Novel", "Cookbook", "Biography", "Sci-Fi", "History"],
}
STATUSES = ["completed", "completed", "completed", "completed", "refunded", "pending"]

start = date(2024, 1, 1)


def main() -> None:
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "order_id", "customer_id", "order_date", "region", "category",
            "product", "quantity", "unit_price", "amount", "status",
        ])
        for i in range(1, N + 1):
            customer = random.choice(CUSTOMERS)
            order_date = start + timedelta(days=random.randint(0, 365))
            region = random.choice(REGIONS)
            category = random.choice(CATEGORIES)
            product = random.choice(PRODUCTS[category])
            quantity = random.randint(1, 5)
            unit_price = round(random.uniform(9.99, 499.99), 2)
            amount = round(quantity * unit_price, 2)
            status = random.choice(STATUSES)
            writer.writerow([
                i, customer, order_date.isoformat(), region, category,
                product, quantity, unit_price, amount, status,
            ])
    print(f"wrote {N} rows to {OUT}")


if __name__ == "__main__":
    main()