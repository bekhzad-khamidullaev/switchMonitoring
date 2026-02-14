from django.http import JsonResponse
from django.shortcuts import render


class MethodNotAllowedMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code != 405:
            return response

        accepts = request.headers.get('Accept', '')
        requested_with = request.headers.get('X-Requested-With', '')
        if 'application/json' in accepts or requested_with == 'XMLHttpRequest':
            return JsonResponse({'detail': 'Method not allowed.'}, status=405)

        return render(request, '405.html', status=405)
