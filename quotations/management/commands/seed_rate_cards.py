from django.core.management.base import BaseCommand
from quotations.models import ServiceRateCard, MaterialRateCard


SERVICE_SAMPLES = [
    ('SRV-SUR', 'Survey', 'Site survey and assessment', 'Job', 2500),
    ('SRV-INS', 'Installation', 'Equipment installation labour', 'Job', 5000),
    ('SRV-FIB', 'Fiber Splicing', 'Fiber optic splicing work', 'Point', 800),
    ('SRV-CCTV', 'CCTV Installation', 'CCTV camera installation', 'Nos', 1200),
    ('SRV-NET', 'Network Setup', 'LAN/WAN network setup', 'Job', 7500),
    ('SRV-AMC', 'AMC Support', 'Annual maintenance support visit', 'Visit', 1500),
]

MATERIAL_SAMPLES = [
    ('MAT-CAT6', 'CAT6 Cable', 'UTP CAT6 cable', 'Generic', 'Mtr', 45),
    ('MAT-FIB', 'Fiber Cable', 'Single mode fiber cable', 'Generic', 'Mtr', 65),
    ('MAT-SW', 'Switch', '24 port managed switch', 'D-Link', 'Nos', 8500),
    ('MAT-RTR', 'Router', 'Enterprise router', 'Cisco', 'Nos', 12000),
    ('MAT-CAM', 'CCTV Camera', 'IP dome camera', 'Hikvision', 'Nos', 4500),
    ('MAT-RACK', 'Rack', '42U server rack', 'Generic', 'Nos', 15000),
]


class Command(BaseCommand):
    help = 'Seed sample service and material rate cards'

    def handle(self, *args, **options):
        for code, name, desc, unit, rate in SERVICE_SAMPLES:
            ServiceRateCard.objects.get_or_create(
                service_code=code,
                defaults={
                    'service_name': name,
                    'description': desc,
                    'unit': unit,
                    'rate': rate,
                    'gst_percent': 18,
                    'is_active': True,
                },
            )
        for code, name, desc, brand, unit, rate in MATERIAL_SAMPLES:
            MaterialRateCard.objects.get_or_create(
                item_code=code,
                defaults={
                    'item_name': name,
                    'description': desc,
                    'brand': brand,
                    'unit': unit,
                    'rate': rate,
                    'gst_percent': 18,
                    'is_active': True,
                },
            )
        self.stdout.write(self.style.SUCCESS('Rate cards seeded.'))
