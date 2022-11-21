from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from .forms import RegistrationForm, UserForm, UserProfileForm
from .models import Account, UserProfile
from store.models import Product
from carts.models import Cart, CartItem
from carts.views import _cart_id
from orders.models import Order, OrderProduct
import requests

# VERIFICATION EMAIL
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage



def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email = form.cleaned_data['email']
            phone_number = form.cleaned_data['phone_number']
            password = form.cleaned_data['password']
            username=email.split('@')[0]

            user = Account.objects.create_user(
                first_name=first_name, 
                last_name=last_name,
                email=email,
                username=username,
                password=password,
                )
            user.phone_number = phone_number
            user.is_active = True
            user.save()

            # CREATE USER PROFILE
            profile = UserProfile()
            profile.user_id = user.id
            profile.profile_picture = 'default/default_avatar.jpg'
            profile.save()

            # USER ACTIVATION
            current_site = get_current_site(request)
            mail_subject = 'Please activate your account'
            message = render_to_string('accounts/account_verification_email.html', {
                'user': user, 
                'domain': current_site, 
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
                })
            to_email = email
            send_email = EmailMessage(mail_subject, message, to=[to_email])
            send_email.send()

            # messages.success(request, 'Activation link sent to your email address')
            return redirect('/accounts/login/?command=verification&email='+email)
    else:
        form = RegistrationForm()

    context = {
        'form': form,
    }
    return render(request, 'accounts/register.html', context)



def login(request):

    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        user = auth.authenticate(email=email, password=password)

        if user is not None:
            try:
                cart = Cart.objects.get(cart_id=_cart_id(request))
                if CartItem.objects.filter(cart=cart).exists():
                    cart_items = CartItem.objects.filter(cart=cart)

                    product_variations = []
                    product_quantity = []
                    product_id = []
                    for item in cart_items:
                        variation = item.variation.all()
                        product_variations.append([list(variation), item.product.product_name])
                        product_quantity.append(item.quantity)
                        product_id.append(item.id)

                    existing_cart_items = CartItem.objects.filter(user=user)
                    existing_variations_list = []
                    id = []
                    for item in existing_cart_items:
                        existing_variation = item.variation.all()
                        existing_variations_list.append([list(existing_variation), item.product.product_name])
                        id.append(item.id)

                    for i, variation in enumerate(product_variations):
                        if variation in existing_variations_list:
                            index = existing_variations_list.index(variation)
                            item_id = id[index]
                            item = CartItem.objects.get(id=item_id)
                            item.quantity += product_quantity[i]
                            item.user = user
                            item.save()
                        else:
                            item = CartItem.objects.get(id=product_id[i])
                            item.user = user
                            item.save()

            except:
                pass
            auth.login(request, user)
            messages.success(request, 'You are now logged in')
            url = request.META.get('HTTP_REFERER')
            try:
                query = requests.utils.urlparse(url).query
                params = dict(x.split('=') for x in query.split('&'))
                if 'next' in params:
                    nextPage = params['next']
                    return redirect(nextPage)
            except:
                return redirect('dashboard')
        else:
            messages.error(request, 'Invalid login credentials !')
            return redirect('login')

    return render(request, 'accounts/login.html', context={})



@login_required(login_url = 'login')
def logout(request):
    auth.logout(request)
    messages.success(request, 'You have been logged out')
    return redirect('login')



def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Account activated !')
        return redirect('login')
    else:
        messages.error(request, 'Invalid activation link !')
        return redirect('register')



@login_required(login_url = 'login')
def dashboard(request):
    orders = Order.objects.filter(user=request.user, is_ordered=True).order_by('-created_at')
    orders_count = orders.count()
    context = {
        "orders": orders,
        "orders_count": orders_count,
    }
    return render(request, 'accounts/dashboard.html', context)



@login_required(login_url = 'login')
def my_orders(request):
    orders = Order.objects.filter(user=request.user, is_ordered=True).order_by('-created_at')

    context = {
        'orders': orders,
    }
    return render(request, 'accounts/my_orders.html', context)



def forgotPassword(request):
    if request.method == 'POST':
        email = request.POST['email']
        if Account.objects.filter(email=email).exists():
            user = Account.objects.get(email__exact=email)

            # RESET PASSWORD EMAIL
            current_site = get_current_site(request)
            mail_subject = 'Please reset your password'
            message = render_to_string('accounts/reset_password_email.html', {
                'user': user, 
                'domain': current_site, 
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
                })
            to_email = email
            send_email = EmailMessage(mail_subject, message, to=[to_email])
            send_email.send()

            messages.success(request, 'Password reset link has been sent to your email address')
            return redirect('login')
        else:
            messages.error(request, 'Account does not exist !')
            return redirect('forgotPassword')
    return render(request, 'accounts/forgotPassword.html', context={})



def reset_password(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        request.session['uid'] = uid
        messages.success(request, 'Please reset your password !')
        return redirect('reset_password_page')
    else:
        messages.error(request, 'Invalid link !')
        return redirect('login')



def resetPasswordPage(request):
    if request.method == 'POST':
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']
        if password == confirm_password:
            uid = request.session.get('uid')
            user = Account.objects.get(pk=uid)
            user.set_password(password)
            user.save()
            messages.success(request, 'Password reset successful')
            return redirect('login')
        else:
            messages.error(request, 'Passwords do not match')
            return redirect('reset_password_page')
    else:
        return render(request, 'accounts/reset_password_page.html', context={})



@login_required(login_url = 'login')
def edit_profile(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully')
            return redirect('edit_profile')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=user_profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'user_profile': user_profile,
    }
    return render(request, 'accounts/edit_profile.html', context)



@login_required(login_url = 'login')
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST['current_password']
        new_password1 = request.POST['new_password1']
        new_password2 = request.POST['new_password2']
        user = Account.objects.get(id=request.user.id)
        if new_password1 == new_password2:
            if user.check_password(current_password):
                user.set_password(new_password1)
                user.save()
                auth.login(request, user)
                messages.success(request, 'Password has been changed successfully')
                return redirect('change_password')
            else:
                messages.error(request, 'Current password not correct')
                return redirect('change_password')
        else:
            messages.error(request, 'New passwords are not the same')
            return redirect('change_password')

    return render(request, 'accounts/change_password.html')



def order_detail(request, order_id):
    order_detail = OrderProduct.objects.filter(order_id=order_id)
    order = Order.objects.get(id=order_id)
    subtotal = 0
    for item in order_detail:
        subtotal += item.product_price * item.quantity


    context = {
        "order_detail": order_detail,
        "order": order,
        "subtotal": subtotal,
    }
    return render(request, 'accounts/order_detail.html', context)
