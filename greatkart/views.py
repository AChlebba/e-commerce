from django.shortcuts import render
from store.models import Product
from store.models import ReviewRating
from django.db.models import Avg

def home(request):
    products = Product.objects.filter(is_available=True).annotate(score=Avg('reviewrating__rating')).order_by('-score')[:4]
    reviews = None
    for product in products:
        reviews = ReviewRating.objects.filter(product_id=product.id, status=True)
        

    context = {
        'products': products,
        'reviews': reviews,
    }
    return render(request, 'home.html', context)