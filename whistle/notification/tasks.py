import logging
import uuid
from datetime import datetime, timezone

from asgiref.sync import async_to_sync
from celery import chord
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from pyapns_client import (
    IOSPayloadAlert,
    IOSPayload,
    IOSNotification,
    APNSClient,
    APNSException,
)
from pyfcm.errors import FCMError
from python_http_client import HTTPError
from redbeat import RedBeatSchedulerEntry
from sendgrid import (
    SendGridAPIClient,
    Email,
    To,
    Content,
    Mail,
    MailSettings,
    SandBoxMode,
)
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from audience.models import Audience, OperatorChoices
from provider.models import (
    Provider,
    ProviderTypeChoices,
    ProviderChoices,
)
from external_user.models import ExternalUser, ExternalUserDevice, PlatformChoices
from notification.models import (
    Notification,
    Broadcast,
    BroadcastRecipient,
    NotificationDelivery,
)
from preference.models import ExternalUserPreference, ChannelChoices
from subscription.models import ExternalUserSubscription
from whistle import utils
from whistle.celery import app
from whistle.client import CustomAPNSClient, CustomFCMNotification

basic_fields = {
    "email",
    "phone",
    "first_name",
    "last_name",
}


@app.task
@transaction.atomic
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

        for recipient in recipients.iterator():
            notification = persist_notification(org_id, broadcast_id, recipient.id)
            tasks.append(
                handle_recipient.s(
                    broadcast_id, org_id, recipient.id, notification.id, data
                )
            )
            recipient_ids.add(recipient.id)

    if "recipients" in data:
        for recipient in data["recipients"]:
            recipient_entity = update_or_create_external_user(
                broadcast_id, org_id, recipient, data
            )
            if recipient_entity:
                if recipient_entity.id not in recipient_ids:
                    notification = persist_notification(
                        org_id, broadcast_id, recipient_entity.id
                    )
                    tasks.append(
                        handle_recipient.s(
                            broadcast_id,
                            org_id,
                            recipient_entity.id,
                            notification.id,
                            data,
                        )
                    )
                    recipient_ids.add(recipient_entity.id)

    if "topic" in data:
        subscribers = ExternalUserSubscription.objects.filter(
            organization_id=org_id, topic=data["topic"]
        )

        for subscriber in subscribers.iterator():
            if subscriber.id not in recipient_ids:
                notification = persist_notification(org_id, broadcast_id, subscriber.id)
                tasks.append(
                    handle_topic_subscriber.s(
                        broadcast_id, org_id, subscriber.id, notification.id, data
                    )
                )
                recipient_ids.add(subscriber.id)

    if "schedule_at" in data:
        entry = RedBeatSchedulerEntry.from_key(
            f"redbeat:broadcast_{broadcast_id}", app=app
        )
        entry.delete()

    result = chord(tasks)(update_broadcast_status.s(broadcast_id, "processed"))

    return broadcast_id


def build_filter_kwargs(filters):
    query_kwargs = {}
    for filter_rec in filters:
        filter_rec.property = filter_rec.property.replace(".", "__")
        if filter_rec.property in basic_fields:
            filter_rec.property = f"{filter_rec.property}_hash"
            filter_rec.value = utils.perform_hash(filter_rec.value)
        match filter_rec.operator:
            case OperatorChoices.EQ:
                query_kwargs[filter_rec.property] = filter_rec.value
            case OperatorChoices.GT:
                query_kwargs[f"{filter_rec.property}__gt"] = filter_rec.value
            case OperatorChoices.LT:
                query_kwargs[f"{filter_rec.property}__lt"] = filter_rec.value
            case OperatorChoices.GTE:
                query_kwargs[f"{filter_rec.property}__gte"] = filter_rec.value
            case OperatorChoices.LTE:
                query_kwargs[f"{filter_rec.property}__lte"] = filter_rec.value
            case OperatorChoices.CONTAINS:
                query_kwargs[f"{filter_rec.property}__contains"] = filter_rec.value
            case _:
                continue
    return query_kwargs


def build_exclude_kwargs(filters):
    query_kwargs = {}
    for filter_rec in filters:
        filter_rec.property = filter_rec.property.replace(".", "__")
        match filter_rec.operator:
            case OperatorChoices.NEQ:
                query_kwargs[filter_rec.property] = filter_rec.value
            case OperatorChoices.DOES_NOT_CONTAIN.value:
                query_kwargs[f"{filter_rec.property}__contains"] = filter_rec.value
            case _:
                continue
    return query_kwargs


@app.task
@transaction.atomic
def handle_recipient(broadcast_id, org_id, recipient_id, notification_id, data):
    recipient = ExternalUser.objects.get(pk=recipient_id)

    if "category" in data:
        preference = ExternalUserPreference.objects.prefetch_related("channels").filter(
            user_id=recipient.id, slug=data["category"]
        )

        if preference:
            route_notification_with_preference(
                broadcast_id,
                org_id,
                notification_id,
                recipient,
                preference.first().channels.all(),
                data,
            )
            return recipient.id
        else:
            route_basic_notification(
                broadcast_id, org_id, notification_id, recipient, data
            )
            return recipient.id
    else:
        route_basic_notification(broadcast_id, org_id, notification_id, recipient, data)
        return recipient.id


@app.task
@transaction.atomic
def handle_topic_subscriber(broadcast_id, org_id, subscriber_id, notification_id, data):
    subscriber = ExternalUserSubscription.objects.get(pk=subscriber_id)

    if "category" in data:
        subscriber_category = subscriber.categories.filter(slug=data["category"])

        preference = ExternalUserPreference.objects.prefetch_related("channels").filter(
            user_id=subscriber.user.id, slug=data["category"]
        )

        if subscriber_category and preference and subscriber_category.first().enabled:
            route_notification_with_preference(
                broadcast_id,
                org_id,
                notification_id,
                subscriber.user,
                preference.first().channels.all(),
                data,
            )
            return subscriber.id
        elif subscriber_category and subscriber_category.first().enabled:
            route_basic_notification(
                broadcast_id, org_id, notification_id, subscriber.user, data
            )
            return subscriber.id
    else:
        route_basic_notification(
            broadcast_id, org_id, notification_id, subscriber.user, data
        )
        return subscriber.id


@app.task
@transaction.atomic
def send_sms(broadcast_id, org_id, user_id, notification_id, data):
    user = ExternalUser.objects.get(id=user_id)
    providers = Provider.objects.prefetch_related("credentials").filter(
        organization_id=org_id, provider_type=ProviderTypeChoices.SMS
    )

    for provider in providers.iterator():
        match provider.provider:
            case ProviderChoices.TWILIO.value:
                handle_twilio(broadcast_id, data, notification_id, provider, user)
            case _:
                continue
    return user_id


@app.task
@transaction.atomic
def send_email(broadcast_id, org_id, user_id, notification_id, data):
    user = ExternalUser.objects.get(id=user_id)
    providers = Provider.objects.prefetch_related("credentials").filter(
        organization_id=org_id, provider_type=ProviderTypeChoices.EMAIL
    )

    for provider in providers.all():
        match provider.provider:
            case ProviderChoices.SENDGRID.value:
                handle_sendgrid(broadcast_id, data, notification_id, provider, user)
            case _:
                continue
    return user_id


@app.task
@transaction.atomic
def send_in_app(broadcast_id, org_id, user_id, notification_id, data):
    title = data["title"]
    content = data["content"]
    action_link = data.get("action_link")

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
                "title": title,
                "content": content,
                "action_link": action_link,
                "additional_info": data.get("additional_info", {}),
            },
        },
    )

    persist_notification_delivery(
        notification_id,
        title,
        content,
        action_link,
        channel=ChannelChoices.IN_APP,
        status="sent",
        sent_at=datetime.now(timezone.utc),
    )

    return user_id


@app.task
@transaction.atomic
def send_push(broadcast_id, org_id, user_id, notification_id, data):
    devices = ExternalUserDevice.objects.filter(user_id=user_id)

    apns = Provider.objects.prefetch_related("credentials").filter(
        organization_id=org_id, provider=ProviderChoices.APNS, enabled=True
    )
    fcm = Provider.objects.prefetch_related("credentials").filter(
        organization_id=org_id, provider=ProviderChoices.FCM, enabled=True
    )

    if not devices:
        logging.info("No devices for user: %s in broadcast: %s", user_id, broadcast_id)
        return

    for device in devices.iterator():
        match device.platform:
            case PlatformChoices.IOS:
                if apns:
                    handle_apns(
                        apns.first(),
                        broadcast_id,
                        data,
                        device,
                        notification_id,
                        user_id,
                    )
                else:
                    logging.info(
                        "APNS account not enabled or found for org: %s",
                        user_id,
                        org_id,
                    )
            case PlatformChoices.ANDROID:
                if fcm:
                    handle_fcm(data, device, fcm.first(), notification_id, user_id)
                else:
                    logging.info(
                        "FCM account not enabled or found for org: %s",
                        user_id,
                        org_id,
                    )
            case _:
                continue
    return user_id


@app.task
@transaction.atomic
def update_broadcast_status(_, broadcast_id, status):
    broadcast = Broadcast.objects.get(pk=broadcast_id)
    broadcast.status = status
    broadcast.save()
    return broadcast_id


@app.task
@transaction.atomic
def add_broadcast_recipient(_, broadcast_id, recipient_id):
    BroadcastRecipient.objects.create(
        broadcast_id=broadcast_id, recipient_id=recipient_id
    )
    return recipient_id


@transaction.atomic
def handle_apns(apns, broadcast_id, data, device, notification_id, user_id):
    credentials_dict = {
        credential.slug: credential.value for credential in apns.credentials.all()
    }
    bundle_id = credentials_dict["bundle_id"]
    use_sandbox = credentials_dict["use_sandbox"]
    key_p8 = credentials_dict["key_p8"]
    key_id = credentials_dict["key_id"]
    team_id = credentials_dict["team_id"]

    title = data.get("providers", {}).get("apns", {}).get("title") or data["title"]
    body = data.get("providers", {}).get("apns", {}).get("body") or data["content"]
    subtitle = data.get("providers", {}).get("apns", {}).get("subtitle")
    payload = IOSPayload(
        alert=IOSPayloadAlert(
            title=title,
            body=body,
            subtitle=subtitle,
        ),
        sound=data.get("providers", {}).get("apns", {}).get("sound") or "default",
        badge=data.get("providers", {}).get("apns", {}).get("badge") or 1,
        category=data.get("category"),
    )
    ios_notification = IOSNotification(
        payload=payload,
        topic=bundle_id.value,
        apns_id=broadcast_id,
    )

    try:
        client = CustomAPNSClient(
            mode=(APNSClient.MODE_DEV if use_sandbox.value else APNSClient.MODE_PROD),
            root_cert_path=None,
            auth_key_path=key_p8.value,
            auth_key_id=key_id.value,
            team_id=team_id.value,
        )
        res = client.push(notification=ios_notification, device_token=device.token)

        logging.info(
            "Apple push notification sent for user: %s with response: %s",
            user_id,
            res,
        )

        persist_notification_delivery(
            notification_id,
            title,
            body,
            data.get("action_link"),
            channel=ChannelChoices.PUSH,
            status="sent",
            sent_at=datetime.now(timezone.utc),
            metadata={"platform": PlatformChoices.IOS.value},
        )

    except APNSException as error:
        logging.info(
            "Failed to send Apple push notification sent for user: %s with status code: %s and apns_id: %s",
            user_id,
            error.status_code,
            error.apns_id,
        )

        persist_notification_delivery(
            notification_id,
            title,
            body,
            data.get("action_link"),
            channel=ChannelChoices.PUSH,
            status="failed",
            reason=f"APNS error with status code: {error.status_code} ",
            metadata={
                "platform": PlatformChoices.IOS.value,
                "apns_id": error.apns_id,
            },
        )


@transaction.atomic
def handle_fcm(data, device, fcm, notification_id, user_id):
    credentials_dict = {
        credential.slug: credential.value for credential in fcm.credentials.all()
    }
    project_id = credentials_dict["project_id"]
    credentials = credentials_dict["credentials"]

    fcm_notification = CustomFCMNotification(
        service_account_file=credentials.value,
        project_id=project_id.value,
    )
    title = data.get("providers", {}).get("fcm", {}).get("title") or data["title"]
    body = data.get("providers", {}).get("fcm", {}).get("body") or data["content"]
    image = data.get("providers", {}).get("fcm", {}).get("image")
    try:
        res = fcm_notification.notify(
            fcm_token=device.token,
            notification_title=title,
            notification_image=image,
            notification_body=body,
        )

        logging.info(
            "FCM notification sent for user: %s with response: %s",
            user_id,
            res,
        )

        persist_notification_delivery(
            notification_id,
            title,
            body,
            data["channels"]["push"].get(
                "action_link",
            ),
            channel=ChannelChoices.PUSH,
            status="sent",
            sent_at=datetime.now(timezone.utc),
            metadata={"platform": PlatformChoices.ANDROID.value},
        )

    except FCMError as e:
        logging.info(
            "Firebase cloud messaging notification failed to send for user: %s with error: %s",
            user_id,
            e,
        )

        persist_notification_delivery(
            notification_id,
            title,
            body,
            data.get("action_link"),
            channel=ChannelChoices.PUSH,
            status="failed",
            error_reason=e,
            metadata={"platform": PlatformChoices.ANDROID.value},
        )


@transaction.atomic
def handle_twilio(broadcast_id, data, notification_id, provider, user):
    credentials_dict = {
        credential.slug: credential.value for credential in provider.credentials.all()
    }
    twilio_client = Client(
        credentials_dict["account_sid"], credentials_dict["auth_token"]
    )
    title = data.get("title")
    content = data.get("content")
    body = (
        data.get("providers", {}).get("twilio", {}).get("body") or f"{title}\n{content}"
    )
    try:
        message = twilio_client.messages.create(
            to=user.phone,
            from_=credentials_dict["from_phone"],
            body=body,
        )
    except TwilioRestException as error:
        logging.error(
            "Twilio failed to send text to user: %s for broadcast: %s with message: ",
            user.id,
            broadcast_id,
            error.msg,
        )

        reason = f"{error.status}: {error.msg}"
        persist_notification_delivery(
            notification_id,
            None,
            None,
            data.get("action_link"),
            channel=ChannelChoices.SMS,
            status="failed",
            error_reason=reason,
        )
        return
    logging.info(
        "Sent twilio sms to user: %s for broadcast: %s with status: %s",
        user.id,
        broadcast_id,
        message.status,
    )
    if message.status in {"failed", "undelivered", "canceled"}:
        status = "failed"
        reason = f"{message.status}: {message.error_message}"
    else:
        status = "sent"
        reason = None
    # todo handle persisting overriden body
    persist_notification_delivery(
        notification_id,
        title,
        content,
        data.get("action_link"),
        channel=ChannelChoices.SMS,
        status=status,
        error_reason=reason,
        metadata={"twilio_message_sid": message.sid},
    )
    return


@transaction.atomic
def handle_sendgrid(broadcast_id, data, notification_id, provider, user):
    credentials_dict = {
        credential.slug: credential.value for credential in provider.credentials.all()
    }

    sg = SendGridAPIClient(api_key=credentials_dict["api_key"])
    from_email = Email(credentials_dict["from_email"])
    to_email = To(user.email)
    mail = Mail(from_email, to_email)
    mail_settings = MailSettings()
    mail_settings.sandbox_mode = SandBoxMode(settings.USE_SENDGRID_SANDBOX)
    mail.mail_settings = mail_settings

    title = data.get("providers", {}).get("sendgrid", {}).get("title") or data["title"]
    content = (
        data.get("providers", {}).get("sendgrid", {}).get("content") or data["content"]
    )
    template_id = data.get("providers", {}).get("sendgrid", {}).get("sg_template_id")
    if template_id:
        mail.dynamic_template_data = data.get("merge_tags")
        mail.template_id = template_id
    else:
        mail.subject = title
        mail.content = Content(
            "text/plain",
            content,
        )

    try:
        response = sg.send(mail)
    except HTTPError as error:
        logging.error(
            "Sendgrid failed to send email to user: %s for broadcast: %s with reason: ",
            user.id,
            broadcast_id,
            error.reason,
        )

        persist_notification_delivery(
            notification_id,
            None,
            None,
            data.get("action_link"),
            channel=ChannelChoices.EMAIL,
            status="failed",
            reason=error.reason,
        )
        return

    logging.info(
        "Sendgrid email with status code: %s sent to user: %s with broadcast: %s",
        response.status_code,
        user.id,
        broadcast_id,
    )

    persist_notification_delivery(
        notification_id,
        None if template_id else title,
        None if template_id else content,
        data.get("action_link"),
        channel=ChannelChoices.EMAIL,
        status="sent",
        sent_at=datetime.now(timezone.utc),
        metadata={
            "sg_x_message_id": response.headers["X-Message-ID"],
            "sg_template_id": template_id,
        },
    )
    return


@transaction.atomic
def persist_notification(org_id, broadcast_id, recipient_id, **kwargs):
    notification = Notification.objects.create(
        organization_id=org_id,
        broadcast_id=broadcast_id,
        recipient_id=recipient_id,
        **kwargs,
    )

    logging.info(
        "Notification record with id: %s persisted for notification: %s",
        notification.id,
    )

    return notification


@transaction.atomic
def persist_notification_delivery(
    notification_id, title=None, content=None, action_link=None, **kwargs
):
    notification_channel = NotificationDelivery.objects.create(
        notification_id=notification_id,
        title=title,
        content=content,
        action_link=action_link,
        **kwargs,
    )

    logging.info(
        "Notification channel record with id: %s persisted for notification: %s",
        notification_channel.id,
    )

    return notification_channel


@transaction.atomic
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
            email_hash = utils.perform_hash(recipient["email"])
            return ExternalUser.objects.get(
                organization_id=org_id, email_hash=email_hash
            )
        except ExternalUser.DoesNotExist:
            broadcast = Broadcast.objects.get(pk=broadcast_id)
            metadata = broadcast.metadata or {}
            metadata["errors"] = metadata.get("errors", {})
            metadata["errors"]["recipients"] = metadata.get("errors").get(
                "recipients", []
            )
            metadata["errors"]["recipients"].append(
                {"email": recipient["email"], "reason": "User email does not exist"}
            )
            broadcast.metadata = metadata
            broadcast.save()

            return


@transaction.atomic
def route_notification_with_preference(
    broadcast_id, org_id, notification_id, recipient, channels, data
):
    tasks = []

    if ChannelChoices.IN_APP.value in data["channels"]:
        web_preference_entity = channels.get(slug=ChannelChoices.IN_APP.value)
        if web_preference_entity.enabled:
            tasks.append(
                send_in_app.s(broadcast_id, org_id, recipient.id, notification_id, data)
            )
        else:
            logging.info(
                "In app disabled for category %s for user: %s in org: %s for broadcast: %s",
                data.get("category", None),
                recipient.id,
                org_id,
                broadcast_id,
            )
            persist_notification_delivery(
                notification_id,
                data["title"],
                data["content"],
                data.get("action_link"),
                channel=ChannelChoices.IN_APP,
                status="not_sent",
                error_reason="User disabled",
            )

    if ChannelChoices.SMS.value in data["channels"]:
        sms_preference_entity = channels.get(slug=ChannelChoices.SMS.value)
        if sms_preference_entity.enabled and recipient.phone:
            tasks.append(send_sms.s(broadcast_id, org_id, recipient.id, data))
        elif sms_preference_entity.enabled and not recipient.phone:
            logging.warning(
                "Trying to route SMS notification without phone on record for user: %s in org: %s for broadcast: %s",
                recipient.id,
                org_id,
                broadcast_id,
            )
            persist_notification_delivery(
                notification_id,
                channel=ChannelChoices.SMS,
                status="failed",
                error_reason="No phone provided for user",
            )
        else:
            logging.info(
                "SMS disabled for category: %s for user: %s in org: %s for broadcast: %s",
                data.get("category", None),
                recipient.id,
                org_id,
                broadcast_id,
            )
            persist_notification_delivery(
                notification_id,
                channel=ChannelChoices.SMS,
                status="not_sent",
                error_reason="User disabled",
            )

    if ChannelChoices.EMAIL.value in data["channels"]:
        email_preference_entity = channels.get(slug=ChannelChoices.EMAIL.value)
        if email_preference_entity.enabled:
            tasks.append(
                send_email.s(broadcast_id, org_id, recipient.id, notification_id, data)
            )
        else:
            logging.info(
                "Email disabled for category: %s for user: %s in org: %s for broadcast: %s",
                data.get("category", None),
                recipient.id,
                org_id,
                broadcast_id,
            )
            persist_notification_delivery(
                notification_id,
                channel=ChannelChoices.EMAIL,
                status="not_sent",
                error_reason="User disabled",
            )

    if ChannelChoices.PUSH.value in data["channels"]:
        mobile_preference_entity = channels.get(slug=ChannelChoices.PUSH.value)
        if mobile_preference_entity.enabled:
            tasks.append(
                send_push.s(broadcast_id, org_id, recipient.id, notification_id, data)
            )
        else:
            logging.info(
                "Mobile push disabled for category: %s for user: %s in org: %s for broadcast: %s",
                data.get("category"),
                recipient.id,
                org_id,
                broadcast_id,
            )
            persist_notification_delivery(
                notification_id,
                channel=ChannelChoices.PUSH,
                status="not_sent",
                error_reason="User disabled",
            )

    result = chord(tasks)(add_broadcast_recipient.s(broadcast_id, recipient.id))

    return result.id


@transaction.atomic
def route_basic_notification(broadcast_id, org_id, notification_id, recipient, data):
    tasks = []

    if ChannelChoices.IN_APP.value in data["channels"]:
        tasks.append(
            send_in_app.s(broadcast_id, org_id, recipient.id, notification_id, data)
        )

    if ChannelChoices.SMS.value in data["channels"]:
        tasks.append(
            send_sms.s(broadcast_id, org_id, recipient.id, notification_id, data)
        )
    elif ChannelChoices.SMS.value in data["channels"] and not recipient.phone:
        logging.warning(
            "Trying to route SMS notification without phone on record for user: %s in org: %s for broadcast: %s",
            recipient.id,
            org_id,
            broadcast_id,
        )
        persist_notification_delivery(
            notification_id,
            channel=ChannelChoices.SMS,
            status="failed",
            error_reason="No phone provided for user",
        )
    if ChannelChoices.EMAIL.value in data["channels"]:
        tasks.append(
            send_email.s(broadcast_id, org_id, recipient.id, notification_id, data)
        )
    if ChannelChoices.PUSH.value in data["channels"]:
        tasks.append(
            send_push.s(broadcast_id, org_id, recipient.id, notification_id, data)
        )

    result = chord(tasks)(add_broadcast_recipient.s(broadcast_id, recipient.id))

    return result.id
