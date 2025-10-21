from django.urls import path
from . import views

app_name = 'donation'

urlpatterns = [
    # Страницы
    path('', views.donation_page, name='donation_page'),
    path('test/', views.test_stripe, name='test_stripe'),
    
    # Stripe API
    path('create-payment-intent/', views.create_payment_intent, name='create_payment_intent'),
    path('confirm-payment/', views.confirm_payment, name='confirm_payment'),
    path('stripe/webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('get-stripe-key/', views.get_stripe_publishable_key, name='get_stripe_key'),
    
    # CoinGate Crypto API
    path('crypto/currencies/', views.get_crypto_currencies, name='crypto_currencies'),
    path('crypto/create-payment/', views.create_crypto_payment, name='create_crypto_payment'),
    path('crypto/status/<str:order_id>/', views.get_crypto_payment_status, name='crypto_payment_status'),
    path('crypto/callback/', views.coingate_callback, name='coingate_callback'),
] 