from django.contrib import admin
from .models import *


class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'size', 'color', 'stock')
    search_fields = ('name', 'color', 'size')
    list_filter = ('category', 'color')
    list_editable = ('price', 'stock')
    ordering = ('name',)


class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'date_created', 'status', 'complete')
    list_filter = ('status', 'complete')
    search_fields = ('customer__user__username',)


class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price')


class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'amount', 'method', 'date_paid')
    list_filter = ('method',)


admin.site.register(Customer)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(Payment, PaymentAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Category)
admin.site.register(Cart)
admin.site.register(CartItem)

admin.site.site_header = "M&M Boutique Admin"
admin.site.site_title = "Boutique Dashboard"
admin.site.index_title = "Store Management"