"""Session-auth views for staff dashboards. Customer accounts use JWT (api/v1/auth/)."""
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .models import Role

ROLE_LANDING = {
    Role.ADMIN: "/dashboard/",
    Role.CASHIER: "/cashier/",
    Role.KITCHEN: "/kitchen/",
}


@require_http_methods(["GET", "POST"])
def staff_login(request):
    if request.method == "GET":
        return render(request, "auth/login.html")

    email = request.POST.get("email", "").strip().lower()
    password = request.POST.get("password", "")
    user = authenticate(request, username=email, password=password)

    if user is None or not user.is_active:
        return render(
            request,
            "auth/login.html",
            {"error": "Invalid email or password."},
            status=200,
        )

    if user.role == Role.CUSTOMER:
        return render(
            request,
            "auth/login.html",
            {"error": "Customer accounts cannot sign in here."},
            status=200,
        )

    login(request, user)
    landing = ROLE_LANDING.get(user.role, "/")
    next_url = request.POST.get("next") or request.GET.get("next") or landing
    return HttpResponseRedirect(next_url)


@require_http_methods(["POST", "GET"])
def staff_logout(request):
    logout(request)
    return redirect("/login/")


@login_required
def dashboard_home(request):
    return render(request, "dashboard/home.html", {"user_role": request.user.role})


@login_required
def cashier_home(request):
    return render(request, "cashier/home.html", {"user_role": request.user.role})


@login_required
def kitchen_home(request):
    return render(request, "kitchen/home.html", {"user_role": request.user.role})
