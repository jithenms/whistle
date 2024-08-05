import logging
import uuid
from datetime import datetime, timezone

from asgiref.sync import async_to_sync
from celery import chord
from celery.exceptions import MaxRetriesExceededError
from celery.utils.time import get_exponential_backoff_interval
from channels.layers import get_channel_layer
from django.conf import settings
from django.db.models import Q
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
    NotificationDelivery,
    DeliveryStatusChoices,
    NotificationStatusChoices,
    BroadcastStatusChoices,
)
from preference.models import ExternalUserPreference, ChannelChoices
from subscription.models import ExternalUserSubscription
from whistle import utils
from whistle.celery import app
from whistle.client import CustomAPNSClient, CustomFCMNotification
from whistle.exceptions import NotificationException

basic_fields = {
    "email",
    "phone",
    "first_name",
    "last_name",
}


@app.task(bind=True, ignore_result=True, queue="broadcasts")
def send_broadcast(self, broadcast_id, org_id, data):
    tasks = []

    broadcast_id = uuid.UUID(broadcast_id)
    org_id = uuid.UUID(org_id)

    recipient_ids = set()

    redacted_data = data.copy()
    redacted_data.update({"recipients": "***"})
    redacted_data.update({"merge_tags": "***"})

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
            notification, created = persist_notification(
                org_id,
                broadcast_id,
                recipient.id,
                status=NotificationStatusChoices.QUEUED,
            )
            if (
                not created
                and notification.status == NotificationStatusChoices.PROCESSED
            ):
                logging.info(
                    "User: %s already successfully processed in broadcast: %s",
                    recipient.id,
                    broadcast_id,
                )
                continue
            tasks.append(
                send_recipient.s(
                    broadcast_id, org_id, recipient.id, notification.id, data=data
                ).set(kwargsrepr=repr({"data": redacted_data}))
            )
            recipient_ids.add(recipient.id)

    if "recipients" in data:
        for recipient in data["recipients"]:
            recipient_entity = update_or_create_external_user(
                broadcast_id, org_id, recipient, data
            )
            if recipient_entity:
                if recipient_entity.id not in recipient_ids:
                    notification, created = persist_notification(
                        org_id,
                        broadcast_id,
                        recipient_entity.id,
                        status=NotificationStatusChoices.QUEUED,
                    )
                    if (
                        not created
                        and notification.status == NotificationStatusChoices.PROCESSED
                    ):
                        logging.info(
                            "User: %s already successfully processed in broadcast: %s",
                            recipient_entity.id,
                            broadcast_id,
                        )
                        continue
                    tasks.append(
                        send_recipient.s(
                            broadcast_id,
                            org_id,
                            recipient_entity.id,
                            notification.id,
                            data=data,
                        ).set(kwargsrepr=repr({"data": redacted_data}))
                    )
                    recipient_ids.add(recipient_entity.id)

    if "topic" in data:
        subscribers = ExternalUserSubscription.objects.select_related("user").filter(
            organization_id=org_id, topic=data["topic"]
        )

        for subscriber in subscribers.iterator():
            if subscriber.user.id not in recipient_ids:
                notification, created = persist_notification(
                    org_id,
                    broadcast_id,
                    subscriber.user.id,
                    status=NotificationStatusChoices.QUEUED,
                )
                if (
                    not created
                    and notification.status == NotificationStatusChoices.PROCESSED
                ):
                    logging.info(
                        "Subscriber: %s already successfully processed in broadcast: %s",
                        subscriber.user.id,
                        broadcast_id,
                    )
                    continue
                tasks.append(
                    send_subscriber.s(
                        broadcast_id, org_id, subscriber.id, notification.id, data=data
                    ).set(kwargsrepr=repr({"data": redacted_data}))
                )
                recipient_ids.add(subscriber.user.id)

    if "schedule_at" in data:
        entry = RedBeatSchedulerEntry.from_key(
            f"redbeat:broadcast_{broadcast_id}", app=app
        )
        entry.delete()

    chord(tasks)(
        send_broadcast_callback.si(broadcast_id, BroadcastStatusChoices.PROCESSED)
    )

    return


@app.task(bind=True, ignore_result=True, queue="notifications")
def send_recipient(self, broadcast_id, org_id, recipient_id, notification_id, data):
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
            return
        else:
            route_basic_notification(
                broadcast_id, org_id, notification_id, recipient, data
            )
            return
    else:
        route_basic_notification(broadcast_id, org_id, notification_id, recipient, data)
        return


@app.task(bind=True, ignore_result=True, queue="notifications")
def send_subscriber(self, broadcast_id, org_id, subscriber_id, notification_id, data):
    subscriber = ExternalUserSubscription.objects.select_related("user").get(
        pk=subscriber_id
    )

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
            return
        elif subscriber_category and subscriber_category.first().enabled:
            route_basic_notification(
                broadcast_id, org_id, notification_id, subscriber.user, data
            )
            return
    else:
        route_basic_notification(
            broadcast_id, org_id, notification_id, subscriber.user, data
        )
        return


@app.task(bind=True, ignore_result=True, queue="outbound", max_retries=5)
def send_sms(self, broadcast_id, org_id, user_id, notification_id, data, phone):
    try:
        delivered_count = (
            NotificationDelivery.objects.filter(
                notification_id=notification_id,
                channel=ChannelChoices.SMS.value,
            )
            .filter(
                Q(status=DeliveryStatusChoices.DELIVERED)
                | Q(status=DeliveryStatusChoices.NOT_SENT)
            )
            .count()
        )
        if delivered_count != 0:
            logging.info(
                "SMS notification already delivered for user: %s in org: %s for broadcast: %s",
                user_id,
                org_id,
                broadcast_id,
            )
            return

        provider = Provider.objects.prefetch_related("credentials").get(
            organization_id=org_id, provider_type=ProviderTypeChoices.SMS
        )

        match provider.provider:
            case ProviderChoices.TWILIO:
                return handle_twilio(
                    broadcast_id,
                    data,
                    notification_id,
                    provider,
                    user_id,
                    phone,
                )
            case _:
                logging.error("Invalid SMS Provider")
                return
    except TwilioRestException as e:
        try:
            countdown = get_exponential_backoff_interval(
                factor=settings.CELERY_RETRY_BACKOFF,
                retries=self.request.retries,
                maximum=settings.CELERY_BACKOFF_MAX,
                full_jitter=settings.CELERY_RETRY_JITTER,
            )
            self.retry(countdown=countdown)
        except MaxRetriesExceededError:
            logging.error(
                "Max retries reached trying to send Twilio SMS for user: %s in broadcast: %s",
                user_id,
                broadcast_id,
            )
            persist_notification_delivery(
                notification_id,
                channel=ChannelChoices.SMS,
                status=DeliveryStatusChoices.UNDELIVERED,
            )


@app.task(bind=True, ignore_result=True, queue="outbound", max_retries=5)
def send_email(self, broadcast_id, org_id, user_id, notification_id, data, email):
    try:
        delivered_count = (
            NotificationDelivery.objects.filter(
                notification_id=notification_id,
                channel=ChannelChoices.EMAIL.value,
            )
            .filter(
                Q(status=DeliveryStatusChoices.DELIVERED)
                | Q(status=DeliveryStatusChoices.NOT_SENT)
            )
            .count()
        )
        if delivered_count != 0:
            logging.info(
                "Email notification already delivered for user: %s in org: %s for broadcast: %s",
                user_id,
                org_id,
                broadcast_id,
            )
            return

        provider = Provider.objects.prefetch_related("credentials").get(
            organization_id=org_id, provider_type=ProviderTypeChoices.EMAIL
        )

        match provider.provider:
            case ProviderChoices.SENDGRID:
                return handle_sendgrid(
                    broadcast_id, data, notification_id, provider, user_id, email
                )
            case _:
                logging.error("Invalid Email Provider")
                return
    except HTTPError as e:
        try:
            countdown = get_exponential_backoff_interval(
                factor=settings.CELERY_RETRY_BACKOFF,
                retries=self.request.retries,
                maximum=settings.CELERY_BACKOFF_MAX,
                full_jitter=settings.CELERY_RETRY_JITTER,
            )
            self.retry(countdown=countdown)
        except MaxRetriesExceededError:
            logging.error(
                "Max retries reached trying to send Sendgrid email for user: %s in broadcast: %s",
                user_id,
                broadcast_id,
            )
            persist_notification_delivery(
                notification_id,
                channel=ChannelChoices.EMAIL,
                status=DeliveryStatusChoices.UNDELIVERED,
            )


@app.task(bind=True, ignore_result=True, queue="outbound", max_retries=5)
def send_in_app(self, broadcast_id, org_id, user_id, notification_id, data):
    try:
        delivered_count = (
            NotificationDelivery.objects.filter(
                notification_id=notification_id,
                channel=ChannelChoices.IN_APP.value,
            )
            .filter(
                Q(status=DeliveryStatusChoices.DELIVERED)
                | Q(status=DeliveryStatusChoices.NOT_SENT)
            )
            .count()
        )
        if delivered_count != 0:
            logging.info(
                "In app notification already delivered for user: %s in org: %s for broadcast: %s",
                user_id,
                org_id,
                broadcast_id,
            )
            return

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
            status=DeliveryStatusChoices.DELIVERED,
        )

        return
    except Exception as e:
        try:
            countdown = get_exponential_backoff_interval(
                factor=settings.CELERY_RETRY_BACKOFF,
                retries=self.request.retries,
                maximum=settings.CELERY_BACKOFF_MAX,
                full_jitter=settings.CELERY_RETRY_JITTER,
            )
            self.retry(countdown=countdown)
        except MaxRetriesExceededError:
            logging.error(
                "Max retries reached trying to send in app notification for user: %s in broadcast: %s",
                user_id,
                broadcast_id,
            )
            persist_notification_delivery(
                notification_id,
                channel=ChannelChoices.IN_APP,
                status=DeliveryStatusChoices.UNDELIVERED,
            )


@app.task(bind=True, ignore_result=True, queue="outbound", max_retries=5)
def send_push(
    self,
    device_id,
    broadcast_id,
    org_id,
    user_id,
    notification_id,
    data,
):
    device = ExternalUserDevice.objects.get(pk=device_id)

    delivered_count = (
        NotificationDelivery.objects.filter(
            notification_id=notification_id,
            channel=ChannelChoices.PUSH.value,
        )
        .filter(
            Q(
                status=DeliveryStatusChoices.DELIVERED,
                metadata__platform=device.platform,
            )
            | Q(status=DeliveryStatusChoices.NOT_SENT)
        )
        .count()
    )

    if delivered_count != 0:
        logging.info(
            "Push notification to device: %s already delivered for user: %s in org: %s for broadcast: %s",
            device_id,
            user_id,
            org_id,
            broadcast_id,
        )
        return

    provider = (
        ProviderChoices.APNS
        if device.platform == PlatformChoices.IOS
        else ProviderChoices.FCM
    )

    provider = Provider.objects.prefetch_related("credentials").filter(
        organization_id=org_id, provider=provider
    )

    if not provider:
        logging.info("%s provider doesn't exist for org: %s", provider.VALUE, org_id)
        return

    match device.platform:
        case PlatformChoices.IOS:
            try:
                return handle_apns(
                    provider,
                    broadcast_id,
                    data,
                    device,
                    notification_id,
                    user_id,
                )
            except APNSException as e:
                try:
                    countdown = get_exponential_backoff_interval(
                        factor=settings.CELERY_RETRY_BACKOFF,
                        retries=self.request.retries,
                        maximum=settings.CELERY_BACKOFF_MAX,
                        full_jitter=settings.CELERY_RETRY_JITTER,
                    )
                    self.retry(countdown=countdown)
                except MaxRetriesExceededError:
                    logging.error(
                        "Max retries reached trying to send APNS notification for user: %s in broadcast: %s",
                        user_id,
                        broadcast_id,
                    )
                    persist_notification_delivery(
                        notification_id,
                        channel=ChannelChoices.PUSH,
                        metadata__platform=PlatformChoices.IOS,
                        status=DeliveryStatusChoices.UNDELIVERED,
                    )
        case PlatformChoices.ANDROID:
            try:
                return handle_fcm(
                    provider,
                    broadcast_id,
                    data,
                    device,
                    notification_id,
                    user_id,
                )
            except FCMError as e:
                try:
                    countdown = get_exponential_backoff_interval(
                        factor=settings.CELERY_RETRY_BACKOFF,
                        retries=self.request.retries,
                        maximum=settings.CELERY_BACKOFF_MAX,
                        full_jitter=settings.CELERY_RETRY_JITTER,
                    )
                    self.retry(countdown=countdown)
                except MaxRetriesExceededError:
                    logging.error(
                        "Max retries reached trying to send FCM notification for user: %s in broadcast: %s",
                        user_id,
                        broadcast_id,
                    )
                    persist_notification_delivery(
                        notification_id,
                        channel=ChannelChoices.PUSH,
                        metadata__platform=PlatformChoices.ANDROID,
                        status=DeliveryStatusChoices.UNDELIVERED,
                    )
        case _:
            logging.info(
                "Platform: %s not recognized for device: %s", device.platform, device_id
            )
            return


@app.task(bind=True, ignore_result=True, queue="broadcasts")
def send_broadcast_callback(self, broadcast_id, status):
    broadcast = Broadcast.objects.get(pk=broadcast_id)
    broadcast.status = status
    broadcast.save()
    return


@app.task(bind=True, ignore_result=True, queue="notifications")
def send_recipient_callback(self, notification_id, status):
    notification = Notification.objects.get(pk=notification_id)
    notification.status = status
    notification.save()
    return


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
            platform=PlatformChoices.IOS.value,
            status=DeliveryStatusChoices.DELIVERED,
        )

    except APNSException as error:
        logging.error(
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
            status=DeliveryStatusChoices.ATTEMPTED,
            reason=f"APNS error with status code: {error.status_code} ",
            metadata={
                "platform": PlatformChoices.IOS.value,
                "apns_id": error.apns_id,
            },
        )

        raise

    return


def handle_fcm(fcm, broadcast_id, data, device, notification_id, user_id):
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
            platform=PlatformChoices.ANDROID.value,
            status=DeliveryStatusChoices.DELIVERED,
            sent_at=datetime.now(timezone.utc),
        )

    except FCMError as e:
        logging.error(
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
            platform=PlatformChoices.ANDROID.value,
            status=DeliveryStatusChoices.ATTEMPTED,
            error_reason=e,
        )

        raise


def handle_twilio(broadcast_id, data, notification_id, provider, user_id, phone):
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
            to=phone,
            from_=credentials_dict["from_phone"],
            body=body,
        )
    except TwilioRestException as error:
        logging.error(
            "Twilio failed to send text to user: %s for broadcast: %s with message: %s, code: %s",
            user_id,
            broadcast_id,
            error.msg,
            error.code,
        )
        persist_notification_delivery(
            notification_id,
            title,
            content,
            data.get("action_link"),
            channel=ChannelChoices.SMS,
            status=DeliveryStatusChoices.ATTEMPTED,
            error_reason=f"{error.msg} (code: {error.code})",
        )
        raise
    logging.info(
        "Sent twilio sms to user: %s for broadcast: %s with status: %s",
        user_id,
        broadcast_id,
        message.status,
    )
    if message.status in {"failed", "undelivered", "canceled"}:
        status = DeliveryStatusChoices.ATTEMPTED
        error_reason = f"{message.status}: {message.error_message}"
    else:
        status = DeliveryStatusChoices.DELIVERED
        error_reason = None
    # todo handle persisting overriden body
    persist_notification_delivery(
        notification_id,
        title,
        content,
        data.get("action_link"),
        channel=ChannelChoices.SMS,
        status=status,
        error_reason=error_reason,
        metadata={"twilio_message_sid": message.sid},
    )

    if status != DeliveryStatusChoices.DELIVERED:
        logging.error("Failed to deliver SMS to Twilio")
        raise NotificationException(
            "Failed to deliver SMS to Twilio", "twilio_sms_failed"
        )

    return


def handle_sendgrid(broadcast_id, data, notification_id, provider, user_id, email):
    credentials_dict = {
        credential.slug: credential.value for credential in provider.credentials.all()
    }

    sg = SendGridAPIClient(api_key=credentials_dict["api_key"])
    from_email = Email(credentials_dict["from_email"])
    to_email = To(email)
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
            user_id,
            broadcast_id,
            error.reason,
        )

        persist_notification_delivery(
            notification_id,
            None if template_id else title,
            None if template_id else content,
            data.get("action_link"),
            channel=ChannelChoices.EMAIL,
            status=DeliveryStatusChoices.ATTEMPTED,
            reason=error.reason,
        )
        raise

    logging.info(
        "Sendgrid email with status code: %s sent to user: %s with broadcast: %s",
        response.status_code,
        user_id,
        broadcast_id,
    )

    persist_notification_delivery(
        notification_id,
        None if template_id else title,
        None if template_id else content,
        data.get("action_link"),
        channel=ChannelChoices.EMAIL,
        status=DeliveryStatusChoices.DELIVERED,
        metadata={
            "sg_x_message_id": response.headers["X-Message-ID"],
            "sg_template_id": template_id,
        },
    )
    return


def persist_notification(org_id, broadcast_id, recipient_id, **kwargs):
    return Notification.objects.get_or_create(
        organization_id=org_id,
        broadcast_id=broadcast_id,
        recipient_id=recipient_id,
        defaults={**kwargs},
    )


def persist_notification_delivery(
    notification_id,
    title=None,
    content=None,
    action_link=None,
    channel=None,
    platform=None,
    **kwargs,
):
    filter_kwargs = {"notification_id": notification_id, "channel": channel}

    if platform:
        filter_kwargs["metadata__platform"] = platform

    notification_channel, created = NotificationDelivery.objects.update_or_create(
        **filter_kwargs,
        create_defaults={
            "title": title,
            "content": content,
            "action_link": action_link,
            "sent_at": datetime.now(timezone.utc),
            **kwargs,
        },
        defaults={
            "sent_at": datetime.now(timezone.utc),
            **kwargs,
        },
    )

    if created:
        logging.info(
            "Notification channel record with id: %s persisted for notification: %s",
            notification_channel.id,
            notification_id,
        )

    return notification_channel


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


def route_notification_with_preference(
    broadcast_id, org_id, notification_id, recipient, channels, data
):
    tasks = []

    redacted_data = data.copy()
    redacted_data.update({"recipients": "***"})
    redacted_data.update({"merge_tags": "***"})

    if ChannelChoices.IN_APP.value in data["channels"]:
        web_preference_entity = channels.get(slug=ChannelChoices.IN_APP.value)
        if web_preference_entity.enabled:
            tasks.append(
                send_in_app.s(
                    broadcast_id, org_id, recipient.id, notification_id, data=data
                ).set(kwargsrepr=repr({"data": redacted_data}))
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
                status=DeliveryStatusChoices.NOT_SENT,
                error_reason="User disabled",
            )

    if ChannelChoices.SMS.value in data["channels"]:
        sms_preference_entity = channels.get(slug=ChannelChoices.SMS.value)
        if sms_preference_entity.enabled and recipient.phone:
            tasks.append(
                send_sms.s(
                    broadcast_id,
                    org_id,
                    recipient.id,
                    notification_id,
                    data=data,
                    phone=recipient.phone,
                ).set(kwargsrepr=repr({"data": redacted_data, "phone": "***"}))
            )
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
                status=DeliveryStatusChoices.NOT_SENT,
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
                status=DeliveryStatusChoices.NOT_SENT,
                error_reason="User disabled",
            )

    if ChannelChoices.EMAIL.value in data["channels"]:
        email_preference_entity = channels.get(slug=ChannelChoices.EMAIL.value)
        if email_preference_entity.enabled:
            tasks.append(
                send_email.s(
                    broadcast_id,
                    org_id,
                    recipient.id,
                    notification_id,
                    data=data,
                    email=recipient.email,
                ).set(kwargsrepr=repr({"data": redacted_data, "email": "***"}))
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
                status=DeliveryStatusChoices.NOT_SENT,
                error_reason="User disabled",
            )

    if ChannelChoices.PUSH.value in data["channels"]:
        mobile_preference_entity = channels.get(slug=ChannelChoices.PUSH.value)
        if mobile_preference_entity.enabled:
            devices = ExternalUserDevice.objects.filter(user_id=recipient.id)
            for device in devices.all():
                tasks.append(
                    send_push.s(
                        device.id,
                        broadcast_id,
                        org_id,
                        recipient.id,
                        notification_id,
                        data,
                    ).set(kwargsrepr=repr({"data": redacted_data}))
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
                status=DeliveryStatusChoices.NOT_SENT,
                error_reason="User disabled",
            )

    chord(tasks)(
        send_recipient_callback.si(notification_id, NotificationStatusChoices.PROCESSED)
    )

    return


def route_basic_notification(broadcast_id, org_id, notification_id, recipient, data):
    tasks = []

    redacted_data = data.copy()
    redacted_data.update({"recipients": "***"})
    redacted_data.update({"merge_tags": "***"})

    if ChannelChoices.IN_APP.value in data["channels"]:
        tasks.append(
            send_in_app.s(
                broadcast_id, org_id, recipient.id, notification_id, data=data
            ).set(kwargsrepr=repr({"data": redacted_data}))
        )

    if ChannelChoices.SMS.value in data["channels"] and recipient.phone:
        tasks.append(
            send_sms.s(
                broadcast_id,
                org_id,
                recipient.id,
                notification_id,
                data=data,
                phone=recipient.phone,
            ).set(kwargsrepr=repr({"data": redacted_data, "phone": "***"}))
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
            status=DeliveryStatusChoices.NOT_SENT,
            error_reason="No phone provided for user",
        )
    if ChannelChoices.EMAIL.value in data["channels"]:
        tasks.append(
            send_email.s(
                broadcast_id,
                org_id,
                recipient.id,
                notification_id,
                data=data,
                email=recipient.email,
            ).set(kwargsrepr=repr({"data": redacted_data, "email": "***"}))
        )
    if ChannelChoices.PUSH.value in data["channels"]:
        devices = ExternalUserDevice.objects.filter(user_id=recipient.id).values("id")
        for device in devices.all():
            tasks.append(
                send_push.s(
                    device.id,
                    broadcast_id,
                    org_id,
                    recipient.id,
                    notification_id,
                    data,
                ).set(kwargsrepr=repr({"data": redacted_data}))
            )

    chord(tasks)(
        send_recipient_callback.si(notification_id, NotificationStatusChoices.PROCESSED)
    )

    return


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
