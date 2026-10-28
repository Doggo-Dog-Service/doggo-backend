"""
Django admin customization.
"""

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from core import models


class UserAdmin(BaseUserAdmin):
    """Define the admin pages for users."""

    ordering = ['id']
    list_display = ['email', 'full_name']
    fieldsets = (
        (None, {'fields': ('profile_picture', 'email', 'password')}),
        (_('Personal Info'), {'fields': ('full_name',)}),
        (
            _('Permissions'),
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                )
            },
        ),
        (_('Important dates'), {'fields': ('last_login',)}),
        (_('Groups'), {'fields': ('groups',)}),
        (_('User Permissions'), {'fields': ('user_permissions',)}),
    )
    readonly_fields = ['last_login']
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'profile_picture',
                    'email',
                    'password1',
                    'password2',
                    'full_name',
                    'is_active',
                    'is_staff',
                    'is_superuser',
                ),
            },
        ),
    )


class ProviderDocumentInline(admin.TabularInline):
    model = models.ProviderDocument
    extra = 0
    can_delete = False
    fields = ('kind', 'document_link', 'created_at')
    readonly_fields = ('kind', 'document_link', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='Arquivo')
    def document_link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">Abrir</a>', obj.document.url)


@admin.register(models.ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'service_type', 'verification_status', 'is_active']
    list_filter = ['verification_status']
    actions = ['approve_providers', 'reject_providers']
    inlines = [ProviderDocumentInline]

    @admin.action(description='Aprovar passeadores selecionados')
    def approve_providers(self, request, queryset):
        count = queryset.update(
            verification_status=models.ProviderProfile.Verification.APPROVED,
            verification_note='',
        )
        self.message_user(request, f'{count} passeador(es) aprovado(s).', messages.SUCCESS)

    @admin.action(description='Recusar passeadores selecionados (motivo em "verification note")')
    def reject_providers(self, request, queryset):
        count = queryset.update(verification_status=models.ProviderProfile.Verification.REJECTED)
        self.message_user(request, f'{count} passeador(es) recusado(s).', messages.SUCCESS)


admin.site.register(models.ClientProfile)
admin.site.register(models.Pet)
admin.site.register(models.Service)
admin.site.register(models.WalkEvent)
admin.site.register(models.ServiceType)
admin.site.register(models.ProviderAvailability)
admin.site.register(models.User, UserAdmin)
admin.site.register(models.Review)
admin.site.register(models.ServiceLocation)
