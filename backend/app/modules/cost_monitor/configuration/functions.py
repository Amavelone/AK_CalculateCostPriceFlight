from dataclasses import dataclass


@dataclass(frozen=True)
class PrimitiveDefinition:
    name: str
    arity: int
    description: str


# Это whitelist capabilities, а не evaluator. Iteration 3 не принимает и не
# исполняет строки формул из внешнего ввода.
ALLOWED_PRIMITIVES = (
    PrimitiveDefinition("add", 2, "Сложение двух чисел."),
    PrimitiveDefinition("multiply", 2, "Умножение двух чисел."),
    PrimitiveDefinition("divide", 2, "Деление с заранее проверенным ненулевым делителем."),
    PrimitiveDefinition("ceil", 1, "Округление числа вверх."),
    PrimitiveDefinition("contains", 2, "Проверка членства значения в разрешённом наборе."),
)

ALLOWED_PRIMITIVE_NAMES = frozenset(item.name for item in ALLOWED_PRIMITIVES)

__all__ = ["ALLOWED_PRIMITIVE_NAMES", "ALLOWED_PRIMITIVES", "PrimitiveDefinition"]
