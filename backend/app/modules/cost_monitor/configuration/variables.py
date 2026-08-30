from dataclasses import dataclass


@dataclass(frozen=True)
class VariableDefinition:
    name: str
    value_type: str
    description: str


REGISTERED_VARIABLES = (
    VariableDefinition("flight_time", "number", "Налёт плеча из canonical route record."),
    VariableDefinition("distance", "number", "Расстояние плеча из canonical route record."),
    VariableDefinition("passengers", "integer", "Количество пассажиров из CalculationRequest."),
    VariableDefinition("aircraft", "string", "Тип воздушного судна из CalculationRequest."),
    VariableDefinition("departure", "iata", "Аэропорт вылета из CalculationRequest."),
    VariableDefinition("arrival", "iata", "Аэропорт посадки из CalculationRequest."),
    VariableDefinition("line_type", "enum:ВВЛ|МВЛ", "Тип линии, разрешённый module code."),
    VariableDefinition("is_techstop", "boolean", "Признак выбранного техстопа."),
)

REGISTERED_VARIABLE_NAMES = frozenset(item.name for item in REGISTERED_VARIABLES)

__all__ = ["REGISTERED_VARIABLE_NAMES", "REGISTERED_VARIABLES", "VariableDefinition"]
