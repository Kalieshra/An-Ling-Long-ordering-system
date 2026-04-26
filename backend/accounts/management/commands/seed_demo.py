"""Populate the database with realistic demo data so a fresh dev environment
runs end-to-end without manual entry. Idempotent: re-running upserts."""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Seed demo categories, menu items, modifier groups, tables, and users."

    @transaction.atomic
    def handle(self, *args, **options):
        from menu.models import Category, MenuItem, ModifierGroup, ModifierOption
        from orders.models import Table

        from accounts.models import Role, User

        # --- Users -----------------------------------------------------------
        users_spec = [
            ("demo-admin@rms.local",    "admin-pw-long-enough",    Role.ADMIN),
            ("demo-cashier@rms.local",  "cashier-pw-long-enough",  Role.CASHIER),
            ("demo-kitchen@rms.local",  "kitchen-pw-long-enough",  Role.KITCHEN),
            ("demo-customer1@rms.local", "customer-pw-long-enough", Role.CUSTOMER),
            ("demo-customer2@rms.local", "customer-pw-long-enough", Role.CUSTOMER),
        ]
        for email, pw, role in users_spec:
            user, _ = User.objects.get_or_create(email=email, defaults={"role": role})
            user.role = role
            user.set_password(pw)
            user.save()

        # --- Categories (3) --------------------------------------------------
        cats_spec = [
            ("Pizzas",  "pizzas",  1),
            ("Burgers", "burgers", 2),
            ("Drinks",  "drinks",  3),
        ]
        cats = {}
        for name, slug, order in cats_spec:
            cats[slug], _ = Category.objects.update_or_create(
                slug=slug, defaults={"name": name, "display_order": order, "is_active": True},
            )

        # --- Dishes (12 total: 6 pizzas + 6 burgers) ------------------------
        pizza_names = ["Margherita", "Pepperoni", "Hawaiian", "Veggie", "BBQ Chicken", "Quattro Formaggi"]
        burger_names = ["Cheeseburger", "Bacon Burger", "Mushroom Burger", "Chicken Burger", "Veggie Burger", "Double Beef"]

        for i, name in enumerate(pizza_names):
            MenuItem.objects.update_or_create(
                category=cats["pizzas"], name=name,
                defaults={
                    "price": Decimal("80") + (i * 10),
                    "item_type": "dish",
                    "is_available": True,
                    "tags": ["featured"] if i < 2 else [],
                    "prep_time_min": 12,
                },
            )

        for i, name in enumerate(burger_names):
            MenuItem.objects.update_or_create(
                category=cats["burgers"], name=name,
                defaults={
                    "price": Decimal("60") + (i * 8),
                    "item_type": "dish",
                    "is_available": True,
                    "prep_time_min": 8,
                },
            )

        # --- Drinks (6) ------------------------------------------------------
        drink_names = ["Cola", "Sprite", "Fanta", "Iced Tea", "Lemonade", "Mineral Water"]
        for i, name in enumerate(drink_names):
            MenuItem.objects.update_or_create(
                category=cats["drinks"], name=name,
                defaults={
                    "price": Decimal("15") + (i * 2),
                    "item_type": "drink",
                    "is_available": True,
                    "prep_time_min": 1,
                },
            )

        # --- Modifier groups (5) --------------------------------------------
        margherita = MenuItem.objects.get(category=cats["pizzas"], name="Margherita")
        pepperoni = MenuItem.objects.get(category=cats["pizzas"], name="Pepperoni")
        cheese_burger = MenuItem.objects.get(category=cats["burgers"], name="Cheeseburger")
        bacon_burger = MenuItem.objects.get(category=cats["burgers"], name="Bacon Burger")
        chicken_burger = MenuItem.objects.get(category=cats["burgers"], name="Chicken Burger")

        modifier_specs = [
            (margherita,    "Size",     [("Small", "0"), ("Medium", "20"), ("Large", "40")], True),
            (pepperoni,     "Size",     [("Small", "0"), ("Medium", "25"), ("Large", "50")], True),
            (cheese_burger, "Cheese",   [("Cheddar", "0"), ("Swiss", "5"), ("Blue", "10")], False),
            (bacon_burger,  "Cooking",  [("Rare", "0"), ("Medium", "0"), ("Well Done", "0")], True),
            (chicken_burger, "Sauce",   [("Mayo", "0"), ("BBQ", "5"), ("Hot", "5")], False),
        ]
        for item, group_name, options, required in modifier_specs:
            group, _ = ModifierGroup.objects.update_or_create(
                menu_item=item, name=group_name,
                defaults={"min_select": 1 if required else 0, "max_select": 1, "is_required": required},
            )
            for opt_name, delta in options:
                ModifierOption.objects.update_or_create(
                    group=group, name=opt_name,
                    defaults={"price_delta": Decimal(delta), "is_available": True},
                )

        # --- Tables (4) ------------------------------------------------------
        for n in range(1, 5):
            Table.objects.update_or_create(
                number=n,
                defaults={"capacity": 2 if n <= 2 else 4, "is_active": True, "qr_token": f"demo-table-{n}"},
            )

        self.stdout.write(self.style.SUCCESS(
            "Seeded: 3 categories, 12 dishes, 6 drinks, 5 modifier groups, 4 tables, "
            "1 admin + 1 cashier + 1 kitchen + 2 customers."
        ))
