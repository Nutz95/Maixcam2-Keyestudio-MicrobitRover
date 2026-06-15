"""Default config.json values."""


def default_config():
    return {
        "mapping_revision": 4,
        "controller_name": "Xbox Wireless Controller",
        "controller_mac": "",
        "camera": {
            "enabled": True,
            "width": 1280,
            "height": 720,
            "fps": 30,
            "format": "yuv420",
            "display_fps": 15,
        },
        "rover": {
            "max_speed": 255,
            "send_interval_ms": 30,
            "deadzone_percent": 5,
            "axis_sensitivity_percent": 70,
            "axis_expo": 2.2,
            "axis_curve": "expo",
            "speed_step": 5,
            "wait_ack": False,
        },
        "mapping": {
            "axes": {
                "drive_forward": "left_y",
                "drive_strafe": "trigger_diff",
                "drive_spin": "right_x",
                "drive_pivot": "left_x",
            },
            "invert": {
                "left_y": False,
                "left_x": False,
                "right_x": False,
                "trigger_diff": False,
            },
            "dpad": {
                "up": "forward",
                "down": "backward",
                "left": "strafe_left",
                "right": "strafe_right",
                "up_left": "diag_fl",
                "up_right": "diag_fr",
                "down_left": "diag_bl",
                "down_right": "diag_br",
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
