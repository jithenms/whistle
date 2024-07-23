import logging
import uuid
from datetime import datetime, timezone, timedelta

from asgiref.sync import async_to_sync
from celery import chord
from celery.schedules import schedule
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from pyapns_client import IOSPayloadAlert, IOSPayload, IOSNotification, APNSClient, APNSException
from python_http_client import HTTPError
from redbeat import RedBeatSchedulerEntry
from sendgrid import SendGridAPIClient, Email, To, Content, Mail, MailSettings, SandBoxMode
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from audience.models import Audience, OperatorChoices
from connector.models import Twilio, Sendgrid, APNS, FCM
from external_user.models import ExternalUser, ExternalUserDevice, PlatformChoices
from notification.models import Notification, Broadcast, NotificationChannel
from preference.models import ExternalUserPreference, ChannelChoices
from subscription.models import ExternalUserSubscription
from whistle_server.celery import app
from whistle_server.client import CustomAPNSClient, CustomFCMNotification
from whistle_server.exceptions import NotificationException

basic_fields = {
    "email",
    "phone",
    "first_name",
    "last_name",
    "external_id",
}


@app.task
def schedule_broadcast(broadcast_id, org_id, data):
    broadcast = Broadcast.objects.get(pk=uuid.UUID(broadcast_id))
    try:
        data["id"] = str(data["id"])
        schedule_at = data.get("schedule_at")
        with transaction.atomic():
            entry = RedBeatSchedulerEntry(app=app)
            entry.name = broadcast_id
            entry.task = "notification.tasks.send_broadcast"
            entry.args = [broadcast_id, org_id, data]
            entry.schedule = schedule(
                max(schedule_at - datetime.now(tz=schedule_at.tzinfo), timedelta(0))
            )
            entry.save()
            broadcast.scheduled_at = schedule_at
            broadcast.status = "scheduled"
            broadcast.save()
            logging.info(
                "Broadcast scheduled at: %s with id: %s for org: %s",
                schedule_at,
                broadcast_id,
                org_id,
            )
            return broadcast.id
    except Exception as error:
        broadcast.status = "failed"
        broadcast.save()
        logging.error(
            "Failed to schedule broadcast: %s in org: %s with error: %s",
            broadcast_id,
            org_id,
            error,
        )
        raise


@app.task
def send_broadcast(broadcast_id, org_id, data):
    tasks = []
    recipient_ids = set()

    broadcast_id = uuid.UUID(broadcast_id)
    org_id = uuid.UUID(org_id)

    if "audience_id" in data:
        audience = Audience.objects.prefetch_related("filters").filter(
            organization_id=org_id, id=data["audience_id"]
        )
        filters = audience.first().filters.all()
        filter_kwargs = build_filter_kwargs(filters)
        exclude_kwargs = build_exclude_kwargs(filters)

        recipients = ExternalUser.objects.filter(
            organization_id=org_id, **filter_kwargs
        ).exclude(**exclude_kwargs)

        logging.info(f"Recipients: {recipients}")

        for recipient in recipients.iterator():
            tasks.append(
                handle_recipient.s(broadcast_id, org_id, recipient.id, data)
            )
            recipient_ids.add(recipient.id)
    elif "recipients" in data:
        if "filters" in data:
            recipients_to_remove = []
            for recipient in data["recipients"]:
                recipient_entity = update_or_create_external_user(
                    broadcast_id, org_id, recipient, data
                )
                if recipient_entity:
                    for filter_input in data["filters"]:
                        filtered = apply_filter_to_recipient(
                            broadcast_id, org_id, filter_input, recipient_entity
                        )
                        if filtered:
                            recipients_to_remove.append(recipient)
            for recipient in recipients_to_remove:
                data["recipients"].remove(recipient)

        for recipient in data["recipients"]:
            recipient_entity = update_or_create_external_user(
                broadcast_id, org_id, recipient, data
            )
            if recipient_entity:
                tasks.append(
                    handle_recipient.s(broadcast_id, org_id, recipient_entity.id, data)
                )
                recipient_ids.add(recipient_entity.id)

    if "topic" in data:
        subscribers = ExternalUserSubscription.objects.filter(
            organization_id=org_id, topic=data["topic"]
        )

        for subscriber in subscribers.iterator():
            if subscriber.id not in recipient_ids:
                tasks.append(
                    handle_topic_subscriber.s(broadcast_id, org_id, subscriber, data)
                )

    if "schedule_at" in data:
        entry = RedBeatSchedulerEntry.from_key(f"redbeat:{broadcast_id}", app=app)
        entry.delete()
        logging.info(
            "Removed scheduled task after invoking for broadcast: %s", broadcast_id
        )

    result = chord(tasks)(update_broadcast_status.s(broadcast_id, "processed"))

    return result.id


def build_filter_kwargs(filters):
    query_kwargs = {}
    for filter_rec in filters:
        match filter_rec.operator.upper():
            case OperatorChoices.EQ.value:
                if filter_rec.property in basic_fields:
                    query_kwargs[filter_rec.property] = filter_rec.value
                else:
                    query_kwargs[f"metadata__{filter_rec.property}"] = filter_rec.value
            case OperatorChoices.GT.value:
                query_kwargs[f"metadata__{filter_rec.property}__gt"] = filter_rec.value
            case OperatorChoices.LT.value:
                query_kwargs[f"metadata__{filter_rec.property}__lt"] = filter_rec.value
            case OperatorChoices.GTE.value:
                query_kwargs[f"metadata__{filter_rec.property}__gte"] = filter_rec.value
            case OperatorChoices.LTE.value:
                query_kwargs[f"metadata__{filter_rec.property}__lte"] = filter_rec.value
            case OperatorChoices.CONTAINS.value:
                query_kwargs[f"metadata__{filter_rec.property}__contains"] = (
                    filter_rec.value
                )
            case _:
                continue
    return query_kwargs


def build_exclude_kwargs(filters):
    query_kwargs = {}
    for filter_rec in filters:
        match filter_rec.operator:
            case OperatorChoices.NEQ:
                if filter_rec.property in basic_fields:
                    query_kwargs[filter_rec.property] = filter_rec.value
                else:
                    query_kwargs[f"metadata__{filter_rec.property}"] = filter_rec.value
            case OperatorChoices.DOES_NOT_CONTAIN.value:
                query_kwargs[f"metadata__{filter_rec.property}__contains"] = (
                    filter_rec.value
                )
            case _:
                continue
    return query_kwargs


def apply_filter_to_recipient(broadcast_id, org_id, filter_input, recipient_entity):
    match filter_input["operator"]:
        case OperatorChoices.EQ.value:
            if filter_input["property"] in basic_fields:
                metadata = recipient_entity.metadata
                if not metadata or not metadata.get(filter_input["property"]):
                    return True
                try:
                    if datetime.strptime(
                            getattr(recipient_entity, filter_input["property"]),
                            settings.DATETIME_FORMAT,
                    ) != datetime.strptime(filter_input["value"]):
                        return True
                except ValueError:
                    if (
                            getattr(recipient_entity, filter_input["property"])
                            != filter_input["value"]
                    ):
                        return True
        case OperatorChoices.NEQ.value:
            if filter_input["property"] in basic_fields:
                metadata = recipient_entity.metadata
                if not metadata or not metadata.get(filter_input["property"]):
                    return True
                try:
                    if datetime.strptime(
                            getattr(recipient_entity, filter_input["property"]),
                            settings.DATETIME_FORMAT,
                    ) == datetime.strptime(filter_input["value"]):
                        return True
                except ValueError:
                    if (
                            getattr(recipient_entity, filter_input["property"])
                            == filter_input["value"]
                    ):
                        return True
        case OperatorChoices.GT.value:
            metadata = recipient_entity.metadata
            if not metadata or not metadata.get(filter_input["property"]):
                return True
            else:
                try:
                    if datetime.strptime(
                            metadata.get(filter_input["property"]),
                            settings.DATETIME_FORMAT,
                    ) <= datetime.strptime(filter_input["value"]):
                        return True
                except ValueError:
                    if metadata.get(filter_input["property"]) <= filter_input["value"]:
                        return True
        case OperatorChoices.LT.value:
            metadata = recipient_entity.metadata
            if not metadata or not metadata.get(filter_input["property"]):
                return True
            else:
                try:
                    if datetime.strptime(
                            metadata.get(filter_input["property"]),
                            settings.DATETIME_FORMAT,
                    ) >= datetime.strptime(filter_input["value"]):
                        return True
                except ValueError:
                    if metadata.get(filter_input["property"]) >= filter_input["value"]:
                        return True
        case OperatorChoices.GTE.value:
            metadata = recipient_entity.metadata
            if not metadata or not metadata.get(filter_input["property"]):
                return True
            else:
                try:
                    if datetime.strptime(
                            metadata.get(filter_input["property"]),
                            settings.DATETIME_FORMAT,
                    ) < datetime.strptime(filter_input["value"]):
                        return True
                except ValueError:
                    if metadata.get(filter_input["property"]) < filter_input["value"]:
                        return True
        case OperatorChoices.LTE.value:
            metadata = recipient_entity.metadata
            if not metadata or not metadata.get(filter_input["property"]):
                return True
            else:
                try:
                    if datetime.strptime(
                            metadata.get(filter_input["property"]),
                            settings.DATETIME_FORMAT,
                    ) > datetime.strptime(filter_input["value"]):
                        return True
                except ValueError:
                    if metadata.get(filter_input["property"]) > filter_input["value"]:
                        return True
        case OperatorChoices.CONTAINS.value:
            metadata = recipient_entity.metadata
            if not metadata or not metadata.get(filter_input["property"]):
                return True
            elif isinstance(
                    metadata.get(filter_input["property"]), str
            ) and filter_input["value"] not in metadata.get(
                filter_input["property"], ""
            ):
                return True
            elif isinstance(
                    metadata.get(filter_input["property"]), list
            ) and filter_input["value"] not in metadata.get(
                filter_input["property"], []
            ):
                return True
        case OperatorChoices.DOES_NOT_CONTAIN.value:
            metadata = recipient_entity.metadata
            if not metadata or not metadata.get(filter_input["property"]):
                return True
            elif isinstance(
                    metadata.get(filter_input["property"]), str
            ) and filter_input["value"] in metadata.get(filter_input["property"], ""):
                return True
            elif isinstance(
                    metadata.get(filter_input["property"]), list
            ) and filter_input["value"] in metadata.get(filter_input["property"], []):
                return True
        case _:
            logging.debug(
                "Broadcast: %s with org: %s passed unsupported operator: %s",
                broadcast_id,
                org_id,
                filter_input["operator"],
            )
    return False


@app.task
def handle_recipient(broadcast_id, org_id, recipient_id, data):
    recipient = ExternalUser.objects.get(pk=recipient_id)

    if "category" in data:
        preference = ExternalUserPreference.objects.prefetch_related(
            "channels"
        ).filter(user_id=recipient.id, slug=data["category"])

        if preference:
            route_notification_with_preference(
                broadcast_id,
                org_id,
                recipient,
                preference.first().channels.all(),
                data,
            )
            return recipient.id
        else:
            route_basic_notification(broadcast_id, org_id, recipient, data)
            return recipient.id
    else:
        route_basic_notification(broadcast_id, org_id, recipient, data)
        return recipient.id


@app.task
def handle_topic_subscriber(broadcast_id, org_id, subscriber_id, data):
    subscriber = ExternalUserSubscription.objects.get(pk=subscriber_id)

    if "category" in data:
        subscriber_category = subscriber.categories.filter(slug=data["category"])

        preference = ExternalUserPreference.objects.prefetch_related(
            "channels"
        ).filter(user_id=subscriber.user.id, slug=data["category"])

        if (
                subscriber_category
                and preference
                and subscriber_category.first().enabled
        ):
            route_notification_with_preference(
                broadcast_id,
                org_id,
                subscriber.user,
                preference.first().channels.all(),
                data,
            )
            return subscriber.id
        elif subscriber_category and subscriber_category.first().enabled:
            route_basic_notification(broadcast_id, org_id, subscriber.user, data)
            return subscriber.id
    else:
        route_basic_notification(broadcast_id, org_id, subscriber.user, data)
        return subscriber.id


@app.task
def send_sms(notification_id, broadcast_id, org_id, user_id, data):
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

        logging.info("Sent Twilio sms to user: %s for broadcast: %s with status: %s", user_id, broadcast_id,
                     message.status)

        if message.status in {"failed", "undelivered", "canceled"}:
            status = "failed"
            reason = f'{message.status}: {message.error_message}'
        else:
            status = "sent"
            reason = ""

        NotificationChannel.objects.create(notification_id=notification_id,
                                           slug=ChannelChoices.SMS, status=status, reason=reason,
                                           metadata={'twilio_message_sid': message.sid})

        return message.sid
    except TwilioRestException as error:
        logging.error(
            "Twilio failed to send text to user: %s for broadcast: %s with message: ",
            user_id,
            broadcast_id,
            error.msg,
        )
        reason = f'{error.status}: {error.msg}'
        NotificationChannel.objects.create(notification_id=notification_id,
                                           slug=ChannelChoices.EMAIL, status="failed", reason=reason)
        raise


@app.task
def send_email(notification_id, broadcast_id, org_id, user_id, data):
    try:
        user = ExternalUser.objects.get(id=user_id)
        sendgrid_conn = Sendgrid.objects.get(organization_id=org_id)
        sg = SendGridAPIClient(api_key=sendgrid_conn.api_key)

        from_email = Email(sendgrid_conn.from_email)
        to_email = To(user.email)

        mail = Mail(from_email, to_email)

        mail_settings = MailSettings()
        mail_settings.sandbox_mode = SandBoxMode(settings.USE_SENDGRID_SANDBOX)
        mail.mail_settings = mail_settings

        if "sendgrid_template_id" in data["channels"]["email"]:
            mail.dynamic_template_data = data["data"]
            mail.template_id = data["channels"]["email"]["sendgrid_template_id"]
        else:
            mail.subject = data["channels"]["email"]["subject"]
            mail.content = Content("text/plain", data["channels"]["email"]["content"])
        response = sg.send(mail)
        logging.info(
            "Sendgrid email with status code: %s sent to user: %s with broadcast: %s",
            response.status_code,
            user_id,
            broadcast_id,
        )

        NotificationChannel.objects.create(notification_id=notification_id,
                                           slug=ChannelChoices.EMAIL, status="sent",
                                           metadata={'sg_x_message_id': response.headers['X-Message-ID']})

        return response.headers['X-Message-ID']
    except HTTPError as error:
        logging.error(
            "Sendgrid failed to send email to user: %s for broadcast: %s with reason: ",
            user_id,
            broadcast_id,
            error.reason,
        )
        NotificationChannel.objects.create(notification_id=notification_id,
                                           slug=ChannelChoices.EMAIL, status="failed", reason=error.reason)
        raise


@app.task
def send_web(notification_id, user_id, data):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {
            "object": "event",
            "type": "notification.created",
            "data": {
                "id": str(notification_id),
                "category": data.get("category", ""),
                "topic": data.get("topic", ""),
                "title": data["title"],
                "content": data["content"],
                "action_link": data.get("action_link", ""),
            },
        },
    )
    notification_channel = NotificationChannel.objects.create(notification_id=notification_id,
                                                              slug=ChannelChoices.WEB, status="sent")
    return notification_channel.id


@app.task
def send_mobile(notification_id, org_id, user_id, data):
    devices = ExternalUserDevice.objects.filter(user_id=user_id)

    if not devices:
        NotificationChannel.objects.create(notification_id=notification_id,
                                           slug=ChannelChoices.MOBILE_PUSH, status="not_sent",
                                           reason="No devices for user")
        return

    apns = APNS.objects.filter(organization_id=org_id)
    fcm = FCM.objects.filter(organization_id=org_id)
    for device in devices.iterator():
        match device.platform:
            case PlatformChoices.IOS:
                if not apns:
                    NotificationChannel.objects.create(notification_id=notification_id,
                                                       slug=ChannelChoices.MOBILE_PUSH,
                                                       status="not_sent", reason="APNS account not configured")
                    continue
                payload = IOSPayload(
                    alert=IOSPayloadAlert(
                        title=data['channels']['mobile_push']['title'],
                        subtitle=data['channels']['mobile_push'].get('subtitle'),
                        body=data['channels']['mobile_push']['body'],
                    ),
                    sound=data['channels']['mobile_push'].get('sound', "default"),
                    badge=data['channels']['mobile_push'].get('badge', 1),
                    category=data.get('category')
                )
                notification = IOSNotification(
                    payload=payload,
                    topic=apns.first().bundle_id,
                    apns_id=notification_id,
                )
                try:
                    client = CustomAPNSClient(
                        mode=(
                            APNSClient.MODE_DEV
                            if apns.first().use_sandbox
                            else APNSClient.MODE_PROD
                        ),
                        root_cert_path=None,
                        auth_key_path=apns.first().key_p8,
                        auth_key_id=apns.first().key_id,
                        team_id=apns.first().team_id,
                    )
                    res = client.push(notification=notification, device_token=device.token)
                    logging.info(
                        "Apple push notification sent for user: %s with response: %s",
                        user_id,
                        res,
                    )
                    NotificationChannel.objects.create(notification_id=notification_id,
                                                       slug=ChannelChoices.MOBILE_PUSH, status="sent")
                except APNSException as error:
                    logging.info(
                        "Failed to send Apple push notification sent for user: %s with error: %s",
                        user_id,
                        error,
                    )
                    NotificationChannel.objects.create(notification_id=notification_id,
                                                       slug=ChannelChoices.MOBILE_PUSH, status="failed")
            case PlatformChoices.ANDROID:
                if not fcm:
                    NotificationChannel.objects.create(notification_id=notification_id,
                                                       slug=ChannelChoices.MOBILE_PUSH,
                                                       status="not_sent", reason="FCM account not configured")
                    continue
                notification = CustomFCMNotification(service_account_file=fcm.first().credentials,
                                                     project_id=fcm.first().project_id)
                res = notification.notify(fcm_token=device.token,
                                          notification_title=data['channels']['mobile_push']['title'],
                                          notification_body=data['channels']['mobile_push']['body'])
                logging.info(
                    "Firebase cloud messaging notification sent for user: %s with response: %s",
                    user_id,
                    res,
                )
                NotificationChannel.objects.create(notification_id=notification_id,
                                                   slug=ChannelChoices.MOBILE_PUSH, status="sent")
            case _:
                continue


@app.task
def update_broadcast_status(_, broadcast_id, status):
    broadcast = Broadcast.objects.get(pk=broadcast_id)
    broadcast.status = status
    broadcast.save()
    return broadcast_id


def persist_notification(broadcast_id, org_id, user_id, data, **kwargs):
    notification = Notification.objects.create(
        organization_id=org_id,
        recipient_id=user_id,
        broadcast_id=broadcast_id,
        category=data.get("category", ""),
        topic=data.get("topic", ""),
        title=data.get("title", ""),
        content=data.get("content", ""),
        action_link=data.get("action_link", ""),
        additional_info=data.get("additional_info"),
        **kwargs,
    )

    logging.info(
        "Notification record with id: %s persisted for user: %s and org: %s for broadcast: %s",
        notification.id,
        user_id,
        org_id,
        broadcast_id,
    )

    return notification


def update_or_create_external_user(broadcast_id, org_id, recipient, data):
    if "external_id" in recipient:
        defaults = {}
        if "first_name" in recipient:
            defaults["first_name"] = recipient["first_name"]
        if "last_name" in recipient:
            defaults["last_name"] = recipient["last_name"]
        if "email" in recipient:
            defaults["email"] = recipient["email"]
        if "phone" in recipient:
            defaults["phone"] = recipient["phone"]

        recipient_entity, created = ExternalUser.objects.update_or_create(
            organization_id=org_id,
            external_id=recipient["external_id"],
            defaults=defaults,
        )

        if created and "channels" in data:
            if "email" in data["channels"] and "email" not in recipient:
                logging.info(
                    "Email included in channels but email not provided for new user for org: %s and broadcast: %s",
                    org_id,
                    broadcast_id,
                )
            if "sms" in data["channels"] and "phone" not in recipient:
                logging.info(
                    "SMS included in channels but phone not provided for new user for org: %s and broadcast: %s",
                    org_id,
                    broadcast_id,
                )

        return recipient_entity

    elif "email" in recipient:
        try:
            return ExternalUser.objects.get(
                organization_id=org_id, email=recipient["email"]
            )
        except ExternalUser.DoesNotExist:
            logging.debug(
                "Recipient not found by email for org: %s and broadcast: %s",
                org_id,
                broadcast_id,
            )

            broadcast = Broadcast.objects.get(pk=broadcast_id)

            if 'errors' not in broadcast.metadata:
                broadcast.metadata['errors'] = {}

            if 'recipients' not in broadcast.metadata['errors']:
                broadcast.metadata['errors']['recipients'] = []

            broadcast.metadata['errors']['recipients'].append({
                'email': recipient["email"],
                'reason': 'User email does not exist'
            })

            broadcast.save()

            return None


def route_notification_with_preference(broadcast_id, org_id, recipient, channels, data):
    logging.info(
        "Routing notification with preference for user: %s in org: %s for broadcast: %s",
        recipient.id,
        org_id,
        broadcast_id,
    )

    notification = persist_notification(broadcast_id, org_id, recipient.id, data, sent_at=datetime.now(timezone.utc))

    web_preference_entity = channels.get(slug=ChannelChoices.WEB.value)
    if web_preference_entity.enabled:
        send_web.delay(notification.id, recipient.id, data)
    else:
        logging.info(
            "Web push disabled for category %s for user: %s in org: %s for broadcast: %s",
            data.get("category", None),
            recipient.id,
            org_id,
            broadcast_id,
        )
        NotificationChannel.objects.create(notification_id=notification.id,
                                           slug=ChannelChoices.WEB, status="not_sent", reason="User disabled")

    if "channels" in data:
        if "sms" in data["channels"]:
            sms_preference_entity = channels.get(slug=ChannelChoices.SMS.value)
            if sms_preference_entity.enabled and recipient.phone:
                send_sms.delay(notification.id, broadcast_id, org_id, recipient.id, data)
            elif sms_preference_entity.enabled and not recipient.phone:
                logging.warning(
                    "Trying to route SMS notification without phone on record for user: %s in org: %s for broadcast: %s",
                    recipient.id,
                    org_id,
                    broadcast_id,
                )
                NotificationChannel.objects.create(notification_id=notification.id,
                                                   slug=ChannelChoices.SMS, status="failed",
                                                   reason="No phone provided for user")
            else:
                logging.info(
                    "SMS disabled for category: %s for user: %s in org: %s for broadcast: %s",
                    data.get("category", None),
                    recipient.id,
                    org_id,
                    broadcast_id,
                )
                NotificationChannel.objects.create(notification_id=notification.id,
                                                   slug=ChannelChoices.SMS, status="not_sent", reason="User disabled")

        if "email" in data["channels"]:
            email_preference_entity = channels.get(slug=ChannelChoices.EMAIL.value)
            if email_preference_entity.enabled:
                send_email.delay(notification.id, broadcast_id, org_id, recipient.id, data)
            else:
                logging.info(
                    "Email disabled for category: %s for user: %s in org: %s for broadcast: %s",
                    data.get("category", None),
                    recipient.id,
                    org_id,
                    broadcast_id,
                )
                NotificationChannel.objects.create(notification_id=notification.id,
                                                   slug=ChannelChoices.EMAIL, status="not_sent", reason="User disabled")

        if "mobile_push" in data['channels']:
            mobile_preference_entity = channels.get(slug=ChannelChoices.MOBILE_PUSH.value)
            if mobile_preference_entity.enabled:
                send_mobile.delay(notification.id, org_id, recipient.id, data)
            else:
                logging.info(
                    "Mobile push disabled for category: %s for user: %s in org: %s for broadcast: %s",
                    data.get("category", None),
                    recipient.id,
                    org_id,
                    broadcast_id,
                )
                NotificationChannel.objects.create(notification_id=notification.id,
                                                   slug=ChannelChoices.MOBILE_PUSH, status="not_sent",
                                                   reason="User disabled")


def route_basic_notification(broadcast_id, org_id, recipient, data):
    logging.info(
        "Routing basic notification for user: %s in org: %s for broadcast: %s",
        recipient.id,
        org_id,
        broadcast_id,
    )

    notification = persist_notification(broadcast_id, org_id, recipient.id, data, sent_at=datetime.now(timezone.utc))
    send_web.delay(notification.id, recipient.id, data)

    if "channels" in data:
        if "sms" in data["channels"] and recipient.phone:
            send_sms.delay(notification.id, broadcast_id, org_id, recipient.id, data)
        elif "sms" in data["channels"] and not recipient.phone:
            logging.warning(
                "Trying to route SMS notification without phone on record for user: %s in org: %s for broadcast: %s",
                recipient.id,
                org_id,
                broadcast_id,
            )
            NotificationChannel.objects.create(notification_id=notification.id,
                                               slug=ChannelChoices.SMS, status="failed",
                                               reason="No phone provided for user")
        if "email" in data["channels"]:
            send_email.delay(notification.id, broadcast_id, org_id, recipient.id, data)
        if "mobile_push" in data["channels"]:
            send_mobile.delay(notification.id, org_id, recipient.id, data)
