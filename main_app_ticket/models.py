from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from .managers import CustomUserManager


# ==============================================================================
# CUSTOM USER  (Employee)
# Source: Employee master sheet — all 200+ real records analysed
# ==============================================================================

class CustomUser(AbstractUser):
    """
    Replaces Django's built-in User.
    Email is the login identifier; username is disabled.
    Every employee in the organisation maps to one row here.
    """

    username        = None
    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class EmployeeType(models.TextChoices):
        ASSISTANT          = "Assistant",          "Assistant"
        SR_ASSISTANT       = "Sr. Assistant",      "Sr. Assistant"
        JR_EXECUTIVE       = "Jr. Executive",      "Jr. Executive"
        EXECUTIVE          = "Executive",           "Executive"
        SR_EXECUTIVE       = "Sr. Executive",       "Sr. Executive"
        DY_MANAGER         = "Dy. Manager",         "Dy. Manager"
        ASSISTANT_MANAGER  = "Assistant Manager",   "Assistant Manager"
        MANAGER            = "Manager",             "Manager"
        SR_MANAGER         = "Sr. Manager",         "Sr. Manager"
        MANAGEMENT_TRAINEE = "Management Trainee",  "Management Trainee"
        AREA_OFFICER       = "Area Officer",        "Area Officer"
        OTHER              = "Other",               "Other"

    class Department(models.TextChoices):
        OPERATIONS       = "OPERATIONS",                            "Operations"
        QUALITY          = "QUALITY",                               "Quality"
        PIB_PES          = "PIB & PES",                             "PIB & PES"
        IT_MIS           = "IT & MIS",                              "IT & MIS"
        MIS_STORE        = "MIS & Store",                           "MIS & Store"
        FINANCE_ACCOUNTS = "FINANCE AND ACCOUNTS",                  "Finance and Accounts"
        SALES_MARKETING  = "SALES & MARKETING",                     "Sales & Marketing"
        HUMAN_RESOURCE   = "HUMAN RESOUCE",                         "Human Resource"
        CS_SUPPORT       = "CS & SUPPORT SERVICES",                 "CS & Support Services"
        CS_LEGAL         = "CS, Legal & Business Support Services",  "CS, Legal & Business Support"
        LOGISTICS        = "LOGISTICS",                             "Logistics"
        PURCHASE         = "PURCHASE",                              "Purchase"
        OTHER            = "OTHER",                                 "Other"

    class EmployeeTitle(models.TextChoices):
        FACILITATOR              = "Facilitator",                 "Facilitator"
        AREA_OFFICER             = "Area Officer",                "Area Officer"
        CLUSTER_MANAGER          = "Cluster Manager",             "Cluster Manager"
        ZONAL_MANAGER            = "Zonal Manager",               "Zonal Manager"
        FES_EXECUTIVE            = "FES Executive",               "FES Executive"
        FES_TECHNICIAN           = "FES Technician",              "FES Technician"
        FES                      = "FES",                         "FES"
        DEVELOPMENT_OFFICER      = "Development Officer",         "Development Officer"
        PARA_VET                 = "Para-Vet",                    "Para-Vet"
        ANIMAL_NUTRITION_OFFICER = "Animal Nutrition Officer",    "Animal Nutrition Officer"
        ANIMAL_NUTRITION_SUPVR   = "Animal Nutrition Supervisor", "Animal Nutrition Supervisor"
        OPERATOR                 = "Operator",                    "Operator"
        CHEMIST                  = "Chemist",                     "Chemist"
        MCC_INCHARGE             = "MCC Incharge",                "MCC Incharge"
        BMC_INCHARGE             = "BMC Incharge",                "BMC Incharge"
        AUDIT_COMPLIANCES        = "Audit & Compliances",         "Audit & Compliances"
        OPS_DOCUMENTATION        = "Operations & Documentation",  "Operations & Documentation"
        PIB_OFFICER              = "PIB Officer",                 "PIB Officer"
        VETERINARIAN             = "Veterinarian",                "Veterinarian"
        IT_SUPPORT               = "IT Support",                  "IT Support"
        IT                       = "IT",                          "IT"
        MIS_INCHARGE             = "MIS Incharge",                "MIS Incharge"
        MIS_STORE                = "MIS & Store",                 "MIS & Store"
        MIS                      = "MIS",                         "MIS"
        STORE_KEEPER             = "Store Keeper",                "Store Keeper"
        FINANCE_CUM_STORE        = "Finance Cum Store",           "Finance Cum Store"
        DEPT_IN_CHARGE           = "Department In Charge",        "Department In Charge"
        PROJECTS_REPORTING       = "Projects & Reporting",        "Projects & Reporting"
        ACCOUNT_EXECUTIVE        = "Account Executive",           "Account Executive"
        PAYMENTS                 = "Payments",                    "Payments"
        STORE                    = "Store",                       "Store"
        PURCHASE_ASSISTANT       = "Purchase Assistant",          "Purchase Assistant"
        PRIMARY_SALES_OFFICER    = "Primary Sales Officer",       "Primary Sales Officer"
        SALES_OFFICER            = "Sales Officer",               "Sales Officer"
        SALES_TRAINEE            = "Sales Trainee",               "Sales Trainee"
        SALES_MIS                = "Sales MIS",                   "Sales MIS"
        PAYROLL_TRAINING         = "Payroll & Training",          "Payroll & Training"
        EXEC_ASSISTANT           = "Executive Assistant",         "Executive Assistant"
        HR_HEAD                  = "HR Head",                     "HR Head"
        DOCUMENTATION            = "Documentation",               "Documentation"
        CUSTOMER_CARE_EXEC       = "Customer Care Executive",     "Customer Care Executive"
        HOD                      = "HOD",                         "HOD"
        TRAINEE                  = "Trainee",                     "Trainee"
        MANAGEMENT_TRAINEE       = "Management Trainee",          "Management Trainee"
        ASST_MANAGER             = "Assistant Manager",           "Assistant Manager"
        OTHER                    = "Other",                       "Other"

    class WorkLocation(models.TextChoices):
        AYODHYA_HO      = "Ayodhya H.O.",   "Ayodhya H.O."
        AYODHYA         = "Ayodhya",         "Ayodhya"
        PRATAPGARH      = "Pratapgarh",      "Pratapgarh"
        AKBARPUR        = "Akbarpur",        "Akbarpur"
        BAHRAICH        = "Bahraich",        "Bahraich"
        BALRAMPUR       = "Balrampur",       "Balrampur"
        NAANPARA        = "Naanpara",        "Naanpara"
        COLONELGANJ     = "Colonelganj",     "Colonelganj"
        BADLAPUR        = "Badlapur",        "Badlapur"
        RAJE_SULTANPUR  = "Raje Sultanpur",  "Raje Sultanpur"
        RAMSANEHI_GHAT  = "Ramsanehi Ghat",  "Ramsanehi Ghat"
        RAM_SANEHI_GHAT = "Ram Sanehi Ghat", "Ram Sanehi Ghat"
        SULTANPUR       = "Sultanpur",       "Sultanpur"
        AMETHI          = "Amethi",          "Amethi"
        MAHARAJGANJ     = "Maharajganj",     "Maharajganj"
        MILKIPUR        = "Milkipur",        "Milkipur"
        BARAUSA         = "Barausa",         "Barausa"
        DEEH            = "Deeh",            "Deeh"
        KURWAR          = "Kurwar",          "Kurwar"
        UMRAWAL         = "Umrawal",         "Umrawal"
        MIHIRPURWA      = "Mihirpurwa",      "Mihirpurwa"
        LALGANJ         = "Lalganj",         "Lalganj"
        RAE_BARELI      = "Rae Bareli",      "Rae Bareli"
        BLARAMPUR       = "Blarampur",       "Blarampur"
        OTHER           = "Other",           "Other"

    class AccountStatus(models.TextChoices):
        ACTIVE        = "Active",        "Active"
        YET_TO_CREATE = "Yet to create", "Yet to Create"
        INACTIVE      = "Inactive",      "Inactive"

    # ------------------------------------------------------------------
    # Core identity
    # ------------------------------------------------------------------
    email = models.EmailField(
        unique=True,
        verbose_name="Email Address",
    )
    secondary_email = models.EmailField(
        blank=True, null=True,
        verbose_name="Secondary Email",
    )
    employee_code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Employee Code",
    )
    account_status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
        verbose_name="Account Status",
    )

    # ------------------------------------------------------------------
    # Employee classification
    # ------------------------------------------------------------------
    employee_type = models.CharField(
        max_length=30,
        choices=EmployeeType.choices,
        default=EmployeeType.ASSISTANT,
        verbose_name="Employee Type",
    )
    employee_title = models.CharField(
        max_length=60,
        choices=EmployeeTitle.choices,
        blank=True, null=True,
        verbose_name="Employee Title",
    )
    department = models.CharField(
        max_length=60,
        choices=Department.choices,
        verbose_name="Department",
    )

    # ------------------------------------------------------------------
    # Contact numbers
    # ------------------------------------------------------------------
    mobile_number = models.CharField(
        max_length=20,
        blank=True, null=True,
        verbose_name="Recovery / Primary Mobile",
    )
    work_phone = models.CharField(
        max_length=20,
        blank=True, null=True,
        verbose_name="Work Phone",
    )
    home_phone = models.CharField(
        max_length=20,
        blank=True, null=True,
        verbose_name="Home Phone",
    )

    # ------------------------------------------------------------------
    # Location & reporting hierarchy
    # ------------------------------------------------------------------
    work_address = models.CharField(
        max_length=60,
        choices=WorkLocation.choices,
        blank=True, null=True,
        verbose_name="Work Location",
    )
    manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="subordinates",
        verbose_name="Manager",
        help_text="Resolved from Manager Email column during import",
    )

    # ------------------------------------------------------------------
    # Geo jurisdiction
    # ------------------------------------------------------------------
    jurisdictions = models.ManyToManyField(
        "Tehsil",
        blank=True,
        related_name="assigned_employees",
        verbose_name="Assigned Tehsil Jurisdictions",
        help_text="Tehsils this employee is responsible for (used in KSTS assignment engine)",
    )

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    login_status = models.BooleanField(
        default=True,
        verbose_name="Login Status",
    )
    remark = models.TextField(
        blank=True, null=True,
        verbose_name="Remark",
    )

    class Meta:
        verbose_name        = "Employee"
        verbose_name_plural = "Employees"
        ordering            = ["employee_code"]
        indexes             = [
            models.Index(fields=["employee_code"]),
            models.Index(fields=["department"]),
            models.Index(fields=["work_address"]),
            models.Index(fields=["employee_type"]),
            models.Index(fields=["employee_title"]),
        ]

    def __str__(self):
        return f"{self.get_full_name()} [{self.employee_code}] — {self.employee_title or self.department}"

    @property
    def is_pib_officer(self):
        return self.employee_title == self.EmployeeTitle.PIB_OFFICER

    @property
    def is_cluster_manager(self):
        return self.employee_title == self.EmployeeTitle.CLUSTER_MANAGER

    @property
    def is_area_officer(self):
        return self.employee_title in (
            self.EmployeeTitle.AREA_OFFICER,
            self.EmployeeType.AREA_OFFICER,
        )

    @property
    def is_facilitator(self):
        return self.employee_title == self.EmployeeTitle.FACILITATOR


# ==============================================================================
# GEOGRAPHY MODELS
# ==============================================================================

class State(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class District(models.Model):
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name="districts")
    code  = models.CharField(max_length=10)
    name  = models.CharField(max_length=100)

    class Meta:
        unique_together = ("state", "code")
        ordering        = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Tehsil(models.Model):
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="tehsils")
    code     = models.CharField(max_length=10)
    name     = models.CharField(max_length=100)

    class Meta:
        unique_together = ("district", "code")
        ordering        = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Village(models.Model):
    tehsil = models.ForeignKey(Tehsil, on_delete=models.PROTECT, related_name="villages")
    code   = models.CharField(max_length=20)
    name   = models.CharField(max_length=100)

    class Meta:
        unique_together = ("tehsil", "code")
        ordering        = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Hamlet(models.Model):
    village = models.ForeignKey(Village, on_delete=models.PROTECT, related_name="hamlets")
    code    = models.CharField(max_length=20)
    name    = models.CharField(max_length=100)

    class Meta:
        unique_together = ("village", "code")
        ordering        = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


# ==============================================================================
# DAIRY HIERARCHY  —  Plant → BMC → MCC → MPP
# ==============================================================================

class Plant(models.Model):
    code             = models.CharField(max_length=10, unique=True)
    transaction_code = models.CharField(max_length=10, blank=True, null=True)
    name             = models.CharField(max_length=200)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class BMC(models.Model):
    plant            = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="bmcs")
    code             = models.CharField(max_length=10)
    transaction_code = models.CharField(max_length=10, blank=True, null=True)
    name             = models.CharField(max_length=200)

    class Meta:
        unique_together = ("plant", "code")
        ordering        = ["code"]
        verbose_name    = "BMC"

    def __str__(self):
        return f"{self.name} ({self.code})"


class MCC(models.Model):
    bmc              = models.ForeignKey(BMC, on_delete=models.PROTECT, related_name="mccs")
    code             = models.CharField(max_length=10)
    transaction_code = models.CharField(max_length=10, blank=True, null=True)
    name             = models.CharField(max_length=200)

    class Meta:
        unique_together = ("bmc", "code")
        ordering        = ["code"]
        verbose_name    = "MCC"

    def __str__(self):
        return f"{self.name} ({self.code})"


class MPP(models.Model):

    class Status(models.TextChoices):
        ACTIVE   = "Active",   "Active"
        INACTIVE = "Inactive", "Inactive"
        CLOSED   = "Closed",   "Closed"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="mpps")
    mcc   = models.ForeignKey(MCC,   on_delete=models.PROTECT, related_name="mpps")

    unique_code      = models.CharField(max_length=20, unique=True, verbose_name="MPP Unique Code")
    transaction_code = models.CharField(max_length=10, blank=True, null=True)
    ex_code          = models.CharField(max_length=10, blank=True, null=True)
    name             = models.CharField(max_length=200)
    short_name       = models.CharField(max_length=50,  blank=True, null=True)
    route_name       = models.CharField(max_length=100, blank=True, null=True)
    route_ex_code    = models.CharField(max_length=20,  blank=True, null=True)
    dpu_station_code = models.CharField(max_length=30,  blank=True, null=True)
    dpu_vendor_code  = models.CharField(max_length=30,  blank=True, null=True)

    state    = models.ForeignKey(State,    on_delete=models.PROTECT, related_name="mpps")
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="mpps")
    tehsil   = models.ForeignKey(Tehsil,   on_delete=models.PROTECT, related_name="mpps")
    village  = models.ForeignKey(Village,  on_delete=models.PROTECT, related_name="mpps")
    hamlet   = models.ForeignKey(Hamlet,   on_delete=models.PROTECT, related_name="mpps",
                                 null=True, blank=True)
    pincode       = models.CharField(max_length=10, blank=True, null=True)
    mobile_number = models.CharField(max_length=15, blank=True, null=True)

    opening_date         = models.DateField(null=True, blank=True)
    closing_date         = models.DateField(null=True, blank=True)
    force_stop_new_share = models.BooleanField(default=False)
    status               = models.CharField(
        max_length=10, choices=Status.choices,
        default=Status.ACTIVE,
    )

    assigned_sahayak = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="assigned_mpps",
        verbose_name="Assigned Sahayak",
        help_text="The Facilitator/field worker responsible for this MPP",
    )

    class Meta:
        ordering     = ["unique_code"]
        verbose_name = "MPP"

    def __str__(self):
        return f"{self.name} ({self.unique_code})"


# ==============================================================================
# FARMER MODEL
# ==============================================================================

class Farmer(models.Model):

    class Gender(models.TextChoices):
        MALE   = "Male",   "Male"
        FEMALE = "Female", "Female"
        OTHER  = "Other",  "Other"

    class CasteCategory(models.TextChoices):
        GENERAL = "General", "General"
        OBC     = "OBC",     "OBC"
        SC      = "SC",      "SC"
        ST      = "ST",      "ST"
        OTHER   = "Other",   "Other"

    class Qualification(models.TextChoices):
        ILLITERATE   = "Illiterate",    "Illiterate"
        PRIMARY      = "Primary",       "Primary"
        MIDDLE       = "Middle",        "Middle"
        HIGH_SCHOOL  = "High School",   "High School"
        INTERMEDIATE = "Intermediate",  "Intermediate"
        GRADUATE     = "Graduate",      "Graduate"
        POST_GRAD    = "Post Graduate", "Post Graduate"
        OTHER        = "Other",         "Other"

    class MemberRelation(models.TextChoices):
        SELF    = "Self",    "Self"
        HUSBAND = "Husband", "Husband"
        WIFE    = "Wife",    "Wife"
        FATHER  = "Father",  "Father"
        MOTHER  = "Mother",  "Mother"
        SON     = "Son",     "Son"
        OTHER   = "Other",   "Other"

    class MemberType(models.TextChoices):
        NONE    = "NONE",    "None"
        REGULAR = "REGULAR", "Regular"
        PREMIUM = "PREMIUM", "Premium"

    class ApprovalStatus(models.TextChoices):
        PENDING  = "Pending",  "Pending"
        APPROVED = "Approved", "Approved"
        REJECTED = "Rejected", "Rejected"

    class MemberStatus(models.TextChoices):
        ACTIVE    = "ACTIVE",    "Active"
        INACTIVE  = "INACTIVE",  "Inactive"
        CANCELLED = "CANCELLED", "Cancelled"
        SUSPENDED = "SUSPENDED", "Suspended"

    class PaymentMode(models.TextChoices):
        CASH   = "CASH",   "Cash"
        DD     = "DD",     "Demand Draft"
        CHEQUE = "CHEQUE", "Cheque"
        ONLINE = "ONLINE", "Online Transfer"

    # Registration
    form_number        = models.CharField(max_length=20, unique=True,  verbose_name="Form Number")
    unique_member_code = models.CharField(max_length=30, unique=True,  verbose_name="Unique Member Code")
    member_tr_code     = models.CharField(max_length=30, blank=True, null=True)
    member_ex_code     = models.CharField(max_length=10, blank=True, null=True)

    # Personal
    member_name     = models.CharField(max_length=200, verbose_name="Member Name")
    father_name     = models.CharField(max_length=200, blank=True, null=True)
    member_relation = models.CharField(max_length=20, choices=MemberRelation.choices, blank=True, null=True)
    gender          = models.CharField(max_length=10, choices=Gender.choices)
    age             = models.PositiveSmallIntegerField(blank=True, null=True)
    birth_date      = models.DateField(blank=True, null=True)
    caste_category  = models.CharField(max_length=10, choices=CasteCategory.choices, blank=True, null=True)
    qualification   = models.CharField(max_length=20, choices=Qualification.choices, blank=True, null=True)
    aadhar_no       = models.CharField(max_length=16, blank=True, null=True, verbose_name="Aadhaar Number")

    # Contact
    mobile_no = models.CharField(max_length=15, blank=True, null=True)
    phone_no  = models.CharField(max_length=15, blank=True, null=True)

    # Address
    house_no    = models.CharField(max_length=50, blank=True, null=True)
    hamlet      = models.ForeignKey(Hamlet,   on_delete=models.PROTECT, related_name="farmers", null=True, blank=True)
    village     = models.ForeignKey(Village,  on_delete=models.PROTECT, related_name="farmers")
    post_office = models.CharField(max_length=100, blank=True, null=True)
    tehsil      = models.ForeignKey(Tehsil,   on_delete=models.PROTECT, related_name="farmers")
    district    = models.ForeignKey(District, on_delete=models.PROTECT, related_name="farmers")
    state       = models.ForeignKey(State,    on_delete=models.PROTECT, related_name="farmers")
    pincode     = models.CharField(max_length=10, blank=True, null=True)

    # MPP
    mpp = models.ForeignKey(MPP, on_delete=models.PROTECT, related_name="farmers", verbose_name="Associated MPP")

    # Livestock — Heifer
    cow_heifer_no       = models.PositiveSmallIntegerField(default=0)
    buffalo_heifer_no   = models.PositiveSmallIntegerField(default=0)
    mix_heifer_no       = models.PositiveSmallIntegerField(default=0)
    desi_cow_heifer_no  = models.PositiveSmallIntegerField(default=0)
    crossbred_heifer_no = models.PositiveSmallIntegerField(default=0)

    # Livestock — Dry
    cow_dry_no          = models.PositiveSmallIntegerField(default=0)
    buffalo_dry_no      = models.PositiveSmallIntegerField(default=0)
    mix_dry_no          = models.IntegerField(default=0)
    desi_cow_dry_no     = models.PositiveSmallIntegerField(default=0)
    crossbred_dry_no    = models.PositiveSmallIntegerField(default=0)

    # Livestock — Total
    cow_animal_nos       = models.PositiveSmallIntegerField(default=0)
    buffalo_animal_nos   = models.PositiveSmallIntegerField(default=0)
    mix_animal_nos       = models.PositiveSmallIntegerField(default=0)
    desi_cow_animal_nos  = models.PositiveSmallIntegerField(default=0)
    crossbred_animal_nos = models.PositiveSmallIntegerField(default=0)

    # Milk
    lpd_no                = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name="Litres Per Day")
    household_consumption = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    market_consumption    = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Bank
    accountant_name    = models.CharField(max_length=200, blank=True, null=True)
    bank_account_no    = models.CharField(max_length=30,  blank=True, null=True)
    member_bank_name   = models.CharField(max_length=200, blank=True, null=True)
    member_branch_name = models.CharField(max_length=200, blank=True, null=True)
    ifsc               = models.CharField(max_length=15,  blank=True, null=True, verbose_name="IFSC Code")

    # Nominee
    nominee_name     = models.CharField(max_length=200, blank=True, null=True)
    nominee_relation = models.CharField(max_length=50,  blank=True, null=True)
    nominee_address  = models.CharField(max_length=255, blank=True, null=True)

    # Particular-1
    particular1_name     = models.CharField(max_length=200, blank=True, null=True)
    particular1_gender   = models.CharField(max_length=10, choices=Gender.choices, blank=True, null=True)
    particular1_age      = models.PositiveSmallIntegerField(blank=True, null=True)
    particular1_relation = models.CharField(max_length=50,  blank=True, null=True)

    # Guardian
    guardian_name     = models.CharField(max_length=200, blank=True, null=True)
    member_family_age = models.PositiveSmallIntegerField(blank=True, null=True)

    # Membership
    member_type   = models.CharField(max_length=10, choices=MemberType.choices, default=MemberType.NONE)
    admission_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    share_qty     = models.PositiveIntegerField(default=0)
    paid_amount   = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Payment
    depositor_bank_name   = models.CharField(max_length=200, blank=True, null=True)
    depositor_branch_name = models.CharField(max_length=200, blank=True, null=True)
    dd_no                 = models.CharField(max_length=30, blank=True, null=True, verbose_name="DD Number")
    transaction_date      = models.DateField(blank=True, null=True)
    payment_mode          = models.CharField(max_length=10, choices=PaymentMode.choices, blank=True, null=True)
    wef_date              = models.DateField(blank=True, null=True, verbose_name="With Effect From Date")

    # Approval
    approval_status = models.CharField(max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING)
    accepted_by     = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_farmers", verbose_name="Accepted By",
    )
    approval_date = models.DateField(blank=True, null=True)
    member_status = models.CharField(max_length=15, choices=MemberStatus.choices, default=MemberStatus.ACTIVE)
    member_cancellation = models.TextField(blank=True, null=True)

    # Key dates
    enrollment_date              = models.DateField(blank=True, null=True, verbose_name="Member Enrolment Date")
    first_board_approved_meeting = models.DateField(blank=True, null=True)
    last_board_approved_meeting  = models.DateField(blank=True, null=True)

    # Audit
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_farmers", verbose_name="Created By",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Farmer"
        verbose_name_plural = "Farmers"
        ordering            = ["form_number"]
        indexes             = [
            models.Index(fields=["unique_member_code"]),
            models.Index(fields=["mobile_no"]),
            models.Index(fields=["aadhar_no"]),
            models.Index(fields=["member_status"]),
            models.Index(fields=["village"]),
            models.Index(fields=["mpp"]),
            models.Index(fields=["approval_status"]),
        ]

    def __str__(self):
        return f"{self.member_name} ({self.unique_member_code})"

    @property
    def total_animals(self):
        return (
            self.cow_animal_nos + self.buffalo_animal_nos + self.mix_animal_nos
            + self.desi_cow_animal_nos + self.crossbred_animal_nos
        )


# ==============================================================================
# TRANSPORTER MODEL
# ==============================================================================

class Transporter(models.Model):

    class AccountGroup(models.TextChoices):
        ZFMP  = "ZFMP",  "ZFMP — Milk Procurement"
        OTHER = "OTHER", "Other"

    class Incoterm(models.TextChoices):
        EXW   = "EXW",   "EXW — Ex Works"
        FOB   = "FOB",   "FOB — Free on Board"
        CIF   = "CIF",   "CIF — Cost, Insurance & Freight"
        CPT   = "CPT",   "CPT — Carriage Paid To"
        DAP   = "DAP",   "DAP — Delivered at Place"
        DDP   = "DDP",   "DDP — Delivered Duty Paid"
        OTHER = "OTHER", "Other"

    class PaymentMethod(models.TextChoices):
        NEFT   = "N",     "NEFT"
        RTGS   = "R",     "RTGS"
        IMPS   = "M",     "IMPS"
        CHEQUE = "C",     "Cheque"
        DRAFT  = "D",     "Demand Draft"
        Y      = "Y",     "Bank Transfer (Y)"
        OTHER  = "OTHER", "Other"

    vendor_code   = models.CharField(max_length=20, unique=True, verbose_name="Vendor Code")
    account_group = models.CharField(max_length=10, choices=AccountGroup.choices, default=AccountGroup.ZFMP)
    search_term1  = models.CharField(max_length=50, blank=True, null=True)
    search_term2  = models.CharField(max_length=50, blank=True, null=True)

    vendor_name    = models.CharField(max_length=200, verbose_name="Vendor / Transporter Name")
    contact_person = models.CharField(max_length=200, blank=True, null=True)
    contact_no     = models.CharField(max_length=20,  blank=True, null=True, verbose_name="Contact Number")
    email          = models.EmailField(blank=True, null=True)

    address = models.CharField(max_length=255, blank=True, null=True)
    city    = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=10,  blank=True, null=True, default="IN")

    incoterm          = models.CharField(max_length=10, choices=Incoterm.choices, blank=True, null=True)
    incoterm_location = models.CharField(max_length=100, blank=True, null=True, verbose_name="Incoterm Location")

    bank_account_no = models.CharField(max_length=30,  blank=True, null=True, verbose_name="Bank Account Number")
    bank_key        = models.CharField(max_length=20,  blank=True, null=True, verbose_name="Bank Key (IFSC)")
    account_holder  = models.CharField(max_length=200, blank=True, null=True)
    payment_terms   = models.CharField(max_length=10,  blank=True, null=True)
    payment_method  = models.CharField(max_length=10,  choices=PaymentMethod.choices, blank=True, null=True)

    gst_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="GST Number")
    msme       = models.CharField(max_length=30, blank=True, null=True, verbose_name="MSME Registration")
    is_blocked = models.BooleanField(default=False, verbose_name="Blocked in SAP")

    company_code   = models.CharField(max_length=10,  blank=True, null=True, verbose_name="SAP Company Code")
    gl_account     = models.CharField(max_length=20,  blank=True, null=True, verbose_name="G/L Account")
    sap_created_by = models.CharField(max_length=50,  blank=True, null=True, verbose_name="SAP Created By")
    sap_created_on = models.DateField(blank=True, null=True, verbose_name="SAP Created On")
    sap_changed_on = models.DateField(blank=True, null=True, verbose_name="SAP Last Changed On")

    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_transporters", verbose_name="Created By (KSTS)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Transporter"
        verbose_name_plural = "Transporters"
        ordering            = ["vendor_code"]
        indexes             = [
            models.Index(fields=["vendor_code"]),
            models.Index(fields=["gst_number"]),
            models.Index(fields=["bank_account_no"]),
            models.Index(fields=["city"]),
        ]

    def __str__(self):
        return f"{self.vendor_name} ({self.vendor_code})"

    @property
    def pan_from_gst(self):
        if self.gst_number and len(self.gst_number) >= 12:
            return self.gst_number[2:12]
        return None


# ==============================================================================
# TICKET MODEL — KSTS
# ==============================================================================

class Ticket(models.Model):
    """
    Central ticket record for the KSTS caller dashboard.

    Caller relation is polymorphic — exactly ONE of farmer / mpp / transporter
    is populated; the other two are NULL.  For 'Other' tickets the caller
    details are captured in the inline fields below.

    Caller contact details (caller_name, caller_mobile, caller_relation)
    capture the *actual person on the phone*, which may differ from the
    registered entity contact — matching the dashboard's Caller Contact Box.
    """

    class TicketType(models.TextChoices):
        SAHAYAK_COMMISSION      = "Sahayak Commission",                        "Sahayak Commission"
        FAT_SNF_VARIATION       = "FAT/SNF Variation",                         "FAT/SNF Variation"
        RATE_ISSUE              = "Rate Issue",                                 "Rate Issue"
        SAHAYAK_MACHINE_ISSUE   = "Sahayak Machine Issue",                      "Sahayak Machine Issue"
        VARIATION_ISSUE         = "Variation Issue",                            "Variation Issue"
        CATTLE_FEED_ISSUE       = "Cattle Feed Issue",                          "Cattle Feed Issue"
        DOCTOR_VET_ISSUE        = "Doctor/Treatment/Medicinal/Vet Type Issue",  "Doctor/Treatment/Vet Issue"
        LOAN_QUERY              = "Loan Query",                                 "Loan Query"
        CATTLE_INDUCTION_QUERY  = "Cattle Induction Query",                     "Cattle Induction Query"
        SEMEN_QUERY             = "Semen Query",                                "Semen Query"
        SUGAM_APP_ISSUE         = "Sugam App Related Issue",                    "Sugam App Related Issue"
        KISAN_APP_ISSUE         = "Kisan App Related Issue",                    "Kisan App Related Issue"
        NUMBER_UPDATE           = "Number Update",                              "Number Update"
        ACCOUNT_UPDATE          = "Account Update",                             "Account Update"
        OTHERS                  = "Others",                                     "Others"

    class Priority(models.TextChoices):
        LOW      = "low",      "Low"
        MEDIUM   = "medium",   "Medium"
        HIGH     = "high",     "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN      = "open",      "Open"
        PENDING   = "pending",   "Pending"      # awaiting info / action from caller/field
        RESOLVED  = "resolved",  "Resolved"
        CLOSED    = "closed",    "Closed"       # archived — no further comments allowed
        ESCALATED = "escalated", "Escalated"    # critical + requires senior intervention
        REOPENED  = "reopened",  "Reopened"   # ← ADD THIS LINE

    class EntityType(models.TextChoices):
        FARMER      = "farmer",      "Farmer"
        SAHAYAK     = "sahayak",     "Sahayak / MPP"
        TRANSPORTER = "transporter", "Transporter"
        OTHER       = "other",       "Other / General"

    class CallerRelation(models.TextChoices):
        """
        Relation of the actual caller to the registered entity.
        Used in the Caller Contact Box on the dashboard.
        """
        SELF            = "Self",            "Self (Member / Owner calling directly)"
        SON             = "Son",             "Son"
        DAUGHTER        = "Daughter",        "Daughter"
        HUSBAND         = "Husband",         "Husband"
        WIFE            = "Wife",            "Wife"
        FATHER          = "Father",          "Father"
        MOTHER          = "Mother",          "Mother"
        BROTHER         = "Brother",         "Brother"
        SISTER          = "Sister",          "Sister"
        NEIGHBOUR       = "Neighbour",       "Neighbour"
        OTHER_RELATIVE  = "Other Relative",  "Other Relative"
        MPP_OPERATOR    = "MPP Operator",    "MPP Operator"
        MPP_OWNER       = "MPP Owner",       "MPP Owner"
        MPP_ASSISTANT   = "MPP Assistant",   "MPP Assistant"
        DRIVER          = "Driver",          "Driver"
        ACCOUNTANT      = "Accountant",      "Accountant"
        STAFF_MEMBER    = "Staff Member",    "Staff Member"
        AGENT           = "Agent",           "Agent"
        OTHER           = "Other",           "Other"

    # ------------------------------------------------------------------
    # Ticket identity
    # ------------------------------------------------------------------
    ticket_id = models.CharField(
        max_length=30, unique=True, editable=False,
        verbose_name="Ticket ID",
        help_text="Auto-generated: TKT-YYYY-NNNNNN",
    )

    # ------------------------------------------------------------------
    # Entity (registered party) — exactly one FK is non-null
    # ------------------------------------------------------------------
    entity_type = models.CharField(
        max_length=15, choices=EntityType.choices,
        verbose_name="Entity Type",
    )
    farmer      = models.ForeignKey(
        Farmer, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tickets", verbose_name="Farmer",
    )
    mpp         = models.ForeignKey(
        MPP, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tickets", verbose_name="Sahayak / MPP",
    )
    transporter = models.ForeignKey(
        Transporter, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tickets", verbose_name="Transporter",
    )

    # ------------------------------------------------------------------
    # 'Other' entity inline fields
    # ------------------------------------------------------------------
    other_caller_name     = models.CharField(max_length=200, blank=True, null=True, verbose_name="Caller Name")
    other_caller_mobile   = models.CharField(max_length=20,  blank=True, null=True, verbose_name="Caller Mobile")
    other_caller_location = models.CharField(max_length=200, blank=True, null=True, verbose_name="Caller Location / Village")

    # ------------------------------------------------------------------
    # Actual caller contact  (may differ from registered entity contact)
    # Captured via the "Caller Contact Box" on the dashboard.
    # ------------------------------------------------------------------
    caller_mobile   = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name="Actual Caller Mobile",
        help_text="The mobile number the call was actually received from. "
                  "May differ from the registered entity contact.",
    )
    caller_name     = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name="Actual Caller Name",
        help_text="Name of the person who actually called (e.g. son, wife, driver).",
    )
    caller_relation = models.CharField(
        max_length=30, choices=CallerRelation.choices,
        blank=True, null=True,
        verbose_name="Caller's Relation to Entity",
        help_text="Relationship of the actual caller to the registered farmer/MPP/transporter.",
    )
    on_behalf_of    = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name="On Behalf Of",
        help_text="Used for 'Other' entity type: who the caller is calling on behalf of.",
    )

    # ------------------------------------------------------------------
    # Ticket classification
    # ------------------------------------------------------------------
    ticket_type = models.CharField(
        max_length=60, choices=TicketType.choices,
        verbose_name="Ticket Type",
    )
    priority = models.CharField(
        max_length=10, choices=Priority.choices,
        default=Priority.MEDIUM,
        verbose_name="Priority",
    )
    status = models.CharField(
        max_length=15, choices=Status.choices,
        default=Status.OPEN,
        verbose_name="Status",
    )

    # ------------------------------------------------------------------
    # Issue description — English + Hindi (auto-translated on dashboard)
    # ------------------------------------------------------------------
    description_en = models.TextField(
        blank=True, null=True,
        verbose_name="Issue Description (English)",
    )
    description_hi = models.TextField(
        blank=True, null=True,
        verbose_name="Issue Description (Hindi — auto-translated)",
    )

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------
    assigned_to = models.ManyToManyField(
        CustomUser,
        blank=True,
        related_name="assigned_tickets",
        verbose_name="Assigned To",
        help_text="One or more employees responsible for resolving this ticket",
    )

    # ------------------------------------------------------------------
    # Resolution timeline
    # ------------------------------------------------------------------
    expected_resolution_date = models.DateField(
        blank=True, null=True,
        verbose_name="Expected Resolution Date",
    )
    resolved_at = models.DateTimeField(
        blank=True, null=True,
        verbose_name="Resolved At",
    )
    resolved_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="resolved_tickets", verbose_name="Resolved By",
    )

    # ------------------------------------------------------------------
    # Escalation
    # ------------------------------------------------------------------
    is_escalated = models.BooleanField(default=False, verbose_name="Escalated")
    escalated_to = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="escalated_tickets", verbose_name="Escalated To",
    )
    escalated_at = models.DateTimeField(blank=True, null=True)
    escalation_reason = models.TextField(
        blank=True, null=True,
        verbose_name="Escalation Reason",
        help_text="Why this ticket was escalated.",
    )

    # ------------------------------------------------------------------
    # SMS tracking
    # ------------------------------------------------------------------
    sms_sent_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="SMS Sent Count",
        help_text="Total SMS notifications sent for this ticket.",
    )
    last_sms_sent_at = models.DateTimeField(
        blank=True, null=True,
        verbose_name="Last SMS Sent At",
    )

    # ------------------------------------------------------------------
    # System audit
    # ------------------------------------------------------------------
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_tickets", verbose_name="Created By (Caller)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Ticket"
        verbose_name_plural = "Tickets"
        ordering            = ["-created_at"]
        indexes             = [
            models.Index(fields=["ticket_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["ticket_type"]),
            models.Index(fields=["entity_type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["farmer"]),
            models.Index(fields=["mpp"]),
            models.Index(fields=["transporter"]),
            models.Index(fields=["is_escalated"]),
            models.Index(fields=["resolved_at"]),
            models.Index(fields=["expected_resolution_date"]),
        ]

    def __str__(self):
        return f"{self.ticket_id} — {self.get_ticket_type_display()} [{self.get_status_display()}]"

    def save(self, *args, **kwargs):
        """Auto-generate ticket_id on first save: TKT-YYYY-NNNNNN."""
        if not self.ticket_id:
            year = timezone.now().year
            last = (
                Ticket.objects.filter(ticket_id__startswith=f"TKT-{year}-")
                .order_by("ticket_id")
                .last()
            )
            seq = 1
            if last:
                try:
                    seq = int(last.ticket_id.split("-")[-1]) + 1
                except (ValueError, IndexError):
                    seq = 1
            self.ticket_id = f"TKT-{year}-{seq:06d}"
        super().save(*args, **kwargs)

    def mark_resolved(self, resolved_by_user):
        """Convenience: resolve a ticket cleanly."""
        self.status      = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        self.resolved_by = resolved_by_user
        self.save(update_fields=["status", "resolved_at", "resolved_by", "updated_at"])

    def mark_pending(self):
        """Move ticket to Pending (awaiting response or field action)."""
        self.status = self.Status.PENDING
        self.save(update_fields=["status", "updated_at"])

    def mark_closed(self, closed_by_user=None):
        """Close ticket — no further comments permitted after this."""
        self.status = self.Status.CLOSED
        if closed_by_user and not self.resolved_by:
            self.resolved_by = closed_by_user
        if not self.resolved_at:
            self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolved_by", "resolved_at", "updated_at"])

    def reopen(self):
        """Reopen a resolved or closed ticket — marks as Reopened, not Open."""
        self.status      = self.Status.REOPENED   # ← was self.Status.OPEN
        self.resolved_at = None
        self.resolved_by = None
        self.save(update_fields=["status", "resolved_at", "resolved_by", "updated_at"])

    def escalate(self, escalated_to_user, reason=""):
        """Escalate ticket."""
        self.is_escalated     = True
        self.status           = self.Status.ESCALATED
        self.escalated_to     = escalated_to_user
        self.escalated_at     = timezone.now()
        self.escalation_reason = reason
        self.save(update_fields=[
            "is_escalated", "status", "escalated_to",
            "escalated_at", "escalation_reason", "updated_at",
        ])

    def log_sms(self):
        """Increment SMS counter."""
        self.sms_sent_count  += 1
        self.last_sms_sent_at = timezone.now()
        self.save(update_fields=["sms_sent_count", "last_sms_sent_at", "updated_at"])

    @property
    def is_overdue(self):
        if self.expected_resolution_date and self.status in (
            self.Status.OPEN, self.Status.PENDING, self.Status.REOPENED  # ← add REOPENED
        ):
            return timezone.now().date() > self.expected_resolution_date
        return False

    @property
    def caller_display_name(self):
        """Human-readable caller name regardless of entity type."""
        if self.farmer:
            return self.farmer.member_name
        if self.mpp:
            return self.mpp.name
        if self.transporter:
            return self.transporter.vendor_name
        return self.other_caller_name or "Unknown Caller"

    @property
    def caller_location(self):
        """Short location string for list views."""
        if self.farmer:
            return f"{self.farmer.village}, {self.farmer.tehsil}"
        if self.mpp:
            return f"{self.mpp.village}, {self.mpp.district}"
        if self.transporter:
            return self.transporter.city or "—"
        return self.other_caller_location or "—"

    @property
    def caller_contact_mobile(self):
        """
        The best mobile number to call back.
        Prefers the actual caller mobile (from Caller Contact Box);
        falls back to the entity's registered mobile.
        """
        if self.caller_mobile:
            return self.caller_mobile
        if self.farmer:
            return self.farmer.mobile_no
        if self.mpp:
            return self.mpp.mobile_number
        if self.transporter:
            return self.transporter.contact_no
        return self.other_caller_mobile


# ==============================================================================
# TICKET COMMENT
# Rich-text comment (HTML from contenteditable) + Hindi auto-translation.
# One row per comment event.  Attachments are linked via TicketCommentAttachment.
# Matches the "Rich Comment Box" in my_tickets.html.
# ==============================================================================

class TicketComment(models.Model):
    """
    A comment posted by an employee on a ticket.

    body_html     — The formatted English content (innerHTML from the rich editor).
    body_text     — Plain-text version of body_html (for search / SMS).
    body_hindi    — Auto-translated Hindi text (from Google Translate API on the frontend).
    hindi_fallback— True when translation was unavailable and body_hindi contains raw English.
    """

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Ticket",
    )
    body_html = models.TextField(
        verbose_name="Comment Body (HTML)",
        help_text="Rich-text HTML produced by the contenteditable editor.",
    )
    body_text = models.TextField(
        blank=True,
        verbose_name="Comment Body (Plain Text)",
        help_text="Stripped plain-text version for search and SMS previews.",
    )
    body_hindi = models.TextField(
        blank=True, null=True,
        verbose_name="Comment Body (Hindi — auto-translated)",
        help_text="Google Translate output captured on the frontend before submission.",
    )
    hindi_fallback = models.BooleanField(
        default=False,
        verbose_name="Hindi Fallback",
        help_text="True when translation was unavailable; body_hindi contains the raw English text.",
    )
    posted_by  = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ticket_comments",
        verbose_name="Posted By",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_internal = models.BooleanField(
        default=False,
        verbose_name="Internal Note",
        help_text="If True, this comment is only visible to employees, not to the caller.",
    )

    class Meta:
        ordering     = ["created_at"]
        verbose_name = "Ticket Comment"
        verbose_name_plural = "Ticket Comments"

    def __str__(self):
        actor = self.posted_by.get_full_name() if self.posted_by else "System"
        return f"Comment on {self.ticket.ticket_id} by {actor} [{self.created_at:%Y-%m-%d %H:%M}]"


# ==============================================================================
# TICKET COMMENT ATTACHMENT
# Files staged and submitted via the Rich Comment Box drag-and-drop zone.
# ==============================================================================

def comment_attachment_upload_path(instance, filename):
    """Store files at:  tickets/<ticket_id>/comments/<comment_pk>/<filename>"""
    return f"tickets/{instance.comment.ticket.ticket_id}/comments/{instance.comment.pk}/{filename}"


class TicketCommentAttachment(models.Model):
    """
    One file attached to a TicketComment.
    Supports images (viewable inline as thumbnails), PDFs, Office docs, archives.
    Max file size enforced on the frontend (20 MB).
    """

    class FileType(models.TextChoices):
        IMAGE = "image", "Image"
        PDF   = "pdf",   "PDF"
        WORD  = "word",  "Word Document"
        EXCEL = "excel", "Excel / CSV"
        PPT   = "ppt",   "PowerPoint"
        ZIP   = "zip",   "Archive (ZIP / RAR)"
        VIDEO = "video", "Video"
        OTHER = "other", "Other"

    comment   = models.ForeignKey(
        TicketComment, on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Comment",
    )
    file           = models.FileField(upload_to=comment_attachment_upload_path)
    file_name      = models.CharField(max_length=255, verbose_name="Original Filename")
    file_type      = models.CharField(max_length=10, choices=FileType.choices, default=FileType.OTHER)
    file_size_bytes= models.PositiveIntegerField(default=0, verbose_name="File Size (bytes)")
    mime_type      = models.CharField(max_length=100, blank=True, null=True, verbose_name="MIME Type")
    uploaded_by    = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="comment_attachments",
    )
    uploaded_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering     = ["uploaded_at"]
        verbose_name = "Comment Attachment"
        verbose_name_plural = "Comment Attachments"

    def __str__(self):
        return f"{self.file_name} → {self.comment.ticket.ticket_id}"

    @property
    def is_image(self):
        return self.file_type == self.FileType.IMAGE

    @property
    def file_size_display(self):
        b = self.file_size_bytes
        if b < 1024:
            return f"{b} B"
        if b < 1_048_576:
            return f"{b / 1024:.1f} KB"
        return f"{b / 1_048_576:.1f} MB"


# ==============================================================================
# TICKET ATTACHMENT  (top-level, attached at ticket creation time)
# Files uploaded via the drag-and-drop dropzone on the Create Ticket form.
# ==============================================================================

def ticket_attachment_upload_path(instance, filename):
    """Store files at:  tickets/<ticket_id>/<filename>"""
    return f"tickets/{instance.ticket.ticket_id}/{filename}"


class TicketAttachment(models.Model):
    """
    One row per file attached directly to a ticket (not to a comment).
    Uploaded via the Create Ticket / Edit Ticket dropzone.
    """

    class FileType(models.TextChoices):
        IMAGE = "image", "Image"
        PDF   = "pdf",   "PDF"
        WORD  = "word",  "Word Document"
        EXCEL = "excel", "Excel / CSV"
        PPT   = "ppt",   "PowerPoint"
        ZIP   = "zip",   "Archive (ZIP / RAR)"
        VIDEO = "video", "Video"
        OTHER = "other", "Other"

    ticket          = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="attachments")
    file            = models.FileField(upload_to=ticket_attachment_upload_path)
    file_name       = models.CharField(max_length=255)
    file_type       = models.CharField(max_length=10, choices=FileType.choices, default=FileType.OTHER)
    file_size_bytes = models.PositiveIntegerField(default=0, verbose_name="File Size (bytes)")
    mime_type       = models.CharField(max_length=100, blank=True, null=True)
    uploaded_by     = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="uploaded_attachments",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering     = ["uploaded_at"]
        verbose_name = "Ticket Attachment"

    def __str__(self):
        return f"{self.file_name} → {self.ticket.ticket_id}"

    @property
    def is_image(self):
        return self.file_type == self.FileType.IMAGE
    
    @property
    def file_size_display(self):
        """Return human-readable file size."""
        b = self.file_size_bytes
        if b < 1024:
            return f"{b} B"
        if b < 1_048_576:
            return f"{b / 1024:.1f} KB"
        return f"{b / 1_048_576:.1f} MB"


# ==============================================================================
# TICKET ACTIVITY LOG
# Immutable, append-only timeline — feeds the Activity Timeline panel and
# the timeline in the Ticket Detail Modal on both home.html and my_tickets.html.
# ==============================================================================

class TicketActivity(models.Model):
    """
    One row = one timeline event.

    All activity types from both templates are covered:
      created, assigned, reassigned, status_change, priority_change,
      comment, attachment, escalated, resolved, reopened, sms_sent,
      pending, closed, other.

    For comment events the related TicketComment FK is populated so the
    activity timeline can render the Hindi bubble and file chips directly.
    """

    class ActivityType(models.TextChoices):
        CREATED         = "created",         "Ticket Created"
        ASSIGNED        = "assigned",        "Assigned"
        REASSIGNED      = "reassigned",      "Reassigned"
        STATUS_CHANGE   = "status_change",   "Status Changed"
        PRIORITY_CHANGE = "priority_change", "Priority Changed"
        COMMENT         = "comment",         "Comment Added"
        ATTACHMENT      = "attachment",      "Attachment Added"
        ESCALATED       = "escalated",       "Escalated"
        RESOLVED        = "resolved",        "Resolved"
        REOPENED        = "reopened",        "Reopened"
        PENDING         = "pending",         "Marked Pending"
        CLOSED          = "closed",          "Closed"
        SMS_SENT        = "sms_sent",        "SMS Sent"
        OTHER           = "other",           "Other"

    ticket        = models.ForeignKey(
        Ticket, on_delete=models.CASCADE,
        related_name="activities",
    )
    activity_type = models.CharField(
        max_length=20, choices=ActivityType.choices,
    )
    performed_by  = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ticket_activities",
    )
    description   = models.TextField(
        blank=True, null=True,
        help_text="Human-readable description shown in the timeline",
    )

    # Linked comment (populated for comment / attachment events)
    comment = models.ForeignKey(
        TicketComment, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="activity_events",
        verbose_name="Related Comment",
        help_text="Populated when activity_type is 'comment' or 'attachment'.",
    )

    # For assignment / reassignment events
    assigned_to = models.ManyToManyField(
        CustomUser, blank=True,
        related_name="activity_assignments",
        verbose_name="Assigned To (this event)",
    )

    # For status change events
    old_status  = models.CharField(max_length=15, choices=Ticket.Status.choices, blank=True, null=True)
    new_status  = models.CharField(max_length=15, choices=Ticket.Status.choices, blank=True, null=True)

    # For priority change events
    old_priority = models.CharField(max_length=10, choices=Ticket.Priority.choices, blank=True, null=True)
    new_priority = models.CharField(max_length=10, choices=Ticket.Priority.choices, blank=True, null=True)

    # For SMS events
    sms_recipient = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name="SMS Recipient Mobile",
    )
    sms_message_preview = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name="SMS Message Preview",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ["created_at"]
        verbose_name        = "Ticket Activity"
        verbose_name_plural = "Ticket Activities"
        indexes             = [
            models.Index(fields=["ticket", "created_at"]),
            models.Index(fields=["activity_type"]),
        ]

    def __str__(self):
        actor = self.performed_by.get_full_name() if self.performed_by else "System"
        return f"[{self.ticket.ticket_id}] {self.get_activity_type_display()} by {actor}"


# ==============================================================================
# TICKET DRAFT
# "Save Draft" button stores partial form state before final submission.
# ==============================================================================

class TicketDraft(models.Model):
    """
    Transient draft saved from the "Save Draft" button on the Create Ticket form.
    Stores the form payload as JSON so any partial state can be restored.
    Promoted to a full Ticket on "Submit"; the draft row is then deleted.
    """

    drafted_by  = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE,
        related_name="ticket_drafts",
    )
    entity_type = models.CharField(
        max_length=15, choices=Ticket.EntityType.choices,
        blank=True, null=True,
    )
    # Snapshot FKs — nullable because the form may be incomplete
    farmer      = models.ForeignKey(Farmer,      on_delete=models.SET_NULL, null=True, blank=True)
    mpp         = models.ForeignKey(MPP,          on_delete=models.SET_NULL, null=True, blank=True)
    transporter = models.ForeignKey(Transporter,  on_delete=models.SET_NULL, null=True, blank=True)

    ticket_type         = models.CharField(max_length=60, blank=True, null=True)
    priority            = models.CharField(max_length=10, blank=True, null=True)
    description_en      = models.TextField(blank=True, null=True)
    description_hi      = models.TextField(blank=True, null=True)
    assignee_ids        = models.JSONField(default=list, blank=True, verbose_name="Assignee Employee IDs (JSON list)")
    expected_resolution = models.DateField(blank=True, null=True)

    # Caller contact box snapshot
    caller_name     = models.CharField(max_length=200, blank=True, null=True)
    caller_mobile   = models.CharField(max_length=20,  blank=True, null=True)
    caller_relation = models.CharField(max_length=30,  blank=True, null=True)
    on_behalf_of    = models.CharField(max_length=200, blank=True, null=True)

    # Other entity inline fields
    other_caller_name     = models.CharField(max_length=200, blank=True, null=True)
    other_caller_mobile   = models.CharField(max_length=20,  blank=True, null=True)
    other_caller_location = models.CharField(max_length=200, blank=True, null=True)

    # Full form snapshot for complete restore
    form_snapshot = models.JSONField(default=dict, blank=True, verbose_name="Full Form Snapshot (JSON)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ticket Draft"
        ordering     = ["-updated_at"]

    def __str__(self):
        return f"Draft by {self.drafted_by.get_full_name()} [{self.updated_at:%Y-%m-%d %H:%M}]"

    def promote_to_ticket(self):
        """
        Convert this draft into a real Ticket.
        Returns the newly created Ticket instance.
        """
        ticket = Ticket.objects.create(
            entity_type      = self.entity_type or Ticket.EntityType.OTHER,
            farmer           = self.farmer,
            mpp              = self.mpp,
            transporter      = self.transporter,
            ticket_type      = self.ticket_type or Ticket.TicketType.OTHERS,
            priority         = self.priority    or Ticket.Priority.MEDIUM,
            description_en   = self.description_en,
            description_hi   = self.description_hi,
            expected_resolution_date = self.expected_resolution,
            created_by       = self.drafted_by,
            # Caller contact
            caller_name      = self.caller_name,
            caller_mobile    = self.caller_mobile,
            caller_relation  = self.caller_relation,
            on_behalf_of     = self.on_behalf_of,
            # Other entity inline
            other_caller_name     = self.other_caller_name,
            other_caller_mobile   = self.other_caller_mobile,
            other_caller_location = self.other_caller_location,
        )

        # Re-attach assignees
        if self.assignee_ids:
            employees = CustomUser.objects.filter(employee_code__in=self.assignee_ids)
            ticket.assigned_to.set(employees)

        # Log the creation event
        activity = TicketActivity.objects.create(
            ticket        = ticket,
            activity_type = TicketActivity.ActivityType.CREATED,
            performed_by  = self.drafted_by,
            description   = "Ticket promoted from draft",
            new_status    = Ticket.Status.OPEN,
        )
        if self.assignee_ids:
            employees = CustomUser.objects.filter(employee_code__in=self.assignee_ids)
            activity.assigned_to.set(employees)
            TicketActivity.objects.create(
                ticket        = ticket,
                activity_type = TicketActivity.ActivityType.ASSIGNED,
                performed_by  = self.drafted_by,
                description   = f"Assigned to {', '.join(e.get_full_name() for e in employees)}",
            )

        self.delete()   # draft consumed
        return ticket


# ==============================================================================
# SMS LOG
# Records every SMS dispatched from the KSTS system.
# Referenced by TicketActivity (sms_sent) and surfaced in the timeline.
# ==============================================================================

class SMSLog(models.Model):
    """
    One row per SMS sent.  Linked to the ticket and optionally to a specific
    activity event for full audit trail.
    """

    class DeliveryStatus(models.TextChoices):
        QUEUED    = "queued",    "Queued"
        SENT      = "sent",      "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED    = "failed",    "Failed"
        UNKNOWN   = "unknown",   "Unknown"

    ticket          = models.ForeignKey(
        Ticket, on_delete=models.CASCADE,
        related_name="sms_logs",
        verbose_name="Ticket",
    )
    activity        = models.ForeignKey(
        TicketActivity, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="sms_logs",
        verbose_name="Related Activity Event",
    )
    recipient_name   = models.CharField(max_length=200, blank=True, null=True)
    recipient_mobile = models.CharField(max_length=20, verbose_name="Recipient Mobile")
    message_text     = models.TextField(verbose_name="Message Text")
    delivery_status  = models.CharField(
        max_length=15, choices=DeliveryStatus.choices,
        default=DeliveryStatus.QUEUED,
    )
    gateway_response = models.TextField(
        blank=True, null=True,
        verbose_name="Gateway Response",
        help_text="Raw response from the SMS gateway API.",
    )
    sent_by  = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="sent_sms",
        verbose_name="Sent By",
    )
    sent_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering     = ["-sent_at"]
        verbose_name = "SMS Log"
        verbose_name_plural = "SMS Logs"
        indexes      = [
            models.Index(fields=["ticket", "sent_at"]),
            models.Index(fields=["recipient_mobile"]),
            models.Index(fields=["delivery_status"]),
        ]

    def __str__(self):
        return f"SMS to {self.recipient_mobile} [{self.get_delivery_status_display()}] — {self.ticket.ticket_id}"
    
class EscalationNotification(models.Model):
    ''''Tracks tier-1 (manager) and tier-2 (C.E.) escalation notifications
    that have been dispatched for a ticket.  One row per ticket.'''
 
    ticket = models.OneToOneField(
        Ticket,
        on_delete=models.CASCADE,
        related_name="escalation_notification",
        verbose_name="Ticket",
    )
 
    # Tier-1 (Reporting Manager)
    tier1_sent_at   = models.DateTimeField(null=True, blank=True, verbose_name="Tier-1 Sent At")
    tier1_recipient = models.EmailField(null=True, blank=True, verbose_name="Tier-1 Recipient (Manager)")
 
    # Tier-2 (C.E.)
    tier2_sent_at   = models.DateTimeField(null=True, blank=True, verbose_name="Tier-2 Sent At")
    tier2_recipient = models.EmailField(null=True, blank=True, verbose_name="Tier-2 Recipient (C.E.)")
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        verbose_name        = "Escalation Notification"
        verbose_name_plural = "Escalation Notifications"
        ordering            = ["-updated_at"]
        indexes             = [
            models.Index(fields=["tier1_sent_at"]),
            models.Index(fields=["tier2_sent_at"]),
        ]
 
    def __str__(self):
        parts = []
        if self.tier1_sent_at:
            parts.append(f"T1→{self.tier1_recipient}")
        if self.tier2_sent_at:
            parts.append(f"T2→{self.tier2_recipient}")
        label = " | ".join(parts) if parts else "pending"
        return f"EscNotif [{self.ticket.ticket_id}] {label}"
 
    @property
    def tier1_sent(self):
        return self.tier1_sent_at is not None
 
    @property
    def tier2_sent(self):
        return self.tier2_sent_at is not None