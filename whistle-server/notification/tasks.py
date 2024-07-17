from datetime import datetime, timezone
import logging

from asgiref.sync import async_to_sync
from celery import chord
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import DatabaseError
from python_http_client import HTTPError
from sendgrid import SendGridAPIClient, Email, To, Content, Mail
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from audience.models import Audience
from connector.models import Twilio, Sendgrid
from external_user.models import ExternalUser
from notification.models import Notification, Broadcast
from preference.models import ExternalUserPreference
from subscription.models import ExternalUserSubscription
from whistle_server.celery import app
from whistle_server.exceptions import NotificationException

basic_fields = {
    "email",
    "phone",
    "first_name",
    "last_name",
    "external_id",
}


@app.task
def send_broadcast(broadcast_id, org_id, data):
    tasks = []
    recipient_ids = set()

    if "audience_id" in data:
        audience = Audience.objects.prefetch_related("filters").filter(
            organization_id=org_id, id=data["audience_id"]
        )
        filters = audience.first().filters.all()
        query_kwargs = build_users_query_kwargs(audience, broadcast_id, filters, org_id)
        recipients = ExternalUser.objects.filter(organization_id=org_id, **query_kwargs)
        for recipient in recipients.iterator():
            try:
                tasks.append(
                    handle_recipient.s(broadcast_id, org_id, recipient.id, data)
                )
                recipient_ids.add(recipient.id)
            except NotificationException:
                continue

    if "recipients" in data:
        if "filters" in data:
            recipients_to_remove = []
            for recipient in data["recipients"]:
                recipient_entity = update_or_create_external_user(
                    broadcast_id, org_id, recipient, data
                )
                for filter_input in data["filters"]:
                    filtered = apply_filter_to_recipient(
                        broadcast_id, org_id, filter_input, recipient_entity
                    )
                    if filtered:
                        recipients_to_remove.append(recipient)
            for recipient in recipients_to_remove:
                data["recipients"].remove(recipient)

        for recipient in data["recipients"]:
            try:
                recipient_entity = update_or_create_external_user(
                    broadcast_id, org_id, recipient, data
                )
                if recipient_entity.id not in recipient_ids:
                    tasks.append(
                        handle_recipient.s(
                            broadcast_id, org_id, recipient_entity.id, data
                        )
                    )
                    recipient_ids.add(recipient_entity.id)
            except NotificationException:
                continue

    if "topic" in data:
        subscribers = ExternalUserSubscription.objects.filter(
            organization_id=org_id, topic=data["topic"]
        )

        for subscriber in subscribers:
            if subscriber.id not in recipient_ids:
                tasks.append(
                    handle_topic_subscriber.s(broadcast_id, org_id, subscriber, data)
                )

    result = chord(tasks)(update_broadcast.s(broadcast_id, org_id, data))

    return result.id


def build_users_query_kwargs(audience, broadcast_id, filters, org_id):
    query_kwargs = {}
    for filter_rec in filters:
        match filter_rec.operator:
            case "=":
                if filter_rec.property in basic_fields:
                    query_kwargs[filter_rec.property] = filter_rec.value
                else:
                    query_kwargs[f"metadata__{filter_rec.property}"] = filter_rec.value
            case ">":
                query_kwargs[f"metadata__{filter_rec.property}__gt"] = filter_rec.value
            case "<":
                query_kwargs[f"metadata__{filter_rec.property}__lt"] = filter_rec.value
            case ">=":
                query_kwargs[f"metadata__{filter_rec.property}__gte"] = filter_rec.value
            case "<=":
                query_kwargs[f"metadata__{filter_rec.property}__lte"] = filter_rec.value
            case "contains":
                query_kwargs[f"metadata__{filter_rec.property}__contains"] = (
                    filter_rec.value
                )
            case _:
                logging.debug(
                    "Broadcast: %s with org: %s passed unsupported operator: %s for audience with id: %s",
                    broadcast_id,
                    org_id,
                    filter_rec.operator,
                    audience.id,
                )
    return query_kwargs


def apply_filter_to_recipient(broadcast_id, org_id, filter_input, recipient_entity):
    match filter_input["operator"]:
        case "=":
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
        case ">":
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
        case "<":
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
        case ">=":
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
        case "<=":
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
        case "contains":
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
    try:
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
    except NotificationException:
        return


@app.task
def handle_topic_subscriber(broadcast_id, org_id, subscriber_id, data):
    try:
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
    except NotificationException:
        return


@app.task(throws=(NotificationException,))
def send_sms(broadcast_id, org_id, user_id, data):
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

        logging.info("twilio sms status: %s", message.status)

        return message
    except TwilioRestException as error:
        logging.error(
            "Twilio failed to send text to user: %s for broadcast: %s with message: ",
            user_id,
            broadcast_id,
            error.msg,
        )
    except Twilio.DoesNotExist:
        logging.error(
            "Twilio account not connected for org: %s for broadcast: %s",
            org_id,
            broadcast_id,
        )
        raise NotificationException(
            "Twilio account not connected", "twilio_account_not_connected"
        )
    except ExternalUser.DoesNotExist:
        logging.error(
            "Recipient not found by id: %s for org: %s and broadcast: %s",
            user_id,
            org_id,
            broadcast_id,
        )
        raise NotificationException(
            "Recipient not found by id",
            "recipient_not_found",
        )


@app.task(throws=(NotificationException,))
def send_email(broadcast_id, org_id, user_id, data):
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
            "Sendgrid email sent to user: %s with broadcast: %s", user_id, broadcast_id
        )
        return response
    except HTTPError as error:
        logging.error(
            "Sendgrid failed to send email to user: %s for broadcast: %s with reason: ",
            user_id,
            broadcast_id,
            error.reason,
        )
    except Sendgrid.DoesNotExist:
        logging.error(
            "Sendgrid account not connected for org: %s for broadcast: %s",
            org_id,
            broadcast_id,
        )
        raise NotificationException(
            "Sendgrid account not connected", "sendgrid_account_not_connected"
        )
    except ExternalUser.DoesNotExist:
        logging.error(
            "Recipient not found by id: %s for org: %s and broadcast: %s",
            user_id,
            org_id,
            broadcast_id,
        )
        raise NotificationException(
            "Recipient not found by id",
            "recipient_not_found",
        )


@app.task(throws=(NotificationException,))
def send_web(notification_id, broadcast_id, org_id, user_id, data):
    try:
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
        return
    except ExternalUser.DoesNotExist:
        logging.error(
            "Recipient not found by id: %s for org: %s and broadcast: %s",
            user_id,
            org_id,
            broadcast_id,
        )
        raise NotificationException(
            "Recipient not found by id",
            "recipient_not_found",
        )


@app.task(throws=(DatabaseError,))
def persist_notification(broadcast_id, org_id, user_id, data, **kwargs):
    if "channels" in data:
        data.pop("channels")
    if "recipients" in data:
        data.pop("recipients")
    try:
        notification = Notification.objects.create(
            organization_id=org_id,
            recipient_id=user_id,
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
    except DatabaseError as error:
        logging.error(
            "Failed to save notification record to database for user: %s "
            "and org: %s for broadcast: %s with database error: %s",
            user_id,
            org_id,
            broadcast_id,
            error,
        )
        raise
    try:
        broadcast = Broadcast.objects.get(pk=broadcast_id)
        external_user = ExternalUser.objects.get(pk=user_id)
        broadcast.recipients.add(external_user)

        logging.info(
            "External user: %s added to broadcast: %s in org: %s",
            user_id,
            broadcast_id,
            org_id,
        )

        return notification.id
    except DatabaseError as error:
        logging.error(
            "Failed to add notification record to broadcast for user: %s "
            "and org: %s for broadcast: %s with database error: %s",
            user_id,
            org_id,
            broadcast_id,
            error,
        )
        raise


@app.task(throws=(DatabaseError,))
def update_broadcast(delivered_to, broadcast_id, org_id, data):
    if "channels" in data:
        data.pop("channels")
    if "recipients" in data:
        data.pop("recipients")
    try:
        broadcast = Broadcast.objects.get(pk=broadcast_id)
        broadcast.status = "processed"
        broadcast.save()
        return broadcast_id
    except DatabaseError as error:
        logging.error(
            "Failed to update broadcast notification to processed for broadcast: %s in org: %s with database error: %s",
            broadcast_id,
            org_id,
            error,
        )
        raise


def update_or_create_external_user(broadcast_id, org_id, recipient, data):
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
                    "Email included in channels but email not provided for new user for org: %s and broadcast: %s",
                    org_id,
                    broadcast_id,
                )
            if "sms" in data["channels"] and "phone" not in recipient:
                logging.error(
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
            logging.error(
                "Recipient not found by email for org: %s and broadcast: %s",
                org_id,
                broadcast_id,
            )
            raise NotificationException(
                "Recipient not found by email",
                "recipient_not_found",
            )
    else:
        logging.error(
            "Identifier for recipient not provided for org: %s and broadcast: %s",
            org_id,
            broadcast_id,
        )
        raise NotificationException(
            "Identifier for recipient not provided",
            "recipient_identifier_not_provided",
        )


def route_notification_with_preference(broadcast_id, org_id, recipient, channels, data):
    logging.info(
        "Routing notification with preference for user: %s in org: %s for broadcast: %s",
        recipient.id,
        org_id,
        broadcast_id,
    )
    web_preference_entity = channels.get(slug="web")
    if web_preference_entity.enabled:
        persist_notification.apply_async(
            (broadcast_id, org_id, recipient.id, data),
            sent_at=datetime.now(timezone.utc),
            link=send_web.s(broadcast_id, org_id, recipient.id, data),
        )
    else:
        logging.info(
            "Web push disabled for category %s for user: %s in org: %s for broadcast: %s",
            data.get("category", None),
            recipient.id,
            org_id,
            broadcast_id,
        )
    if "channels" in data:
        if "sms" in data["channels"] and recipient.phone is not None:
            sms_preference_entity = channels.get(slug="sms")
            if sms_preference_entity.enabled:
                send_sms.delay(broadcast_id, org_id, recipient.id, data)
            else:
                logging.info(
                    "SMS disabled for category %s for user: %s in org: %s for broadcast: %s",
                    data.get("category", None),
                    recipient.id,
                    org_id,
                    broadcast_id,
                )

        if "email" in data["channels"]:
            email_preference_entity = channels.get(slug="email")
            if email_preference_entity.enabled:
                send_email.delay(broadcast_id, org_id, recipient.id, data)
            else:
                logging.info(
                    "Email disabled for category %s for user: %s in org: %s for broadcast: %s",
                    data.get("category", None),
                    recipient.id,
                    org_id,
                    broadcast_id,
                )


def route_basic_notification(broadcast_id, org_id, recipient, data):
    logging.info(
        "Routing basic notification for user: %s in org: %s for broadcast: %s",
        recipient.id,
        org_id,
        broadcast_id,
    )
    persist_notification.apply_async(
        (broadcast_id, org_id, recipient.id, data),
        sent_at=datetime.now(timezone.utc),
        link=send_web.s(broadcast_id, org_id, recipient.id, data),
    )
    if "channels" in data:
        if "sms" in data["channels"] and recipient.phone is not None:
            send_sms.delay(broadcast_id, org_id, recipient.id, data)
        elif recipient.phone is None:
            logging.warning(
                "Trying to route SMS notification without phone on record for user: %s in org: %s for broadcast: %s",
                recipient.id,
                org_id,
                broadcast_id,
            )
        if "email" in data["channels"]:
            send_email.delay(broadcast_id, org_id, recipient.id, data)
