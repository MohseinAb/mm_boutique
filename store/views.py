from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import CreateUserForm, ProfileForm
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.db.models import Sum, F, Q
from django.contrib.auth.decorators import user_passes_test
from django.db.models.functions import TruncDate, TruncMonth, TruncYear
from django.core.paginator import Paginator
from .models import Product, Cart, CartItem, Customer, Order, OrderItem, Category, Payment
from decimal import Decimal
from django.http import JsonResponse
import json
from django.conf import settings
from django.db import transaction

# Microservice helper imports
from .services import convert_php_to_usd, log_order_to_firebase, send_email_receipt



def register(request):
    if request.method == "POST":
        form = CreateUserForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = CreateUserForm()

    return render(request, 'store/register.html', {'form': form})


def landing(request):
    return render(request, 'store/landing.html')


def login_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if user.is_superuser:
                return redirect('admin_dashboard')

            if user.is_staff:
                return redirect('staff_dashboard')

            return redirect('landing')

    return render(request, 'store/login.html')


def logout_user(request):
    logout(request)
    return redirect('landing')


def product_list(request):
    products = Product.objects.all().order_by('-id')
    categories = Category.objects.all()

    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')

    if search_query:
        products = products.filter(name__icontains=search_query)

    if category_filter:
        products = products.filter(category_id=category_filter)

    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    paged_products = paginator.get_page(page_number)

    return render(request, 'store/products.html', {
        'products': paged_products,
        'categories': categories,
        'search_query': search_query,
        'category_filter': category_filter,
    })


def product_detail(request, id):
    product = get_object_or_404(Product, id=id)
    return render(request, 'store/product_detail.html', {'product': product})


@login_required
def add_to_cart(request, product_id):
    customer = Customer.objects.filter(user=request.user).first()

    if not customer:
        return redirect('landing')

    product = get_object_or_404(Product, id=product_id)
    cart, created = Cart.objects.get_or_create(customer=customer)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)

    if not created:
        item.quantity += 1
        item.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        total_items = sum(i.quantity for i in cart.cartitem_set.all())
        return JsonResponse({'status': 'success', 'cart_count': total_items})

    return redirect('cart')


@login_required
def cart_view(request):
    customer = Customer.objects.filter(user=request.user).first()

    if not customer:
        return redirect('landing')

    cart = Cart.objects.filter(customer=customer).first()

    if not cart:
        items = []
        total = 0
    else:
        items = CartItem.objects.filter(cart=cart)
        total = sum(item.product.price * item.quantity for item in items)

    return render(request, 'store/cart.html', {
        'items': items,
        'total': total
    })


@login_required
def checkout(request):
    customer, created = Customer.objects.get_or_create(user=request.user)

    cart = Cart.objects.filter(customer=customer).first()
    if not cart:
        return redirect('cart')

    items = CartItem.objects.filter(cart=cart)
    if not items.exists():
        return redirect('cart')

    total = sum(item.product.price * item.quantity for item in items)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            payment_method = data.get('payment_method')
            usd_paid = float(data.get('usd_paid', 0.0))
            
            # Extract Delivery Data
            delivery_method = data.get('delivery_method', 'Pickup')
            street_address = data.get('street_address', '')
            city = data.get('city', '')
            zip_code = data.get('zip_code', '')

            with transaction.atomic():
                order = Order.objects.create(
                    customer=customer,
                    complete=True,
                    status='Pending',
                    delivery_method=delivery_method,
                    street_address=street_address,
                    city=city,
                    zip_code=zip_code
                )

                for item in items:
                    product = item.product
                    if product.stock >= item.quantity:
                        product.stock -= item.quantity
                    else:
                        product.stock = 0
                    product.save()

                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        quantity=item.quantity,
                        price=item.product.price
                    )

                Payment.objects.create(
                    order=order,
                    amount=total,
                    method=payment_method
                )

                items.delete()

            firebase_result = log_order_to_firebase(
                order_id=str(order.id),
                customer_name=request.user.username,
                php_total=float(total),
                usd_paid=usd_paid if usd_paid > 0 else float(total)
            )


            # 4. Call Microservice: Send Email Receipt
            customer_email = request.user.email if request.user.email else "customer@example.com"
            email_result = send_email_receipt(
                email=customer_email,
                order_id=str(order.id),
                total=float(total)
            )

            return JsonResponse({
                'status': 'success',
                'order_id': order.id,
                'firebase_status': firebase_result.get('status'),
                'email_status': email_result.get('status')
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    conversion_data = convert_php_to_usd(float(total))
    usd_amount = conversion_data.get("usd_amount", 0.0)
    exchange_rate = conversion_data.get("exchange_rate", 0.0)

    context = {
        'items': items,
        'total': total,
        'usd_amount': usd_amount,
        'exchange_rate': exchange_rate,
        'paypal_client_id': 'test',
        'customer': customer,
    }
    return render(request, 'store/checkout.html', context)


@login_required
def user_orders(request):
    customer = Customer.objects.filter(user=request.user).first()

    if not customer:
        return redirect('landing')

    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'All')

    orders = Order.objects.filter(customer=customer).order_by('-date_created')

    if search_query:
        orders = orders.filter(id__icontains=search_query)

    if status_filter and status_filter != 'All':
        orders = orders.filter(status=status_filter)

    paginator = Paginator(orders, 5)
    page_number = request.GET.get('page')
    paged_orders = paginator.get_page(page_number)

    status_choices = ['All', 'Pending', 'Preparing', 'Ready for Pickup', 'Completed', 'Cancelled']

    return render(request, 'store/orders.html', {
        'orders': paged_orders,
        'search_query': search_query,
        'status_filter': status_filter,
        'status_choices': status_choices
    })


@staff_member_required
def manage_orders(request):
    orders = Order.objects.filter(complete=True).select_related('customer__user').order_by('-date_created')

    search_query = request.GET.get('search', '')
    if search_query:
        orders = orders.filter(
            Q(customer__user__username__icontains=search_query) |
            Q(id__icontains=search_query)
        )

    status_filter = request.GET.get('status', '')
    if status_filter and status_filter != 'All':
        orders = orders.filter(status=status_filter)

    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    orders = paginator.get_page(page_number)

    context = {
        'orders': orders,
        'search_query': search_query,
        'status_filter': status_filter,
        'status_choices': ['All'] + [choice[0] for choice in Order.STATUS_CHOICES],
    }
    return render(request, 'store/manage_orders.html', context)


@login_required
def update_quantity(request, item_id, action):
    item = get_object_or_404(CartItem, id=item_id)
    cart = item.cart

    if action == 'increase':
        if item.quantity < item.product.stock:
            item.quantity += 1
            item.save()
    elif action == 'decrease':
        item.quantity -= 1
        if item.quantity <= 0:
            item.delete()
            item = None
        else:
            item.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        cart_items = CartItem.objects.filter(cart=cart)
        cart_total = sum(i.product.price * i.quantity for i in cart_items)
        cart_count = sum(i.quantity for i in cart_items)

        return JsonResponse({
            'status': 'success',
            'new_quantity': item.quantity if item else 0,
            'item_total': float(item.product.price * item.quantity) if item else 0,
            'cart_total': float(cart_total),
            'cart_count': cart_count
        })

    return redirect('cart')


@login_required
def remove_item(request, item_id):
    item = get_object_or_404(CartItem, id=item_id)
    cart = item.cart
    item.delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        cart_items = CartItem.objects.filter(cart=cart)
        cart_total = sum(i.product.price * i.quantity for i in cart_items)
        cart_count = sum(i.quantity for i in cart_items)

        return JsonResponse({
            'status': 'success',
            'cart_total': float(cart_total),
            'cart_count': cart_count
        })

    return redirect('cart')


@staff_member_required
def update_status(request, order_id, status):
    order = get_object_or_404(Order, id=order_id)

    if order.status == 'Completed' or order.status == 'Cancelled':
        return redirect('manage_orders')

    allowed_statuses = ['Pending', 'Preparing', 'Ready for Pickup', 'Completed', 'Cancelled']

    if status in allowed_statuses:
        if status == 'Cancelled':
            with transaction.atomic():
                for item in order.orderitem_set.all():
                    product = item.product
                    product.stock += item.quantity
                    product.save()

        order.status = status
        order.save()

    return redirect('manage_orders')


@login_required
def profile(request):
    customer, created = Customer.objects.get_or_create(user=request.user)

    return render(request, 'store/profile.html', {
        'customer': customer
    })


@login_required
def edit_profile(request):
    customer, created = Customer.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=customer)

        if form.is_valid():
            form.save()

            username = request.POST.get('username')
            if username:
                request.user.username = username

            email = request.POST.get('email')
            if email is not None:        
                request.user.email = email

            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            if first_name is not None:
                request.user.first_name = first_name
            if last_name is not None:
                request.user.last_name = last_name

            password = request.POST.get('password')
            if password:
                request.user.set_password(password)

            request.user.save()
            update_session_auth_hash(request, request.user)

            return redirect('profile')

    else:
        form = ProfileForm(instance=customer)

    return render(request, 'store/edit_profile.html', {
        'form': form,
        'customer': customer,
        'username': request.user.username,
        'email': request.user.email,
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
    })


@staff_member_required
def staff_dashboard(request):
    active_orders_count = Order.objects.exclude(status__in=['Completed', 'Cancelled']).count()
    refund_needed_count = Order.objects.filter(status='Cancelled', refunded=False).count()

    return render(request, 'store/staff/dashboard.html', {
        'active_orders_count': active_orders_count,
        'refund_needed_count': refund_needed_count
    })


@staff_member_required
def add_product(request):
    categories = Category.objects.all()

    if request.method == "POST":
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        size = request.POST.get('size')
        color = request.POST.get('color')
        stock = request.POST.get('stock')
        image = request.FILES.get('image')

        if name and category_id and price and size and color and stock:
            Product.objects.create(
                name=name,
                category_id=category_id,
                price=price,
                size=size,
                color=color,
                stock=stock,
                image=image
            )

            return redirect('manage_products')

    return render(request, 'store/staff/add_product.html', {
        'categories': categories
    })


@staff_member_required
def manage_products(request):
    product_search = request.GET.get('product_search', '')
    category_filter = request.GET.get('category_filter', '')

    products = Product.objects.all().order_by('-id')

    if product_search:
        products = products.filter(name__icontains=product_search)

    if category_filter:
        products = products.filter(category_id=category_filter)

    product_paginator = Paginator(products, 10)
    product_page = request.GET.get('product_page')
    paged_products = product_paginator.get_page(product_page)

    category_search = request.GET.get('category_search', '')
    categories = Category.objects.all().order_by('name')

    if category_search:
        categories = categories.filter(name__icontains=category_search)

    category_paginator = Paginator(categories, 10)
    category_page = request.GET.get('category_page')
    paged_categories = category_paginator.get_page(category_page)

    all_categories = Category.objects.all()

    return render(request, 'store/staff/manage_products.html', {
        'products': paged_products,
        'categories': paged_categories,
        'all_categories': all_categories,
        'product_search': product_search,
        'category_filter': category_filter,
        'category_search': category_search,
    })


@staff_member_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    categories = Category.objects.all()

    if request.method == "POST":
        product.name = request.POST.get('name')
        product.category_id = request.POST.get('category')
        product.price = request.POST.get('price')
        product.size = request.POST.get('size')
        product.color = request.POST.get('color')
        product.stock = request.POST.get('stock')

        if request.FILES.get('image'):
            product.image = request.FILES.get('image')

        product.save()

        return redirect('manage_products')

    return render(request, 'store/staff/edit_product.html', {
        'product': product,
        'categories': categories
    })


@staff_member_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.delete()
    return redirect('manage_products')


@staff_member_required
def manage_categories(request):
    categories = Category.objects.all()
    return render(request, 'store/staff/manage_categories.html', {'categories': categories})


@staff_member_required
def staff_profile(request):
    user = request.user

    if request.method == "POST":
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.save()

        return redirect('staff_profile')

    return render(request, 'store/staff/profile.html', {
        'user': user
    })


@login_required
def edit_staff_account(request):
    user = request.user
    if not user.is_staff:
        return redirect('landing')

    customer, created = Customer.objects.get_or_create(user=user)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()

            user.username = request.POST.get('username')
            user.email = request.POST.get('email')
            user.first_name = request.POST.get('first_name')
            user.last_name = request.POST.get('last_name')

            password = request.POST.get('password')
            if password:
                user.set_password(password)

            user.save()
            update_session_auth_hash(request, user)
            return redirect('staff_profile')
    else:
        form = ProfileForm(instance=customer)

    return render(request, 'store/staff/edit_profile.html', {
        'user': user,
        'form': form
    })


@staff_member_required
def add_category(request):
    if request.method == "POST":
        name = request.POST.get('name')
        Category.objects.create(name=name)
        return redirect('manage_products')

    return render(request, 'store/staff/add_category.html')


@staff_member_required
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        category.name = request.POST.get('name')
        category.save()
        return redirect('manage_products')

    return render(request, 'store/staff/edit_category.html', {'category': category})


@staff_member_required
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    category.delete()
    return redirect('manage_products')


@staff_member_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('landing')

    user_search = request.GET.get('user_search', '')
    users_qs = User.objects.all().order_by('id')
    if user_search:
        users_qs = users_qs.filter(username__icontains=user_search)

    user_paginator = Paginator(users_qs, 10)
    user_page_number = request.GET.get('user_page')
    users = user_paginator.get_page(user_page_number)

    products = Product.objects.all()
    orders = Order.objects.all()

    total_sales = orders.filter(complete=True).exclude(status='Cancelled').aggregate(
        total=Sum(F('orderitem__price') * F('orderitem__quantity'))
    )['total'] or 0

    total_orders = orders.count()
    total_users = users_qs.count()

    refund_queue = Order.objects.filter(status='Cancelled', refunded=False)
    refund_needed_count = refund_queue.count()

    daily_sales_qs = (
        OrderItem.objects
        .filter(order__complete=True)
        .exclude(order__status='Cancelled')
        .annotate(date=TruncDate('order__date_created'))
        .values('date')
        .annotate(total_sales=Sum(F('price') * F('quantity')))
        .order_by('date')
    )

    daily_sales = []
    for sale in daily_sales_qs:
        daily_sales.append({
            'date': sale['date'].strftime("%Y-%m-%d") if sale['date'] else '',
            'total_sales': float(sale['total_sales'] or 0)
        })

    pending_count = orders.filter(status='Pending').count()
    processing_count = orders.filter(status='Preparing').count()
    shipped_count = orders.filter(status='Ready for Pickup').count()
    delivered_count = orders.filter(status='Completed').count()

    context = {
        'users': users,
        'products': products,
        'orders': orders,
        'total_sales': float(total_sales),
        'total_orders': total_orders,
        'total_users': total_users,
        'daily_sales': daily_sales,
        'pending_count': pending_count,
        'processing_count': processing_count,
        'shipped_count': shipped_count,
        'delivered_count': delivered_count,
        'user_search': user_search,
        'refund_queue': refund_queue,
        'refund_needed_count': refund_needed_count,
    }

    return render(request, 'store/admin/dashboard.html', context)


@staff_member_required
def toggle_staff(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.user.id == user.id:
        return redirect('admin_dashboard')

    user.is_staff = not user.is_staff
    user.save()

    return redirect('admin_dashboard')


@staff_member_required
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.user.id == user.id:
        return redirect('admin_dashboard')

    user.delete()

    return redirect('admin_dashboard')


def is_admin(user):
    return user.is_staff or user.is_superuser


@user_passes_test(is_admin)
def admin_sales_report(request):
    view = request.GET.get('view', 'daily')
    month = request.GET.get('month')
    year = request.GET.get('year')

    try:
        month = int(month) if month and month != 'None' and month != '' else None
    except ValueError:
        month = None
    try:
        year = int(year) if year and year != 'None' and year != '' else None
    except ValueError:
        year = None

    all_orders = Order.objects.filter(complete=True).order_by('-date_created')

    if year:
        all_orders = all_orders.filter(date_created__year=year)
    if month:
        all_orders = all_orders.filter(date_created__month=month)

    completed_orders = all_orders.filter(status='Completed')
    total_sales = completed_orders.aggregate(
        total=Sum(F('orderitem__price') * F('orderitem__quantity'))
    )['total'] or 0
    total_orders_count = all_orders.count()

    sales_trend = []
    dates = []
    totals = []

    if view == "daily":
        sales_trend = (
            completed_orders
            .annotate(date=TruncDate('date_created'))
            .values('date')
            .annotate(total=Sum(F('orderitem__price') * F('orderitem__quantity')))
            .order_by('date')
        )
        dates = [item['date'].strftime("%Y-%m-%d") for item in sales_trend]
        totals = [float(item['total'] or 0) for item in sales_trend]
    elif view == "monthly":
        sales_trend = (
            completed_orders
            .annotate(month=TruncMonth('date_created'))
            .values('month')
            .annotate(total=Sum(F('orderitem__price') * F('orderitem__quantity')))
            .order_by('month')
        )
    elif view == "yearly":
        sales_trend = (
            completed_orders
            .annotate(year=TruncYear('date_created'))
            .values('year')
            .annotate(total=Sum(F('orderitem__price') * F('orderitem__quantity')))
            .order_by('year')
        )

    paginator = Paginator(all_orders, 10)
    page_number = request.GET.get('page')
    paged_orders = paginator.get_page(page_number)

    years_list = [d.year for d in Order.objects.dates('date_created', 'year', order='DESC')]

    context = {
        'orders': paged_orders,
        'total_sales': float(total_sales),
        'total_orders': total_orders_count,
        'view': view,
        'dates': dates,
        'totals': totals,
        'monthly_sales': sales_trend if view == 'monthly' else [],
        'yearly_sales': sales_trend if view == 'yearly' else [],
        'selected_month': month,
        'selected_year': year,
        'years': years_list,
        'months_list': range(1, 13),
    }

    return render(request, 'store/admin/sales_report.html', context)


@login_required
def cancel_order(request, order_id):
    customer = get_object_or_404(Customer, user=request.user)
    order = get_object_or_404(Order, id=order_id, customer=customer)

    if order.status == 'Pending':
        with transaction.atomic():
            order_items = order.orderitem_set.all()
            for item in order_items:
                product = item.product
                product.stock += item.quantity
                product.save()

            order.status = 'Cancelled'
            order.save()

        return JsonResponse({'status': 'success', 'message': 'Order cancelled successfully.'})

    return JsonResponse({'status': 'error', 'message': 'Orders can only be cancelled while Pending.'}, status=400)


@user_passes_test(lambda u: u.is_superuser)
def mark_refunded(request, order_id):
    order = get_object_or_404(Order, id=order_id, status='Cancelled')
    order.refunded = True
    order.save()
    return redirect('admin_dashboard')