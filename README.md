# Whistle

Whistle is a modern notification platform that enables multi-channel communication with users. It's built with Django and designed to handle real-time notifications across various channels.

## 🚀 Features

- **Multi-channel notifications**: Send notifications via email, push, SMS, and in-app channels
- **Real-time delivery**: WebSocket support for instant in-app notifications
- **Broadcast functionality**: Target specific user segments for mass notifications
- **Delivery tracking**: Monitor notification status (delivered, seen, read, clicked)
- **User preferences**: Allow users to manage their notification preferences
- **Organization support**: Multi-tenant architecture for managing different organizations
- **Scheduled notifications**: Queue notifications for delivery at specific times

## 🏗️ Architecture

Whistle consists of several microservices:

- **API Server**: RESTful API for managing notifications, users, and preferences
- **WebSocket Server**: Handles real-time notification delivery
- **Celery Workers**: Process asynchronous tasks for notification delivery
- **Scheduler**: Manages scheduled notifications and recurring tasks

## 🛠️ Tech Stack

- **Backend**: Django 5.0, Django REST Framework
- **Real-time**: Django Channels with WebSockets
- **Database**: PostgreSQL
- **Caching/Messaging**: Redis
- **Task Queue**: Celery with Redis broker
- **Monitoring**: Sentry, Flower (Celery monitoring)
- **Containerization**: Docker, Docker Compose

## 🔧 Main Components

- **notification**: Core notification models and delivery logic
- **user**: User management and authentication
- **external_user**: Management of end-users receiving notifications
- **organization**: Multi-tenant organization management
- **preference**: User notification preferences
- **subscription**: Subscription management
- **provider**: Integration with various notification providers
- **realtime**: WebSocket and real-time communication
- **audience**: User segmentation for targeted notifications

## 🚦 Getting Started

### Prerequisites

- Docker and Docker Compose
- PostgreSQL (optional for local development)
- Redis (optional for local development)

### Environment Setup

1. Clone the repository:
   ```
   git clone https://github.com/whistlehq/whistle.git
   cd whistle
   ```

2. Create environment file:
   ```
   cp whistle/whistle/.env.example whistle/whistle/.env
   ```

3. Edit the `.env` file with your configuration values

### Running with Docker Compose

Start all services:
```
docker-compose up
```

Or run specific services:
```
docker-compose up api websockets
```

### API Endpoints

The API documentation is available at `/api/schema/swagger-ui/` when the server is running.

## 🧪 Development

### Local Development Setup

1. Create a virtual environment:
   ```
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r whistle/requirements.txt
   ```

3. Set up database:
   ```
   cd whistle
   python manage.py migrate
   ```

4. Create a superuser:
   ```
   python manage.py createsuperuser
   ```

5. Run the development server:
   ```
   python manage.py runserver
   ```

## 📈 Monitoring

- **Celery Flower**: Monitor task queues at http://localhost:5555
- **Sentry**: Error tracking and performance monitoring (configured in settings)

## 🔐 Security

- JWT-based authentication
- AWS KMS for encryption of sensitive data
- HTTPS/TLS communication