from django.shortcuts import render, redirect
from carts.models import CartItem
from django.http import JsonResponse
from .forms import OrderForm
from .models import Order, Payment, OrderProduct
from store.models import Product
import datetime
from django.contrib import messages
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
import json
from django.views.decorators.csrf import csrf_protect

def payment(request):
    body = json.loads(request.body)
    order = Order.objects.get(user=request.user, is_ordered=False, order_number=body['orderID'])
    payment = Payment(
        user = request.user,
        payment_id = body['payment_id'],
        payment_method = body['payment_method'],
        amount_paid = order.order_total,
        status = body['status'],

    )
    payment.save()
    order.payment = payment
    order.is_ordered = True
    order.save()

    # Move CartItems to OrderProduct table
    cart_items = CartItem.objects.filter(user=request.user)
    for item in cart_items:
        orderproduct = OrderProduct()
        orderproduct.order_id = order.id
        orderproduct.payment = payment
        orderproduct.user_id = request.user.id
        orderproduct.product_id = item.product_id
        orderproduct.quantity = item.quantity
        orderproduct.product_price = item.product.price
        orderproduct.ordered = True
        orderproduct.save()

        cart_item = CartItem.objects.get(id=item.id)
        product_variation = cart_item.variation.filter(product_id=item.product_id)
        orderproduct = OrderProduct.objects.get(id=orderproduct.id)
        orderproduct.variation.set(product_variation)
        orderproduct.save()

    # Reduce the quantity of sold products
        product = Product.objects.get(id=item.product_id)
        product.stock -= item.quantity
        product.save()

    # Clear cart
    CartItem.objects.filter(user = request.user).delete()

    # Send order email to customer
    mail_subject = 'Thank you for your order!'
    message = render_to_string('orders/order_received_email.html', {
        'user': request.user, 
        'order': order,
    })
    to_email = request.user.email
    send_email = EmailMessage(mail_subject, message, to=[to_email])
    send_email.send()

    # Send order number and transaction details
    data = {
        'order_number': order.order_number,
        'payment_id': payment.payment_id,
    }
    return JsonResponse(data)





def place_order(request, total=0, quantity=0):
    current_user = request.user
    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count()
    if cart_count <= 0:
        return redirect('store')

    grand_total = 0
    tax = 0
    for cart_item in cart_items:
        total += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity
    tax = (2* total) / 100
    grand_total += total + tax

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            data = Order()
            data.user = current_user
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone_number = form.cleaned_data['phone_number']
            data.email = form.cleaned_data['email']
            data.address_line1 = form.cleaned_data['address_line1']
            data.address_line2 = form.cleaned_data['address_line2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.order_note = form.cleaned_data['order_note']

            data.order_total = grand_total
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')
            data.save()

            yr = int(datetime.date.today().strftime('%Y'))
            mt = int(datetime.date.today().strftime('%m'))
            dt = int(datetime.date.today().strftime('%d'))
            d = datetime.date(yr,mt,dt)
            current_date = d.strftime('%Y%m%d')
            order_number = current_date + str(data.id)
            data.order_number = order_number
            data.save()

            order = Order.objects.get(user=current_user, is_ordered=False, order_number=order_number)
            context = {
                'order' : order,
                'cart_items' : cart_items,
                'total' : total,
                'tax' : tax,
                'grand_total' : grand_total,
            }
            return render(request, 'orders/payment.html', context)
        else:
            messages.error(request, 'Invalid checkot informations !')
            return redirect('checkout')
    else:
        context = {}
        return redirect('checkout')



def order_complete(request):
    print('0')
    order_number = request.GET.get('order_number')
    print('00')
    print(order_number)
    payment_id = request.GET.get('payment_id')
    print('000')
    print(payment_id)
    

    try:
        print('1')
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        print('2')
        order_products = OrderProduct.objects.filter(order_id=order.id)
        print('3')
        payment = Payment.objects.get(payment_id=payment_id)
        print('4')
        subtotal = 0
        for item in order_products:
            subtotal += item.product_price * item.quantity
        context = {
            "order_products": order_products,
            "order": order,
            "order_number": order.order_number,
            "payment_id": payment.payment_id,
            "payment": payment,
            "subtotal": subtotal,
        }
        return render(request, 'orders/order_complete.html', context)
    except (Payment.DoesNotExist, Order.DoesNotExist):
        return redirect('home')


    