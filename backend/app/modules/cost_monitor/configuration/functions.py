from dataclasses import dataclass


@dataclass(frozen=True)
class PrimitiveDefinition:
    name: str
    arity: int
    description: str


# This is a capability whitelist, not an expression evaluator. Configuration
# payloads cannot introduce formulas or executable expressions.
ALLOWED_PRIMITIVES = (
    PrimitiveDefinition("add", 2, "Сложение двух чисел."),
    PrimitiveDefinition("subtract", 2, "Вычитание двух чисел."),
    PrimitiveDefinition("multiply", 2, "Умножение двух чисел."),
    PrimitiveDefinition("divide", 2, "Деление с заранее проверенным ненулевым делителем."),
    PrimitiveDefinition("round", 1, "Явное округление до разрешённого числа знаков."),
    PrimitiveDefinition("sum", -1, "Агрегация разрешённых частей шага."),
)

ALLOWED_PRIMITIVE_NAMES = frozenset(item.name for item in ALLOWED_PRIMITIVES)

__all__ = ["ALLOWED_PRIMITIVE_NAMES", "ALLOWED_PRIMITIVES", "PrimitiveDefinition"]
