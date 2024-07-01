import uuid
from datetime import datetime

from sendgrid import SendGridAPIClient, Email, To, Content, Mail
from twilio.rest import Client

from authn.models import Organization
from connector.models import Twilio, Sendgrid
from notification.serializers import NotificationSerializer
from user.models import User, UserPreference, UserSubscription
from whistle_server.celery import app


@app.task
def send_notification(payload, org):
    org_ent = Organization.objects.get(pk=uuid.UUID(org['id']))
    user_ent = User.objects.get(organization=org_ent, external_id=payload['external_id'])
    if 'topic' in payload:
        sub_ent = UserSubscription.objects.prefetch_related('categories').filter(user=user_ent, topic=payload['topic'])
        if not sub_ent:
            route_basic_notification(org, payload)
        else:
            if 'category' in payload:
                sub_cat = sub_ent.first().categories.filter(slug=payload['category'])
                if not sub_cat:
                    route_basic_notification(org, payload)
                elif sub_cat.first().enabled:
                    route_basic_notification(org, payload)
            else:
                route_basic_notification(org, payload)
    elif 'category' in payload:
        pref_ent = UserPreference.objects.prefetch_related('channels').filter(user=user_ent, slug=payload['category'])

        if not pref_ent:
            route_basic_notification(org, payload)
        else:
            web_pref = pref_ent.first().channels.get(slug='web')

            if web_pref.enabled:
                send_web.delay(payload, org)

            if 'channels' in payload:
                if 'sms' in payload['channels']:
                    sms_pref = pref_ent.channels.get(slug='sms')
                    if sms_pref.enabled:
                        send_sms.delay(payload, org)

                if 'email' in payload['channels']:
                    email_pref = pref_ent.channels.get(slug='email')
                    if email_pref.enabled:
                        send_email.delay(payload, org)
    else:
        route_basic_notification(org, payload)


def route_basic_notification(org, payload):
    send_web.delay(payload, org)
    if 'channels' in payload:
        if 'sms' in payload['channels']:
            send_sms.delay(payload, org)

        if 'email' in payload['channels']:
            send_email.delay(payload, org)


@app.task
def send_sms(payload, org):
    try:
        org_ent = Organization.objects.get(pk=uuid.UUID(org['id']))
        user_ent = User.objects.get(organization=org_ent, external_id=payload['external_id'])
        twilio_conn = Twilio.objects.get(organization=org_ent)

        twilio_client = Client(twilio_conn.account_sid, twilio_conn.auth_token)

        message = twilio_client.messages.create(
            to=user_ent.phone,
            from_=twilio_conn.from_phone,
            body=payload['channels']['sms']['body'])

        print(f'twilio sms status: {message.status}')
    except (Twilio.DoesNotExist, Organization.DoesNotExist, User.DoesNotExist) as error:
        print(error)
        return


@app.task
def send_email(payload, org):
    try:
        org_ent = Organization.objects.get(pk=uuid.UUID(org['id']))
        user_ent = User.objects.get(organization=org_ent, external_id=payload['external_id'])
        sendgrid_conn = Sendgrid.objects.get(organization=org_ent)
        sg = SendGridAPIClient(api_key=sendgrid_conn.api_key)

        from_email = Email(sendgrid_conn.from_email)
        to_email = To(user_ent.email)
        subject = payload['channels']['email']['subject']
        content = Content("text/plain", payload['channels']['email']['content'])
        mail = Mail(from_email, to_email, subject, content)
        response = sg.client.mail.send.post(request_body=mail.get())
        print(f'sendgrid email status: {response.status_code}, {response.body}, {response.headers}')
    except (Sendgrid.DoesNotExist, Organization.DoesNotExist, User.DoesNotExist) as error:
        print(error)
        return


@app.task
def send_web(payload, org):
    try:
        org_ent = Organization.objects.get(pk=uuid.UUID(org['id']))
        user_ent = User.objects.get(organization=org_ent, external_id=payload['external_id'])
        # todo implement sockets
        data = persist_notification(payload=payload, organization=org_ent, recipient=user_ent, sent_at=datetime.now(),
                                    status='delivered')
        print(f'web push record: {data}')
    except (Organization.DoesNotExist, User.DoesNotExist) as error:
        print(error)
        return


def persist_notification(payload, org, recipient, **kwargs):
    serializer_data = {key: value for key, value in payload.items() if key not in ['external_id', 'channels']}
    serializer = NotificationSerializer(data=serializer_data)
    serializer.is_valid(raise_exception=True)
    serializer.save(organization=org, recipient=recipient, **kwargs)
    return serializer.data
