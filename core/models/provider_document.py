from django.db import models

from .profile import ProviderProfile


class ProviderDocument(models.Model):
    class Kind(models.TextChoices):
        DOC_FRONT = 'doc_front', 'Documento (frente)'
        DOC_BACK = 'doc_back', 'Documento (verso)'

    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name='documents')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    document = models.ForeignKey('uploader.Document', on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['provider', 'kind'], name='unique_provider_document_kind')]

    def __str__(self):
        return f'({self.id}) prestador {self.provider_id}: {self.kind}'
