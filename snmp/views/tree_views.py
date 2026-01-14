from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def monitoring_tree_view(request):
    return render(request, 'monitoring_tree.html')
