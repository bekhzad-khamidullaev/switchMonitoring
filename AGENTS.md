# Codex CLI Agents for Django Backend Development

This document describes autonomous agents used in Codex CLI to build and maintain **Django backend applications** with **senior-level code quality** and best practices.

---

## 1. Project Scaffold Agent

**Role:**  
Generate the initial Django project structure following best practices.

**Responsibilities:**
- Create Django project and apps with clean folder structure.
- Configure settings for multiple environments (development, staging, production).
- Set up virtual environment, requirements, and dependencies.
- Include base templates for REST API, admin, and authentication.
- Ensure code follows PEP8, semantic naming, and maintainability standards.

**Input:**  
- Project name
- List of apps
- Optional database choice (PostgreSQL, MySQL, SQLite)

**Output:**  
- Scaffolded Django project with modular apps
- Base settings and configuration files
- Environment-specific setup

---

## 2. Model Generator Agent

**Role:**  
Generate database models with best practices and scalability in mind.

**Responsibilities:**
- Create Django models with proper fields, constraints, and relations.
- Include indexes and unique constraints for performance.
- Generate migrations automatically.
- Ensure models are clean, maintainable, and documented.
- Include custom managers and querysets if needed.

**Input:**  
- Entity definitions (fields, types, relations)
- Business rules

**Output:**  
- Django model classes
- Initial migrations
- Clean, maintainable code

---

## 3. API Generator Agent

**Role:**  
Build RESTful APIs with Django REST Framework (DRF) or GraphQL.

**Responsibilities:**
- Create serializers, views, and routers/endpoints.
- Apply pagination, filtering, and search.
- Add permissions, authentication, and rate-limiting.
- Ensure endpoints follow best practices and are fully testable.
- Maintain clear, documented, and secure code.

**Input:**  
- Models to expose
- Endpoint types (GET, POST, PUT, DELETE)
- Access control rules

**Output:**  
- Fully functional API endpoints
- Serializer and view files
- Senior-level code quality

---

## 4. Business Logic Agent

**Role:**  
Implement core backend logic following clean architecture principles.

**Responsibilities:**
- Create service layers, utility modules, and helper functions.
- Encapsulate complex business rules.
- Ensure testability and modularity.
- Apply senior-level coding practices: DRY, SOLID, and maintainability.

**Input:**  
- Business requirements
- Models and data flow

**Output:**  
- Service modules
- Well-documented, maintainable code
- Unit tests

---

## 5. Authentication & Authorization Agent

**Role:**  
Implement secure authentication and access control.

**Responsibilities:**
- Configure Django auth or third-party solutions (JWT, OAuth2).
- Set up role-based access control.
- Enforce password policies and security best practices.
- Ensure all endpoints are protected and properly tested.

**Input:**  
- Roles and permissions
- Authentication strategy

**Output:**  
- Auth modules
- Middleware and decorators
- Secure, maintainable implementation

---

## 6. Testing Agent

**Role:**  
Ensure code quality through automated tests.

**Responsibilities:**
- Generate unit, integration, and API tests.
- Ensure coverage for models, views, serializers, and services.
- Apply mocking and fixtures for clean tests.
- Enforce test-driven development (TDD) practices when possible.

**Input:**  
- Django apps and modules
- Business logic specifications

**Output:**  
- Test files
- Test coverage reports
- Recommendations for improvements

---

## 7. Deployment & CI/CD Agent

**Role:**  
Prepare the backend for deployment and integrate CI/CD pipelines.

**Responsibilities:**
- Generate Dockerfiles, compose files, and environment configurations.
- Set up migrations and data seeding scripts.
- Configure CI/CD for automated testing, building, and deployment.
- Optimize for scalability and maintainability in production.

**Input:**  
- Deployment environment
- CI/CD preferences

**Output:**  
- Docker-ready Django project
- CI/CD pipelines and scripts
- Senior-level production-ready code

---

### Notes

- All agents ensure **senior-level code quality**: modular, maintainable, secure, and well-documented.
- Focus on **scalability, testability, and clean architecture**.
- Agents communicate via Codex CLI commands to minimize manual work.
- Emphasis on best practices: PEP8, DRY, SOLID, security, and performance.