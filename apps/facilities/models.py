from django.db import models

class Building(models.Model):
    name = models.CharField(max_length=50, unique=True, blank=True, null=True)
    number = models.IntegerField(unique=True)

    def __str__(self):
        return f"{self.name} (Building {self.number})"


class Room(models.Model):
    ROOM_TYPES = [
        ('lecture', 'Lecture Hall'),
        ('lab', 'Laboratory'),
        ('office', 'Office'),
        ('other', 'Other'),
    ]

    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='rooms')
    floor = models.IntegerField()
    number = models.IntegerField()
    name = models.CharField(max_length=50, blank=True, null=True)  # for labs and special rooms
    capacity = models.IntegerField()
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='lecture')

    class Meta:
        unique_together = ('building', 'floor', 'number')  # no two rooms with same number in same building

    def __str__(self):
        if self.name:
            return f"{self.name} ({self.building.name} - Floor {self.floor})"
        return f"{self.building.number}{self.floor}{self.number}"