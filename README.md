# Beers Marketplace API

## Project Overview

The Beers Marketplace API is a RESTful API built using Django and PostgreSQL to serve a beers marketplace. The API supports a mobile application built with React Native, which allows users to browse, purchase, and gift beers from various pubs. The app also includes social networking features, such as finding and following friends, and uploading and viewing stories. Additionally, the app supports geopositioning to filter beer offers by distance and integrates with multiple payment gateways for funding user accounts.

## Features

- **Geopositioning**: Filter beer offers from subscribed pubs sorted by distance (nearest to furthest).
- **Purchasing Options**: Buy beers for consumption in pubs or as gifts for friends.
- **QR Code Redemption**: Claim purchased beers in pubs by scanning a QR code.
- **Social Networking**: Find and follow friends, upload and view stories.
- **Payment Integration**: Fund accounts using credit/debit cards (Stripe), PayPal, and local bank transfers.

## Project Structure

The project is organized into several directories, each responsible for different functionalities:

- **administration**: Manages administrative tasks related to the project.
- **beers**: Core functionality related to beers, including settings and configurations.
- **common**: Shared resources and utilities used across the project.
- **locations**: Manages location-related functionalities.
- **notifications**: Handles notification-related functionalities.
- **payments**: Manages payment-related functionalities.
- **stores**: Manages store-related functionalities.
- **stories**: Manages story-related functionalities.
- **templates**: Contains HTML templates for various functionalities.
- **tests**: Contains test files for different functionalities and modules.

## Dependencies

The project relies on several key dependencies:

- **Django**: A high-level Python Web framework for rapid development.
- **Django REST Framework**: A toolkit for building Web APIs.
- **Celery**: An asynchronous task queue/job queue based on distributed message passing.
- **Boto3**: AWS SDK for Python to interact with Amazon's cloud services.
- **Gunicorn**: A Python WSGI HTTP Server for UNIX.
- **Stripe**: Payment gateway for credit/debit card transactions.
- **PayPal**: Payment gateway for PayPal transactions.
- **PostgreSQL**: Relational database for storing application data.

## Models

### Users

- **User**: Custom user model with fields for user information and authentication.

### Beers

- **Beer**: Represents a beer with fields for name, description, price, and pub association.
- **Pub**: Represents a pub with fields for name, location, and available beers.

### Payments

- **Payment**: Represents a payment transaction with fields for amount, user, and payment method.
- **DocType**: Enumeration for document types (RIF, CI).

### Stores

- **Store**: Represents a store with fields for name, location, and available products.
- **DocType**: Enumeration for document types (RIF, CI).

### Stories

- **Story**: Represents a user story with fields for content, user, and timestamp.

## Configuration Settings

The project includes multiple settings files for different environments:

- **settings.py**: Base settings for the project.
- **settings_production.py**: Production-specific settings.
- **settings_testing.py**: Testing-specific settings.

### Key Configuration Settings

- **SECRET_KEY**: Secret key for signing cookies and other security-sensitive operations.
- **DATABASES**: Configuration for the PostgreSQL database.
- **INSTALLED_APPS**: List of installed Django apps.
- **ALLOWED_HOSTS**: List of host/domain names that the Django site can serve.
- **CACHES**: Configuration for the project's cache system.
- **EMAIL_BACKEND**: Configuration for email management.
- **CELERY_BROKER_URL**: URL for the Celery broker.
- **STATICFILES_DIRS**: Directories for static files.

## Getting Started

### Prerequisites

- Python 3.x
- PostgreSQL
- Git

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up the PostgreSQL database and update the `DATABASES` setting in `settings.py`.

5. Apply database migrations:
   ```bash
   python manage.py migrate
   ```

6. Run the development server:
   ```bash
   python manage.py runserver
   ```

### Running Tests

To run the tests, use the following command:
```bash
python manage.py test
```

## Deployment

For deployment, ensure that the production settings are configured correctly in `settings_production.py`. Use a WSGI server like Gunicorn to serve the application in a production environment.

This README file provides a comprehensive overview of the Beers Marketplace API project, including its features, structure, dependencies, models, configuration settings, and instructions for getting started, running tests, and contributing.