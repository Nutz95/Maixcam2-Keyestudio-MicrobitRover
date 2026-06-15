"""Default config.json values."""


def default_config():
    return {
        "mapping_revision": 2,
        "controller_name": "Xbox Wireless Controller",
        "controller_mac": "",
        "rover": {
            "max_speed": 255,
            "send_interval_ms": 50,
            "deadzone_percent": 2,
            "wait_ack": False,
        },
        "mapping": {
            "axes": {
                "drive_forward": "left_y",
                "drive_strafe": "trigger_diff",
                "drive_rotate": "left_x",
            },
            "invert": {
                "left_y": False,
                "left_x": False,
                "trigger_diff": False,
            },
            "buttons": {
                "btn_a": "stop",
                "btn_b": None,
                "btn_x": None,
                "btn_y": None,
                "btn_lb": None,
                "btn_rb": None,
                "btn_start": None,
                "btn_select": None,
            },
        },
        "evdev": {
            "layout": "maixcam_bt",
        },
    }
