from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls import reverse

class Category(models.Model):
    name = models.CharField("Название", max_length=100)
    slug = models.SlugField("Слаг", max_length=100, unique=True)
    description = models.TextField("Описание", blank=True)
    is_active = models.BooleanField("Активна", default=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ("name",)
    
    def __str__(self) -> str:
        return self.name

class Dish(models.Model):
    """Dish - блюдо - единица каталога"""

    class Kind(models.TextChoices):
        READY = "ready", "Готово к употреблению"
        CHILLED = "chilled", "Охлажденная продукция"
        FROZEN = "frozen", "Замороженная продукция"

    name = models.CharField("Название", max_length=200)
    slug = models.SlugField("Слаг", max_length=200, unique=True)
    description = models.TextField("Описание", blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="dishes",
        verbose_name="Категория"
    )
    calories = models.PositiveIntegerField(
        "Калорийность, ккал/порция",
        validators=[MinValueValidator(1)],        
    )
    price = models.DecimalField(
        "Цена, ₽",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    weight_grams = models.PositiveIntegerField(
        "Вес порции, г",
        validators=[MinValueValidator(1)],
    )
    kind = models.CharField(
        "Вид продукции",
        max_length=10,
        choices=Kind.choices,
        default=Kind.READY,
    )
    is_active = models.BooleanField("Активно", default=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Блюдо"
        verbose_name_plural = "Блюда"
        ordering = ("name",)
        indexes = [
            models.Index(fields=["kind", "is_active"]),
            models.Index(fields=["category", "is_active"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(price__gt=0),
                name="dish_price_positive",
            ),
            models.CheckConstraint(
                check=models.Q(calories__gt=0),
                name="dish_calories_positive",
            ),
        ]

    def __str__(self) -> str:
        return self.name

class MealSet(models.Model):
    """Комплект еды: "на день", "на неделю", "бизнес-ланч" или "произвольный пользовательский комплект" """

    class SetType(models.TextChoices):
        DAY = "day", "Дневной рацион"
        WEEK = "week", "Рацион на неделю"
        LUNCH = "lunch", "Бизнес-ланч"
        CUSTOM = "custom", "Произвольный комплект"

    name = models.CharField("Название", max_length=200)
    slug = models.SlugField("Слаг", max_length=200, unique=True)
    set_type = models.CharField(
        "Тип комплекта",
        max_length=10,
        choices=SetType.choices,
    )
    duration_days = models.PositiveSmallIntegerField(
        "Длительность, дней",
        default=1,
        validators=[MinValueValidator(1)],
    )
    servings_per_day = models.PositiveSmallIntegerField(
        "порций в день",
        default=1,
        validators=[MinValueValidator(1)],
    )
    is_active = models.BooleanField("Активен", default=True)
    cached_price = models.DecimalField(
        "Стоимость, ₽ (кэш)",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
    )
    cached_calories = models.PositiveIntegerField(
        "Калорийность, ккал (кэш)",
        null=True,
        blank=True,
        editable=False,
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Комплект"
        verbose_name_plural = "Комплекты"
        ordering = ("name",)
        indexes = [
            models.Index(fields=["set_type", "is_active"]),
            models.Index(fields=["cached_price"]),
            models.Index(fields=["cached_calories"]),
        ] 

    def __str__(self) -> str:
        return self.name

    def recalculate_totals(self) -> None:
        totals = self.items.aggregate(
            total_price=Sum(F("dish__price") * F("quantity")),
            total_calories=Sum(F("dish__calories") * F("quantity")),
        )
        multiplier = self.servings_per_day
        self.cached_price = (totals["total_price"] or Decimal("0")) * multiplier
        self.cached_calories = (totals["total_calories"] or 0) * multiplier
        self.save(update_fields=["cached_price", "cached_calories", "update_at"])

class MealSetItem(models.Model):
    """Позиция состава комплекта: блюдо + количество (+ день внутри рациона). """

    meal_set = models.ForeignKey(
        MealSet,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Комплект",
    )
    dish = models.ForeignKey(
        Dish,
        on_delete=models.PROTECT,
        related_name="meal_set_items",
        verbose_name="Блюдо",
    )
    quantity = models.PositiveSmallIntegerField(
        "Количество порций",
        default=1,
        validators=[MinValueValidator(1)],
    )
    day_number = models.PositiveSmallIntegerField(
        "День внутри комплекта",
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        verbose_name = "Позиция комплекта"
        verbose_name_plural = "Позиции комплектов"
        ordering = ("meal_set", "day_number", "dish__name")
        constraints = [
            models.UniqueConstraint(
                fields=["meal_set", "dish", "day_number"],
                name="uniq_mealsetitem_set_dish_day",
            ),
            models.CheckConstraint(
                check=models.Q(quantity__gt=0),
                name="mealsetitem_quantity_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.dish} * {self.quantity}"


@receiver(post_save, sender=MealSetItem)
def _mealsetitem_saved(sender, instance: MealSetItem, **kwargs) -> None:
    instance.meal_set.recalculate_totals()


@receiver(post_delete, sender=MealSetItem)
def _mealsetitem_deleted(sender, instance: MealSetItem, **kwargs) -> None:
    instance.meal_set.recalculate_totals()

     
