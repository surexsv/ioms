
from django.db import models

class Client(models.Model):

    COMPANY_TYPE = (
        ('TELECOM', 'Telecom'),
        ('IT', 'IT Infrastructure'),
        ('CCTV', 'CCTV'),
        ('NETWORK', 'Networking'),
        ('WIFI', 'WiFi'),
    )

    name = models.CharField(max_length=200)
    company_type = models.CharField(max_length=20, choices=COMPANY_TYPE)
    gst_number = models.CharField(max_length=20, blank=True)
    address = models.TextField()
    contact_person = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)

    def __str__(self):
        return self.name


# Create your models here.
