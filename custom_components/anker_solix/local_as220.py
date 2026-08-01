"""Local AS220 (SOLIX S2000) support for the Anker Solix integration.

NOT part of the upstream integration. Everything here is additive and lives
OUTSIDE the vendored ``solixapi/`` tree on purpose: upstream replaces that whole
directory wholesale on each sync with thomluther/anker-solix-api, so anything
placed inside it conflicts on every release. Registering at runtime instead means
this fork shares no files with upstream and merges cleanly.

All the hard work here is thomluther's. The message-map schema, the hex decoders,
the ``DeviceHexDataTypes`` vocabulary, the command templates this builds on
(``CMD_SOC_LIMITS_V2``, ``CMD_REALTIME_TRIGGER``, ``CMD_STATUS_REQUEST``), the
MQTT session handling and the entity layer that turns any of this into HA
entities are all his design and his code. This module only fills in the AS220
field offsets, decoded against a live unit, in the format he defined.

Two things upstream will not carry, which is why this exists:

* AS220 telemetry is not released yet (a beta is expected; see
  thomluther/ha-anker-solix#578 and thomluther/anker-solix-api#322).
* The ``0103`` SoC-limit options are deliberately widened below the app's 80 %
  floor. Upstream declined this on policy - "I do not plan to support options
  that are not supported by the App, even if they might work" - which is a
  perfectly reasonable line for a shared integration to hold. It is kept here
  because ULO-window arbitrage needs a ceiling well under 80. Confirmed on two
  units that the device accepts and holds sub-80 values; the app's slider is a
  UI clamp only. Risk is local and accepted.

``register()`` is written to SHRINK as upstream catches up: once a release ships
its own AS220 map, that map wins and only the still-missing pieces are filled in.
When nothing is left to add, this file can be deleted and the fork retired.
"""

from typing import Final

from .solixapi.apitypes import (
    DeviceHexDataTypes,
    SolixDeviceCapacity,
    SolixDeviceCategory,
    SolixDeviceType,
)
from .solixapi.mqtt_pps import MODELS
from .solixapi.mqttcmdmap import (
    BYTES,
    CMD_AC_CHARGE_LIMIT,
    CMD_REALTIME_TRIGGER,
    CMD_SOC_LIMITS_V2,
    CMD_STATUS_REQUEST,
    COMMAND_LIST,
    FACTOR,
    LENGTH,
    NAME,
    SIGNED,
    TYPE,
    VALUE_DEFAULT,
    VALUE_MAX,
    VALUE_MAX_STATE,
    VALUE_MIN,
    VALUE_OPTIONS,
    VALUE_STEP,
    SolixMqttCommands,
)
from .solixapi.mqttmap import SOLIXMQTTMAP, _PPS_VERSIONS_0830

MODEL: Final[str] = "AS220"
CAPACITY_WH: Final[int] = 2010

# Widened SoC options - see the module docstring. Kept as module constants so the
# widening can still be applied on top of an upstream-supplied AS220 map.
MAX_SOC_OPTIONS: Final[list[int]] = [30, 40, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
MIN_SOC_OPTIONS: Final[list[int]] = [1, 5, 10, 15, 20, 30, 40, 50, 55, 60, 65, 70, 80, 90]


_AS220_0421 = {
    "a2": {
        BYTES: {
            "01": {
                NAME: "device_sn",
                TYPE: DeviceHexDataTypes.str.value,
            },
            "20": {
                NAME: "device_pn",
                TYPE: DeviceHexDataTypes.str.value,
            },
        }
    },
    "a3": {
        BYTES: {
            "00": {
                NAME: "charging_status",  # (0-3): Inactive (0), DC Input (1), AC Input (2), Both (3)
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "04": {
                NAME: "ac_input_limit_max",  # Max supported charge limit, seems fix
                TYPE: DeviceHexDataTypes.sile.value,
            },
            "06": {
                NAME: "unknown_a3_06",
                TYPE: DeviceHexDataTypes.sile.value,
            },
            "07": {
                NAME: "unknown_a3_07",
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "08": {
                NAME: "unknown_a3_08",
                TYPE: DeviceHexDataTypes.sile.value,
            },
            "10": {
                NAME: "unknown_a3_10",
                TYPE: DeviceHexDataTypes.sile.value,
            },
        }
    },
    "a4": {
        BYTES: {
            "04": {
                NAME: "ac_input_limit",  # AC charge limit: 100-2400 W, step: 100
                TYPE: DeviceHexDataTypes.sile.value,
            },
            "06": {
                NAME: "ac_frequency",  # 60 / 50 Hz
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "13": {
                NAME: "device_timeout_minutes",  # 0 (Never), 30, 60, 120, 240, 360, 720, 1440
                TYPE: DeviceHexDataTypes.sile.value,
            },
            "15": {
                NAME: "display_timeout_seconds",  # 0 (Never), 10, 30, 60, 300, 1800
                TYPE: DeviceHexDataTypes.sile.value,
            },
            "17": {
                NAME: "display_mode",  # Low (1), Medium (2), High (3)
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "19": {
                NAME: "temp_unit_fahrenheit",  # Celsius (0) or Fahrenheit (1)
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "20": {
                NAME: "ac_fast_charge_switch",  # Ultrafast Charge switch: Disabled (0) or Enabled (1)
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "21": {
                NAME: "display_switch",  # Off (0), On (1)
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "22": {
                NAME: "port_memory_switch",  # Output Port Memory switch: Disabled (0) or Enabled (1)
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "23": {
                NAME: "max_soc",  # max_soc %
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "24": {
                NAME: "min_soc",  # min_soc %
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "28": {
                NAME: "ac_output_timeout_minutes",  # minutes; AS220 replaces ac_output_timeout_seconds (live: 240=4h, 720=12h)
                TYPE: DeviceHexDataTypes.sile.value,
            },
        }
    },
    "a5": {
        BYTES: {
            "00": {
                NAME: "temperature",
                SIGNED: True,
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "01": {
                NAME: "charging_status_a5_1",  # (0-3): Mirrors a3
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "02": {
                NAME: "battery_soc",  # Battery SOC
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "03": {
                NAME: "battery_soh",  # Battery SOH
                TYPE: DeviceHexDataTypes.ui.value,
            },
        }
    },
    "a6": {
        BYTES: {
            "00": {
                NAME: "output_power_total",  # Output power total (AC + DC)
                TYPE: DeviceHexDataTypes.sile.value,
            },
            "02": {
                NAME: "ac_input_power",  # Input power total charge
                TYPE: DeviceHexDataTypes.sile.value,
            },
            "04": {
                NAME: "dc_input_power_total",  # # DC input power (solar + car charging)
                TYPE: DeviceHexDataTypes.sile.value,
            },
            "06": {
                NAME: "remaining_time_hours",  # hours with factor 0.1
                TYPE: DeviceHexDataTypes.sile.value,
                FACTOR: 0.1,
                SIGNED: False,
            },
            "08": {
                NAME: "main_battery_soc",  # SOC of main battery only?
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "10": {
                NAME: "ac_input_plug_status",  # 0: Disconnected, 1: connected
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "11": {
                NAME: "input_power_total",  # AC and DC input power combined
                TYPE: DeviceHexDataTypes.sile.value,
            },
        },
    },
    "a7": {
        BYTES: {
            "00": {
                NAME: "ac_output_power_switch",  # Off (0), On (1)
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "01": {
                NAME: "ac_output_power",  # AC Output power
                TYPE: DeviceHexDataTypes.sile.value,
            },
            "03": {
                NAME: "ac_input_power_switch",  # AC input / charging active (0/1) - live-confirmed: 0->1 when charging
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "04": {
                NAME: "ac_input_power_dup?",  # AC input power (dup of a6 ac_input_power) - live-confirmed = input W
                TYPE: DeviceHexDataTypes.sile.value,
            },
        }
    },
    "aa": {
        BYTES: {
            "00": {
                NAME: "usb_status",  # USB total status: Inactive (0), Discharging (1), Charging (2)
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "01": {
                NAME: "usb_power",  # Total USB power
                TYPE: DeviceHexDataTypes.sile.value,
            },
        }
    },
    "d9": {
        # AS220: AC-output mode selector + backup + Time-of-Use plan (layout differs from A1783).
        BYTES: (
            {
                "00": {
                    NAME: "usage_mode_raw",  # 0=Standard/UPS, 3=Time-of-Use, 4=Self-Consumption, 5=Custom
                    TYPE: DeviceHexDataTypes.ui.value,
                },
                "01": {
                    NAME: "usage_mode",  # 0=Standard, 1=Time-of-Use, 2=Self-Consumption, 3=Custom
                    TYPE: DeviceHexDataTypes.ui.value,
                },
                "02": {
                    NAME: "backup_soc",  # backup reserve % (discharge floor)
                    TYPE: DeviceHexDataTypes.ui.value,
                },
                "03": {
                    NAME: "max_soc_dup?",  # max_soc %
                    TYPE: DeviceHexDataTypes.ui.value,
                },
                "04": {
                    NAME: "min_soc_dup?",  # min_soc %
                    TYPE: DeviceHexDataTypes.ui.value,
                },
                "05": {
                    NAME: "tou_slot_count",  # number of Time-of-Use periods following at byte 6+
                    TYPE: DeviceHexDataTypes.ui.value,
                },
            }
            # Byte 6+ holds the TOU schedule: {tariff(1=Peak,2=Mid,3=Off), start_hr, end_hr} x tou_slot_count
            | {
                k: v
                for idx in range(1, 8)
                for k, v in {
                    f"{6 + (idx - 1) * 3:02d}": {
                        NAME: f"tou_slot_{idx}_tariff",
                        TYPE: DeviceHexDataTypes.ui.value,
                    },
                    f"{7 + (idx - 1) * 3:02d}": {
                        NAME: f"tou_slot_{idx}_start_hour",
                        TYPE: DeviceHexDataTypes.ui.value,
                    },
                    f"{8 + (idx - 1) * 3:02d}": {
                        NAME: f"tou_slot_{idx}_end_hour",
                        TYPE: DeviceHexDataTypes.ui.value,
                    },
                }.items()
            }
        )
    },
    "dd": {
        # Custom-mode charge/discharge schedule (live-confirmed vs app).
        BYTES: (
            {
                "00": {
                    NAME: "custom_mode_switch",  # 0/1
                    TYPE: DeviceHexDataTypes.ui.value,
                },
                "01": {
                    NAME: "custom_mode_weekdays",  # Bitmask: 0:sun:sat:fri:thu:wed:tue:mon
                    TYPE: DeviceHexDataTypes.ui.value,
                },
                "02": {
                    NAME: "custom_slot_count",
                    TYPE: DeviceHexDataTypes.ui.value,
                },
            }
            # Byte 3+ holds slots: {mode(1=charge,2=discharge), start_min(u16 LE), end_min(u16 LE)} x custom_slot_count.
            | {
                k: v
                for idx in range(1, 6)
                for k, v in {
                    f"{3 + (idx - 1) * 5:02d}": {
                        NAME: f"custom_slot_{idx}_load_mode",
                        TYPE: DeviceHexDataTypes.ui.value,
                    },
                    f"{4 + (idx - 1) * 5:02d}": {
                        NAME: f"custom_slot_{idx}_start_minutes",
                        TYPE: DeviceHexDataTypes.sile.value,
                        SIGNED: False,
                    },
                    f"{6 + (idx - 1) * 5:02d}": {
                        NAME: f"custom_slot_{idx}_end_minutes",
                        TYPE: DeviceHexDataTypes.sile.value,
                        SIGNED: False,
                    },
                }.items()
            }
        )
    },
    "df": {
        # Silent-mode schedule (live-confirmed vs app)
        BYTES: {
            "00": {
                NAME: "silent_mode_switch",  # 0/1
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "01": {
                NAME: "silent_mode_weekdays",  # Bitmask: 0:sun:sat:fri:thu:wed:tue:mon
                TYPE: DeviceHexDataTypes.ui.value,
            },
            "02": {
                NAME: "silent_mode_start_minutes",  # start, minutes of day (u16 LE)
                TYPE: DeviceHexDataTypes.sile.value,
                SIGNED: False,
            },
            "04": {
                NAME: "silent_mode_end_minutes",  # end, minutes of day (u16 LE)
                TYPE: DeviceHexDataTypes.sile.value,
                SIGNED: False,
            },
        }
    },
    "f0": {
        BYTES: {
            "00": {
                NAME: "ac_output_power_switch_f0",  # dup of ac_output_power_switch - live-confirmed via isolation test
                TYPE: DeviceHexDataTypes.ui.value,
            },
        }
    },
    "fd": {NAME: "unknown_fd_timestamp"},
    "fe": {NAME: "msg_timestamp"},
}

_AS220_MAP = {
    # AC Recharging Power - the app's charge-rate slider. Capping this matters during
    # an outage: the S2000's AC input sits on a Pion-backed circuit, so an uncapped
    # recharge pulls hard on the much larger Pion pack, and it also lets the unit be
    # fed from the EGO inverter or the TP300V2 without tripping their overcurrent
    # protection.
    #
    # NOT confirmed by capture on AS220 - inferred. Message type 0044 is what every
    # other PPS model in SOLIXMQTTMAP uses for CMD_AC_CHARGE_LIMIT (A1780, A1783 and
    # the C1000/C800 family all map it identically), and the command's STATE_NAME
    # "ac_input_limit" is already decoded by _AS220_0421 at a4/04 - so a write can be
    # verified against the device's own telemetry read-back, which is how the 0103
    # SoC limits were confirmed. VALUE_MAX_STATE binds the ceiling to the device's
    # reported ac_input_limit_max (a3/04, reads 1200 on this unit) rather than
    # hardcoding a variant-specific number.
    "0044": CMD_AC_CHARGE_LIMIT
    | {
        "a2": {
            **CMD_AC_CHARGE_LIMIT["a2"],
            VALUE_MIN: 100,
            VALUE_MAX: 1200,
            VALUE_MAX_STATE: "ac_input_limit_max",
            VALUE_STEP: 100,
        }
    },
    "0057": CMD_REALTIME_TRIGGER,  # for regular status messages 0405 etc
    "0100": CMD_STATUS_REQUEST
    | {  # Device status request (one time status messages 0900)
        "a2": {
            TYPE: DeviceHexDataTypes.bin.value,
            LENGTH: 1,
            BYTES: {
                "00": {
                    NAME: "push_status_request",  # Push (1)
                    TYPE: DeviceHexDataTypes.ui.value,
                    VALUE_DEFAULT: 1,
                },
            },
        }
    },
    "0402": {
        "a2": {
            NAME: "device_sn",
            TYPE: DeviceHexDataTypes.str.value,
        },
        "fe": {NAME: "msg_timestamp"},
    },
    # Device settings command group. Confirmed on AS220 firmware 1.0.2.2 by
    # capture on 2026-07-31: moving the app's charge limit publishes 0103 on
    # cmd/anker_power/AS220/<sn>/req and the device acks with 0903.
    #   ff 09 25 00 03 00 0f 01 03    header, msg type 0103
    #   a1 01 22                      message class 0x22 = command
    #   aa 02 01 <soc>                max_soc  - varied 5f/5a/50/64 across
    #                                 four writes of 95/90/80/100 %, 4/4 match
    #   ab 02 01 05                   min_soc  - unchanged, matches the
    #                                 power_cutoff=5 the device already reports
    #   fd 0e 00 "1785544508686"      ms timestamp as a string -> TIMESTAMP_FD,
    #                                 which is what makes this a _V2 command
    # So the existing CMD_SOC_LIMITS_V2 template applies unchanged, including
    # its VALUE_OPTIONS [80, 85, 90, 95, 100] - the app refuses below 80 too.
    "0103": {
        COMMAND_LIST: [
            SolixMqttCommands.soc_limits,  # field aa, ab
        ],
        # The app's slider bottoms out at 80 %, but that is a UI clamp only:
        # CONFIRMED 2026-07-31 that the device accepts sub-80 over MQTT. Wrote
        # 70 and then 30 and all three views agreed - the HA select, the
        # device's own 0421 telemetry (max_soc=70 stable over three polls), and
        # the Anker app itself, which displayed 70 % despite refusing to set it.
        # So the options are widened for AS220 ONLY; the `|` merges build new
        # dicts, leaving the shared CMD_SOC_LIMITS_V2 that A1761/A1763/A1765
        # reference completely untouched.
        #
        # CAUTION: 0103 carries aa AND ab in one frame, so setting max_soc also
        # rewrites min_soc from whatever the integration last cached - observed
        # silently reverting min_soc 10 -> 5. Set min first, then max.
        SolixMqttCommands.soc_limits: CMD_SOC_LIMITS_V2
        | {
            "aa": CMD_SOC_LIMITS_V2["aa"]
            | {
                VALUE_OPTIONS: [30, 40, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100],
            },
            # min_soc is the DISCHARGE floor, and it is the lever that can stop
            # a discharge mid-flight: raise it above the current SoC and the
            # unit has no headroom left to discharge into. The app caps it at
            # 20 %, which is useless for that - so widen it the same way the
            # max_soc list was widened, on the same evidence that the app's
            # limits are UI-side only.
            "ab": CMD_SOC_LIMITS_V2["ab"]
            | {
                VALUE_OPTIONS: [1, 5, 10, 15, 20, 30, 40, 50, 55, 60, 65, 70, 80, 90],
            },
        },
    },
    # Interval: ~3-5 seconds, but only with realtime trigger
    "0421": _AS220_0421,
    # Interval: Irregular, triggered on app actions
    "0504": {
        "a2": {
            BYTES: {
                "00": {
                    NAME: "dc_input_power_total?",  # # DC input power (solar + car charging)
                    TYPE: DeviceHexDataTypes.sile.value,
                },
                "02": {
                    NAME: "remaining_time_hours?",  # hours with factor 0.1
                    TYPE: DeviceHexDataTypes.sile.value,
                    FACTOR: 0.1,
                    SIGNED: False,
                },
                "04": {
                    NAME: "main_battery_soc?",  # SOC of main battery only?
                    TYPE: DeviceHexDataTypes.ui.value,
                },
            }
        },
        "fd": {NAME: "utc_timestamp"},
        "fe": {NAME: "msg_timestamp"},
    },
    # Interval: Irregular, triggered on app actions, no fixed interval
    "0830": _PPS_VERSIONS_0830,
    # Interval: Only as response to status request, same content as 0421
    "0900": _AS220_0421,
}

def _register_device_type() -> None:
    """Make the AS220 known to the API layer.

    SolixDeviceCapacity/Category are frozen dataclasses, but frozen only guards
    instance assignment - setting a class attribute is fine, and every consumer
    reads them through hasattr/getattr (api.py:187, hesapi.py:115,
    mqtttypes.py:931), never as dataclass fields.
    """
    if not hasattr(SolixDeviceCapacity, MODEL):
        setattr(SolixDeviceCapacity, MODEL, CAPACITY_WH)
    if not hasattr(SolixDeviceCategory, MODEL):
        setattr(SolixDeviceCategory, MODEL, SolixDeviceType.PPS.value)
    MODELS.add(MODEL)


def _widen_soc_options(model_map: dict) -> None:
    """Lift the 80 % floor off whichever 0103 soc_limits command is in place.

    Rebuilds with ``|`` rather than mutating, so the shared CMD_SOC_LIMITS_V2
    template that A1761/A1763/A1765 also reference is left untouched.

    NOTE 0103 carries aa AND ab in a single frame, so writing max_soc also
    rewrites min_soc from the integration's cache - observed silently reverting
    min_soc 10 -> 5. Set min first, then max.
    """
    cmd = (model_map.get("0103") or {}).get(SolixMqttCommands.soc_limits)
    if not cmd:
        return
    for tag, options in (("aa", MAX_SOC_OPTIONS), ("ab", MIN_SOC_OPTIONS)):
        if tag in cmd:
            model_map["0103"][SolixMqttCommands.soc_limits] = cmd = cmd | {
                tag: cmd[tag] | {VALUE_OPTIONS: options}
            }


def register() -> None:
    """Register AS220 support. Idempotent, and additive over upstream.

    If a future upstream release ships its own AS220 map, that map wins and only
    the message types it is missing get filled in from here - so upstream
    telemetry fixes are picked up automatically rather than being shadowed.
    """
    _register_device_type()
    existing = SOLIXMQTTMAP.get(MODEL)
    if existing is None:
        SOLIXMQTTMAP[MODEL] = dict(_AS220_MAP)
    else:
        for msg_type, definition in _AS220_MAP.items():
            existing.setdefault(msg_type, definition)
    _widen_soc_options(SOLIXMQTTMAP[MODEL])
