class ControllerState:
  """Etat courant de la manette (axes normalises et boutons)."""

  def __init__(self):
    self.left_x = 0
    self.left_y = 0
    self.right_x = 0
    self.right_y = 0
    self.lt = 0
    self.rt = 0
    self.dpad_x = 0
    self.dpad_y = 0
    self.buttons = {}
    self.pressed_edge = {}

  def trigger_diff(self):
    return int(self.rt) - int(self.lt)

  def set_button(self, name, pressed):
    was = self.buttons.get(name, False)
    self.buttons[name] = pressed
    if pressed and not was:
      self.pressed_edge[name] = True

  def consume_edges(self):
    edges = dict(self.pressed_edge)
    self.pressed_edge.clear()
    return edges

  def copy(self):
    clone = ControllerState()
    clone.left_x = self.left_x
    clone.left_y = self.left_y
    clone.right_x = self.right_x
    clone.right_y = self.right_y
    clone.lt = self.lt
    clone.rt = self.rt
    clone.dpad_x = self.dpad_x
    clone.dpad_y = self.dpad_y
    clone.buttons = dict(self.buttons)
    clone.pressed_edge = dict(self.pressed_edge)
    return clone

  def display_axis_x(self):
    return self.left_x

  def display_axis_y(self):
    return self.left_y
