# Phase 2 — Menu Management — Design

**Date:** 2026-04-25
**Author:** Solo developer (Zagazig, Sharqia, Egypt) + Claude
**Parent spec:** `docs/superpowers/specs/2026-04-24-rms-mvp-design.md` (§6 Phase 2)
**Status:** Approved for implementation planning
**Branch:** `phase-2-menu` (cut from `main` after `phase-1-foundation` tag)

---

## 1. Purpose

Give the admin full CRUD over the menu (Category, MenuItem, ModifierGroup, ModifierOption, Ingredient, Recipe) and expose a public read-only HTTP API the cashier POS, kitchen display, and future customer mobile app will consume. Image upload works end-to-end. Search is fuzzy enough to forgive typos in either Arabic or English.

By end of Phase 2, the demo flow is: admin signs in → creates "Drinks" category → adds "Iced Latte" with image and a "Size" modifier group → flips it `is_available=True` → unauthenticated `GET /api/v1/menu/items/?category=drinks` returns the item with nested modifier groups.

## 2. Non-goals (deferred)

- Stock auto-deduction on order paid (Phase 7)
- Image resizing / multiple sizes / CDN
- Drag-drop reorder of modifier groups (server form re-render is good enough)
- Full-text search ranking (trigram similarity is the search Phase 2 ships)
- Arabic translation pipeline (model has `name_ar` field; admin UI has the input; no machine translation)
- Featured items endpoint (`/menu/featured/`) and its caching — Phase 5
- Bulk import/export (CSV, JSON)
- A separate inventory adjustments ledger — `Ingredient.stock_qty` is editable directly in Phase 2; the audit log lives in Phase 7

## 3. Scope summary

| Area | In Phase 2 |
|---|---|
| Models | Category, MenuItem, ModifierGroup, ModifierOption, Ingredient, Recipe |
| Postgres extension | `pg_trgm` enabled via migration; GIN index on `MenuItem.name` |
| Admin dashboard CRUD | `/dashboard/categories/`, `/dashboard/menu/`, `/dashboard/inventory/` (CoreUI templates, server-rendered, no SPA) |
| Django admin | All six models registered with inlines (ModifierGroupInline, ModifierOptionInline, RecipeInline) |
| Public API | `GET /api/v1/menu/categories/`, `/items/?category=&type=&search=&ordering=`, `/items/<id>/` |
| Image upload | Direct `ImageField`, Pillow magic-byte validation, 5 MB cap enforced in form layer |
| Auth | `/dashboard/*` admin-only via existing `AllowedRoleForPath`; menu API `AllowAny` |
| Tests | ~40-50 new tests across unit / integration / E2E |

## 4. Architecture

### 4.1 Apps

A new Django app `menu` is added under `backend/`. It has no inbound dependencies from `accounts`. The dashboards app already exists from Phase 1 and gains new templates under `templates/dashboard/{categories,menu,inventory}/`.

```
backend/
├── accounts/        # Phase 1 — User, Role, auth, role-gating
├── menu/            # NEW — Phase 2
│   ├── models.py
│   ├── managers.py
│   ├── serializers.py
│   ├── views_api.py
│   ├── views_dashboard.py
│   ├── forms.py
│   ├── filters.py
│   ├── admin.py
│   ├── urls_api.py
│   ├── urls_dashboard.py
│   └── migrations/
└── templates/
    └── dashboard/
        ├── categories/{list,form,confirm_delete}.html
        ├── menu/{list,form,confirm_delete}.html
        └── inventory/{list,form,confirm_delete}.html
```

### 4.2 Routing

`backend/rms/urls.py` is extended:

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("accounts.urls_api")),
    path("api/v1/menu/", include("menu.urls_api")),       # NEW
    path("dashboard/menu/",       include("menu.urls_dashboard", namespace="menu")),  # NEW
    path("", include("accounts.urls_web")),
]
```

The middleware reads `STAFF_PATH_ROLES` to gate `/dashboard/`. `/dashboard/menu/`, `/dashboard/categories/`, and `/dashboard/inventory/` all start with `/dashboard/`, so they inherit the admin-only gate without any changes to the middleware. The existing `dashboard_home` view at `/dashboard/` gains nav links to the new pages.

### 4.3 Persistence

Two migrations land in this phase:

1. `menu/migrations/0001_initial.py` — auto-generated. Creates Category, MenuItem, ModifierGroup, ModifierOption, Ingredient, Recipe with all fields and ordinary indexes.
2. `menu/migrations/0002_pg_trgm.py` — hand-written `RunSQL` migration that runs `CREATE EXTENSION IF NOT EXISTS pg_trgm` and adds the GIN trigram index on `menuitem.name` via raw SQL. This is separate so a database without superuser rights can still apply 0001 then ask its DBA for the extension.

The trigram index is also declared on `MenuItem.Meta.indexes` for completeness, but the actual `CREATE INDEX` runs in 0002 after the extension exists.

### 4.4 Shared services (none)

Phase 2 has no business-logic services file (no orchestration that crosses model boundaries). Forms and views talk to models directly; the admin dashboard CRUD and API both go through the same model managers (`MenuItem.objects.available()`).

## 5. Data model

```python
# backend/menu/models.py
from decimal import Decimal

from django.contrib.postgres.indexes import GinIndex
from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return self.name


class MenuItemManager(models.Manager):
    def available(self):
        return self.filter(is_available=True, category__is_active=True)


class MenuItem(models.Model):
    class Type(models.TextChoices):
        DISH = "dish", "Dish"
        DRINK = "drink", "Drink"
        COMBO = "combo", "Combo"

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="items")
    name = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    item_type = models.CharField(max_length=10, choices=Type.choices, default=Type.DISH)
    price = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    image = models.ImageField(upload_to="menu/", blank=True, null=True)
    is_available = models.BooleanField(default=True, db_index=True)
    prep_time_min = models.PositiveSmallIntegerField(default=10)
    calories = models.PositiveIntegerField(null=True, blank=True)
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MenuItemManager()

    class Meta:
        indexes = [
            models.Index(fields=["category", "is_available"]),
            models.Index(fields=["item_type", "is_available"]),
            GinIndex(
                fields=["name"],
                name="menuitem_name_trgm_idx",
                opclasses=["gin_trgm_ops"],
            ),
        ]
        ordering = ["category__display_order", "name"]

    def __str__(self) -> str:
        return self.name


class ModifierGroup(models.Model):
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, related_name="modifier_groups"
    )
    name = models.CharField(max_length=80)
    min_select = models.PositiveSmallIntegerField(default=0)
    max_select = models.PositiveSmallIntegerField(default=1)
    is_required = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order"]


class ModifierOption(models.Model):
    group = models.ForeignKey(
        ModifierGroup, on_delete=models.CASCADE, related_name="options"
    )
    name = models.CharField(max_length=80)
    price_delta = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_available = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order"]


class Ingredient(models.Model):
    class Unit(models.TextChoices):
        GRAM = "g", "Grams"
        KG = "kg", "Kilograms"
        ML = "ml", "Milliliters"
        L = "l", "Liters"
        PIECE = "pc", "Piece"

    name = models.CharField(max_length=100, unique=True)
    unit = models.CharField(max_length=4, choices=Unit.choices)
    stock_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    low_threshold = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    supplier = models.CharField(max_length=120, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def is_low(self) -> bool:
        return self.stock_qty <= self.low_threshold


class Recipe(models.Model):
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, related_name="recipe_items"
    )
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.PROTECT, related_name="used_in"
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=3)

    class Meta:
        unique_together = [("menu_item", "ingredient")]
```

### Data-model rules

- **`Category.on_delete=PROTECT` from MenuItem**: prevents accidental category deletion when items reference it. Admin UI surfaces this as "this category has 12 items; deactivate or move them first".
- **`MenuItem` deletion cascades** to its `ModifierGroup`s and `Recipe` rows (a deleted dish has no orphan modifiers).
- **`ModifierGroup` cascades** to its `ModifierOption`s.
- **`Ingredient.on_delete=PROTECT` from Recipe**: prevents deletion of an ingredient still referenced by a dish recipe. Admin UI explains.
- **Audit fields** (`created_at`, `updated_at`) are model-level only (not on the API); they're for ops debugging.
- **Slug** on Category is required and unique — used for URL-friendly filter `?category=salads`. Auto-generated from `name` in the admin form (Django's `prepopulated_fields = {"slug": ("name",)}`).
- **`tags` JSONField** is a flat list of strings (`["spicy", "vegan"]`) — not searched in Phase 2 (Phase 5 may add a tag filter).

## 6. Admin dashboard CRUD

### 6.1 URL map

| Method | URL | View | Template |
|---|---|---|---|
| GET | `/dashboard/menu/categories/` | `CategoryListView` | `dashboard/categories/list.html` |
| GET, POST | `/dashboard/menu/categories/new/` | `CategoryCreateView` | `dashboard/categories/form.html` |
| GET, POST | `/dashboard/menu/categories/<int:pk>/edit/` | `CategoryUpdateView` | `dashboard/categories/form.html` |
| GET, POST | `/dashboard/menu/categories/<int:pk>/delete/` | `CategoryDeleteView` | `dashboard/categories/confirm_delete.html` |
| GET | `/dashboard/menu/items/` | `MenuItemListView` | `dashboard/menu/list.html` |
| GET, POST | `/dashboard/menu/items/new/` | `MenuItemCreateView` | `dashboard/menu/form.html` |
| GET, POST | `/dashboard/menu/items/<int:pk>/edit/` | `MenuItemUpdateView` | `dashboard/menu/form.html` |
| POST | `/dashboard/menu/items/<int:pk>/toggle/` | `MenuItemToggleAvailableView` | — (302 back to list) |
| GET, POST | `/dashboard/menu/items/<int:pk>/delete/` | `MenuItemDeleteView` | `dashboard/menu/confirm_delete.html` |
| GET | `/dashboard/menu/inventory/` | `IngredientListView` | `dashboard/inventory/list.html` |
| GET, POST | `/dashboard/menu/inventory/new/` | `IngredientCreateView` | `dashboard/inventory/form.html` |
| GET, POST | `/dashboard/menu/inventory/<int:pk>/edit/` | `IngredientUpdateView` | `dashboard/inventory/form.html` |
| GET, POST | `/dashboard/menu/inventory/<int:pk>/delete/` | `IngredientDeleteView` | `dashboard/inventory/confirm_delete.html` |

URLs live under `/dashboard/menu/` so the existing `STAFF_PATH_ROLES["/dashboard/"] = "admin"` gate covers all of them. No middleware change needed.

### 6.2 Views

All views inherit from Django's generic `ListView` / `CreateView` / `UpdateView` / `DeleteView` plus a `LoginRequiredMixin` (the role check is the middleware's job, but `LoginRequiredMixin` adds the `request.user` shortcut). The `MenuItemForm` is rendered with `inlineformset_factory(MenuItem, ModifierGroup)` plus a nested `inlineformset_factory(ModifierGroup, ModifierOption)`. The `MenuItemCreateView`/`UpdateView`'s `form_valid` saves the parent then loops the formsets — pattern is "boring server-side form" with no JS.

**`MenuItemToggleAvailableView`** is the one POST-only view. It flips `is_available` and redirects back; used by an "✓/✕" button in the list.

### 6.3 Templates

- All extend `base.html` (CoreUI styling).
- Forms render with Bootstrap classes; `{{ form.image }}` renders the standard file input.
- The list views use Bootstrap `<table>` (no DataTables JS) — pagination via Django's `Paginator` (25 per page).

### 6.4 Image cap (5 MB)

`menu/forms.py::MenuItemForm.clean_image()` and `CategoryForm.clean_image()`:

```python
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

def clean_image(self):
    image = self.cleaned_data.get("image")
    if image and image.size > MAX_UPLOAD_BYTES:
        raise forms.ValidationError(
            f"Image is {image.size // 1024} KB; max is {MAX_UPLOAD_BYTES // 1024} KB."
        )
    return image
```

Pillow already validates magic bytes when the file is saved into the `ImageField`.

## 7. Public read-only API

### 7.1 Endpoints

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/v1/menu/categories/` | List of `{id, name, slug, description, image_url, display_order}` |
| `GET` | `/api/v1/menu/items/` | Paginated list of `{id, name, name_ar, item_type, price, image_url, prep_time_min, calories, tags, category: {id, slug, name}}` |
| `GET` | `/api/v1/menu/items/<int:id>/` | Detail above + nested `modifier_groups: [{id, name, min_select, max_select, is_required, options: [{id, name, price_delta, is_available}]}]` |

All three: `permission_classes = [AllowAny]`, `authentication_classes = []` (no JWT required).

### 7.2 Filters

`MenuItemFilter` (django-filter):
- `category` — exact match on `category__slug`
- `type` — exact match on `item_type`
- `search` — `TrigramSimilarity('name', value)` ≥ 0.15, ordered by similarity DESC
- `ordering` — DRF `OrderingFilter`, whitelist `["name", "price"]`
- `available=true` is the implicit default (always filtered to `is_available=True AND category__is_active=True`); admin can opt out with `?available=all` (undocumented, used by smoke tests)

### 7.3 pg_trgm fallback

If pg_trgm isn't available (e.g. some CI configurations), the search falls back to `name__icontains=value`. The fallback is a runtime check at filter init:

```python
class MenuItemFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")

    def filter_search(self, queryset, name, value):
        try:
            from django.contrib.postgres.search import TrigramSimilarity
            return (
                queryset.annotate(sim=TrigramSimilarity("name", value))
                .filter(sim__gte=0.15)
                .order_by("-sim")
            )
        except Exception:
            return queryset.filter(name__icontains=value)
```

### 7.4 Pagination

DRF's default `PageNumberPagination` with `PAGE_SIZE=20`. Configured in `REST_FRAMEWORK` settings.

### 7.5 Serializer details

- `image_url`: `serializers.ImageField()` (built-in) returns absolute URL when `request` is in context.
- `category` is nested but read-only, serialized via `CategoryMiniSerializer` (id, slug, name).
- Detail serializer prefetches modifier groups + options via `prefetch_related("modifier_groups__options")` to avoid N+1.

## 8. Django admin (back door)

`menu/admin.py` registers all six models. Highlights:

- `MenuItemAdmin`:
  - `list_display = ("name", "category", "item_type", "price", "is_available", "updated_at")`
  - `list_filter = ("category", "item_type", "is_available")`
  - `search_fields = ("name", "name_ar")`
  - `inlines = [ModifierGroupInline, RecipeInline]`
- `ModifierGroupInline` is a `TabularInline` with nested `StackedInline` for options (Django supports two levels of inline cleanly via `nested_admin` or by using a `TabularInline` for options on `ModifierGroupAdmin` page-edit view; we ship the simpler version: one inline level on MenuItem (groups), and clicking through to ModifierGroup gives an option inline).
- `CategoryAdmin` has `prepopulated_fields = {"slug": ("name",)}`.
- `IngredientAdmin` has `list_display = ("name", "unit", "stock_qty", "low_threshold", "supplier")`, with a custom `low_stock` boolean column.

## 9. Testing strategy

### 9.1 Unit (`tests/unit/`)

- `test_menu_models.py` (~10 tests):
  - Category: slug uniqueness; ordering by `display_order`
  - MenuItem: price `MinValueValidator`; `MenuItemManager.available()` excludes `is_available=False` AND `category.is_active=False`
  - ModifierGroup / Option: ordering by `display_order`
  - Ingredient: `is_low` property; unit choices
  - Recipe: `unique_together(menu_item, ingredient)`
- `test_menu_filters.py` (~6 tests): each filter independently + a combined test
- `test_menu_forms.py` (~5 tests): image-size limit; required fields; modifier formset valid + invalid

### 9.2 Integration (`tests/integration/`)

- `test_menu_api.py` (~10 tests):
  - `GET /menu/categories/` returns active only
  - `GET /menu/items/` returns available only by default
  - `?category=<slug>` filter
  - `?type=dish` filter
  - `?search=marg` matches "Margherita" via trigram (skipped on non-Postgres)
  - `?ordering=price` ascending
  - `GET /menu/items/<id>/` returns nested modifier groups
  - 404 on unknown id
  - Image URL is absolute
  - No auth header required (anon access)
- `test_menu_dashboard.py` (~12 tests):
  - Admin can list / create / edit / delete categories
  - Admin can create a menu item with image + 2 modifier groups + 3 options
  - Admin toggling `is_available` flips the field
  - Image upload > 5 MB returns form error (uses `SimpleUploadedFile`)
  - Cashier user gets 403 on every dashboard URL
  - Kitchen user gets 403
  - Anonymous redirected to `/login/`

### 9.3 E2E (`tests/e2e/test_phase2_menu.py`, ~5 Playwright tests)

1. Admin signs in → creates category → category appears in dashboard list AND in `GET /api/v1/menu/categories/`
2. Admin creates dish with PNG image upload + one modifier group with two options → API detail returns nested modifiers
3. Admin toggles dish off → API list omits it; toggles on → API list includes it
4. `?search=burgr` finds "Burger" (trigram fuzzy match)
5. Cashier signs in, navigates to `/dashboard/menu/items/` → 403 page rendered with role-aware message

All 13 Phase 1 E2E tests still pass.

## 10. Definition of done

1. New migrations apply cleanly to a fresh database AND to the existing `phase-1-foundation` database.
2. `pg_trgm` extension enabled; `CREATE EXTENSION` migration is idempotent.
3. Admin can perform every documented CRUD operation through the dashboard UI without errors.
4. Django admin (`/admin/menu/`) supports the same operations.
5. `GET /api/v1/menu/categories/` and `/items/` work for unauthenticated callers; correct filtering and search.
6. `GET /api/v1/menu/items/<id>/` returns nested modifier groups + options.
7. Image upload of a real photo (≥1 MB, <5 MB) succeeds; 6 MB upload is rejected with a clear form error.
8. All new tests (~40-50) pass; all existing 65 tests still pass.
9. `ruff check .` clean.
10. `docker compose up -d` cycles cleanly with the new migrations applied automatically.

## 11. Open points (resolved at implementation time, not now)

- Decimal precision for `price` is fixed at `(10, 2)` — sufficient for EGP up to 99,999,999.99. No need to raise.
- Whether the dashboard list pages need a search box for menu items by name. Decision: ship without it; admin can use the Django admin search if needed. Adding a search box is a one-line GET param read.
- Whether modifier groups should allow zero options after the form save. Decision: yes, an empty group is allowed (admin might be planning options); no validation error.
