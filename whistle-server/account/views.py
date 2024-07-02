from django.shortcuts import render


def get_account(request):
    
    return render(request, "account/account.html")
