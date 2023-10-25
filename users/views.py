from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages


def index(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Successfully logged in!")
            return redirect('index')
        else:
            messages.error(request, "Invalid credentials. Please try again!")
            return redirect('index')

    else:
        return render(request, 'index.html', {})

def login_user(request):
    return redirect('index')

def logout_user(request):
    logout(request)
    messages.success(request, "Successfully logged out!")
    return redirect('index')