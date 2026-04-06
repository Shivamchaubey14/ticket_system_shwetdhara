from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Q, Prefetch
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from .models import *


# ==============================================================================
# CUSTOM ADMIN SITE
# ==============================================================================

class KSTSAdminSite(admin.AdminSite):
    site_header = "Member Sahayak Support System — Admin"
    site_title = "KSTS Admin Portal"
    index_title = "Welcome to the KSTS Dashboard"
    index_template = "admin/index.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "geo-overview/",
                self.admin_view(self.geo_overview),
                name="geo-overview",
            ),
            path(
                "mpp-overview/",
                self.admin_view(self.mpp_overview),
                name="mpp-overview",
            ),
            path(
                "farmer-overview/",
                self.admin_view(self.farmer_overview),
                name="farmer-overview",
            ),
            path(
                "ticket-overview/",
                self.admin_view(self.ticket_overview),
                name="ticket-overview",
            ),
        ]
        return custom_urls + urls

    # ------------------------------------------------------------------
    # Custom dashboard views
    # ------------------------------------------------------------------

    def geo_overview(self, request):
        context = {
            "title": "Geography Overview",
            "states": State.objects.annotate(district_count=Count("districts")).order_by("name"),
            "districts": District.objects.annotate(tehsil_count=Count("tehsils")).order_by("name"),
            "tehsils": Tehsil.objects.annotate(village_count=Count("villages")).order_by("name"),
        }
        return render(request, "admin/geo_overview.html", context)

    def mpp_overview(self, request):
        context = {
            "title": "MPP Overview",
            "total_mpps": MPP.objects.count(),
            "active_mpps": MPP.objects.filter(status=MPP.Status.ACTIVE).count(),
            "inactive_mpps": MPP.objects.filter(status=MPP.Status.INACTIVE).count(),
            "unassigned": MPP.objects.filter(assigned_sahayak__isnull=True).count(),
            "plants": Plant.objects.annotate(mpp_count=Count("mpps")).order_by("code"),
        }
        return render(request, "admin/mpp_overview.html", context)

    def farmer_overview(self, request):
        context = {
            "title": "Farmer Overview",
            "total": Farmer.objects.count(),
            "active": Farmer.objects.filter(member_status=Farmer.MemberStatus.ACTIVE).count(),
            "pending": Farmer.objects.filter(approval_status=Farmer.ApprovalStatus.PENDING).count(),
            "approved": Farmer.objects.filter(approval_status=Farmer.ApprovalStatus.APPROVED).count(),
            "by_district": Farmer.objects.values("district__name")
                                             .annotate(count=Count("id"))
                                             .order_by("-count")[:15],
        }
        return render(request, "admin/farmer_overview.html", context)

    def ticket_overview(self, request):
        context = {
            "title": "Ticket Overview",
            "total": Ticket.objects.count(),
            "open": Ticket.objects.filter(status=Ticket.Status.OPEN).count(),
            "pending": Ticket.objects.filter(status=Ticket.Status.PENDING).count(),
            "resolved": Ticket.objects.filter(status=Ticket.Status.RESOLVED).count(),
            "closed": Ticket.objects.filter(status=Ticket.Status.CLOSED).count(),
            "escalated": Ticket.objects.filter(status=Ticket.Status.ESCALATED).count(),
            "overdue": Ticket.objects.filter(
                status__in=[Ticket.Status.OPEN, Ticket.Status.PENDING],
                expected_resolution_date__lt=timezone.now().date()
            ).count(),
            "by_type": Ticket.objects.values("ticket_type")
                                      .annotate(count=Count("id"))
                                      .order_by("-count")[:10],
        }
        return render(request, "admin/ticket_overview.html", context)


ksts_admin = KSTSAdminSite(name="ksts_admin")


# ==============================================================================
# CUSTOM USER / EMPLOYEE ADMIN
# ==============================================================================

@admin.register(CustomUser, site=ksts_admin)
class CustomUserAdmin(UserAdmin):
    """
    Employee admin — mirrors the role-badge pattern from the reference admin.py.
    """

    # ------------------------------------------------------------------
    # Fieldsets for change view
    # ------------------------------------------------------------------
    fieldsets = (
        (None, {
            "fields": ("email", "password"),
        }),
        ("Personal Info", {
            "fields": (
                "first_name", "last_name",
                "secondary_email",
                "mobile_number", "work_phone", "home_phone",
            ),
        }),
        ("Employee Details", {
            "fields": (
                "employee_code", "employee_type", "employee_title",
                "department", "work_address", "manager",
            ),
        }),
        ("Geo Jurisdictions", {
            "fields": ("jurisdictions",),
            "description": "Tehsils this employee is responsible for (used in ticket assignment).",
        }),
        ("Status & Flags", {
            "fields": (
                "account_status", "login_status", "remark",
            ),
        }),
        ("Django Permissions", {
            "fields": (
                "is_active", "is_staff", "is_superuser",
                "groups", "user_permissions",
            ),
            "classes": ("collapse",),
        }),
        ("Important Dates", {
            "fields": ("last_login", "date_joined"),
            "classes": ("collapse",),
        }),
    )

    # ------------------------------------------------------------------
    # Fieldsets for add view
    # ------------------------------------------------------------------
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email", "password1", "password2",
                "first_name", "last_name",
                "employee_code", "employee_type", "employee_title",
                "department", "work_address",
                "mobile_number", "work_phone",
                "account_status",
            ),
        }),
    )

    # ------------------------------------------------------------------
    # List view
    # ------------------------------------------------------------------
    list_display = (
        "employee_code", "full_name_display", "email",
        "employee_type", "employee_title_badge",
        "department_badge", "work_address",
        "mobile_number", "account_status_badge",
        "is_active", "edit_button",
    )
    list_display_links = ("email",)
    list_filter = (
        "employee_type", "department", "work_address",
        "account_status", "is_active",
    )
    search_fields = (
        "email", "first_name", "last_name",
        "employee_code", "mobile_number", "work_phone",
    )
    ordering = ("employee_code",)
    list_editable = ("is_active",)
    list_per_page = 500
    readonly_fields = ("date_joined", "last_login")
    filter_horizontal = ("groups", "user_permissions", "jurisdictions")

    actions = [
        "mark_active", "mark_inactive",
        "assign_pib_title", "assign_facilitator_title",
        "assign_cluster_manager_title",
    ]

    # ------------------------------------------------------------------
    # Custom display helpers
    # ------------------------------------------------------------------

    def full_name_display(self, obj):
        return obj.get_full_name() or "—"
    full_name_display.short_description = "Name"
    full_name_display.admin_order_field = "first_name"

    def employee_title_badge(self, obj):
        if not obj.employee_title:
            return "—"
        color_map = {
            "PIB Officer":      "#7B1FA2",
            "Cluster Manager":  "#1565C0",
            "Area Officer":     "#E65100",
            "Zonal Manager":    "#2E7D32",
            "Facilitator":      "#0277BD",
            "Chemist":          "#558B2F",
            "HOD":              "#B71C1C",
            "Veterinarian":     "#4A148C",
        }
        color = color_map.get(obj.employee_title, "#546E7A")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;">{}</span>',
            color, obj.employee_title,
        )
    employee_title_badge.short_description = "Title"

    def department_badge(self, obj):
        color_map = {
            "PIB & PES":            "#4A148C",
            "OPERATIONS":           "#1B5E20",
            "QUALITY":              "#01579B",
            "IT & MIS":             "#E65100",
            "FINANCE AND ACCOUNTS": "#827717",
            "SALES & MARKETING":    "#880E4F",
            "HUMAN RESOUCE":        "#006064",
            "LOGISTICS":            "#3E2723",
            "PURCHASE":             "#37474F",
        }
        color = color_map.get(obj.department, "#546E7A")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;">{}</span>',
            color, obj.department,
        )
    department_badge.short_description = "Department"

    def account_status_badge(self, obj):
        color_map = {
            "Active":        "#28A745",
            "Inactive":      "#DC3545",
            "Yet to create": "#FFC107",
        }
        color = color_map.get(obj.account_status, "#6C757D")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;">{}</span>',
            color, obj.account_status,
        )
    account_status_badge.short_description = "Account"

    def edit_button(self, obj):
        return format_html(
            '<a class="button" href="{}/change/">Edit</a>', obj.pk
        )
    edit_button.short_description = "Actions"

    # ------------------------------------------------------------------
    # Bulk actions
    # ------------------------------------------------------------------

    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True, account_status=CustomUser.AccountStatus.ACTIVE)
        self.message_user(request, f"{updated} employees marked active.")
    mark_active.short_description = "Mark selected employees as active"

    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False, account_status=CustomUser.AccountStatus.INACTIVE)
        self.message_user(request, f"{updated} employees marked inactive.")
    mark_inactive.short_description = "Mark selected employees as inactive"

    def assign_pib_title(self, request, queryset):
        queryset.update(employee_title=CustomUser.EmployeeTitle.PIB_OFFICER)
        self.message_user(request, f"{queryset.count()} employees assigned PIB Officer title.")
    assign_pib_title.short_description = "Set title → PIB Officer"

    def assign_facilitator_title(self, request, queryset):
        queryset.update(employee_title=CustomUser.EmployeeTitle.FACILITATOR)
        self.message_user(request, f"{queryset.count()} employees assigned Facilitator title.")
    assign_facilitator_title.short_description = "Set title → Facilitator"

    def assign_cluster_manager_title(self, request, queryset):
        queryset.update(employee_title=CustomUser.EmployeeTitle.CLUSTER_MANAGER)
        self.message_user(request, f"{queryset.count()} employees assigned Cluster Manager title.")
    assign_cluster_manager_title.short_description = "Set title → Cluster Manager"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("manager")
            .prefetch_related("jurisdictions")
        )


# ==============================================================================
# GEOGRAPHY ADMINS
# ==============================================================================

@admin.register(State, site=ksts_admin)
class StateAdmin(admin.ModelAdmin):
    list_display = ("name", "district_count", "farmer_count", "mpp_count")
    search_fields = ("name",)
    ordering = ("name",)
    list_per_page = 30

    def district_count(self, obj):
        count = obj.districts.count()
        if count:
            url = f"{ksts_admin.name}:main_app_ticket_district_changelist"
            return format_html(
                '<a href="{}?state__id__exact={}">{}</a>', url, obj.pk, count
            )
        return count
    district_count.short_description = "Districts"

    def farmer_count(self, obj):
        return obj.farmers.count()
    farmer_count.short_description = "Farmers"

    def mpp_count(self, obj):
        return obj.mpps.count()
    mpp_count.short_description = "MPPs"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("districts", "farmers", "mpps")
        )


class TehsilInline(admin.TabularInline):
    model = Tehsil
    extra = 0
    fields = ("code", "name")
    ordering = ("name",)
    show_change_link = True


@admin.register(District, site=ksts_admin)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "state", "tehsil_count", "farmer_count", "mpp_count")
    list_filter = ("state",)
    search_fields = ("code", "name", "state__name")
    ordering = ("state__name", "name")
    list_per_page = 30
    inlines = [TehsilInline]
    autocomplete_fields = ["state"]

    def tehsil_count(self, obj):
        count = obj.tehsils.count()
        if count:
            url = f"{ksts_admin.name}:main_app_ticket_tehsil_changelist"
            return format_html(
                '<a href="{}?district__id__exact={}">{}</a>', url, obj.pk, count
            )
        return count
    tehsil_count.short_description = "Tehsils"

    def farmer_count(self, obj):
        return obj.farmers.count()
    farmer_count.short_description = "Farmers"

    def mpp_count(self, obj):
        return obj.mpps.count()
    mpp_count.short_description = "MPPs"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("state")
            .prefetch_related("tehsils", "farmers", "mpps")
        )


class VillageInline(admin.TabularInline):
    model = Village
    extra = 0
    fields = ("code", "name")
    ordering = ("name",)
    show_change_link = True


@admin.register(Tehsil, site=ksts_admin)
class TehsilAdmin(admin.ModelAdmin):
    list_display = (
        "code", "name", "district", "state_display",
        "village_count", "farmer_count", "mpp_count", "assigned_employees_count",
    )
    list_filter = ("district__state", "district")
    search_fields = ("code", "name", "district__name")
    ordering = ("district__name", "name")
    list_per_page = 30
    inlines = [VillageInline]
    autocomplete_fields = ["district"]

    def state_display(self, obj):
        return obj.district.state.name
    state_display.short_description = "State"
    state_display.admin_order_field = "district__state__name"

    def village_count(self, obj):
        return obj.villages.count()
    village_count.short_description = "Villages"

    def farmer_count(self, obj):
        return obj.farmers.count()
    farmer_count.short_description = "Farmers"

    def mpp_count(self, obj):
        return obj.mpps.count()
    mpp_count.short_description = "MPPs"

    def assigned_employees_count(self, obj):
        count = obj.assigned_employees.count()
        if count:
            url = f"{ksts_admin.name}:main_app_ticket_customuser_changelist"
            return format_html(
                '<a href="{}?jurisdictions__id__exact={}">{}</a>', url, obj.pk, count
            )
        return count
    assigned_employees_count.short_description = "Assigned Staff"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("district__state")
            .prefetch_related("villages", "farmers", "mpps", "assigned_employees")
        )


class HamletInline(admin.TabularInline):
    model = Hamlet
    extra = 0
    fields = ("code", "name")
    ordering = ("name",)


@admin.register(Village, site=ksts_admin)
class VillageAdmin(admin.ModelAdmin):
    list_display = (
        "code", "name", "tehsil", "district_display",
        "hamlet_count", "farmer_count", "mpp_count",
    )
    list_filter = ("tehsil__district__state", "tehsil__district", "tehsil")
    search_fields = ("code", "name", "tehsil__name")
    ordering = ("tehsil__name", "name")
    list_per_page = 30
    inlines = [HamletInline]
    autocomplete_fields = ["tehsil"]

    def district_display(self, obj):
        return obj.tehsil.district.name
    district_display.short_description = "District"

    def hamlet_count(self, obj):
        return obj.hamlets.count()
    hamlet_count.short_description = "Hamlets"

    def farmer_count(self, obj):
        return obj.farmers.count()
    farmer_count.short_description = "Farmers"

    def mpp_count(self, obj):
        return obj.mpps.count()
    mpp_count.short_description = "MPPs"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("tehsil__district")
            .prefetch_related("hamlets", "farmers", "mpps")
        )


@admin.register(Hamlet, site=ksts_admin)
class HamletAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "village", "tehsil_display", "farmer_count")
    list_filter = ("village__tehsil__district",)
    search_fields = ("code", "name", "village__name")
    ordering = ("village__name", "name")
    list_per_page = 40
    autocomplete_fields = ["village"]

    def tehsil_display(self, obj):
        return obj.village.tehsil.name
    tehsil_display.short_description = "Tehsil"

    def farmer_count(self, obj):
        return obj.farmers.count()
    farmer_count.short_description = "Farmers"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("village__tehsil")
            .prefetch_related("farmers")
        )


# ==============================================================================
# DAIRY HIERARCHY ADMINS — Plant → BMC → MCC → MPP
# ==============================================================================

class BMCInline(admin.TabularInline):
    model = BMC
    extra = 0
    fields = ("code", "transaction_code", "name")
    show_change_link = True


@admin.register(Plant, site=ksts_admin)
class PlantAdmin(admin.ModelAdmin):
    list_display = ("code", "transaction_code", "name", "bmc_count", "mpp_count")
    search_fields = ("code", "name")
    ordering = ("code",)
    list_per_page = 20
    inlines = [BMCInline]

    def bmc_count(self, obj):
        count = obj.bmcs.count()
        if count:
            url = f"{ksts_admin.name}:main_app_ticket_bmc_changelist"
            return format_html(
                '<a href="{}?plant__id__exact={}">{}</a>', url, obj.pk, count
            )
        return count
    bmc_count.short_description = "BMCs"

    def mpp_count(self, obj):
        count = obj.mpps.count()
        if count:
            url = f"{ksts_admin.name}:main_app_ticket_mpp_changelist"
            return format_html(
                '<a href="{}?plant__id__exact={}">{}</a>', url, obj.pk, count
            )
        return count
    mpp_count.short_description = "MPPs"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("bmcs", "mpps")


class MCCInline(admin.TabularInline):
    model = MCC
    extra = 0
    fields = ("code", "transaction_code", "name")
    show_change_link = True


@admin.register(BMC, site=ksts_admin)
class BMCAdmin(admin.ModelAdmin):
    list_display = ("code", "transaction_code", "name", "plant", "mcc_count", "mpp_count")
    list_filter = ("plant",)
    search_fields = ("code", "name", "plant__name")
    ordering = ("plant__code", "code")
    list_per_page = 30
    inlines = [MCCInline]
    autocomplete_fields = ["plant"]

    def mcc_count(self, obj):
        count = obj.mccs.count()
        if count:
            url = f"{ksts_admin.name}:main_app_ticket_mcc_changelist"
            return format_html(
                '<a href="{}?bmc__id__exact={}">{}</a>', url, obj.pk, count
            )
        return count
    mcc_count.short_description = "MCCs"

    def mpp_count(self, obj):
        return MPP.objects.filter(mcc__bmc=obj).count()
    mpp_count.short_description = "MPPs"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("plant").prefetch_related("mccs")


@admin.register(MCC, site=ksts_admin)
class MCCAdmin(admin.ModelAdmin):
    list_display = ("code", "transaction_code", "name", "bmc", "plant_display", "mpp_count")
    list_filter = ("bmc__plant", "bmc")
    search_fields = ("code", "name", "bmc__name")
    ordering = ("bmc__name", "code")
    list_per_page = 30
    autocomplete_fields = ["bmc"]

    def plant_display(self, obj):
        return obj.bmc.plant.name
    plant_display.short_description = "Plant"

    def mpp_count(self, obj):
        count = obj.mpps.count()
        if count:
            url = f"{ksts_admin.name}:main_app_ticket_mpp_changelist"
            return format_html(
                '<a href="{}?mcc__id__exact={}">{}</a>', url, obj.pk, count
            )
        return count
    mpp_count.short_description = "MPPs"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("bmc__plant")
            .prefetch_related("mpps")
        )


@admin.register(MPP, site=ksts_admin)
class MPPAdmin(admin.ModelAdmin):
    list_display = (
        "unique_code", "name", "short_name",
        "mcc", "plant_display",
        "district_display", "tehsil_display",
        "mobile_number",
        "assigned_sahayak_display",
        "status",
        "status_badge",
        "farmer_count",
        "opening_date",
    )
    list_filter = (
        "status",
        "plant",
        "mcc__bmc",
        "mcc",
        "district",
        "tehsil",
    )
    search_fields = (
        "unique_code", "name", "short_name",
        "transaction_code", "ex_code",
        "mobile_number",
        "assigned_sahayak__first_name",
        "assigned_sahayak__last_name",
        "assigned_sahayak__employee_code",
    )
    list_editable = ("status",)
    list_per_page = 30
    ordering = ("unique_code",)
    readonly_fields = ("unique_code",)
    autocomplete_fields = [
        "plant", "mcc", "state", "district",
        "tehsil", "village", "hamlet", "assigned_sahayak",
    ]

    fieldsets = (
        ("Identifiers", {
            "fields": ("unique_code", "transaction_code", "ex_code", "name", "short_name"),
        }),
        ("Dairy Hierarchy", {
            "fields": ("plant", "mcc"),
        }),
        ("Route", {
            "fields": ("route_name", "route_ex_code", "dpu_station_code", "dpu_vendor_code"),
            "classes": ("collapse",),
        }),
        ("Geography", {
            "fields": ("state", "district", "tehsil", "village", "hamlet", "pincode"),
        }),
        ("Contact", {
            "fields": ("mobile_number",),
        }),
        ("Operations", {
            "fields": (
                "status", "opening_date", "closing_date",
                "force_stop_new_share",
            ),
        }),
        ("Assigned Sahayak", {
            "fields": ("assigned_sahayak",),
        }),
    )

    actions = ["activate_mpps", "deactivate_mpps", "close_mpps"]

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def plant_display(self, obj):
        return obj.plant.name
    plant_display.short_description = "Plant"
    plant_display.admin_order_field = "plant__name"

    def district_display(self, obj):
        return obj.district.name
    district_display.short_description = "District"
    district_display.admin_order_field = "district__name"

    def tehsil_display(self, obj):
        return obj.tehsil.name
    tehsil_display.short_description = "Tehsil"
    tehsil_display.admin_order_field = "tehsil__name"

    def assigned_sahayak_display(self, obj):
        if not obj.assigned_sahayak:
            return format_html('<span style="color:#DC3545;">Unassigned</span>')
        emp = obj.assigned_sahayak
        return format_html(
            '<a href="{}/change/">{} [{}]</a>',
            emp.pk,
            emp.get_full_name() or emp.email,
            emp.employee_code,
        )
    assigned_sahayak_display.short_description = "Sahayak"

    def status_badge(self, obj):
        color_map = {
            "Active":   "#28A745",
            "Inactive": "#FFC107",
            "Closed":   "#DC3545",
        }
        color = color_map.get(obj.status, "#6C757D")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;">● {}</span>',
            color, obj.status,
        )
    status_badge.short_description = "Status"

    def farmer_count(self, obj):
        count = obj.farmers.count()
        if count:
            url = f"{ksts_admin.name}:main_app_ticket_farmer_changelist"
            return format_html(
                '<a href="{}?mpp__id__exact={}">{}</a>', url, obj.pk, count
            )
        return count
    farmer_count.short_description = "Farmers"

    # ------------------------------------------------------------------
    # Bulk actions
    # ------------------------------------------------------------------

    def activate_mpps(self, request, queryset):
        updated = queryset.update(status=MPP.Status.ACTIVE)
        self.message_user(request, f"{updated} MPPs activated.")
    activate_mpps.short_description = "Activate selected MPPs"

    def deactivate_mpps(self, request, queryset):
        updated = queryset.update(status=MPP.Status.INACTIVE)
        self.message_user(request, f"{updated} MPPs deactivated.")
    deactivate_mpps.short_description = "Deactivate selected MPPs"

    def close_mpps(self, request, queryset):
        updated = queryset.update(status=MPP.Status.CLOSED, closing_date=timezone.now().date())
        self.message_user(request, f"{updated} MPPs closed.")
    close_mpps.short_description = "Close selected MPPs (set closing date today)"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "plant", "mcc__bmc",
                "state", "district", "tehsil", "village", "hamlet",
                "assigned_sahayak",
            )
            .prefetch_related("farmers")
        )


# ==============================================================================
# FARMER ADMIN
# ==============================================================================

@admin.register(Farmer, site=ksts_admin)
class FarmerAdmin(admin.ModelAdmin):
    list_display = (
        "form_number", "unique_member_code",
        "member_name", "gender_badge",
        "mobile_no", "aadhar_no",
        "village", "tehsil_display", "district_display",
        "mpp_link",
        "member_status_badge", "approval_status_badge",
        "total_animals",
        "enrollment_date",
        "edit_button",
    )
    list_filter = (
        "member_status",
        "approval_status",
        "gender",
        "caste_category",
        "qualification",
        "payment_mode",
        "member_type",
        "district",
        "tehsil",
        "mpp__plant",
        "mpp__mcc",
    )
    search_fields = (
        "form_number", "unique_member_code",
        "member_name", "father_name",
        "mobile_no", "phone_no",
        "aadhar_no",
        "bank_account_no",
        "village__name", "tehsil__name", "district__name",
        "mpp__name", "mpp__unique_code",
    )
    list_per_page = 30
    ordering = ("form_number",)
    date_hierarchy = "enrollment_date"
    readonly_fields = (
        "created_at", "updated_at",
        "total_animals",
        "form_number", "unique_member_code",
    )
    autocomplete_fields = [
        "hamlet", "village", "tehsil", "district", "state",
        "mpp", "accepted_by", "created_by",
    ]

    fieldsets = (
        ("Registration IDs", {
            "fields": (
                "form_number", "unique_member_code",
                "member_tr_code", "member_ex_code",
            ),
        }),
        ("Personal Details", {
            "fields": (
                "member_name", "father_name", "member_relation",
                "gender", "age", "birth_date",
                "caste_category", "qualification",
                "aadhar_no",
            ),
        }),
        ("Contact", {
            "fields": ("mobile_no", "phone_no"),
        }),
        ("Address", {
            "fields": (
                "house_no",
                "hamlet", "village", "post_office",
                "tehsil", "district", "state", "pincode",
            ),
        }),
        ("Dairy Association", {
            "fields": ("mpp",),
        }),
        ("Animal Inventory — Heifer", {
            "fields": (
                "cow_heifer_no", "buffalo_heifer_no", "mix_heifer_no",
                "desi_cow_heifer_no", "crossbred_heifer_no",
            ),
            "classes": ("collapse",),
        }),
        ("Animal Inventory — Dry", {
            "fields": (
                "cow_dry_no", "buffalo_dry_no", "mix_dry_no",
                "desi_cow_dry_no", "crossbred_dry_no",
            ),
            "classes": ("collapse",),
        }),
        ("Animal Inventory — Total", {
            "fields": (
                "cow_animal_nos", "buffalo_animal_nos", "mix_animal_nos",
                "desi_cow_animal_nos", "crossbred_animal_nos",
                "total_animals",
            ),
        }),
        ("Milk Production", {
            "fields": (
                "lpd_no", "household_consumption", "market_consumption",
            ),
        }),
        ("Bank Details", {
            "fields": (
                "accountant_name", "bank_account_no",
                "member_bank_name", "member_branch_name", "ifsc",
            ),
            "classes": ("collapse",),
        }),
        ("Nominee", {
            "fields": (
                "nominee_name", "nominee_relation", "nominee_address",
            ),
            "classes": ("collapse",),
        }),
        ("Particular 1 / Secondary Contact", {
            "fields": (
                "particular1_name", "particular1_gender",
                "particular1_age", "particular1_relation",
            ),
            "classes": ("collapse",),
        }),
        ("Guardian", {
            "fields": ("guardian_name", "member_family_age"),
            "classes": ("collapse",),
        }),
        ("Membership & Shares", {
            "fields": (
                "member_type",
                "admission_fee", "share_qty", "paid_amount",
            ),
        }),
        ("Payment / Deposit", {
            "fields": (
                "depositor_bank_name", "depositor_branch_name",
                "dd_no", "transaction_date",
                "payment_mode", "wef_date",
            ),
            "classes": ("collapse",),
        }),
        ("Approval & Lifecycle", {
            "fields": (
                "approval_status", "accepted_by", "approval_date",
                "member_status", "member_cancellation",
            ),
        }),
        ("Key Dates", {
            "fields": (
                "enrollment_date",
                "first_board_approved_meeting",
                "last_board_approved_meeting",
            ),
        }),
        ("Audit", {
            "fields": ("created_by", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    actions = [
        "approve_farmers", "reject_farmers",
        "mark_active", "mark_inactive", "mark_cancelled",
    ]

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def gender_badge(self, obj):
        color_map = {
            "Male":   "#1565C0",
            "Female": "#880E4F",
            "Other":  "#546E7A",
        }
        color = color_map.get(obj.gender, "#546E7A")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;">{}</span>',
            color, obj.gender,
        )
    gender_badge.short_description = "Gender"

    def tehsil_display(self, obj):
        return obj.tehsil.name
    tehsil_display.short_description = "Tehsil"
    tehsil_display.admin_order_field = "tehsil__name"

    def district_display(self, obj):
        return obj.district.name
    district_display.short_description = "District"
    district_display.admin_order_field = "district__name"

    def mpp_link(self, obj):
        return format_html(
            '<a href="{}/change/">{}</a>',
            obj.mpp.pk,
            obj.mpp.name,
        )
    mpp_link.short_description = "MPP"
    mpp_link.admin_order_field = "mpp__name"

    def member_status_badge(self, obj):
        color_map = {
            "ACTIVE":    "#28A745",
            "INACTIVE":  "#FFC107",
            "CANCELLED": "#DC3545",
            "SUSPENDED": "#6C757D",
        }
        color = color_map.get(obj.member_status, "#6C757D")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;">{}</span>',
            color, obj.member_status,
        )
    member_status_badge.short_description = "Status"

    def approval_status_badge(self, obj):
        color_map = {
            "Pending":  "#FFC107",
            "Approved": "#28A745",
            "Rejected": "#DC3545",
        }
        color = color_map.get(obj.approval_status, "#6C757D")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;">{}</span>',
            color, obj.approval_status,
        )
    approval_status_badge.short_description = "Approval"

    def edit_button(self, obj):
        return format_html(
            '<a class="button" href="{}/change/">Edit</a>', obj.pk
        )
    edit_button.short_description = "Actions"

    # ------------------------------------------------------------------
    # Bulk actions
    # ------------------------------------------------------------------

    def approve_farmers(self, request, queryset):
        updated = queryset.filter(
            approval_status=Farmer.ApprovalStatus.PENDING
        ).update(
            approval_status=Farmer.ApprovalStatus.APPROVED,
            accepted_by=request.user,
            approval_date=timezone.now().date(),
        )
        self.message_user(request, f"{updated} farmers approved.")
    approve_farmers.short_description = "Approve selected farmers"

    def reject_farmers(self, request, queryset):
        updated = queryset.filter(
            approval_status=Farmer.ApprovalStatus.PENDING
        ).update(
            approval_status=Farmer.ApprovalStatus.REJECTED,
            accepted_by=request.user,
            approval_date=timezone.now().date(),
        )
        self.message_user(request, f"{updated} farmers rejected.")
    reject_farmers.short_description = "Reject selected farmers"

    def mark_active(self, request, queryset):
        updated = queryset.update(member_status=Farmer.MemberStatus.ACTIVE)
        self.message_user(request, f"{updated} farmers marked active.")
    mark_active.short_description = "Mark selected farmers as active"

    def mark_inactive(self, request, queryset):
        updated = queryset.update(member_status=Farmer.MemberStatus.INACTIVE)
        self.message_user(request, f"{updated} farmers marked inactive.")
    mark_inactive.short_description = "Mark selected farmers as inactive"

    def mark_cancelled(self, request, queryset):
        updated = queryset.update(member_status=Farmer.MemberStatus.CANCELLED)
        self.message_user(request, f"{updated} farmers marked as cancelled.")
    mark_cancelled.short_description = "Mark selected farmers as cancelled"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "hamlet", "village", "tehsil", "district", "state",
                "mpp__plant", "mpp__mcc",
                "accepted_by", "created_by",
            )
        )


# ==============================================================================
# TRANSPORTER ADMIN
# ==============================================================================

@admin.register(Transporter, site=ksts_admin)
class TransporterAdmin(admin.ModelAdmin):
    list_display = (
        "vendor_code", "vendor_name", "contact_person",
        "contact_no", "email", "city",
        "account_group", "payment_method",
        "is_blocked", "edit_button",
    )
    list_filter = (
        "account_group",
        "payment_method",
        "is_blocked",
        "city",
    )
    search_fields = (
        "vendor_code", "vendor_name", "contact_person",
        "contact_no", "email", "gst_number",
        "bank_account_no",
    )
    list_per_page = 30
    ordering = ("vendor_code",)
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ["created_by"]

    fieldsets = (
        ("Identifiers", {
            "fields": ("vendor_code", "account_group", "vendor_name"),
        }),
        ("Contact Details", {
            "fields": ("contact_person", "contact_no", "email"),
        }),
        ("Address", {
            "fields": ("address", "city", "country"),
        }),
        ("SAP Integration", {
            "fields": (
                "search_term1", "search_term2",
                "incoterm", "incoterm_location",
            ),
            "classes": ("collapse",),
        }),
        ("Banking Details", {
            "fields": (
                "bank_account_no", "bank_key",
                "account_holder", "payment_terms",
                "payment_method",
            ),
        }),
        ("Tax & Compliance", {
            "fields": ("gst_number", "msme", "is_blocked"),
        }),
        ("SAP Metadata", {
            "fields": (
                "company_code", "gl_account",
                "sap_created_by", "sap_created_on",
                "sap_changed_on",
            ),
            "classes": ("collapse",),
        }),
        ("Audit", {
            "fields": ("created_by", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def edit_button(self, obj):
        return format_html(
            '<a class="button" href="{}/change/">Edit</a>', obj.pk
        )
    edit_button.short_description = "Actions"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("created_by")


# ==============================================================================
# TICKET ADMIN
# ==============================================================================

class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0
    fields = ("body_text", "posted_by", "is_internal", "created_at")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


class TicketAttachmentInline(admin.TabularInline):
    model = TicketAttachment
    extra = 0
    fields = ("file_name", "file_type", "file_size_display", "uploaded_at")
    readonly_fields = ("file_name", "file_type", "file_size_display", "uploaded_at")
    can_delete = True

    def file_size_display(self, obj):
        return obj.file_size_display
    file_size_display.short_description = "Size"


class TicketActivityInline(admin.TabularInline):
    model = TicketActivity
    extra = 0
    fields = ("activity_type", "performed_by", "description", "created_at")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(Ticket, site=ksts_admin)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_id", "ticket_type", "status_badge",
        "priority_badge", "entity_type", "caller_display",
        "assigned_to_display", "created_at", "is_overdue_badge",
        "edit_button",
    )
    list_filter = (
        "status",
        "priority",
        "ticket_type",
        "entity_type",
        "created_at",
        "is_escalated",
    )
    search_fields = (
        "ticket_id",
        "description_en",
        "description_hi",
        "farmer__member_name",
        "farmer__mobile_no",
        "mpp__name",
        "mpp__mobile_number",
        "transporter__vendor_name",
        "transporter__contact_no",
        "caller_name",
        "caller_mobile",
        "other_caller_name",
        "other_caller_mobile",
    )
    list_per_page = 30
    ordering = ("-created_at",)
    readonly_fields = (
        "ticket_id", "created_at", "updated_at",
        "resolved_at", "escalated_at", "sms_sent_count", "last_sms_sent_at",
    )
    autocomplete_fields = [
        "farmer", "mpp", "transporter",
        "assigned_to", "resolved_by", "escalated_to", "created_by",
    ]
    inlines = [TicketCommentInline, TicketAttachmentInline, TicketActivityInline]
    filter_horizontal = ["assigned_to"]

    fieldsets = (
        ("Ticket Identity", {
            "fields": ("ticket_id", "entity_type", "created_by", "created_at"),
        }),
        ("Entity (Registered Party)", {
            "fields": ("farmer", "mpp", "transporter"),
            "description": "Exactly one of these should be selected based on entity_type.",
        }),
        ("Other Entity Details", {
            "fields": ("other_caller_name", "other_caller_mobile", "other_caller_location"),
            "classes": ("collapse",),
        }),
        ("Caller Contact Box", {
            "fields": ("caller_name", "caller_mobile", "caller_relation", "on_behalf_of"),
            "description": "Actual caller information (may differ from registered entity).",
        }),
        ("Ticket Details", {
            "fields": ("ticket_type", "priority", "status"),
        }),
        ("Description", {
            "fields": ("description_en", "description_hi"),
        }),
        ("Assignment", {
            "fields": ("assigned_to",),
        }),
        ("Resolution Timeline", {
            "fields": ("expected_resolution_date", "resolved_at", "resolved_by"),
        }),
        ("Escalation", {
            "fields": ("is_escalated", "escalated_to", "escalated_at", "escalation_reason"),
            "classes": ("collapse",),
        }),
        ("SMS Tracking", {
            "fields": ("sms_sent_count", "last_sms_sent_at"),
            "classes": ("collapse",),
        }),
        ("Audit", {
            "fields": ("updated_at",),
            "classes": ("collapse",),
        }),
    )

    actions = [
        "mark_open", "mark_pending", "mark_resolved",
        "mark_closed", "mark_escalated",
        "set_priority_low", "set_priority_medium",
        "set_priority_high", "set_priority_critical",
    ]

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def status_badge(self, obj):
        color_map = {
            "open":      "#FFC107",
            "pending":   "#17A2B8",
            "resolved":  "#28A745",
            "closed":    "#6C757D",
            "escalated": "#DC3545",
        }
        color = color_map.get(obj.status, "#6C757D")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;">{}</span>',
            color, obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def priority_badge(self, obj):
        color_map = {
            "low":      "#28A745",
            "medium":   "#FFC107",
            "high":     "#FD7E14",
            "critical": "#DC3545",
        }
        color = color_map.get(obj.priority, "#6C757D")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;">{}</span>',
            color, obj.get_priority_display(),
        )
    priority_badge.short_description = "Priority"

    def caller_display(self, obj):
        return obj.caller_display_name
    caller_display.short_description = "Caller"

    def assigned_to_display(self, obj):
        assigned = obj.assigned_to.all()
        if not assigned:
            return format_html('<span style="color:#DC3545;">Unassigned</span>')
        names = [f"{e.get_full_name() or e.email}" for e in assigned[:3]]
        if len(assigned) > 3:
            names.append(f"+{len(assigned)-3}")
        return ", ".join(names)
    assigned_to_display.short_description = "Assigned To"

    def is_overdue_badge(self, obj):
        if obj.is_overdue:
            return format_html(
                '<span style="background:#DC3545;color:#fff;padding:2px 8px;'
                'border-radius:4px;font-size:11px;">Overdue</span>'
            )
        return "—"
    is_overdue_badge.short_description = "Overdue"

    def edit_button(self, obj):
        return format_html(
            '<a class="button" href="{}/change/">Edit</a>', obj.pk
        )
    edit_button.short_description = "Actions"

    # ------------------------------------------------------------------
    # Bulk actions
    # ------------------------------------------------------------------

    def mark_open(self, request, queryset):
        updated = queryset.update(status=Ticket.Status.OPEN, resolved_at=None)
        self.message_user(request, f"{updated} tickets marked as open.")
    mark_open.short_description = "Mark as Open"

    def mark_pending(self, request, queryset):
        for ticket in queryset:
            ticket.mark_pending()
        self.message_user(request, f"{queryset.count()} tickets marked as pending.")
    mark_pending.short_description = "Mark as Pending"

    def mark_resolved(self, request, queryset):
        for ticket in queryset:
            ticket.mark_resolved(request.user)
        self.message_user(request, f"{queryset.count()} tickets marked as resolved.")
    mark_resolved.short_description = "Mark as Resolved"

    def mark_closed(self, request, queryset):
        for ticket in queryset:
            ticket.mark_closed(request.user)
        self.message_user(request, f"{queryset.count()} tickets closed.")
    mark_closed.short_description = "Close tickets"

    def mark_escalated(self, request, queryset):
        for ticket in queryset:
            ticket.escalate(request.user, "Escalated via admin bulk action")
        self.message_user(request, f"{queryset.count()} tickets escalated.")
    mark_escalated.short_description = "Escalate tickets"

    def set_priority_low(self, request, queryset):
        updated = queryset.update(priority=Ticket.Priority.LOW)
        self.message_user(request, f"{updated} tickets set to Low priority.")
    set_priority_low.short_description = "Set Priority → Low"

    def set_priority_medium(self, request, queryset):
        updated = queryset.update(priority=Ticket.Priority.MEDIUM)
        self.message_user(request, f"{updated} tickets set to Medium priority.")
    set_priority_medium.short_description = "Set Priority → Medium"

    def set_priority_high(self, request, queryset):
        updated = queryset.update(priority=Ticket.Priority.HIGH)
        self.message_user(request, f"{updated} tickets set to High priority.")
    set_priority_high.short_description = "Set Priority → High"

    def set_priority_critical(self, request, queryset):
        updated = queryset.update(priority=Ticket.Priority.CRITICAL)
        self.message_user(request, f"{updated} tickets set to Critical priority.")
    set_priority_critical.short_description = "Set Priority → Critical"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "farmer", "mpp", "transporter",
                "resolved_by", "escalated_to", "created_by",
            )
            .prefetch_related("assigned_to", "comments")
        )


@admin.register(TicketComment, site=ksts_admin)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ("__str__", "ticket", "body_text_preview", "posted_by", "is_internal", "created_at")
    list_filter = ("is_internal", "created_at", "posted_by")
    search_fields = ("body_text", "body_hindi", "ticket__ticket_id")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ["ticket", "posted_by"]

    def body_text_preview(self, obj):
        return obj.body_text[:100] + "..." if len(obj.body_text) > 100 else obj.body_text
    body_text_preview.short_description = "Comment Preview"

    fieldsets = (
        (None, {
            "fields": ("ticket", "posted_by", "is_internal"),
        }),
        ("Comment Content", {
            "fields": ("body_html", "body_text", "body_hindi", "hindi_fallback"),
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(TicketCommentAttachment, site=ksts_admin)
class TicketCommentAttachmentAdmin(admin.ModelAdmin):
    list_display = ("file_name", "file_type", "file_size_display", "comment", "uploaded_by", "uploaded_at")
    list_filter = ("file_type", "uploaded_at")
    search_fields = ("file_name", "comment__ticket__ticket_id")
    readonly_fields = ("uploaded_at",)

    def file_size_display(self, obj):
        return obj.file_size_display
    file_size_display.short_description = "Size"


@admin.register(TicketAttachment, site=ksts_admin)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ("file_name", "file_type", "file_size_display", "ticket", "uploaded_by", "uploaded_at")
    list_filter = ("file_type", "uploaded_at")
    search_fields = ("file_name", "ticket__ticket_id")
    readonly_fields = ("uploaded_at",)

    def file_size_display(self, obj):
        return obj.file_size_display
    file_size_display.short_description = "Size"


@admin.register(TicketActivity, site=ksts_admin)
class TicketActivityAdmin(admin.ModelAdmin):
    list_display = ("__str__", "ticket", "activity_type", "performed_by", "created_at")
    list_filter = ("activity_type", "created_at")
    search_fields = ("ticket__ticket_id", "description")
    readonly_fields = ("created_at",)
    autocomplete_fields = ["ticket", "performed_by", "comment"]

    fieldsets = (
        (None, {
            "fields": ("ticket", "activity_type", "performed_by"),
        }),
        ("Details", {
            "fields": ("description", "comment"),
        }),
        ("State Changes", {
            "fields": (
                "old_status", "new_status",
                "old_priority", "new_priority",
            ),
            "classes": ("collapse",),
        }),
        ("Assignment", {
            "fields": ("assigned_to",),
            "classes": ("collapse",),
        }),
        ("SMS", {
            "fields": ("sms_recipient", "sms_message_preview"),
            "classes": ("collapse",),
        }),
        ("Audit", {
            "fields": ("created_at",),
            "classes": ("collapse",),
        }),
    )


@admin.register(TicketDraft, site=ksts_admin)
class TicketDraftAdmin(admin.ModelAdmin):
    list_display = ("__str__", "drafted_by", "entity_type", "ticket_type", "updated_at")
    list_filter = ("entity_type", "updated_at")
    search_fields = ("drafted_by__email", "ticket_type", "description_en")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ["drafted_by", "farmer", "mpp", "transporter"]

    fieldsets = (
        ("Draft Info", {
            "fields": ("drafted_by", "entity_type", "updated_at"),
        }),
        ("Entity", {
            "fields": ("farmer", "mpp", "transporter"),
        }),
        ("Other Entity", {
            "fields": ("other_caller_name", "other_caller_mobile", "other_caller_location"),
            "classes": ("collapse",),
        }),
        ("Caller Contact", {
            "fields": ("caller_name", "caller_mobile", "caller_relation", "on_behalf_of"),
            "classes": ("collapse",),
        }),
        ("Ticket Details", {
            "fields": ("ticket_type", "priority", "description_en", "description_hi"),
        }),
        ("Assignment", {
            "fields": ("assignee_ids",),
        }),
        ("Timeline", {
            "fields": ("expected_resolution",),
        }),
        ("Snapshot", {
            "fields": ("form_snapshot",),
            "classes": ("collapse",),
        }),
    )


@admin.register(SMSLog, site=ksts_admin)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = (
        "__str__", "recipient_name", "recipient_mobile",
        "delivery_status_badge", "ticket", "sent_by", "sent_at",
    )
    list_filter = ("delivery_status", "sent_at")
    search_fields = ("recipient_mobile", "recipient_name", "message_text", "ticket__ticket_id")
    readonly_fields = ("sent_at",)
    autocomplete_fields = ["ticket", "activity", "sent_by"]

    def delivery_status_badge(self, obj):
        color_map = {
            "queued":    "#FFC107",
            "sent":      "#17A2B8",
            "delivered": "#28A745",
            "failed":    "#DC3545",
            "unknown":   "#6C757D",
        }
        color = color_map.get(obj.delivery_status, "#6C757D")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;">{}</span>',
            color, obj.get_delivery_status_display(),
        )
    delivery_status_badge.short_description = "Status"

    fieldsets = (
        (None, {
            "fields": ("ticket", "activity", "recipient_name", "recipient_mobile"),
        }),
        ("Message", {
            "fields": ("message_text",),
        }),
        ("Delivery", {
            "fields": ("delivery_status", "gateway_response"),
        }),
        ("Audit", {
            "fields": ("sent_by", "sent_at"),
        }),
    )
    
@admin.register(EscalationNotification)
class EscalationNotificationAdmin(admin.ModelAdmin):
    list_display  = ("ticket", "tier1_sent_at", "tier1_recipient",
                        "tier2_sent_at", "tier2_recipient", "updated_at")
    list_filter   = ("tier1_sent_at", "tier2_sent_at")
    search_fields = ("ticket__ticket_id", "tier1_recipient", "tier2_recipient")
    ordering      = ("-updated_at",)
    readonly_fields = (
        "ticket", "tier1_sent_at", "tier1_recipient",
        "tier2_sent_at", "tier2_recipient",
        "created_at", "updated_at",
    )