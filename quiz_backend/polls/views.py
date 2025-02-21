from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Poll, Choice, UserResponse
import json





def poll_detail(request, poll_id):
    poll = get_object_or_404(Poll, id=poll_id)
    return render(request, 'polls/poll_detail.html', {'poll': poll})

def poll_list(request):
    polls = Poll.objects.all()
    return render(request, 'polls/poll_list.html', {'polls': polls})

@csrf_exempt
def submit_answer(request, poll_id):
    if request.method == 'POST' and request.user.is_authenticated:
        data = json.loads(request.body)
        choice_id = data.get('choice_id')
        poll = get_object_or_404(Poll, id=poll_id)
        choice = get_object_or_404(Choice, id=choice_id, poll=poll)

        if not UserResponse.objects.filter(poll=poll, user=request.user).exists():
            UserResponse.objects.create(poll=poll, choice=choice, user=request.user)
            if not choice.is_correct:
                choice.votes += 1
                choice.save()

        total_votes = UserResponse.objects.filter(poll=poll).count()
        choices = poll.choices.all()
        results = [
            {
                'text': c.text,
                'votes': c.votes if not c.is_correct else (total_votes - sum(ch.votes for ch in choices if not ch.is_correct)),
                'is_correct': c.is_correct,
                'percentage': (c.votes / total_votes * 100) if total_votes > 0 else 0
            } for c in choices
        ]
        return JsonResponse({'results': results})
    return JsonResponse({'error': 'Invalid request or not authenticated'}, status=400)
