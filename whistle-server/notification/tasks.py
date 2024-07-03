from datetime import datetime

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from sendgrid import SendGridAPIClient, Email, To, Content, Mail
from twilio.rest import Client

from connector.models import Twilio, Sendgrid
from notification.serializers import NotificationSerializer, BatchNotificationSerializer
from external_user.models import (
    ExternalUserPreference,
    ExternalUserSubscription,
    ExternalUser,
)
from whistle_server.celery import app

# todo store error info and delivery data in db


@app.task
def send_batch_notification(batch_id, org_id, data):
    recipient_external_ids = set(
        recipient["external_id"] for recipient in data["recipients"]
    )

    if "category" in data and not "topic" in data:
        for rec in data["recipients"]:
            recipient = ExternalUser.objects.filter(
                organization_id=org_id, external_id=rec["external_id"]
            )

            if not recipient:
                continue

            preference = ExternalUserPreference.objects.prefetch_related(
                "channels"
            ).filter(user_id=recipient.first().id, slug=data["category"])

            if not preference:
                route_basic_notification(batch_id, org_id, recipient.first().id, data)
            else:
                route_notification_with_preference(
                    batch_id,
                    org_id,
                    recipient.first().id,
                    preference.first().channels.all(),
                    data,
                )

    elif "topic" in data:
        subscribers = ExternalUserSubscription.objects.filter(
            organization_id=org_id, topic=data["topic"]
        )

        if "category" in data:
            for rec in data["recipients"]:
                recipient = ExternalUser.objects.filter(
                    organization_id=org_id, external_id=rec["external_id"]
                )

                if not recipient:
                    continue

                preference = ExternalUserPreference.objects.prefetch_related(
                    "channels"
                ).filter(user_id=recipient.first().id, slug=data["category"])

                if not preference:
                    route_basic_notification(
                        batch_id, org_id, recipient.first().id, data
                    )
                else:
                    route_notification_with_preference(
                        batch_id,
                        org_id,
                        recipient.first().id,
                        preference.first().channels.all(),
                        data,
                    )
            for subscriber in subscribers:
                if subscriber.user.external_id in recipient_external_ids:
                    continue

                subscriber_category = subscriber.categories.filter(
                    slug=data["category"]
                )

                preference = ExternalUserPreference.objects.prefetch_related(
                    "channels"
                ).filter(user_id=subscriber.user.id, slug=data["category"])

                if subscriber_category:
                    if not preference and subscriber_category.first().enabled:
                        route_basic_notification(
                            batch_id, org_id, subscriber.user.id, data
                        )
                    elif preference and subscriber_category.first().enabled:
                        route_notification_with_preference(
                            batch_id,
                            org_id,
                            subscriber.user.id,
                            preference.first().channels.all(),
                            data,
                        )
        else:
            for rec in data["recipients"]:
                recipient = ExternalUser.objects.filter(
                    organization_id=org_id, external_id=rec["external_id"]
                )

                if not recipient:
                    continue

                route_basic_notification(batch_id, org_id, recipient.first().id, data)
            for subscriber in subscribers:
                if subscriber.user.external_id in recipient_external_ids:
                    continue
                route_basic_notification(batch_id, org_id, subscriber.user.id, data)
    else:
        for rec in data["recipients"]:
            recipient = ExternalUser.objects.filter(
                organization_id=org_id, external_id=rec["external_id"]
            )

            if not recipient:
                continue

            route_basic_notification(batch_id, org_id, recipient.first().id, data)

    persist_batch_notification(batch_id, org_id, data, status="processed")


def route_notification_with_preference(batch_id, org_id, user_id, channels, data):
    web_preference_entity = channels.get(slug="web")
    if web_preference_entity.enabled:
        send_web.delay(batch_id, org_id, user_id, data)
    if "channels" in data:
        if "sms" in data["channels"]:
            sms_preference_entity = channels.get(slug="sms")
            if sms_preference_entity.enabled:
                send_sms.delay(batch_id, org_id, user_id, data)

        if "email" in data["channels"]:
            email_preference_entity = channels.get(slug="email")
            if email_preference_entity.enabled:
                send_email.delay(batch_id, org_id, user_id, data)


@app.task
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
    except (
        Twilio.DoesNotExist,
        ExternalUser.DoesNotExist,
    ) as error:
        print(error)


@app.task
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
        print(
            f"sendgrid email status: {response.status_code}, {response.body}, {response.headers}"
        )
    except (
        Sendgrid.DoesNotExist,
        ExternalUser.DoesNotExist,
    ) as error:
        print(error)
        return


@app.task
def send_web(batch_id, org_id, user_id, data):
    try:
        user = ExternalUser.objects.get(pk=user_id)
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
        data = persist_notification(
            org_id, user.id, data, status="delivered", sent_at=datetime.now()
        )
        print(f"web push record: {data}")
    except ExternalUser.DoesNotExist as error:
        print(error)
        return


def route_basic_notification(batch_id, org_id, user_id, data):
    print(data)
    send_web.delay(batch_id, org_id, user_id, data)
    if "channels" in data:
        if "sms" in data["channels"]:
            send_sms.delay(batch_id, org_id, user_id, data)

        if "email" in data["channels"]:
            send_email.delay(batch_id, org_id, user_id, data)


def persist_batch_notification(batch_id, org_id, data, **kwargs):
    serializer = BatchNotificationSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save(id=batch_id, organization_id=org_id, **kwargs)
    return serializer.data


def persist_notification(org_id, user_id, data, **kwargs):
    print(data)
    if "channels" in data:
        del data["channels"]

    if "recipients" in data:
        del data["recipients"]

    serializer = NotificationSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save(organization_id=org_id, recipient_id=user_id, **kwargs)
    return serializer.data
