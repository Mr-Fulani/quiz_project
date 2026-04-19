import logging
from celery import shared_task
from django.conf import settings
from .models import Donation
from .utils import send_donation_thank_you_email

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_donation_email_task(self, donation_id):
    """
    Асинхронная задача для отправки благодарственного письма за донат.
    """
    try:
        donation = Donation.objects.get(id=donation_id)
        logger.info(f"Запуск задачи отправки email для доната {donation_id}")
        
        success = send_donation_thank_you_email(donation)
        
        if success:
            logger.info(f"Email успешно отправлен для доната {donation_id}")
            return True
        else:
            logger.warning(f"Email не был отправлен для доната {donation_id} (проверьте статус или наличие email)")
            return False
            
    except Donation.DoesNotExist:
        logger.error(f"Донат с ID {donation_id} не найден")
        return False
    except Exception as exc:
        logger.error(f"Ошибка при отправке email для доната {donation_id}: {str(exc)}")
        raise self.retry(exc=exc)
