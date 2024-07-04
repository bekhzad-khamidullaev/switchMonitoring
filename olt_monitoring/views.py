from django.shortcuts import render, get_object_or_404
from .models import Olt, Slot
from django.http import JsonResponse

def get_host_slots(request, olt_id):
    # Fetch the Olt object
    olt = get_object_or_404(Olt, id=olt_id)
    
    # Get related Slot objects using the related_query_name
    slots = Slot.objects.filter(slot=olt)
    
    # Construct JSON response
    slot_data = [{'slot_number': slot.slot_number, 'temperature': slot.temperature} for slot in slots]
    return JsonResponse({'hostname': olt.hostname, 'slots': slot_data})
    
    # Example of rendering a template
    # context = {
    #     'olt': olt,
    #     'slots': slots,
    # }
    # return render(request, 'host_slots.html', context)
