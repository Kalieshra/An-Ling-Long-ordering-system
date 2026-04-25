"""Filter set for the MenuItem list endpoint."""
import django_filters

from .models import MenuItem


class MenuItemFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name="category__slug")
    type = django_filters.CharFilter(field_name="item_type")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = MenuItem
        fields: list[str] = []  # explicit declarations above suffice

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        try:
            from django.contrib.postgres.search import TrigramSimilarity

            return (
                queryset.annotate(sim=TrigramSimilarity("name", value))
                .filter(sim__gte=0.15)
                .order_by("-sim")
            )
        except Exception:
            return queryset.filter(name__icontains=value)
