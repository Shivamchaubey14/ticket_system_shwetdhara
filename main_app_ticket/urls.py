# ksts/urls.py
from django.urls import path

from main_app_ticket import escalation_api_views
from . import views
from . import api_views

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────────
    path("",                    views.loginView,            name="login"),
    path("logout/",             views.logoutView,           name="logout"),
    path("is_authenticated/",   views.is_authenticated_view,name="is_authenticated"),
    path("send_message/",       views.send_message,         name="send_message"),

    # Password reset (2-step)
    path("reset-password/",
         views.password_reset_view,
         name="password_reset"),
    path("reset-password/<uidb64>/<token>/",
         views.password_reset_confirm_view,
         name="password_reset_confirm"),

    # ── Pages ──────────────────────────────────────────────────────────────────
    path("home/",               views.home,                 name="home"),
    path("my_tickets/",         views.my_tickets,           name="my_tickets"),
    path("bulk-upload/",        views.bulk_upload,          name="bulk_upload"),
    path("bulk-upload/progress/",views.bulk_upload_progress,name="bulk_upload_progress"),

    # ── Search APIs ────────────────────────────────────────────────────────────
    path("api/farmer/search/",      api_views.farmer_search,      name="api_farmer_search"),
    path("api/sahayak/search/",     api_views.sahayak_search,     name="api_sahayak_search"),
    path("api/transporter/search/", api_views.transporter_search, name="api_transporter_search"),
    path("api/employee/search/",    api_views.employee_search,    name="api_employee_search"),

    # ── Ticket APIs ────────────────────────────────────────────────────────────
    path("api/tickets/",                                api_views.ticket_list,     name="api_ticket_list"),
    path("api/tickets/search/",                         api_views.ticket_search,   name="api_ticket_search"),
    path("api/tickets/create/",                         api_views.ticket_create,   name="api_ticket_create"),
    path("api/tickets/<str:ticket_id>/activity/",       api_views.ticket_activity, name="api_ticket_activity"),
    path("api/tickets/<str:ticket_id>/resolve/",        api_views.ticket_resolve,  name="api_ticket_resolve"),
    path("api/tickets/<str:ticket_id>/close/",          api_views.ticket_close,    name="api_ticket_close"),
    path("api/tickets/<str:ticket_id>/reopen/",         api_views.ticket_reopen,   name="api_ticket_reopen"),
    path("api/tickets/<str:ticket_id>/escalate/",       api_views.ticket_escalate, name="api_ticket_escalate"),
    path("api/tickets/<str:ticket_id>/update/",         api_views.ticket_update,   name="api_ticket_update"),
    path("api/tickets/<str:ticket_id>/reassign/",       api_views.ticket_reassign, name="api_ticket_reassign"),
    path("api/tickets/export/", api_views.ticket_export_excel, name="api_ticket_export"),
    path("api/my-tickets/export/", api_views.my_tickets_export, name="my_tickets_export"),
    path("api/farmer/<int:farmer_pk>/tickets/", api_views.farmer_tickets, name="farmer_tickets"),
    path('api/sahayak/<int:mpp_pk>/tickets/', api_views.sahayak_tickets, name="sahayak_tickets"),
    path('api/transporter/<int:trans_pk>/tickets/', api_views.transporter_tickets, name="transporter_tickets"),
    path("api/escalation/trigger/", escalation_api_views.escalation_trigger, name="escalation_trigger"),
    path("api/escalation/status/",  escalation_api_views.escalation_status,  name="escalation_status"),
    
#   --- Org Hierarchy API----------------------------------------------------------
    path('api/org/hierarchy/', api_views.org_hierarchy_api, name='org_hierarchy_api'),
]