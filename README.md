# 2025–2026 Secure Software Project — MEI, University of Coimbra

**Authors** - João R. Campos <jrcampos@dei.uc.pt>  

## Baseline System Overview

This repository contains a baseline implementation of a document management web application used in the **Secure Software** course project.

The system allows users to upload and manage documents and provides a small administrative interface for managing user accounts. The application is intentionally simple and is designed to serve as a starting point for the project.

Students will extend, analyze, and improve this system throughout the course.

---

## Technology Stack

The system is implemented using the following technologies:

- **Python / Flask** – web application
- **PostgreSQL** – relational database
- **HTML, CSS, JavaScript** – user interface
- **Docker / Docker Compose** – containerized deployment
- **GitHub Actions** – automation pipeline

---

## System Structure

The repository is organized into the following main components:

```text
web/        Web application source code
db/         Database container and initialization scripts
tests/      Automated tests
.github/    CI/CD workflows
```
The system is deployed using Docker containers orchestrated with Docker Compose.

---

## Running the Application

The system can be started locally using Docker Compose.

```bash
docker compose up --build
```
Once the containers start, the application will be available at:

http://localhost:8000

The application should start within a few seconds. The `/health` endpoint can be used to verify that the system is running correctly.

To reset the database and recreate the initial dataset:
```bash
docker compose down -v
docker compose up --build
```

---

## Example Accounts

The initial database contains a few example users. (NOTE: these accounts must be kept)

| Username | Password      |
|------|---------------|
| admin | L\|fP1D%327mB |
| alice | tth1mJj5?£58  |
| bob | De586:Iq6}?!  |


---
## Application Endpoints

The web application exposes several HTTP endpoints.

### Existing Endpoints

The following endpoints are already exist in the baseline system.

#### Authentication

| Method | Endpoint | Description |
|------|------|------|
| GET | `/login` | Display login page |
| POST | `/login` | Authenticate user |
| GET | `/logout` | Terminate the current session |

#### Documents

| Method | Endpoint | Description |
|------|------|------|
| GET | `/documents` | List documents belonging to the authenticated user |
| POST | `/documents/upload` | Upload a new document |
| GET | `/documents/<id>` | View document details |

#### System

| Method | Endpoint | Description |
|------|------|------|
| GET | `/` | Redirect to login or documents page |
| GET | `/health` | Application health check |

### Additional System Functionality

The following endpoints represent functionality that is part of the **intended system design** but is **not implemented in the baseline version** of the application.

Students are expected to implement these endpoints as part of the project.

| Method | Endpoint | Description |
|------|------|------|
| GET | `/documents/<id>/download` | Download a document |
| POST | `/documents/<id>/share` | Share a document with another user |
| GET | `/shared` | List documents shared with the current user |
| GET | `/shared/<id>/download` | Download a shared document |
| GET | `/admin/users` | List system users |
| POST | `/admin/users/<id>/enable` | Enable a user account |
| POST | `/admin/users/<id>/disable` | Disable a user account |

These endpoints must be implemented and are expected by an automated validation tool. Students may extend the system by implementing other additional features as required by the project.

---

## CI/CD Pipeline

The repository includes a basic GitHub Actions pipeline composed of three workflows:
- Integration – verifies that the system builds and runs correctly
- Delivery – prepares the application artifacts for deployment
- Deployment – deploys the system to a target environment

These workflows provide a starting point that can be improved as part of the project.

---

## Project Context

This repository represents the initial baseline of the system used in the course project.

Students are expected to:
- analyze the current implementation
- extend the system with additional functionality
- improve testing and automation
- apply secure software engineering practices

The detailed description of the assignment can be found in the course materials.