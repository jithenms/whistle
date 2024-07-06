import datetime
import logging

from asgiref.sync import async_to_sync
from celery import chord
from channels.layers import get_channel_layer
from django.db import DatabaseError
from python_http_client import HTTPError
from sendgrid import SendGridAPIClient, Email, To, Content, Mail
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from connector.models import Twilio, Sendgrid
from external_user.models import ExternalUser
from notification.models import Notification, BatchNotification
from notification.serializers import BatchNotificationSerializer
from preference.models import ExternalUserPreference
from subscription.models import ExternalUserSubscription
from whistle_server.celery import app
from whistle_server.exceptions import NotificationException


@app.task
def send_batch_notification(batch_id, org_id, data):
    tasks = []
    recipient_ids = set()

    for recipient in data["recipients"]:
        recipient_entity = update_or_create_external_user(
            batch_id, org_id, recipient, data
        )

        tasks.append(handle_input_recipient.s(batch_id, org_id, recipient_entity.id, data))

        recipient_ids.add(recipient_entity.id)

    if "topic" in data:
        subscribers = ExternalUserSubscription.objects.filter(organization_id=org_id, topic=data["topic"])

        for subscriber in subscribers:
            if subscriber.id not in recipient_ids:
                tasks.append(handle_topic_subscriber.s(batch_id, org_id, subscriber, data))

    result = chord(tasks)(batch_notification_callback.s(batch_id, org_id, data))

    return result


@app.task
def handle_input_recipient(batch_id, org_id, recipient_id, data):
    try:
        recipient = ExternalUser.objects.get(pk=recipient_id)

        if "category" in data:
            preference = ExternalUserPreference.objects.prefetch_related(
                "channels"
            ).filter(user_id=recipient.id, slug=data['category'])

            if preference:
                route_notification_with_preference(
                    batch_id,
                    org_id,
                    recipient,
                    preference.first().channels.all(),
                    data,
                )
                return recipient.id
            else:
                route_basic_notification(batch_id, org_id, recipient, data)
                return recipient.id
        else:
            route_basic_notification(batch_id, org_id, recipient, data)
            return recipient.id
    except NotificationException:
        return None


@app.task
def handle_topic_subscriber(batch_id, org_id, subscriber_id, data):
    try:
        subscriber = ExternalUserSubscription.objects.get(pk=subscriber_id)

        if "category" in data:
            subscriber_category = subscriber.categories.filter(
                slug=data["category"]
            )

            preference = ExternalUserPreference.objects.prefetch_related(
                "channels"
            ).filter(user_id=subscriber.user.id, slug=data["category"])

            if subscriber_category and preference and subscriber_category.first().enabled:
                route_notification_with_preference(
                    batch_id,
                    org_id,
                    subscriber.user,
                    preference.first().channels.all(),
                    data,
                )
                return subscriber.id
            elif subscriber_category and subscriber_category.first().enabled:
                route_basic_notification(batch_id, org_id, subscriber.user, data)
                return subscriber.id
        else:
            route_basic_notification(batch_id, org_id, subscriber.user, data)
            return subscriber.id
    except NotificationException:
        return None


@app.task(throws=(NotificationException,))
def send_sms(batch_id, org_id, user_id, data):
    try:
        user = ExternalUser.objects.get(id=user_id)
        twilio_connection = Twilio.objects.get(organization_id=org_id)

        twilio_client = Client(
            twilio_connection.account_sid, twilio_connection.auth_token
        )

        message = twilio_client.messages.create(
            to=user.phone,
            from_=twilio_connection.from_phone,
            body=data["channels"]["sms"]["body"],
        )

        print(f"twilio sms status: {message.status}")
    except TwilioRestException as error:
        logging.error(
            "Twilio failed to send text to user: %s for batch: %s with message: ",
            user_id,
            batch_id,
            error.msg,
        )
    except Twilio.DoesNotExist:
        logging.error(
            "Twilio account not connected for org: %s for batch: %s", org_id, batch_id
        )
        raise NotificationException(
            "Twilio account not connected", "twilio_account_not_connected"
        )
    except ExternalUser.DoesNotExist:
        logging.error(
            "Recipient not found by id: %s for org: %s and batch: %s",
            user_id,
            org_id,
            batch_id,
        )
        raise NotificationException(
            "Recipient not found by id",
            "recipient_not_found",
        )


@app.task(throws=(NotificationException,))
def send_email(batch_id, org_id, user_id, data):
    try:
        user = ExternalUser.objects.get(id=user_id)
        sendgrid_conn = Sendgrid.objects.get(organization_id=org_id)
        sg = SendGridAPIClient(api_key=sendgrid_conn.api_key)

        from_email = Email(sendgrid_conn.from_email)
        to_email = To(user.email)
        subject = data["channels"]["email"]["subject"]
        content = Content("text/plain", data["channels"]["email"]["content"])
        mail = Mail(from_email, to_email, subject, content)
        response = sg.client.mail.send.post(request_body=mail.get())
        logging.info(
            "Sendgrid email sent to user: %s with batch: %s", user_id, batch_id
        )
    except HTTPError as error:
        logging.error(
            "Sendgrid failed to send email to user: %s for batch: %s with reason: ",
            user_id,
            batch_id,
            error.reason,
        )
    except Sendgrid.DoesNotExist:
        logging.error(
            "Sendgrid account not connected for org: %s for batch: %s", org_id, batch_id
        )
        raise NotificationException(
            "Sendgrid account not connected", "sendgrid_account_not_connected"
        )
    except ExternalUser.DoesNotExist:
        logging.error(
            "Recipient not found by id: %s for org: %s and batch: %s",
            user_id,
            org_id,
            batch_id,
        )
        raise NotificationException(
            "Recipient not found by id",
            "recipient_not_found",
        )


@app.task(throws=(NotificationException,))
def send_web(batch_id, org_id, user_id, data):
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user_id}",
            {
                "object": "event",
                "type": "notification.created",
                "data": {
                    "category": data.get("category"),
                    "topic": data.get("topic"),
                    "title": data["title"],
                    "content": data["content"],
                    "action_link": data.get("action_link"),
                },
            },
        )
    except ExternalUser.DoesNotExist:
        logging.error(
            "Recipient not found by id: %s for org: %s and batch: %s",
            user_id,
            org_id,
            batch_id,
        )
        raise NotificationException(
            "Recipient not found by id",
            "recipient_not_found",
        )


@app.task
def persist_notification(web_response, batch_id, org_id, user_id, data, **kwargs):
    logging.info(web_response)
    data.pop("channels")
    data.pop('recipients')
    try:
        notification = Notification.objects.create(organization_id=org_id, recipient_id=user_id,
                                                   category=data.get('category', ""), topic=data.get('topic', ""),
                                                   title=data.get('title', ""),
                                                   content=data.get('content', ""),
                                                   action_link=data.get('action_link', ""), **kwargs)
        logging.info(
            "Notification record with id: %s persisted for user: %s and org: %s for batch: %s",
            notification.id,
            user_id,
            org_id,
            batch_id,
        )
        return
    except DatabaseError as error:
        logging.error(
            "Failed to save notification record to database for user: %s "
            "and org: %s for batch: %s with database error: %s",
            user_id,
            org_id,
            batch_id,
            error,
        )
        raise


@app.task(throws=(DatabaseError,))
def batch_notification_callback(results, batch_id, org_id, data):
    logging.info(results)
    delivered_to = [recipient_id for recipient_id in results if recipient_id]
    try:
        serializer = BatchNotificationSerializer(
            context={"id": batch_id, "org_id": org_id, "delivered_to": delivered_to},
            data={**data, 'status': "processed",
                  'sent_at': datetime.datetime.now(datetime.timezone.utc)})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logging.info(
            "Batch notification record with id: %s persisted for org: %s",
            batch_id,
            org_id,
        )
    except DatabaseError as error:
        logging.error(
            "Failed to save batch notification record to database for org: %s "
            "for batch: %s with database error: %s",
            org_id,
            batch_id,
            error,
        )
        raise


def update_or_create_external_user(batch_id, org_id, recipient, data):
    if "external_id" in recipient:
        recipient_entity, created = ExternalUser.objects.update_or_create(
            organization_id=org_id,
            external_id=recipient["external_id"],
            defaults={
                "first_name": recipient.get("first_name", ""),
                "last_name": recipient.get("last_name", ""),
                "email": recipient.get("email", ""),
                "phone": recipient.get("phone", ""),
            },
        )

        if created and "channels" in data:
            if "email" in data["channels"] and "email" not in recipient:
                logging.error(
                    "Email included in channels but email not provided for new user for org: %s and batch: %s",
                    org_id,
                    batch_id,
                )
                raise NotificationException(
                    "Email included in channels but email not provided for new user",
                    "no_email_provided_for_new_user",
                )
            if "sms" in data["channels"] and "phone" not in recipient:
                logging.error(
                    "SMS included in channels but phone not provided for new user for org: %s and batch: %s",
                    org_id,
                    batch_id,
                )
                raise NotificationException(
                    "SMS included in channels but phone not provided for new user",
                    "no_phone_provided_for_new_user",
                )

        return recipient_entity

    elif "email" in recipient:
        try:
            return ExternalUser.objects.get(
                organization_id=org_id, email=recipient["email"]
            )
        except ExternalUser.DoesNotExist:
            logging.error(
                "Recipient not found by email for org: %s and batch: %s",
                org_id,
                batch_id,
            )
            raise NotificationException(
                "Recipient not found by email",
                "recipient_not_found",
            )
    else:
        logging.error(
            "Identifier for recipient not provided for org: %s and batch: %s",
            org_id,
            batch_id,
        )
        raise NotificationException(
            "Identifier for recipient not provided",
            "recipient_identifier_not_provided",
        )


def route_notification_with_preference(batch_id, org_id, recipient, channels, data):
    logging.info(
        "Routing notification with preference for user: %s in org: %s for batch: %s",
        recipient.id,
        org_id,
        batch_id,
    )
    web_preference_entity = channels.get(slug="web")
    if web_preference_entity.enabled:
        send_web.apply_async((batch_id, org_id, recipient.id, data), link=persist_notification.s(
            batch_id,
            org_id,
            recipient.id,
            data,
            status="delivered",
            sent_at=datetime.datetime.now(datetime.timezone.utc),
        ))
    else:
        logging.info(
            "Web push disabled for category %s for user: %s in org: %s for batch: %s",
            data.get("category", None),
            recipient.id,
            org_id,
            batch_id,
        )
    if "channels" in data:
        if "sms" in data["channels"] and recipient.phone is not None:
            sms_preference_entity = channels.get(slug="sms")
            if sms_preference_entity.enabled:
                send_sms.delay(batch_id, org_id, recipient.id, data)
            else:
                logging.info(
                    "SMS disabled for category %s for user: %s in org: %s for batch: %s",
                    data.get("category", None),
                    recipient.id,
                    org_id,
                    batch_id,
                )

        if "email" in data["channels"]:
            email_preference_entity = channels.get(slug="email")
            if email_preference_entity.enabled:
                send_email.delay(batch_id, org_id, recipient.id, data)
            else:
                logging.info(
                    "Email disabled for category %s for user: %s in org: %s for batch: %s",
                    data.get("category", None),
                    recipient.id,
                    org_id,
                    batch_id,
                )


def route_basic_notification(batch_id, org_id, recipient, data):
    logging.info(
        "Routing basic notification for user: %s in org: %s for batch: %s",
        recipient.id,
        org_id,
        batch_id,
    )
    send_web.apply_async((batch_id, org_id, recipient.id, data), link=persist_notification.s(
        batch_id,
        org_id,
        recipient.id,
        data,
        status="delivered",
        sent_at=datetime.datetime.now(datetime.timezone.utc),
    ), link_error=persist_notification.s(
        batch_id,
        org_id,
        recipient.id,
        data,
        status="failed",
        sent_at=datetime.datetime.now(datetime.timezone.utc),
    ))
    if "channels" in data:
        if "sms" in data["channels"] and recipient.phone is not None:
            send_sms.delay(batch_id, org_id, recipient.id, data)
        elif recipient.phone is None:
            logging.warning(
                "Trying to route SMS notification without phone on record for user: %s in org: %s for batch: %s",
                recipient.id,
                org_id,
                batch_id,
            )
        if "email" in data["channels"]:
            send_email.delay(batch_id, org_id, recipient.id, data)
