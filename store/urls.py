from django.urls import path
from . import views

urlpatterns = [

    path('', views.landing, name='landing'),  # homepage
    path('profile/', views.profile, name='profile'),
    path('products/', views.product_list, name='products'),
    path('staff/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/products/', views.manage_products, name='manage_products'),
    path('staff/products/add/', views.add_product, name='add_product'),
    path('staff/products/edit/<int:product_id>/', views.edit_product, name='edit_product'),
    path('staff/products/delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('staff/categories/', views.manage_categories, name='manage_categories'),
    path('staff/profile/', views.staff_profile, name='staff_profile'),
    path('product/<int:id>/', views.product_detail, name='product_detail'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_user, name='logout'),
    path('cart/', views.cart_view, name='cart'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.user_orders, name='orders'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('manage-orders/', views.manage_orders, name='manage_orders'),
    path('update/<int:item_id>/<str:action>/', views.update_quantity, name='update_quantity'),
    path('remove/<int:item_id>/', views.remove_item, name='remove_item'),
    path('update-status/<int:order_id>/<str:status>/', views.update_status, name='update_status'),
    path('staff/categories/add/', views.add_category, name='add_category'),
    path('staff/categories/edit/<int:category_id>/', views.edit_category, name='edit_category'),
    path('staff/categories/delete/<int:category_id>/', views.delete_category, name='delete_category'),
    path('staff/profile/edit/', views.edit_staff_account, name='edit_staff_account'),
    path('sales-report/', views.admin_sales_report, name='sales_report'),
    path('toggle-staff/<int:user_id>/', views.toggle_staff, name='toggle_staff'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('cancel-order/<int:order_id>/', views.cancel_order, name='cancel_order'),
    path('mark-refunded/<int:order_id>/', views.mark_refunded, name='mark_refunded')
]