from django.shortcuts import render

from django.http import JsonResponse

def test_api(request):
    """
    Простое API, возвращающее тестовые данные.
    """
    return JsonResponse({'message': 'Привет из Django!', 'status': 'success'})

