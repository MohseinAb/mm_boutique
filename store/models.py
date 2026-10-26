from django.db import models
from django.contrib.auth.models import User


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    size = models.CharField(max_length=50)
    color = models.CharField(max_length=50)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    stock = models.IntegerField()

    def __str__(self):
        return self.name


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200, null=True)
    phone = models.CharField(max_length=200, null=True)
    
    # New dedicated address fields
    street_address = models.CharField(max_length=200, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    zip_code = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return str(self.name) if self.name else "Customer"


class Order(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Preparing', 'Preparing'),
        ('Ready for Pickup', 'Ready for Pickup'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    )
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    complete = models.BooleanField(default=False, null=True, blank=False)
    transaction_id = models.CharField(max_length=100, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    refunded = models.BooleanField(default=False)
    
    # New Delivery Fields
    delivery_method = models.CharField(max_length=20, default='Pickup')
    street_address = models.CharField(max_length=200, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    zip_code = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return str(self.id)


class OrderItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    def __str__(self):
        return self.product.name

    @property
    def get_total(self):
        if self.price:
            return self.quantity * self.price
        return 0


class Payment(models.Model):
    METHOD_CHOICES = (
        ('COP', 'Cash on Pickup'), # Changed from COD to COP for accuracy
        ('PayPal', 'PayPal'),       # Changed from Card to PayPal
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=50, choices=METHOD_CHOICES)
    date_paid = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment for Order {self.order.id} via {self.get_method_display()}"

class Cart(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)