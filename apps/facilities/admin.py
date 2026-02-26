from django.contrib import admin
from .models import Building, Room

class RoomInline(admin.TabularInline):
    model = Room
    extra = 1

@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ('name', 'number')
    inlines = [RoomInline]  # lets you add rooms directly from the building page

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'floor', 'capacity', 'room_type')
    list_filter = ('building', 'floor', 'room_type')