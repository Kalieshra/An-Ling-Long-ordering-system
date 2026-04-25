"""DRF serializers for the customer orders API."""
from rest_framework import serializers

from .exceptions import OrderValidationError
from .models import Order, OrderItem, OrderItemModifier
from .services import create_order


class OrderItemInputSerializer(serializers.Serializer):
    menu_item = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    modifiers = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class OrderItemModifierOutSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="option.name", read_only=True)

    class Meta:
        model = OrderItemModifier
        fields = ("option", "name", "price_delta")


class OrderItemOutSerializer(serializers.ModelSerializer):
    modifiers = OrderItemModifierOutSerializer(many=True, read_only=True)
    name = serializers.CharField(source="menu_item.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "menu_item", "name", "quantity", "unit_price", "notes", "modifiers")


class OrderListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = (
            "uuid", "number", "order_type", "status", "payment_status",
            "subtotal", "tax", "total", "created_at",
        )


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemOutSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "uuid", "number", "order_type", "status", "payment_status",
            "subtotal", "tax", "service_charge", "discount", "total",
            "delivery_address", "customer_phone", "notes",
            "items", "snapshot",
            "created_at", "confirmed_at", "ready_at", "served_at",
        )


class OrderCreateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=[Order.Type.TAKEAWAY, Order.Type.DELIVERY])
    items = OrderItemInputSerializer(many=True)
    delivery_address = serializers.CharField(required=False, allow_blank=True, default="")
    customer_phone = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        return value

    def create(self, validated_data):
        try:
            return create_order(
                cart=validated_data["items"],
                customer=self.context["request"].user,
                order_type=validated_data["type"],
                delivery_address=validated_data["delivery_address"],
                customer_phone=validated_data["customer_phone"],
                notes=validated_data["notes"],
                initial_status=Order.Status.PENDING,
            )
        except OrderValidationError as e:
            raise serializers.ValidationError(str(e)) from e
