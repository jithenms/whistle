from datetime import datetime

from sendgrid import SendGridAPIClient, Email, To, Content, Mail
from twilio.rest import Client

from connector.models import Twilio, Sendgrid
from notification.serializers import NotificationSerializer
from organization.models import Organization
from user.models import User, UserPreference, UserSubscription
from whistle_server.celery import app


@app.task
def send_notification(external_id, org_id, payload):
    org_entity = Organization.objects.get(pk=org_id)
    user_entity = User.objects.get(organization=org_entity, external_id=external_id)
    if "topic" in payload:
        subscription_entity = UserSubscription.objects.prefetch_related(
            "categories"
        ).filter(user=user_entity, topic=payload["topic"])
        if not subscription_entity:
            route_basic_notification(external_id, org_id, payload)
        else:
            if "category" in payload:
                category_entity = subscription_entity.first().categories.filter(
                    slug=payload["category"]
                )
                if not category_entity:
                    route_basic_notification(external_id, org_id, payload)
                elif category_entity.first().enabled:
                    route_basic_notification(external_id, org_id, payload)
            else:
                route_basic_notification(external_id, org_id, payload)
    elif "category" in payload:
        preference_entity = UserPreference.objects.prefetch_related("channels").filter(
            user=user_entity, slug=payload["category"]
        )

        if not preference_entity:
            route_basic_notification(external_id, org_id, payload)
        else:
            web_preference_entity = preference_entity.first().channels.get(slug="web")

            if web_preference_entity.enabled:
                send_web.delay(external_id, org_id, payload)

            if "channels" in payload:
                if "sms" in payload["channels"]:
                    sms_preference_entity = preference_entity.channels.get(slug="sms")
                    if sms_preference_entity.enabled:
                        send_sms.delay(external_id, org_id, payload)

                if "email" in payload["channels"]:
                    email_preference_entity = preference_entity.channels.get(
                        slug="email"
                    )
                    if email_preference_entity.enabled:
                        send_email.delay(external_id, org_id, payload)
    else:
        route_basic_notification(external_id, org_id, payload)


def route_basic_notification(external_id, org_id, payload):
    send_web.delay(external_id, org_id, payload)
    if "channels" in payload:
        if "sms" in payload["channels"]:
            send_sms.delay(external_id, org_id, payload)

        if "email" in payload["channels"]:
            send_email.delay(external_id, org_id, payload)


@app.task
def send_sms(external_id, org_id, payload):
    try:
        org_entity = Organization.objects.get(pk=org_id)
        user_entity = User.objects.get(organization=org_entity, external_id=external_id)
        twilio_connection = Twilio.objects.get(organization=org_entity)

        twilio_client = Client(
            twilio_connection.account_sid, twilio_connection.auth_token
        )

        message = twilio_client.messages.create(
            to=user_entity.phone,
            from_=twilio_connection.from_phone,
            body=payload["channels"]["sms"]["body"],
        )

        print(f"twilio sms status: {message.status}")
    except (Twilio.DoesNotExist, Organization.DoesNotExist, User.DoesNotExist) as error:
        print(error)
        return


@app.task
def send_email(external_id, org_id, payload):
    try:
        org_entity = Organization.objects.get(pk=org_id)
        user_entity = User.objects.get(organization=org_entity, external_id=external_id)
        sendgrid_conn = Sendgrid.objects.get(organization=org_entity)
        sg = SendGridAPIClient(api_key=sendgrid_conn.api_key)

        from_email = Email(sendgrid_conn.from_email)
        to_email = To(user_entity.email)
        subject = payload["channels"]["email"]["subject"]
        content = Content("text/plain", payload["channels"]["email"]["content"])
        mail = Mail(from_email, to_email, subject, content)
        response = sg.client.mail.send.post(request_body=mail.get())
        print(
            f"sendgrid email status: {response.status_code}, {response.body}, {response.headers}"
        )
    except (
        Sendgrid.DoesNotExist,
        Organization.DoesNotExist,
        User.DoesNotExist,
    ) as error:
        print(error)
        return


@app.task
def send_web(external_id, org_id, payload):
    try:
        org_entity = Organization.objects.get(pk=org_id)
        user_entity = User.objects.get(organization=org_entity, external_id=external_id)
        # todo implement sockets
        data = persist_notification(
            user_entity, org_entity, payload, sent_at=datetime.now(), status="delivered"
        )
        print(f"web push record: {data}")
    except (Organization.DoesNotExist, User.DoesNotExist) as error:
        print(error)
        return


def persist_notification(recipient, org, payload, **kwargs):
    serializer_data = {
        key: value
        for key, value in payload.items()
        if key not in ["external_id", "channels"]
    }
    serializer = NotificationSerializer(data=serializer_data)
    serializer.is_valid(raise_exception=True)
    serializer.save(organization=org, recipient=recipient, **kwargs)
    return serializer.data
