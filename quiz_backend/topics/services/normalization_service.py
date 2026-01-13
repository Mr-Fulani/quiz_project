from dataclasses import dataclass
from typing import Dict, List, Tuple
from django.db.models import Count
from topics.models import Subtopic
from topics.utils import normalize_subtopic_name


@dataclass
class SubtopicGroup:
    """
    Описывает группу подтем с одинаковым нормализованным названием.
    """
    topic_id: int
    normalized_name: str
    canonical: Subtopic
    duplicates: List[Subtopic]


def group_subtopics() -> Dict[Tuple[int, str], List[Subtopic]]:
    """
    Группирует подтемы по (topic_id, нормализованное название).
    """
    grouped: Dict[Tuple[int, str], List[Subtopic]] = {}
    for subtopic in Subtopic.objects.select_related('topic'):
        key = (subtopic.topic_id, normalize_subtopic_name(subtopic.name))
        grouped.setdefault(key, []).append(subtopic)
    return grouped


def build_subtopic_groups() -> List[SubtopicGroup]:
    """
    Возвращает список групп, где есть потенциальные дубликаты.
    Выбирает каноническую подтему как ту, у которой больше всего задач.
    Если задач одинаково, выбирает с наименьшим ID.
    """
    groups: List[SubtopicGroup] = []
    for (topic_id, normalized), items in group_subtopics().items():
        if len(items) == 1:
            continue
        
        # Аннотируем количество задач для каждой подтемы
        items_with_counts = [
            (item, item.tasks.count()) for item in items
        ]
        
        # Сортируем: сначала по количеству задач (убывание), потом по ID (возрастание)
        canonical_item, _ = max(items_with_counts, key=lambda x: (x[1], -x[0].id))
        canonical = canonical_item
        duplicates = [item for item in items if item.id != canonical.id]
        groups.append(SubtopicGroup(
            topic_id=topic_id,
            normalized_name=normalized,
            canonical=canonical,
            duplicates=duplicates,
        ))
    return groups

