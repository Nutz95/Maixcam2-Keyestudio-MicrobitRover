"""Parse helpers for config.json sections (no classes)."""


def section(data: dict, name: str) -> dict:
  value = data.get(name)
  return value if isinstance(value, dict) else {}


def as_int(block: dict, key: str, default: int) -> int:
  try:
    return int(block.get(key, default))
  except (TypeError, ValueError):
    return default


def as_float(block: dict, key: str, default: float) -> float:
  try:
    return float(block.get(key, default))
  except (TypeError, ValueError):
    return default


def as_bool(block: dict, key: str, default: bool) -> bool:
  value = block.get(key, default)
  if isinstance(value, bool):
    return value
  if isinstance(value, str):
    return value.strip().lower() in ("1", "true", "yes", "on")
  return bool(value) if value is not None else default


def as_str(block: dict, key: str, default: str) -> str:
  value = block.get(key, default)
  return default if value is None else str(value)


def as_str_list(block: dict, key: str) -> list:
  value = block.get(key, [])
  if not isinstance(value, list):
    return []
  return [str(item) for item in value if item is not None]
