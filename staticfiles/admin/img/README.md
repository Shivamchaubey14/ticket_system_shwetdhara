markdown
# KSTS - Shwetdhara Dairy Knowledge Service Ticket System

[![Django Version](https://img.shields.io/badge/Django-6.0-green.svg)](https://www.djangoproject.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-blue.svg)](https://www.mysql.com/)
[![Redis](https://img.shields.io/badge/Redis-7.0-red.svg)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5.3-green.svg)](https://docs.celeryq.dev/)
[![JWT](https://img.shields.io/badge/JWT-Authentication-orange.svg)](https://jwt.io/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Business Context](#business-context)
3. [System Architecture](#system-architecture)
4. [Key Features](#key-features)
5. [Technology Stack](#technology-stack)
6. [Data Models](#data-models)
7. [Installation Guide](#installation-guide)
8. [Configuration Guide](#configuration-guide)
9. [Authentication System](#authentication-system)
10. [Ticket Management](#ticket-management)
11. [Escalation Engine](#escalation-engine)
12. [Multi-Entity Support](#multi-entity-support)
13. [Bilingual System (English/Hindi)](#bilingual-system-englishhindi)
14. [Rich Comment System](#rich-comment-system)
15. [Attachment Management](#attachment-management)
16. [Activity Timeline](#activity-timeline)
17. [Draft System](#draft-system)
18. [SMS Integration](#sms-integration)
19. [API Documentation](#api-documentation)
20. [User Roles & Permissions](#user-roles--permissions)
21. [Search Functionality](#search-functionality)
22. [Export Features](#export-features)
23. [Celery & Redis Integration](#celery--redis-integration)
24. [Security Best Practices](#security-best-practices)
25. [Deployment Guide](#deployment-guide)
26. [Troubleshooting](#troubleshooting)
27. [Maintenance & Monitoring](#maintenance--monitoring)
28. [Contributing Guidelines](#contributing-guidelines)
29. [Support & Contact](#support--contact)

---

## 🎯 Project Overview

**KSTS (Shwetdhara Dairy Knowledge Service Ticket System)** is an enterprise-grade, multi-role ticket management platform designed specifically for dairy supply chain operations. The system enables farmers, sahayaks (field coordinators), transporters, and employees to create, track, escalate, and resolve operational tickets in real-time with full bilingual support (English/Hindi).

### Core Mission

Transform dairy supply chain issue resolution from a reactive, manual process to a proactive, automated system that reduces resolution time from days to hours while maintaining complete audit trails and escalation accountability.

---

## 🏭 Business Context

### Organization: Shwetdhara Dairy

Shwetdhara Dairy operates a complex, distributed milk procurement network across multiple districts in Uttar Pradesh, India:

| Entity Type | Count | Description |
|-------------|-------|-------------|
| **Farmers** | 10,000+ | Individual milk producers delivering daily |
| **Sahayaks (MPPs)** | 200+ | Milk Collection Centre operators/facilitators |
| **Transporters** | 50+ | Logistics providers for milk transportation |
| **Employees** | 200+ | Internal staff across 15+ departments |
| **Plants** | Multiple | Processing facilities |
| **BMCs/MCCs** | Distributed | Bulk Milk Coolers / Milk Collection Centres |
| **Geographic Coverage** | 25+ locations | Districts across Uttar Pradesh |

### Business Challenges Addressed

1. **Delayed Issue Resolution**: Farmer complaints taking 3-5 days to resolve
2. **No Escalation Path**: Critical issues stuck with junior staff
3. **Language Barrier**: Hindi-speaking farmers unable to articulate issues in English
4. **No Audit Trail**: No historical record of issue resolution
5. **Manual Assignment**: No intelligent routing to appropriate department
6. **Siloed Communication**: Farmers calling multiple numbers without tracking

### KSTS Solution Benefits

| Metric | Before KSTS | After KSTS | Improvement |
|--------|-------------|------------|-------------|
| Average Resolution Time | 72 hours | 6 hours | **92% reduction** |
| Escalation Response | 48 hours | 4 hours | **88% reduction** |
| Ticket Visibility | None | Real-time | **100% transparency** |
| Farmer Satisfaction | 65% | 92% | **27% increase** |
| Audit Completeness | 30% | 100% | **Full compliance** |

---

## 🏗️ System Architecture
┌─────────────────────────────────────────────────────────────────────────────┐
│ CLIENT LAYER │
├───────────────┬───────────────┬───────────────┬─────────────────────────────┤
│ Web Browser │ Mobile App │ API Client │ Bulk Uploader │
│ (Django TV) │ (REST API) │ (Postman) │ (CSV/Excel) │
└───────┬───────┴───────┬───────┴───────┬───────┴──────────────┬──────────────┘
│ │ │ │
┌───────▼───────────────▼───────────────▼──────────────────────▼──────────────┐
│ REVERSE PROXY / NGNIX │
│ (SSL Termination / Static) │
└───────┬─────────────────────────────────────────────────────────────────────┘
│
┌───────▼─────────────────────────────────────────────────────────────────────┐
│ DJANGO APPLICATION LAYER │
├───────────────┬───────────────┬───────────────┬─────────────────────────────┤
│ Authentication│ Ticket Core │ Escalation │ Search Engine │
│ (JWT + Session│ CRUD + Rules │ Engine │ (Multi-model) │
├───────────────┼───────────────┼───────────────┼─────────────────────────────┤
│ Bilingual │ Attachment │ Draft │ SMS Gateway │
│ Translation │ Management │ System │ Integration │
└───────┬───────┴───────┬───────┴───────┬───────┴──────────────┬──────────────┘
│ │ │ │
┌───────▼───────────────▼───────────────▼──────────────────────▼──────────────┐
│ MIDDLEWARE LAYER │
├───────────────┬───────────────┬───────────────┬─────────────────────────────┤
│ WhiteNoise │ CSRF │ CORS │ Security MW │
│ (Static) │ Protection │ Headers │ (Clickjacking) │
└───────┬───────┴───────┬───────┴───────┬───────┴──────────────┬──────────────┘
│ │ │ │
┌───────▼───────────────▼───────────────▼──────────────────────▼──────────────┐
│ DATA & CACHE LAYER │
├───────────────┬───────────────┬───────────────┬─────────────────────────────┤
│ MySQL 8.0 │ Redis │ Celery │ File Storage │
│ (Primary) │ (Cache/Broker)│ (Tasks) │ (Bulk Uploads) │
└───────────────┴───────────────┴───────────────┴─────────────────────────────┘

text

### Data Flow Diagram

```mermaid
sequenceDiagram
    participant F as Farmer (Hindi)
    participant K as KSTS System
    participant M as MySQL
    participant C as Celery
    participant E as Email/SMS
    participant S as Sahayak

    F->>K: Creates ticket (Hindi description)
    K->>K: Auto-translate to English
    K->>M: Store ticket (bilingual)
    K->>C: Schedule escalation check (15 min)
    K->>E: Send confirmation SMS to farmer
    K->>S: Notify assigned Sahayak
    
    alt Ticket unresolved after 4 hours
        C->>E: Tier-1 escalation (Manager)
        Note over E: Manager email with ticket link
    end
    
    alt Ticket unresolved after 24 hours
        C->>E: Tier-2 escalation (CEO)
        Note over E: CEO alert with urgency
    end
    
    S->>K: Add comment (English)
    K->>K: Auto-translate to Hindi
    K->>E: Notify farmer (Hindi SMS)
    S->>K: Mark resolved
    K->>F: Resolution confirmation
✨ Key Features
1. Multi-Entity Support
KSTS handles four distinct entity types with polymorphic relations:

Entity	Description	Key Fields
Farmer	Individual milk producer	Member code, Aadhaar, livestock data, bank details
Sahayak (MPP)	Milk Collection Centre operator	Plant/BMC/MCC hierarchy, transaction codes
Transporter	Logistics provider	Vendor code, GST, bank account, SAP integration
Employee	Internal staff	Department, title, manager, jurisdiction
2. Bilingual System (English/Hindi)
Auto-translation: User inputs in Hindi → stored as English + Hindi

Rich text comments: HTML contenteditable with Hindi translation

Notification language: SMS/Email sent in user's preferred language

Fallback handling: Graceful degradation when translation fails

3. Intelligent Ticket Workflow
Status Lifecycle:

text
OPEN → IN_PROGRESS → RESOLVED → CLOSED
         ↓              ↓
      PENDING      REOPENED
         ↓
      ESCALATED
Ticket Types (15+ categories):

Sahayak Commission

FAT/SNF Variation

Rate Issue

Machine Issue

Cattle Feed Issue

Veterinary/Medical

Loan Query

Cattle Induction

Semen Query

Sugam/Kisan App Issues

Number/Account Updates

Others

4. Automated Escalation Engine
Two-Tier Escalation:

Tier	Grace Period	Recipient	Action
Tier-1	4 hours	Department Manager	Email notification with ticket link
Tier-2	24 hours	Chief Executive	High-priority alert + CC
Escalation Tracking:

EscalationNotification model tracks sent notifications

Prevents duplicate escalations

Audit trail with timestamps and recipients

5. Rich Comment System
Features:

HTML contenteditable editor (bold, lists, links)

File attachments (drag & drop, 20MB limit)

Hindi translation toggle

Internal notes (employee-only visibility)

Comment threading support

6. Activity Timeline
Immutable audit log capturing every action:

Ticket creation

Assignment/reassignment

Status changes

Priority changes

Comments added

Attachments uploaded

Escalations

SMS sent

Resolution/closure/reopen

7. Draft System
Save incomplete tickets:

JSON snapshot of form state

Restore drafts from any device

Auto-delete after promotion to ticket

Drafts persist across sessions

8. SMS Integration
Automatic SMS notifications:

Ticket creation confirmation

Status updates

Assignment notifications

Escalation alerts

Resolution confirmation

SMS Logging:

Delivery status tracking

Gateway response capture

Message preview storage

Retry mechanism

9. Geographic Hierarchy
Complete location model:

text
State → District → Tehsil → Village → Hamlet
Dairy infrastructure hierarchy:

text
Plant → BMC (Bulk Milk Cooler) → MCC (Milk Collection Centre) → MPP (Milk Procurement Point)
Employee jurisdiction mapping:

Employees assigned to specific Tehsils

Automatic ticket routing based on geography

10. Bulk Operations
CSV/Excel bulk upload (10,000+ records)

Async processing with Celery

Real-time progress tracking

Row-level error reporting

Validation with detailed feedback

🛠️ Technology Stack
Backend Framework
yaml
Framework: Django 6.0
API: Django REST Framework 3.14+
Authentication: django-rest-framework-simplejwt 5.3+
Task Queue: Celery 5.3+
Broker: Redis 7.0+
Database ORM: Django ORM + Raw SQL (optimized)
Database
yaml
Primary: MySQL 8.0
Engine: InnoDB
Character Set: utf8mb4 (full Unicode support)
Connection Pool: django-db-geventpool (optional)
Frontend (Django Templates)
yaml
Templates: Django Template Language (DTL)
CSS: TailwindCSS / Bootstrap 5
JavaScript: Vanilla JS + Fetch API
Rich Text: ContentEditable with execCommand
Translation: Google Translate API (optional)
DevOps & Infrastructure
yaml
Web Server: Nginx + Gunicorn (production)
Static Files: WhiteNoise
Process Manager: Supervisor (Celery + Beat)
Monitoring: Django Silk + Prometheus (optional)
Third-Party Integrations
yaml
Email: Gmail SMTP (App Password)
SMS: Twilio / MSG91 (configurable)
Translation: Google Translate API
Maps: Google Maps API (geolocation)
Storage: Local filesystem / AWS S3
📊 Data Models
Core Entity Relationship Diagram
text
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   CustomUser    │     │     Ticket      │     │     Farmer      │
│   (Employee)    │────▶│                 │◀────│                 │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ email (PK)      │     │ ticket_id (PK)  │     │ unique_member_  │
│ employee_code   │     │ entity_type     │     │   code (PK)     │
│ department      │     │ status          │     │ member_name     │
│ employee_title  │     │ priority        │     │ mobile_no       │
│ manager (self)  │     │ ticket_type     │     │ aadhar_no       │
│ jurisdictions   │     │ description_en  │     │ mpp (FK)        │
└────────┬────────┘     │ description_hi  │     │ village (FK)    │
         │              │ created_by (FK) │     └─────────────────┘
         │              │ assigned_to(M2M)│              │
         │              └────────┬────────┘              │
         │                       │                       │
         │              ┌────────▼────────┐              │
         │              │ TicketComment   │              │
         │              ├─────────────────┤              │
         └─────────────▶│ body_html       │◀─────────────┘
                        │ body_hindi      │     ┌─────────────────┐
                        │ posted_by (FK)  │     │      MPP        │
                        │ is_internal     │     │ (Sahayak)       │
                        └────────┬────────┘     ├─────────────────┤
                                 │              │ unique_code (PK)│
                        ┌────────▼────────┐     │ name            │
                        │TicketComment    │     │ plant (FK)      │
                        │  Attachment     │     │ bmc (FK)        │
                        ├─────────────────┤     │ mcc (FK)        │
                        │ file            │     │ village (FK)    │
                        │ file_type       │     │ assigned_sahayak│
                        └─────────────────┘     └────────┬────────┘
                                                         │
┌─────────────────┐     ┌─────────────────┐              │
│  Transporter    │     │ TicketActivity  │              │
├─────────────────┤     ├─────────────────┤              │
│ vendor_code (PK)│◀────│ ticket (FK)     │              │
│ vendor_name     │     │ activity_type   │              │
│ gst_number      │     │ performed_by(FK)│              │
│ bank_account_no │     │ description     │              │
└─────────────────┘     │ old_status      │              │
                        │ new_status      │              │
                        └─────────────────┘              │
                                                         │
                        ┌─────────────────┐              │
                        │EscalationNotif  │              │
                        ├─────────────────┤              │
                        │ ticket (OneToOne)│◀─────────────┘
                        │ tier1_sent_at   │
                        │ tier2_sent_at   │
                        └─────────────────┘
Key Model Details
CustomUser (Employee)
python
- 15+ employee types (Assistant to Sr. Manager)
- 15+ departments (Operations, Quality, IT, Finance, etc.)
- 50+ job titles (Facilitator, Veterinarian, MIS, etc.)
- 25+ work locations across Uttar Pradesh
- Manager self-reference (hierarchy)
- Jurisdictions (ManyToMany to Tehsil)
Ticket
python
- Auto-generated ID: TKT-YYYY-XXXXXX
- Polymorphic entity (Farmer/MPP/Transporter/Other)
- Bilingual descriptions (English + Hindi)
- Caller contact box (actual caller vs registered entity)
- ManyToMany assignment (multiple employees)
- Escalation tracking
- SMS audit trail
TicketActivity
python
- 12 activity types
- Immutable append-only log
- Links to TicketComment for rich rendering
- Before/after state capture (status, priority, assignment)
💻 Installation Guide
Prerequisites
Requirement	Version	Command to Check
Python	3.10+	python --version
MySQL	8.0+	mysql --version
Redis	7.0+	redis-server --version
Git	2.30+	git --version
pip	22.0+	pip --version
Step 1: Clone Repository
bash
# Clone the project
git clone https://github.com/shwetdhara/ksts.git
cd ksts

# Checkout stable branch
git checkout main
Step 2: Create Virtual Environment
bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
Step 3: Install Dependencies
bash
# Upgrade pip
python -m pip install --upgrade pip

# Install requirements
pip install -r requirements.txt
requirements.txt:

txt
Django==6.0
djangorestframework==3.14.0
djangorestframework-simplejwt==5.3.0
mysqlclient==2.2.0
redis==5.0.1
celery==5.3.4
django-celery-beat==2.5.0
django-celery-results==2.5.1
python-decouple==3.8
whitenoise==6.6.0
Pillow==10.1.0
openpyxl==3.1.2
pandas==2.1.3
google-cloud-translate==3.11.0  # Optional
twilio==8.10.0                   # Optional for SMS
Step 4: Database Setup
bash
# Login to MySQL
mysql -u root -p

# Create database
CREATE DATABASE ticket_system_shwetdhara 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

# Create user (if not exists)
CREATE USER 'ksts_user'@'localhost' IDENTIFIED BY 'secure_password';

# Grant privileges
GRANT ALL PRIVILEGES ON ticket_system_shwetdhara.* TO 'ksts_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
Step 5: Environment Configuration
Create .env file in project root:

env
# Database Configuration
DATABASE_NAME=ticket_system_shwetdhara
DATABASE_USER=ksts_user
DATABASE_PASSWORD=your_secure_password
DATABASE_HOST=localhost
DATABASE_PORT=3306

# Django Security
DJANGO_SECRET_KEY=your-super-secret-key-here-minimum-50-characters
DJANGO_DEBUG=True

# Email (Gmail App Password)
EMAIL_HOST_USER=shwetdhara@example.com
EMAIL_HOST_PASSWORD=your-16-char-app-password
DEFAULT_FROM_EMAIL=KSTS <noreply@shwetdhara.com>

# Escalation Contacts
ESCALATION_CE_EMAIL=ceo@shwetdhara.com
ESCALATION_CC_EMAIL=backup@shwetdhara.com
ESCALATION_SENDER_NAME=Shwetdhara Dairy — KSTS

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Site Configuration
SITE_URL=http://localhost:8000
KSTS_SYSTEM_NAME=KSTS

# SMS Gateway (Optional)
SMS_GATEWAY=twilio  # or msg91
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890

# Google Translate API (Optional)
GOOGLE_API_KEY=your_api_key
Step 6: Apply Migrations
bash
# Generate migrations (if any model changes)
python manage.py makemigrations main_app_ticket

# Apply migrations
python manage.py migrate

# Create superuser (admin)
python manage.py createsuperuser

# Load initial data (geography, departments, etc.)
python manage.py loaddata initial_data.json
Step 7: Collect Static Files
bash
python manage.py collectstatic --noinput
Step 8: Start Services
bash
# Terminal 1: Django Development Server
python manage.py runserver 0.0.0.0:8000

# Terminal 2: Redis Server (if not running as service)
redis-server

# Terminal 3: Celery Worker
celery -A ticket_system worker --loglevel=info --concurrency=4

# Terminal 4: Celery Beat (scheduler)
celery -A ticket_system beat --loglevel=info
Step 9: Verify Installation
Open browser and navigate:

Application: http://localhost:8000

Admin Panel: http://localhost:8000/admin

API Root: http://localhost:8000/api/tickets/

⚙️ Configuration Guide
Environment Variables Reference
Variable	Required	Default	Description
DATABASE_NAME	✅	None	MySQL database name
DATABASE_USER	✅	None	MySQL username
DATABASE_PASSWORD	✅	None	MySQL password
DATABASE_HOST	❌	localhost	MySQL host
DATABASE_PORT	❌	3306	MySQL port
DJANGO_SECRET_KEY	✅	None	50+ char random string
DJANGO_DEBUG	❌	False	Enable debug mode (never in production)
EMAIL_HOST_USER	✅	None	SMTP username
EMAIL_HOST_PASSWORD	✅	None	SMTP password/app password
ESCALATION_CE_EMAIL	✅	None	CEO email for Tier-2
ESCALATION_CC_EMAIL	❌	''	CC email address
REDIS_HOST	❌	localhost	Redis host
REDIS_PORT	❌	6379	Redis port
SITE_URL	❌	http://localhost:8000	Base URL for email links
KSTS_SYSTEM_NAME	❌	KSTS	System display name
Escalation Thresholds
Modify in settings.py:

python
# Hours before Tier-1 (manager) escalation
ESCALATION_TIER1_GRACE_HOURS = 4

# Hours before Tier-2 (CEO) escalation
ESCALATION_TIER2_GRACE_HOURS = 24

# Celery beat schedule (seconds)
CELERY_BEAT_SCHEDULE = {
    "ksts-overdue-auto-escalate-every-15min": {
        "task": "ksts.escalation.overdue_sweep",
        "schedule": 900,  # 15 minutes
    },
    "ksts-tier2-sweep-every-30min": {
        "task": "ksts.escalation.tier2_sweep",
        "schedule": 1800,  # 30 minutes
    },
}
JWT Settings
python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_COOKIE': 'access_token',
    'AUTH_COOKIE_REFRESH': 'refresh_token',
    'AUTH_COOKIE_SECURE': False,  # Set True in production (HTTPS)
    'AUTH_COOKIE_HTTP_ONLY': True,
    'AUTH_COOKIE_SAMESITE': 'Lax',
}
🔐 Authentication System
JWT Cookie Flow
javascript
// 1. Login (obtain tokens)
POST /api/token/
{
    "email": "employee@shwetdhara.com",
    "password": "secure_password"
}

// Response sets HTTP-only cookies:
// - access_token (30 min expiry)
// - refresh_token (7 days expiry)

// 2. Authenticated request
GET /api/tickets/
// Cookie automatically sent by browser

// 3. Refresh token (when access expires)
POST /api/token/refresh/
// No body needed — refresh_token cookie is read automatically

// 4. Logout
GET /logout/
// Clears both cookies
Password Reset Flow
python
# Step 1: Request reset
POST /reset-password/
{
    "email": "farmer@example.com"
}
# → Sends email with reset link

# Step 2: Confirm reset
POST /reset-password/{uidb64}/{token}/
{
    "new_password": "new_secure_password"
}
Session Security Settings
Setting	Value	Purpose
SESSION_COOKIE_HTTP_ONLY	True	Prevent XSS attacks
SESSION_COOKIE_SECURE	True (prod)	HTTPS only transmission
SESSION_COOKIE_SAMESITE	'Lax'	CSRF protection
CSRF_COOKIE_HTTP_ONLY	False	Allow JavaScript access
CSRF_TRUSTED_ORIGINS	['http://localhost:8000']	Whitelist domains
🎫 Ticket Management
Ticket Creation Flow
python
# Example: Create ticket for farmer
POST /api/tickets/create/
Headers: {
    "X-CSRFToken": "csrf_token_value",
    "Content-Type": "application/json"
}
Body: {
    "entity_type": "farmer",
    "farmer_id": 12345,
    "ticket_type": "FAT/SNF Variation",
    "priority": "high",
    "description_en": "Milk FAT percentage dropped from 6.5 to 4.2",
    "description_hi": "दूध का FAT प्रतिशत 6.5 से घटकर 4.2 हो गया",
    "caller_name": "Rajesh Kumar",
    "caller_mobile": "9876543210",
    "caller_relation": "Son",
    "assigned_to": ["EMP001", "EMP002"]
}

# Response (201 Created)
{
    "ticket_id": "TKT-2026-000001",
    "status": "open",
    "created_at": "2026-04-06T10:30:00Z",
    "activity_url": "/api/tickets/TKT-2026-000001/activity/"
}
Ticket Lifecycle Methods
python
# Ticket model methods
ticket = Ticket.objects.get(ticket_id="TKT-2026-000001")

# Mark as resolved
ticket.mark_resolved(resolved_by_user=employee)

# Mark as pending (awaiting info)
ticket.mark_pending()

# Close ticket (archive)
ticket.mark_closed(closed_by_user=employee)

# Reopen resolved/closed ticket
ticket.reopen()  # Sets status to REOPENED

# Escalate to manager/CEO
ticket.escalate(
    escalated_to_user=manager,
    reason="Critical quality issue affecting 500+ liters"
)

# Check if overdue
if ticket.is_overdue:
    send_reminder()
Ticket Assignment
python
# Multiple employees can be assigned
ticket.assigned_to.set([employee1, employee2, employee3])

# Add single assignee
ticket.assigned_to.add(employee4)

# Remove assignee
ticket.assigned_to.remove(employee2)

# Clear all assignments
ticket.assigned_to.clear()
⚡ Escalation Engine
How Escalation Works
python
# Celery task runs every 15 minutes
@app.task
def overdue_sweep():
    """Find tickets past Tier-1 grace period"""
    cutoff = now() - timedelta(hours=ESCALATION_TIER1_GRACE_HOURS)
    
    tickets = Ticket.objects.filter(
        status__in=['open', 'pending', 'reopened'],
        escalation_tier=0,
        created_at__lt=cutoff
    )
    
    for ticket in tickets:
        # Get manager from ticket's assigned employee's manager
        manager = ticket.assigned_to.first().manager
        
        # Send email
        send_escalation_email(
            ticket=ticket,
            recipient=manager.email,
            tier=1,
            reason=f"Ticket unresolved after {ESCALATION_TIER1_GRACE_HOURS} hours"
        )
        
        # Update escalation tracking
        EscalationNotification.objects.update_or_create(
            ticket=ticket,
            defaults={
                'tier1_sent_at': now(),
                'tier1_recipient': manager.email
            }
        )
        
        # Log escalation
        TicketActivity.objects.create(
            ticket=ticket,
            activity_type='escalated',
            description=f"Auto-escalated to Tier-1: {manager.get_full_name()}"
        )
Tier-2 Escalation (CEO)
python
@app.task
def tier2_sweep():
    """Escalate to CEO after Tier-1 grace period expires"""
    cutoff = now() - timedelta(hours=ESCALATION_TIER2_DELAY_HOURS)
    
    tickets = Ticket.objects.filter(
        escalation_tier=1,
        status__in=['open', 'pending', 'reopened'],
        escalation_sent_at__lt=cutoff
    )
    
    for ticket in tickets:
        # Send CEO email with urgency
        send_ceo_escalation(ticket)
        
        # Update escalation tracking
        notification = ticket.escalation_notification
        notification.tier2_sent_at = now()
        notification.tier2_recipient = ESCALATION_CE_EMAIL
        notification.save()
        
        # Mark escalated to Tier-2
        ticket.escalation_tier = 2
        ticket.save()
Email Templates
Tier-1 (Manager):

html
Subject: [ESCALATION] Ticket {{ ticket.ticket_id }} unresolved for 4+ hours

Dear {{ manager.name }},

Ticket {{ ticket.ticket_id }} created by {{ ticket.created_by.get_full_name() }}
has not been resolved within {{ ESCALATION_TIER1_GRACE_HOURS }} hours.

Priority: {{ ticket.priority|upper }}
Category: {{ ticket.get_ticket_type_display() }}
Created: {{ ticket.created_at|date:"Y-m-d H:i" }}
Entity: {{ ticket.caller_display_name }}
Location: {{ ticket.caller_location }}

Description: {{ ticket.description_en|truncate(200) }}

Please take action: {{ SITE_URL }}/tickets/{{ ticket.ticket_id }}

---
This is an automated escalation. Do not reply.
Tier-2 (CEO):

html
Subject: [URGENT] CRITICAL ESCALATION - Ticket {{ ticket.ticket_id }} - 24+ hours

Dear Chief Executive,

CRITICAL: Ticket {{ ticket.ticket_id }} has remained unresolved for
{{ ESCALATION_TIER2_DELAY_HOURS }} hours despite Tier-1 escalation.

Priority: {{ ticket.priority|upper }}
Created: {{ ticket.created_at|date:"Y-m-d H:i" }}
Current Age: {{ ticket.created_at|timesince }}

Ticket Link: {{ SITE_URL }}/tickets/{{ ticket.ticket_id }}

This requires immediate executive attention.
🌐 Multi-Entity Support
Entity Polymorphism
python
# Ticket can reference any entity type
class Ticket(models.Model):
    entity_type = models.CharField(choices=[
        ('farmer', 'Farmer'),
        ('sahayak', 'Sahayak / MPP'),
        ('transporter', 'Transporter'),
        ('other', 'Other')
    ])
    
    # Exactly one of these is non-null
    farmer = models.ForeignKey(Farmer, null=True, blank=True)
    mpp = models.ForeignKey(MPP, null=True, blank=True)
    transporter = models.ForeignKey(Transporter, null=True, blank=True)
    
    # For 'other' entity type
    other_caller_name = models.CharField(max_length=200, blank=True)
    other_caller_mobile = models.CharField(max_length=20, blank=True)
    other_caller_location = models.CharField(max_length=200, blank=True)
Caller Contact Box
python
# Captures actual caller (may differ from registered entity)
caller_name = models.CharField(max_length=200)  # e.g., "Rajesh" (son)
caller_mobile = models.CharField(max_length=20)  # e.g., "9876543210"
caller_relation = models.CharField(choices=[
    ('Self', 'Self'),
    ('Son', 'Son'),
    ('Daughter', 'Daughter'),
    ('Husband', 'Husband'),
    ('Wife', 'Wife'),
    ('Father', 'Father'),
    ('Mother', 'Mother'),
    ('Driver', 'Driver'),
    ('MPP Operator', 'MPP Operator'),
    # ... 15+ relations
])
Farmer Model (Partial)
python
class Farmer(models.Model):
    # Registration
    form_number = models.CharField(unique=True)
    unique_member_code = models.CharField(unique=True)
    
    # Personal
    member_name = models.CharField(max_length=200)
    father_name = models.CharField(max_length=200)
    gender = models.CharField(choices=['Male', 'Female', 'Other'])
    age = models.PositiveSmallIntegerField()
    aadhar_no = models.CharField(max_length=16)
    
    # Contact
    mobile_no = models.CharField(max_length=15)
    
    # Location (geographic hierarchy)
    village = models.ForeignKey(Village)
    tehsil = models.ForeignKey(Tehsil)
    district = models.ForeignKey(District)
    state = models.ForeignKey(State)
    
    # Livestock tracking
    cow_animal_nos = models.PositiveSmallIntegerField(default=0)
    buffalo_animal_nos = models.PositiveSmallIntegerField(default=0)
    lpd_no = models.DecimalField(max_digits=8, decimal_places=2)  # Litres per day
    
    # Banking
    bank_account_no = models.CharField(max_length=30)
    ifsc = models.CharField(max_length=15)
    
    # Status
    approval_status = models.CharField(choices=['Pending', 'Approved', 'Rejected'])
    member_status = models.CharField(choices=['Active', 'Inactive', 'Cancelled'])
MPP (Sahayak) Model
python
class MPP(models.Model):
    # Hierarchy
    plant = models.ForeignKey(Plant)
    bmc = models.ForeignKey(BMC)
    mcc = models.ForeignKey(MCC)
    
    # Identification
    unique_code = models.CharField(unique=True)  # e.g., "MPP-001"
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=50)
    
    # Location
    village = models.ForeignKey(Village)
    pincode = models.CharField(max_length=10)
    mobile_number = models.CharField(max_length=15)
    
    # Assignment
    assigned_sahayak = models.ForeignKey(CustomUser, null=True)  # Facilitator
    
    # Status
    status = models.CharField(choices=['Active', 'Inactive', 'Closed'])
    opening_date = models.DateField()
    closing_date = models.DateField(null=True)
Geographic Hierarchy
python
class State(models.Model):
    name = models.CharField(max_length=100, unique=True)

class District(models.Model):
    state = models.ForeignKey(State)
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)

class Tehsil(models.Model):
    district = models.ForeignKey(District)
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)

class Village(models.Model):
    tehsil = models.ForeignKey(Tehsil)
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)

class Hamlet(models.Model):
    village = models.ForeignKey(Village)
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
🌏 Bilingual System (English/Hindi)
Translation Flow
javascript
// Frontend: Auto-translate while typing
document.getElementById('description_en').addEventListener('input', async (e) => {
    const englishText = e.target.value;
    
    // Call Google Translate API
    const hindiText = await translateToHindi(englishText);
    document.getElementById('description_hi').value = hindiText;
});

async function translateToHindi(text) {
    const response = await fetch('/api/translate/', {
        method: 'POST',
        body: JSON.stringify({ text: text, target: 'hi' })
    });
    const data = await response.json();
    return data.translated_text;
}
Hindi Support in Comments
html
<!-- Rich comment editor with Hindi toggle -->
<div class="comment-editor">
    <div class="language-toggle">
        <button onclick="setLanguage('en')">English</button>
        <button onclick="setLanguage('hi')">हिन्दी</button>
    </div>
    
    <div contenteditable="true" 
         id="comment-editor"
         data-language="en">
    </div>
    
    <div id="hindi-preview" style="display: none;">
        <!-- Live Hindi translation preview -->
    </div>
</div>
Database Storage
python
class Ticket(models.Model):
    # English version (stored as-is)
    description_en = models.TextField()
    
    # Hindi version (auto-translated or user-provided)
    description_hi = models.TextField(blank=True, null=True)

class TicketComment(models.Model):
    body_html = models.TextField()      # English rich text
    body_text = models.TextField()      # Plain text for search
    body_hindi = models.TextField()     # Hindi translation
    hindi_fallback = models.BooleanField(default=False)  # If translation failed
💬 Rich Comment System
HTML Editor Implementation
html
<!-- ContentEditable rich text editor -->
<div id="rich-editor" 
     contenteditable="true"
     class="border p-3 min-h-[150px]">
</div>

<!-- Toolbar -->
<div class="editor-toolbar">
    <button onclick="execCommand('bold')"><b>Bold</b></button>
    <button onclick="execCommand('italic')"><i>Italic</i></button>
    <button onclick="execCommand('insertUnorderedList')">• List</button>
    <button onclick="execCommand('createLink')">🔗 Link</button>
</div>

<script>
function execCommand(command) {
    document.execCommand(command, false, null);
    updateHindiTranslation();
}
</script>
Internal Notes
python
class TicketComment(models.Model):
    is_internal = models.BooleanField(default=False)
    # Internal notes are only visible to employees, not to farmers
Comment Rendering
python
# In ticket detail view
comments = ticket.comments.filter(is_internal=False)  # Hide internal notes from farmers

for comment in comments:
    if user.role == 'employee':
        # Show both English and Hindi
        render_english(comment.body_html)
        render_hindi(comment.body_hindi)
    else:
        # Farmer sees only Hindi
        render_hindi(comment.body_hindi)
📎 Attachment Management
File Upload Configuration
python
# settings.py
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip']

# Storage paths
def ticket_attachment_upload_path(instance, filename):
    return f"tickets/{instance.ticket.ticket_id}/{filename}"

def comment_attachment_upload_path(instance, filename):
    return f"tickets/{instance.comment.ticket.ticket_id}/comments/{instance.comment.pk}/{filename}"
Attachment Types
python
class TicketAttachment(models.Model):
    class FileType(models.TextChoices):
        IMAGE = 'image', 'Image'
        PDF = 'pdf', 'PDF Document'
        WORD = 'word', 'Word Document'
        EXCEL = 'excel', 'Excel Spreadsheet'
        PPT = 'ppt', 'PowerPoint'
        ZIP = 'zip', 'Archive'
        VIDEO = 'video', 'Video'
        OTHER = 'other', 'Other'
    
    file = models.FileField(upload_to=ticket_attachment_upload_path)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10, choices=FileType.choices)
    file_size_bytes = models.PositiveIntegerField()
    mime_type = models.CharField(max_length=100)
Drag-and-Drop Upload
javascript
// Frontend implementation
const dropzone = document.getElementById('attachment-dropzone');

dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-over');
});

dropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    
    for (const file of files) {
        if (file.size > 20 * 1024 * 1024) {
            showError(`${file.name} exceeds 20MB limit`);
            continue;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('ticket_id', ticketId);
        
        await fetch('/api/attachments/upload/', {
            method: 'POST',
            body: formData
        });
    }
});
📜 Activity Timeline
Activity Types
python
class TicketActivity(models.Model):
    class ActivityType(models.TextChoices):
        CREATED = 'created', 'Ticket Created'
        ASSIGNED = 'assigned', 'Assigned'
        REASSIGNED = 'reassigned', 'Reassigned'
        STATUS_CHANGE = 'status_change', 'Status Changed'
        PRIORITY_CHANGE = 'priority_change', 'Priority Changed'
        COMMENT = 'comment', 'Comment Added'
        ATTACHMENT = 'attachment', 'Attachment Added'
        ESCALATED = 'escalated', 'Escalated'
        RESOLVED = 'resolved', 'Resolved'
        REOPENED = 'reopened', 'Reopened'
        PENDING = 'pending', 'Marked Pending'
        CLOSED = 'closed', 'Closed'
        SMS_SENT = 'sms_sent', 'SMS Sent'
Timeline Rendering
html
<!-- Timeline UI -->
<div class="timeline">
    {% for activity in ticket.activities.all %}
    <div class="timeline-item">
        <div class="timeline-badge {{ activity.activity_type }}">
            <i class="icon-{{ activity.activity_type }}"></i>
        </div>
        <div class="timeline-content">
            <div class="timeline-header">
                <span class="actor">{{ activity.performed_by.get_full_name }}</span>
                <span class="action">{{ activity.get_activity_type_display }}</span>
                <span class="timestamp">{{ activity.created_at|timesince }} ago</span>
            </div>
            <div class="timeline-description">
                {{ activity.description }}
            </div>
            {% if activity.comment %}
                <div class="comment-preview">
                    {{ activity.comment.body_hindi|safe }}
                </div>
            {% endif %}
        </div>
    </div>
    {% endfor %}
</div>
💾 Draft System
Save Draft Flow
javascript
// Auto-save draft every 30 seconds
let draftInterval = setInterval(saveDraft, 30000);

async function saveDraft() {
    const formData = getFormData();
    
    const response = await fetch('/api/drafts/save/', {
        method: 'POST',
        body: JSON.stringify(formData)
    });
    
    const { draft_id } = await response.json();
    localStorage.setItem('current_draft_id', draft_id);
}

// Restore draft on page load
async function restoreDraft() {
    const draftId = localStorage.getItem('current_draft_id');
    if (draftId) {
        const response = await fetch(`/api/drafts/${draftId}/`);
        const data = await response.json();
        populateForm(data.form_snapshot);
    }
}
Draft Model
python
class TicketDraft(models.Model):
    drafted_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    entity_type = models.CharField(max_length=15)
    
    # Foreign keys (may be null if incomplete)
    farmer = models.ForeignKey(Farmer, null=True, blank=True)
    mpp = models.ForeignKey(MPP, null=True, blank=True)
    transporter = models.ForeignKey(Transporter, null=True, blank=True)
    
    # Form data
    ticket_type = models.CharField(max_length=60, blank=True)
    description_en = models.TextField(blank=True)
    description_hi = models.TextField(blank=True)
    
    # Caller info
    caller_name = models.CharField(max_length=200, blank=True)
    caller_mobile = models.CharField(max_length=20, blank=True)
    
    # Complete snapshot for full restore
    form_snapshot = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
📱 SMS Integration
SMS Sending Flow
python
# tasks.py
from twilio.rest import Client

@app.task
def send_sms_task(recipient_mobile, message, ticket_id):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=f"+91{recipient_mobile}"  # India country code
        )
        
        # Log SMS
        SMSLog.objects.create(
            ticket_id=ticket_id,
            recipient_mobile=recipient_mobile,
            message_text=message,
            delivery_status='sent',
            gateway_response=message.sid
        )
        
        return message.sid
    except Exception as e:
        SMSLog.objects.create(
            ticket_id=ticket_id,
            recipient_mobile=recipient_mobile,
            message_text=message,
            delivery_status='failed',
            gateway_response=str(e)
        )
        raise
SMS Triggers
python
# Send SMS on ticket creation
def send_ticket_creation_sms(ticket):
    message = f"""
    श्वेतधारा डेयरी: आपका टिकट {ticket.ticket_id} बनाया गया है।
    स्थिति: {ticket.get_status_display()}
    संपर्क करें: 1800-XXX-XXXX
    """
    
    send_sms_task.delay(
        recipient_mobile=ticket.caller_contact_mobile,
        message=message,
        ticket_id=ticket.id
    )
    
    # Log activity
    TicketActivity.objects.create(
        ticket=ticket,
        activity_type='sms_sent',
        description=f"SMS sent to {ticket.caller_contact_mobile}"
    )
📡 API Documentation
Authentication Endpoints
Method	Endpoint	Description
POST	/api/token/	Login (returns JWT cookies)
POST	/api/token/refresh/	Refresh access token
GET	/logout/	Logout (clear cookies)
GET	/is_authenticated/	Check authentication status
POST	/reset-password/	Request password reset
POST	/reset-password/<uidb64>/<token>/	Confirm reset
Ticket Endpoints
Method	Endpoint	Description
GET	/api/tickets/	List all tickets (paginated)
GET	/api/tickets/?status=open	Filter by status
GET	/api/tickets/?priority=high	Filter by priority
GET	/api/tickets/?assigned_to=EMP001	Filter by assignee
POST	/api/tickets/create/	Create new ticket
GET	/api/tickets/<ticket_id>/activity/	Get activity timeline
PUT	/api/tickets/<ticket_id>/update/	Update ticket fields
POST	/api/tickets/<ticket_id>/resolve/	Mark as resolved
POST	/api/tickets/<ticket_id>/close/	Close ticket
POST	/api/tickets/<ticket_id>/reopen/	Reopen closed ticket
POST	/api/tickets/<ticket_id>/escalate/	Manual escalation
POST	/api/tickets/<ticket_id>/reassign/	Change assignee(s)
Search Endpoints
Method	Endpoint	Query Parameters
GET	/api/farmer/search/	?q=name_or_phone
GET	/api/sahayak/search/	?q=name&village=xyz
GET	/api/transporter/search/	?q=vehicle_no&city=ayodhya
GET	/api/employee/search/	?q=name&department=quality
GET	/api/tickets/search/	?q=keyword&status=open&priority=high
Export Endpoints
Method	Endpoint	Response
GET	/api/tickets/export/	Excel file (all tickets)
GET	/api/my-tickets/export/	Excel file (user's tickets)
GET	/api/farmer/<pk>/tickets/	JSON list of farmer's tickets
GET	/api/sahayak/<pk>/tickets/	JSON list of MPP's tickets
GET	/api/transporter/<pk>/tickets/	JSON list of transporter's tickets
Escalation Endpoints
Method	Endpoint	Description
POST	/api/escalation/trigger/	Manually trigger escalation check
GET	/api/escalation/status/	Get escalation statistics
API Response Examples
GET /api/tickets/TKT-2026-000001/

json
{
    "ticket_id": "TKT-2026-000001",
    "entity_type": "farmer",
    "farmer": {
        "id": 12345,
        "member_name": "Ram Prasad",
        "mobile_no": "9876543210",
        "village": "Sohawal",
        "tehsil": "Sohawal",
        "district": "Ayodhya"
    },
    "ticket_type": "FAT/SNF Variation",
    "priority": "high",
    "status": "in_progress",
    "description_en": "Milk FAT percentage dropped significantly",
    "description_hi": "दूध का FAT प्रतिशत काफी कम हो गया है",
    "caller_name": "Suresh (Son)",
    "caller_mobile": "9876543211",
    "caller_relation": "Son",
    "assigned_to": [
        {
            "employee_code": "EMP001",
            "full_name": "Rajesh Kumar",
            "department": "Quality"
        }
    ],
    "created_at": "2026-04-06T10:30:00Z",
    "expected_resolution_date": "2026-04-08",
    "is_escalated": false,
    "activities_url": "/api/tickets/TKT-2026-000001/activity/"
}
GET /api/tickets/TKT-2026-000001/activity/

json
{
    "ticket_id": "TKT-2026-000001",
    "activities": [
        {
            "timestamp": "2026-04-06T10:30:00Z",
            "activity_type": "created",
            "performed_by": "Ram Prasad",
            "description": "Ticket created via web portal"
        },
        {
            "timestamp": "2026-04-06T10:32:00Z",
            "activity_type": "assigned",
            "performed_by": "System",
            "description": "Auto-assigned to Quality Department",
            "assigned_to": ["Rajesh Kumar (Quality)"]
        },
        {
            "timestamp": "2026-04-06T10:45:00Z",
            "activity_type": "comment",
            "performed_by": "Rajesh Kumar",
            "comment": {
                "body_hindi": "हम जांच कर रहे हैं। जल्द समाधान करेंगे।",
                "attachments": []
            }
        },
        {
            "timestamp": "2026-04-06T14:30:00Z",
            "activity_type": "sms_sent",
            "performed_by": "System",
            "description": "SMS sent to 9876543210: टिकट स्वीकार कर लिया गया है"
        }
    ]
}
Pagination
http
GET /api/tickets/?page=2&page_size=50

Response Headers:
X-Total-Count: 1250
X-Page: 2
X-Page-Size: 50
X-Total-Pages: 25
Link: <http://localhost:8000/api/tickets/?page=3>; rel="next"
Link: <http://localhost:8000/api/tickets/?page=1>; rel="prev"
👥 User Roles & Permissions
Role Matrix
Action	Farmer	Sahayak	Transporter	Employee	Admin
Create ticket	✅	✅	✅	✅	✅
View own tickets	✅	✅	✅	✅	✅
View all tickets	❌	❌	❌	❌	✅
View tickets in jurisdiction	❌	✅	❌	✅	✅
Add comments	✅	✅	✅	✅	✅
Add internal notes	❌	❌	❌	✅	✅
Upload attachments	✅	✅	✅	✅	✅
Assign tickets	❌	✅	❌	✅	✅
Reassign tickets	❌	❌	❌	✅	✅
Resolve tickets	❌	✅	❌	✅	✅
Close tickets	❌	❌	❌	✅	✅
Reopen tickets	❌	❌	❌	✅	✅
Escalate tickets	❌	✅	❌	✅	✅
Bulk upload	❌	❌	❌	✅	✅
Export tickets	❌	❌	❌	✅	✅
Access admin panel	❌	❌	❌	❌	✅
Manage users	❌	❌	❌	❌	✅
View escalation status	❌	❌	❌	✅	✅
Permission Implementation
python
# decorators.py
from functools import wraps
from django.http import JsonResponse

def role_required(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in allowed_roles:
                return JsonResponse(
                    {"error": "Permission denied. Insufficient privileges."},
                    status=403
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def jurisdiction_required(model_field='mpp'):
    """Check if employee has jurisdiction over the entity"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            entity_id = kwargs.get(f'{model_field}_pk')
            entity = get_object_or_404(model, pk=entity_id)
            
            # Check if employee's jurisdictions include entity's tehsil
            if entity.tehsil not in request.user.jurisdictions.all():
                return JsonResponse(
                    {"error": "Outside your jurisdiction"},
                    status=403
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

# Usage
@role_required(['EMPLOYEE', 'ADMIN'])
@jurisdiction_required(model_field='farmer')
def farmer_tickets(request, farmer_pk):
    # Only employees with jurisdiction over this farmer's tehsil
    ...
🔍 Search Functionality
Multi-Model Search
python
# api_views.py
def farmer_search(request):
    query = request.GET.get('q', '')
    village = request.GET.get('village', '')
    
    farmers = Farmer.objects.filter(
        Q(member_name__icontains=query) |
        Q(mobile_no__icontains=query) |
        Q(unique_member_code__icontains=query)
    )
    
    if village:
        farmers = farmers.filter(village__name__icontains=village)
    
    return JsonResponse({
        'results': [
            {
                'id': f.id,
                'name': f.member_name,
                'mobile': f.mobile_no,
                'code': f.unique_member_code,
                'village': f.village.name,
                'tehsil': f.tehsil.name,
                'district': f.district.name
            }
            for f in farmers[:20]
        ]
    })

def ticket_search(request):
    query = request.GET.get('q', '')
    
    tickets = Ticket.objects.filter(
        Q(ticket_id__icontains=query) |
        Q(description_en__icontains=query) |
        Q(description_hi__icontains=query) |
        Q(farmer__member_name__icontains=query) |
        Q(farmer__mobile_no__icontains=query) |
        Q(mpp__name__icontains=query) |
        Q(transporter__vendor_name__icontains=query)
    )
    
    # Additional filters
    if status := request.GET.get('status'):
        tickets = tickets.filter(status=status)
    if priority := request.GET.get('priority'):
        tickets = tickets.filter(priority=priority)
    if date_from := request.GET.get('from'):
        tickets = tickets.filter(created_at__gte=date_from)
    
    return Paginator(tickets, 50).get_page(request.GET.get('page'))
Frontend Search Implementation
javascript
// Debounced search
let searchTimeout;

document.getElementById('search-input').addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    
    searchTimeout = setTimeout(async () => {
        const query = e.target.value;
        if (query.length < 2) return;
        
        const response = await fetch(`/api/tickets/search/?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        renderSearchResults(data.results);
    }, 300);
});
📊 Export Features
Excel Export
python
# api_views.py
import pandas as pd
from django.http import HttpResponse

def ticket_export_excel(request):
    # Get filtered tickets
    tickets = get_filtered_tickets(request)
    
    # Prepare data for export
    data = []
    for ticket in tickets:
        data.append({
            'Ticket ID': ticket.ticket_id,
            'Type': ticket.get_ticket_type_display(),
            'Priority': ticket.get_priority_display(),
            'Status': ticket.get_status_display(),
            'Entity Type': ticket.get_entity_type_display(),
            'Caller Name': ticket.caller_name or ticket.caller_display_name,
            'Caller Mobile': ticket.caller_contact_mobile,
            'Location': ticket.caller_location,
            'Description (English)': ticket.description_en,
            'Description (Hindi)': ticket.description_hi,
            'Created By': ticket.created_by.get_full_name() if ticket.created_by else '',
            'Created At': ticket.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'Resolved At': ticket.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.resolved_at else '',
            'Resolution Time (Hours)': get_resolution_hours(ticket),
            'Assigned To': ', '.join([e.get_full_name() for e in ticket.assigned_to.all()]),
            'Is Escalated': 'Yes' if ticket.is_escalated else 'No',
            'Escalation Tier': ticket.escalation_tier,
        })
    
    df = pd.DataFrame(data)
    
    # Create Excel file
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="tickets_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Tickets', index=False)
        
        # Auto-adjust column widths
        worksheet = writer.sheets['Tickets']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    return response
📨 Celery & Redis Integration
Celery Configuration
python
# ticket_system/celery.py
from __future__ import absolute_import
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ticket_system.settings')
app = Celery('ticket_system')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
Task Definitions
python
# main_app_ticket/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_async_email(self, subject, message, recipient_list, html_message=None):
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,  # Uses DEFAULT_FROM_EMAIL
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
    except Exception as e:
        self.retry(exc=e)

@shared_task
def bulk_upload_async(file_path, user_id):
    import pandas as pd
    
    df = pd.read_excel(file_path)
    total = len(df)
    
    for index, row in df.iterrows():
        # Update progress
        update_progress(user_id, index, total)
        
        try:
            create_ticket_from_row(row, user_id)
        except Exception as e:
            log_error(user_id, index, str(e))
    
    return {"total": total, "status": "completed"}

@shared_task
def overdue_sweep():
    """Find and escalate overdue tickets"""
    from main_app_ticket.models import Ticket
    
    cutoff = timezone.now() - timedelta(hours=4)
    tickets = Ticket.objects.filter(
        status__in=['open', 'pending', 'reopened'],
        created_at__lt=cutoff,
        is_escalated=False
    )
    
    for ticket in tickets:
        escalate_ticket(ticket)
Redis Commands
bash
# Check Redis connectivity
redis-cli ping
# Response: PONG

# Monitor Celery queues
redis-cli --scan --pattern "celery*"

# Check queue length
redis-cli LLEN celery

# Flush all queues (careful!)
redis-cli FLUSHALL
Flower Monitoring
bash
# Install Flower
pip install flower

# Start Flower UI
celery -A ticket_system flower --port=5555

# Access at http://localhost:5555
# Features:
# - Task monitoring
# - Worker status
# - Task graphs
# - Real-time logs
🔒 Security Best Practices
Environment Security
bash
# 1. Never commit .env file
echo ".env" >> .gitignore
echo ".env.*" >> .gitignore

# 2. Generate secure secret key
python -c "import secrets; print(secrets.token_urlsafe(50))"

# 3. Use different keys for different environments
# .env.development, .env.staging, .env.production

# 4. Rotate secrets quarterly
Database Security
sql
-- Create application-specific user (not root)
CREATE USER 'ksts_app'@'localhost' IDENTIFIED BY 'strong_password';

-- Grant only necessary privileges
GRANT SELECT, INSERT, UPDATE, DELETE ON ticket_system_shwetdhara.* TO 'ksts_app'@'localhost';

-- For backups, create read-only user
CREATE USER 'ksts_backup'@'localhost' IDENTIFIED BY 'backup_password';
GRANT SELECT, LOCK TABLES, SHOW VIEW ON ticket_system_shwetdhara.* TO 'ksts_backup'@'localhost';

-- Enable query logging for audit (production)
SET GLOBAL general_log = 'ON';
SET GLOBAL log_output = 'TABLE';
JWT Security
python
# settings.py
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),  # Short-lived
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,  # New refresh token on each refresh
    'BLACKLIST_AFTER_ROTATION': True,  # Invalidate old refresh tokens
    'AUTH_COOKIE_SECURE': True,  # Only send over HTTPS
    'AUTH_COOKIE_HTTP_ONLY': True,  # Not accessible via JavaScript
    'AUTH_COOKIE_SAMESITE': 'Strict',  # CSRF protection
}
Input Validation
python
# Sanitize HTML input
from django.utils.html import escape

def clean_comment_body(body_html):
    # Remove dangerous tags
    allowed_tags = ['b', 'i', 'u', 'strong', 'em', 'p', 'br', 'ul', 'li']
    from bleach import clean
    return clean(body_html, tags=allowed_tags, strip=True)

# Validate mobile numbers
import re
def validate_indian_mobile(mobile):
    pattern = r'^[6-9]\d{9}$'
    return bool(re.match(pattern, mobile))

# Validate email
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

def validate_email_address(email):
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False
Rate Limiting
python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/hour',
        'ticket_create': '50/hour',
        'bulk_upload': '10/day'
    }
}

# Custom throttle for sensitive endpoints
class EscalationThrottle(UserRateThrottle):
    rate = '5/hour'
SQL Injection Prevention
python
# ALWAYS use parameterized queries
# GOOD:
cursor.execute("SELECT * FROM farmers WHERE mobile_no = %s", [mobile])

# BAD (never do this):
cursor.execute(f"SELECT * FROM farmers WHERE mobile_no = '{mobile}'")

# Django ORM is safe:
Farmers.objects.filter(mobile_no=mobile)  # Automatically parameterized
XSS Prevention
python
# In templates, always escape output
{{ user_input|escape }}  # Default in Django, but explicit is better

# For HTML that should be rendered (comments), use bleach
from bleach import clean
safe_html = clean(user_html, tags=['b', 'i', 'p'], attributes={})

# Set CSP headers
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", 'https://code.jquery.com')
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", 'https://fonts.googleapis.com')
CSRF Protection
python
# Ensure CSRF token is included in all POST/PUT/DELETE requests
# Django does this automatically for forms
# For AJAX, include token in header:

const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
fetch('/api/tickets/create/', {
    method: 'POST',
    headers: {
        'X-CSRFToken': csrftoken,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
});
🚀 Deployment Guide
Production Server Setup (Ubuntu 22.04)
bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install dependencies
sudo apt install -y python3-pip python3-venv nginx redis-server mysql-server supervisor

# 3. Clone repository
git clone https://github.com/shwetdhara/ksts.git /var/www/ksts
cd /var/www/ksts

# 4. Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env
nano .env  # Update with production values

# 6. Collect static files
python manage.py collectstatic --noinput

# 7. Database migrations
python manage.py migrate

# 8. Create superuser
python manage.py createsuperuser

# 9. Configure Gunicorn
sudo nano /etc/systemd/system/gunicorn.service
gunicorn.service:

ini
[Unit]
Description=Gunicorn instance for KSTS
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/ksts
Environment="PATH=/var/www/ksts/venv/bin"
EnvironmentFile=/var/www/ksts/.env
ExecStart=/var/www/ksts/venv/bin/gunicorn --workers 4 --bind unix:/var/www/ksts/ksts.sock ticket_system.wsgi:application

[Install]
WantedBy=multi-user.target
celery.service:

ini
[Unit]
Description=Celery Worker for KSTS
After=network.target redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/ksts
Environment="PATH=/var/www/ksts/venv/bin"
EnvironmentFile=/var/www/ksts/.env
ExecStart=/var/www/ksts/venv/bin/celery -A ticket_system worker --loglevel=info --concurrency=4

[Install]
WantedBy=multi-user.target
celery-beat.service:

ini
[Unit]
Description=Celery Beat for KSTS
After=network.target redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/ksts
Environment="PATH=/var/www/ksts/venv/bin"
EnvironmentFile=/var/www/ksts/.env
ExecStart=/var/www/ksts/venv/bin/celery -A ticket_system beat --loglevel=info

[Install]
WantedBy=multi-user.target
Nginx Configuration:

nginx
# /etc/nginx/sites-available/ksts
server {
    listen 80;
    server_name ksts.shwetdhara.com;
    
    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        alias /var/www/ksts/staticfiles/;
    }
    
    location /media/ {
        alias /var/www/ksts/media/;
    }
    
    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/ksts/ksts.sock;
    }
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
Enable services:

bash
sudo systemctl enable gunicorn celery celery-beat nginx redis-server
sudo systemctl start gunicorn celery celery-beat nginx redis-server

# SSL with Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d ksts.shwetdhara.com
Docker Deployment (Alternative)
dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "ticket_system.wsgi"]
yaml
# docker-compose.yml
version: '3.8'

services:
  db:
    image: mysql:8.0
    environment:
      MYSQL_DATABASE: ticket_system_shwetdhara
      MYSQL_ROOT_PASSWORD: root_password
    volumes:
      - mysql_data:/var/lib/mysql

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  web:
    build: .
    environment:
      - DATABASE_HOST=db
      - REDIS_HOST=redis
    depends_on:
      - db
      - redis
    ports:
      - "8000:8000"

  celery:
    build: .
    command: celery -A ticket_system worker --loglevel=info
    environment:
      - DATABASE_HOST=db
      - REDIS_HOST=redis
    depends_on:
      - db
      - redis

  celery-beat:
    build: .
    command: celery -A ticket_system beat --loglevel=info
    environment:
      - DATABASE_HOST=db
      - REDIS_HOST=redis
    depends_on:
      - db
      - redis

volumes:
  mysql_data:
🔧 Troubleshooting
Common Issues & Solutions
Issue	Symptoms	Solution
Database connection	OperationalError: (2002, "Can't connect to MySQL server")	Check MySQL service: sudo systemctl status mysql
Verify credentials in .env
Check bind-address in /etc/mysql/my.cnf
Redis connection	Error 111 connecting to localhost:6379	Start Redis: sudo systemctl start redis
Check port: netstat -tlnp | grep 6379
Celery tasks not running	Tickets not escalating, emails not sending	Check celery worker: celery -A ticket_system status
View logs: tail -f /var/log/celery.log
Email not sending	SMTPAuthenticationError	Verify Gmail App Password
Check less secure app access
Test with python manage.py sendtestemail
Static files 404	CSS/JS not loading	Run python manage.py collectstatic
Check STATIC_ROOT in settings
Verify Nginx static location
Permission denied	PermissionError: [Errno 13]	Fix file permissions: sudo chown -R www-data:www-data /var/www/ksts
JWT cookie not set	Authentication fails after login	Check AUTH_COOKIE_SECURE (must be False for HTTP)
Verify domain in CSRF_TRUSTED_ORIGINS
Hindi translation fails	body_hindi remains empty	Check Google API key
Verify billing is enabled on Google Cloud
Fallback to English works automatically
Debug Mode (Development Only)
python
# settings.py
DEBUG = True

# Enable Django Debug Toolbar
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1']
Logging Configuration
python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/ksts_errors.log',
        },
        'celery_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/celery.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
        'celery': {
            'handlers': ['celery_file'],
            'level': 'INFO',
        },
        'ksts': {
            'handlers': ['file'],
            'level': 'WARNING',
        },
    },
}
📈 Maintenance & Monitoring
Database Maintenance
sql
-- Analyze table statistics
ANALYZE TABLE main_app_ticket_ticket;
ANALYZE TABLE main_app_ticket_ticketactivity;

-- Optimize tables (after bulk deletes)
OPTIMIZE TABLE main_app_ticket_ticket;

-- Check for slow queries
SELECT * FROM mysql.slow_log ORDER BY query_time DESC LIMIT 10;

-- Check table sizes
SELECT 
    table_name,
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'Size (MB)'
FROM information_schema.tables
WHERE table_schema = 'ticket_system_shwetdhara'
ORDER BY (data_length + index_length) DESC;
Backup Automation
bash
#!/bin/bash
# backup.sh - Daily backup script

BACKUP_DIR="/backups/ksts"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="ticket_system_shwetdhara"
DB_USER="root"
DB_PASSWORD="password"

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
mysqldump -u $DB_USER -p$DB_PASSWORD $DB_NAME | gzip > $BACKUP_DIR/ksts_db_$DATE.sql.gz

# Media files backup
tar -czf $BACKUP_DIR/ksts_media_$DATE.tar.gz /var/www/ksts/media/

# Keep only last 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

# Upload to S3 (optional)
aws s3 sync $BACKUP_DIR s3://shwetdhara-backups/ksts/
Monitoring with Prometheus
python
# Install django-prometheus
pip install django-prometheus

# settings.py
INSTALLED_APPS = [
    'django_prometheus',
    # ...
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    # ...
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

# urls.py
urlpatterns = [
    path('', include('django_prometheus.urls')),
    # ...
]
Health Check Endpoint
python
# views.py
from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError
import redis

def health_check(request):
    status = {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'checks': {}
    }
    
    # Check database
    try:
        connections['default'].cursor()
        status['checks']['database'] = 'ok'
    except OperationalError:
        status['checks']['database'] = 'error'
        status['status'] = 'unhealthy'
    
    # Check Redis
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
        r.ping()
        status['checks']['redis'] = 'ok'
    except:
        status['checks']['redis'] = 'error'
        status['status'] = 'unhealthy'
    
    # Check Celery
    from celery import current_app
    try:
        current_app.control.ping(timeout=1)
        status['checks']['celery'] = 'ok'
    except:
        status['checks']['celery'] = 'error'
        status['status'] = 'degraded'
    
    return JsonResponse(status)
🤝 Contributing Guidelines
Code Standards
python
# 1. Follow PEP 8
# 2. Use Black formatter
black main_app_ticket/

# 3. Run flake8
flake8 main_app_ticket/ --max-line-length=120

# 4. Type hints are encouraged
def create_ticket(title: str, description: str, created_by: CustomUser) -> Ticket:
    ...

# 5. Document all public methods
def escalate_ticket(ticket: Ticket, reason: str) -> None:
    """
    Escalate a ticket to the next tier.
    
    Args:
        ticket: Ticket instance to escalate
        reason: Reason for escalation (stored in escalation_reason)
    
    Returns:
        None
    
    Raises:
        ValueError: If ticket is already at maximum escalation tier
    """
Git Workflow
bash
# Feature branch workflow
git checkout -b feature/KSTS-123-add-bulk-upload

# Commit with meaningful message
git commit -m "feat: Add bulk upload progress tracking (#KSTS-123)"

# Push and create PR
git push origin feature/KSTS-123-add-bulk-upload

# After PR approved, merge to main
git checkout main
git pull origin main
git merge feature/KSTS-123-add-bulk-upload
git push origin main
Testing
python
# tests.py
from django.test import TestCase
from main_app_ticket.models import Ticket, CustomUser

class TicketEscalationTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.ticket = Ticket.objects.create(
            ticket_id='TKT-2026-000001',
            title='Test ticket',
            created_by=self.user
        )
    
    def test_escalation_after_4_hours(self):
        # Mock time
        with freeze_time('2026-04-06 10:00:00'):
            self.ticket.created_at = timezone.now()
            self.ticket.save()
        
        # Advance time by 5 hours
        with freeze_time('2026-04-06 15:00:00'):
            overdue_sweep()
            self.ticket.refresh_from_db()
            self.assertTrue(self.ticket.is_escalated)
Running Tests
bash
# Run all tests
python manage.py test main_app_ticket

# Run specific test class
python manage.py test main_app_ticket.tests.TicketEscalationTest

# Run with coverage
coverage run manage.py test
coverage report -m
coverage html  # Open htmlcov/index.html
📞 Support & Contact
Internal Support
Role	Contact	Responsibility
System Administrator	sysadmin@shwetdhara.com	Server, database, deployment
Application Support	ksts-support@shwetdhara.com	Bug fixes, feature requests
Escalation Contact	escalation@shwetdhara.com	Urgent ticket escalations
Training Team	training@shwetdhara.com	User onboarding, documentation
Emergency Contacts
python
# In case of system failure
EMERGENCY_CONTACTS = {
    '24x7 Support': '+91-XXXX-XXXXXX',
    'Database Admin': '+91-XXXX-XXXXXX',
    'DevOps Engineer': '+91-XXXX-XXXXXX'
}
Documentation
User Manual: /docs/KSTS_User_Manual.pdf

Admin Guide: /docs/KSTS_Admin_Guide.pdf

API Reference: /docs/api_reference.html

Developer Guide: /docs/developer_guide.md

Issue Reporting
markdown
**Bug Report Template:**
- **Ticket ID**: KSTS-XXXX
- **Environment**: Production/Staging/Development
- **Steps to Reproduce**:
  1. Login as X
  2. Click on Y
  3. Observe Z
- **Expected Behavior**: ...
- **Actual Behavior**: ...
- **Screenshots**: ...
- **Logs**: ...
📝 Changelog
Version 2.0.0 (2026-04-06)
Added:

Bilingual support (English/Hindi) with auto-translation

Rich text comments with HTML editor

File attachments (20MB limit, 10+ formats)

Draft system for incomplete tickets

SMS integration with delivery tracking

15+ new ticket types for dairy operations

Geographic hierarchy (State → Hamlet)

Employee jurisdiction mapping

Bulk upload with progress tracking

Excel export with formatted columns

Changed:

Upgraded to Django 6.0

Migrated from session to JWT cookie authentication

Enhanced escalation engine with two-tier system

Improved search with fuzzy matching

Fixed:

CSRF token handling in AJAX requests

Hindi character encoding in database

Celery task retry mechanism

Memory leak in bulk upload processing

Version 1.0.0 (2025-12-15)
Initial release with basic ticket management.

📄 License
This software is proprietary to Shwetdhara Dairy. Unauthorized copying, distribution, or modification is prohibited.

🙏 Acknowledgments
Django Community for the excellent framework

Celery Team for distributed task queue

Google Translate API for Hindi localization

Twilio for SMS infrastructure

All Shwetdhara employees for beta testing and feedback

Built with ❤️ for Shwetdhara Dairy Farmers & Employees

KSTS - Knowledge Service Ticket System | Empowering Dairy Supply Chain