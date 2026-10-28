"""Regras da verificação de passeadores: envio de documentos e volta para análise."""

from django.db import transaction

from core.models import ProviderDocument, ProviderProfile


def submit_document(provider, kind, document):
    """Cria ou substitui o documento do mesmo `kind`. Passeador recusado que reenvia volta para `pending`."""
    with transaction.atomic():
        provider = ProviderProfile.objects.select_for_update().get(pk=provider.pk)
        record, _ = ProviderDocument.objects.update_or_create(
            provider=provider, kind=kind, defaults={'document': document}
        )
        if provider.verification_status == ProviderProfile.Verification.REJECTED:
            provider.verification_status = ProviderProfile.Verification.PENDING
            provider.verification_note = ''
            provider.save(update_fields=['verification_status', 'verification_note'])
    return record
