from django.contrib import admin
from .models import Category, Dish, MealSet, MealSetItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "kind", "price", "calories", "weight_grams", "is_active")
    list_filter = ("kind", "is_active", "category")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class MealSetItemInline(admin.TabularInline):
    model = MealSetItem
    extra = 1
    autocomplete_fields = ("dish",)


@admin.register(MealSet)
class MealSetAdmin(admin.ModelAdmin):
    list_display = (
        "name", "set_type", "duration_days", "servings_per_day",
        "cached_price", "cached_calories", "is_active",
    )
    list_filter = ("set_type", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MealSetItemInline]
    readonly_fields = ("cached_price", "cached_calories")

    