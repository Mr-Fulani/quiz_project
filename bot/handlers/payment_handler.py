"""
Обработчики платежей через Telegram Stars.

Все докстринги и комментарии на русском языке в соответствии с требованиями проекта.
"""

import logging
from aiogram import Router, types, F
from aiogram.filters import Command

logger = logging.getLogger(__name__)
router = Router()


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    """
    Обработчик pre_checkout_query - запрос перед оплатой.
    
    Здесь можно проверить дополнительные условия перед оплатой.
    Для простого случая просто одобряем все платежи.
    
    Args:
        pre_checkout_query: Запрос от Telegram перед оплатой
    """
    try:
        logger.info(f"Pre-checkout query received: {pre_checkout_query.id}")
        logger.info(f"Payload: {pre_checkout_query.invoice_payload}")
        logger.info(f"User: {pre_checkout_query.from_user.id}")
        logger.info(f"Currency: {pre_checkout_query.currency}")
        logger.info(f"Total amount: {pre_checkout_query.total_amount}")
        
        # Можно добавить дополнительные проверки здесь
        # Например, проверить что donation с таким payload существует
        
        await pre_checkout_query.answer(ok=True)
        logger.info(f"Pre-checkout approved for query {pre_checkout_query.id}")
        
    except Exception as e:
        logger.error(f"Error in pre_checkout_query handler: {str(e)}", exc_info=True)
        # Отклоняем платеж при ошибке
        await pre_checkout_query.answer(
            ok=False,
            error_message="Sorry, payment processing error. Please try again later."
        )


@router.message(F.content_type == types.ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: types.Message):
    """
    Обработчик successful_payment - успешная оплата.
    
    Обновляет статус donation в базе данных и отправляет благодарственное сообщение.
    
    Args:
        message: Сообщение от Telegram с информацией об успешном платеже
    """
    try:
        # Импортируем Django модель здесь, после того как Django настроен в main.py
        from quiz_backend.donation.models import Donation
        
        payment_info = message.successful_payment
        
        logger.info(f"Successful payment received!")
        logger.info(f"User: {message.from_user.id}")
        logger.info(f"Currency: {payment_info.currency}")
        logger.info(f"Total amount: {payment_info.total_amount}")
        logger.info(f"Payload: {payment_info.invoice_payload}")
        logger.info(f"Telegram payment charge ID: {payment_info.telegram_payment_charge_id}")
        logger.info(f"Provider payment charge ID: {payment_info.provider_payment_charge_id}")
        
        # Извлекаем donation_id из payload
        try:
            # Payload имеет формат "donation_{id}"
            payload = payment_info.invoice_payload
            if payload.startswith('donation_'):
                donation_id = int(payload.split('_')[1])
                logger.info(f"Extracted donation ID: {donation_id}")
                
                # Обновляем donation в базе данных
                try:
                    donation = Donation.objects.get(id=donation_id)
                    donation.status = 'completed'
                    donation.telegram_payment_charge_id = payment_info.telegram_payment_charge_id
                    donation.save()
                    
                    logger.info(f"Donation {donation_id} marked as completed")
                    
                    # Отправляем благодарственное сообщение
                    thank_you_text = (
                        "🎉 <b>Спасибо за вашу поддержку!</b>\n\n"
                        f"Ваш донат на сумму {payment_info.total_amount} {payment_info.currency} успешно получен.\n"
                        f"Номер платежа: #{donation_id}\n\n"
                        "Ваша поддержка помогает нам развивать проект! ❤️"
                    )
                    
                    await message.answer(
                        thank_you_text,
                        parse_mode="HTML"
                    )
                    
                except Donation.DoesNotExist:
                    logger.error(f"Donation {donation_id} not found in database")
                    await message.answer(
                        "Платеж получен, но возникла ошибка при обработке. "
                        "Пожалуйста, свяжитесь с поддержкой."
                    )
                except Exception as db_error:
                    logger.error(f"Database error: {str(db_error)}", exc_info=True)
                    await message.answer(
                        "Платеж получен, но возникла ошибка при сохранении. "
                        "Пожалуйста, свяжитесь с поддержкой."
                    )
            else:
                logger.error(f"Invalid payload format: {payload}")
                await message.answer(
                    "Платеж получен, но возникла ошибка при обработке payload."
                )
                
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing payload: {str(e)}", exc_info=True)
            await message.answer(
                "Платеж получен, но возникла ошибка при обработке."
            )
        
    except Exception as e:
        logger.error(f"Error in successful_payment handler: {str(e)}", exc_info=True)
        await message.answer(
            "Произошла ошибка при обработке платежа. Пожалуйста, свяжитесь с поддержкой."
        )

