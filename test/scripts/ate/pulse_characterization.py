from ctypes import *
import time
import csv
import os
from datetime import datetime

from dwfconstants import *

# ============================================================
# CONFIGURATION
# ============================================================

DWF_PATH = "/Library/Frameworks/dwf.framework/dwf"

# Current calibration
R_SHUNT = 0.530

# Approximate zero-current CH1 offset from calibration.
# Added-current measurements do not depend on this value,
# because baseline subtraction cancels the offset.
CH1_OFFSET = 0.000577

# Sample fast enough to resolve millisecond-scale battery response
SAMPLE_RATE = 100000.0

# Capture before and after every pulse
PRE_TIME = 0.250
POST_TIME = 0.500

# Allow battery to recover between tests
RECOVERY_TIME = 30.0

# Start with one repeat to verify operation.
# Change to 3 after the first successful sweep.
REPEATS = 3

# Pulse lengths to characterize
PULSE_DURATIONS = [
    0.010,     # 10 ms
    0.050,     # 50 ms
    0.100,     # 100 ms
    0.500,     # 500 ms
    1.000      # 1 s
]

# Emergency shutdown threshold.
# This is NOT yet the final Rev B pass/fail voltage.
ABORT_VBAT_MIN = 2.40

LOADS = [
    {
        "name": "996",
        "dio": 0,
        "resistance": 996.0
    },
    {
        "name": "550p4",
        "dio": 1,
        "resistance": 550.4
    },
    {
        "name": "329p5",
        "dio": 2,
        "resistance": 329.5
    },
    {
        "name": "220p3",
        "dio": 3,
        "resistance": 220.3
    }
]

ALL_LOAD_MASK = 0

for load in LOADS:
    ALL_LOAD_MASK |= 1 << load["dio"]


RESULTS_DIR = "results"
WAVEFORM_DIR = os.path.join(
    RESULTS_DIR,
    "waveforms"
)

SUMMARY_CSV = os.path.join(
    RESULTS_DIR,
    "cr2032_pulse_summary.csv"
)


# ============================================================
# DWF SETUP
# ============================================================

dwf = cdll.LoadLibrary(DWF_PATH)
hdwf = c_int()


# ============================================================
# DIGITAL CONTROL
# ============================================================

def all_loads_off():
    """Force every artificial load OFF."""

    dwf.FDwfDigitalIOOutputSet(
        hdwf,
        c_uint(0)
    )

    dwf.FDwfDigitalIOConfigure(hdwf)


def set_single_load(dio):
    """Turn exactly one load ON."""

    dwf.FDwfDigitalIOOutputSet(
        hdwf,
        c_uint(1 << dio)
    )

    dwf.FDwfDigitalIOConfigure(hdwf)


# ============================================================
# ANALOG RECORDING
# ============================================================

def capture_pulse(dio, pulse_time):
    """
    Continuously record CH1 and CH2 while a load pulse occurs.

    Returns:
        times
        ch1_data
        ch2_data
        actual_on_time
        actual_off_time
        aborted
    """

    total_time = (
        PRE_TIME
        + pulse_time
        + POST_TIME
    )

    # Record mode is intended for continuous acquisition.
    dwf.FDwfAnalogInAcquisitionModeSet(
        hdwf,
        acqmodeRecord
    )

    dwf.FDwfAnalogInFrequencySet(
        hdwf,
        c_double(SAMPLE_RATE)
    )

    dwf.FDwfAnalogInRecordLengthSet(
        hdwf,
        c_double(total_time)
    )

    # Start acquisition
    dwf.FDwfAnalogInConfigure(
        hdwf,
        c_bool(False),
        c_bool(True)
    )

    sts = c_byte()

    available = c_int()
    lost = c_int()
    corrupted = c_int()

    ch1_all = []
    ch2_all = []

    start_wall = time.perf_counter()

    load_on = False
    load_off = False
    aborted = False

    actual_on_time = None
    actual_off_time = None

    while True:

        now = time.perf_counter()
        elapsed = now - start_wall

        # -----------------------------------
        # Turn load ON
        # -----------------------------------

        if (
            not load_on
            and elapsed >= PRE_TIME
        ):

            set_single_load(dio)

            load_on = True
            actual_on_time = elapsed

        # -----------------------------------
        # Turn load OFF
        # -----------------------------------

        if (
            load_on
            and not load_off
            and elapsed >= PRE_TIME + pulse_time
        ):

            all_loads_off()

            load_off = True
            actual_off_time = elapsed

        # -----------------------------------
        # Read available scope data
        # -----------------------------------

        dwf.FDwfAnalogInStatus(
            hdwf,
            c_bool(True),
            byref(sts)
        )

        dwf.FDwfAnalogInStatusRecord(
            hdwf,
            byref(available),
            byref(lost),
            byref(corrupted)
        )

        count = available.value

        if count > 0:

            ch1_buffer = (
                c_double * count
            )()

            ch2_buffer = (
                c_double * count
            )()

            dwf.FDwfAnalogInStatusData(
                hdwf,
                c_int(0),
                ch1_buffer,
                c_int(count)
            )

            dwf.FDwfAnalogInStatusData(
                hdwf,
                c_int(1),
                ch2_buffer,
                c_int(count)
            )

            new_ch1 = list(ch1_buffer)
            new_ch2 = list(ch2_buffer)

            ch1_all.extend(new_ch1)
            ch2_all.extend(new_ch2)

            # Emergency battery protection
            if load_on and not load_off:

                if min(new_ch2) < ABORT_VBAT_MIN:

                    print(
                        "\nWARNING: VBAT below "
                        f"{ABORT_VBAT_MIN:.2f} V."
                    )

                    print(
                        "Aborting load pulse."
                    )

                    all_loads_off()

                    load_off = True
                    aborted = True

                    actual_off_time = (
                        time.perf_counter()
                        - start_wall
                    )

        if sts.value == DwfStateDone.value:
            break

        time.sleep(0.001)

    # Safety
    all_loads_off()

    if actual_off_time is None:
        actual_off_time = (
            time.perf_counter()
            - start_wall
        )

    sample_count = min(
        len(ch1_all),
        len(ch2_all)
    )

    ch1_all = ch1_all[:sample_count]
    ch2_all = ch2_all[:sample_count]

    times = [
        i / SAMPLE_RATE
        for i in range(sample_count)
    ]

    return (
        times,
        ch1_all,
        ch2_all,
        actual_on_time,
        actual_off_time,
        aborted
    )


# ============================================================
# ANALYSIS
# ============================================================

def analyze_waveform(
    times,
    ch1,
    ch2,
    pulse_start,
    pulse_end
):

    pre_indices = [
        i
        for i, t in enumerate(times)
        if (
            t >= pulse_start - 0.100
            and t < pulse_start
        )
    ]

    pulse_indices = [
        i
        for i, t in enumerate(times)
        if (
            t >= pulse_start
            and t <= pulse_end
        )
    ]

    post_indices = [
        i
        for i, t in enumerate(times)
        if (
            t > pulse_end
            and t <= pulse_end + 0.250
        )
    ]

    if (
        not pre_indices
        or not pulse_indices
    ):
        raise RuntimeError(
            "Not enough waveform samples "
            "for pulse analysis."
        )

    # -----------------------------------
    # Baseline
    # -----------------------------------

    baseline_vbat = sum(
        ch2[i]
        for i in pre_indices
    ) / len(pre_indices)

    baseline_ch1_raw = sum(
        ch1[i]
        for i in pre_indices
    ) / len(pre_indices)

    baseline_shunt_corrected = (
        baseline_ch1_raw
        - CH1_OFFSET
    )

    baseline_current = (
        baseline_shunt_corrected
        / R_SHUNT
    )

    # -----------------------------------
    # Loaded battery voltage
    # -----------------------------------

    pulse_vbat = [
        ch2[i]
        for i in pulse_indices
    ]

    vbat_min = min(
        pulse_vbat
    )

    battery_droop = (
        baseline_vbat
        - vbat_min
    )

    # -----------------------------------
    # Current
    # -----------------------------------

    pulse_ch1_raw = [
        ch1[i]
        for i in pulse_indices
    ]

    # Total current uses stored
    # instrument-offset calibration.
    total_currents = [
        (
            value - CH1_OFFSET
        ) / R_SHUNT
        for value in pulse_ch1_raw
    ]

    # Added current uses immediate
    # pre-pulse baseline.
    # This is more robust to offset drift.
    added_currents = [
        (
            value - baseline_ch1_raw
        ) / R_SHUNT
        for value in pulse_ch1_raw
    ]

    avg_total_current = (
        sum(total_currents)
        / len(total_currents)
    )

    max_total_current = max(
        total_currents
    )

    avg_added_current = (
        sum(added_currents)
        / len(added_currents)
    )

    max_added_current = max(
        added_currents
    )

    # -----------------------------------
    # PCB rail
    # -----------------------------------

    pulse_vpcb = []

    for i in pulse_indices:

        corrected_shunt = (
            ch1[i]
            - CH1_OFFSET
        )

        vpcb = (
            ch2[i]
            - corrected_shunt
        )

        pulse_vpcb.append(vpcb)

    vpcb_min = min(
        pulse_vpcb
    )

    # -----------------------------------
    # Recovery
    # -----------------------------------

    if post_indices:

        recovery_vbat = sum(
            ch2[i]
            for i in post_indices[-1000:]
        ) / min(
            len(post_indices),
            1000
        )

    else:
        recovery_vbat = float("nan")

    recovery_error = (
        baseline_vbat
        - recovery_vbat
    )

    return {
        "baseline_vbat_V":
            baseline_vbat,

        "vbat_min_V":
            vbat_min,

        "battery_droop_mV":
            battery_droop * 1000,

        "vpcb_min_V":
            vpcb_min,

        "baseline_current_mA":
            baseline_current * 1000,

        "avg_total_current_mA":
            avg_total_current * 1000,

        "max_sampled_total_current_mA":
            max_total_current * 1000,

        "avg_added_current_mA":
            avg_added_current * 1000,

        "max_sampled_added_current_mA":
            max_added_current * 1000,

        "recovery_vbat_V":
            recovery_vbat,

        "recovery_error_mV":
            recovery_error * 1000
    }


# ============================================================
# FILE OUTPUT
# ============================================================

def save_waveform(
    filename,
    times,
    ch1,
    ch2
):

    os.makedirs(
        WAVEFORM_DIR,
        exist_ok=True
    )

    filepath = os.path.join(
        WAVEFORM_DIR,
        filename
    )

    with open(
        filepath,
        "w",
        newline=""
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "time_s",
            "ch1_raw_V",
            "vbat_V"
        ])

        for t, v1, v2 in zip(
            times,
            ch1,
            ch2
        ):
            writer.writerow([
                t,
                v1,
                v2
            ])

    return filepath


def save_summary(row):

    os.makedirs(
        RESULTS_DIR,
        exist_ok=True
    )

    exists = os.path.isfile(
        SUMMARY_CSV
    )

    fieldnames = [
        "timestamp",
        "repeat",
        "dio",
        "load_resistance_ohm",

        "requested_pulse_ms",
        "actual_pulse_ms",
        "aborted",

        "baseline_vbat_V",
        "vbat_min_V",
        "battery_droop_mV",

        "vpcb_min_V",

        "baseline_current_mA",
        "avg_total_current_mA",
        "max_sampled_total_current_mA",

        "avg_added_current_mA",
        "max_sampled_added_current_mA",

        "recovery_vbat_V",
        "recovery_error_mV",

        "waveform_file"
    ]

    with open(
        SUMMARY_CSV,
        "a",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        if not exists:
            writer.writeheader()

        writer.writerow(row)


# ============================================================
# OPEN AD2
# ============================================================

print(
    "Opening Analog Discovery 2..."
)

dwf.FDwfDeviceOpen(
    c_int(-1),
    byref(hdwf)
)

if hdwf.value == 0:

    error = create_string_buffer(512)

    dwf.FDwfGetLastErrorMsg(
        error
    )

    print(
        "ERROR:",
        error.value.decode()
    )

    raise SystemExit(1)


print("AD2 connected.")


# ============================================================
# MAIN TEST
# ============================================================

try:

    # Digital outputs
    dwf.FDwfDigitalIOOutputEnableSet(
        hdwf,
        c_uint(ALL_LOAD_MASK)
    )

    all_loads_off()

    # Analog channels
    dwf.FDwfAnalogInChannelEnableSet(
        hdwf,
        c_int(0),
        c_bool(True)
    )

    dwf.FDwfAnalogInChannelEnableSet(
        hdwf,
        c_int(1),
        c_bool(True)
    )

    # CH1 shunt
    dwf.FDwfAnalogInChannelRangeSet(
        hdwf,
        c_int(0),
        c_double(0.5)
    )

    # CH2 battery
    dwf.FDwfAnalogInChannelRangeSet(
        hdwf,
        c_int(1),
        c_double(10.0)
    )

    print(
        "\n================================"
    )
    print(
        "CR2032 PULSE CHARACTERIZATION"
    )
    print(
        "================================"
    )

    print(
        f"\nSample rate: "
        f"{SAMPLE_RATE / 1000:.0f} kS/s"
    )

    print(
        f"Emergency VBAT cutoff: "
        f"{ABORT_VBAT_MIN:.2f} V"
    )

    for repeat in range(
        1,
        REPEATS + 1
    ):

        for load in LOADS:

            for pulse_time in PULSE_DURATIONS:

                dio = load["dio"]
                resistance = load["resistance"]

                print(
                    "\n--------------------------------"
                )

                print(
                    f"Repeat {repeat}/{REPEATS}"
                )

                print(
                    f"DIO{dio} - "
                    f"{resistance:.1f} ohm"
                )

                print(
                    f"Pulse = "
                    f"{pulse_time * 1000:.0f} ms"
                )

                all_loads_off()

                time.sleep(2)

                (
                    times,
                    ch1,
                    ch2,
                    pulse_start,
                    pulse_end,
                    aborted
                ) = capture_pulse(
                    dio,
                    pulse_time
                )

                metrics = analyze_waveform(
                    times,
                    ch1,
                    ch2,
                    pulse_start,
                    pulse_end
                )

                actual_pulse = (
                    pulse_end
                    - pulse_start
                )

                timestamp = (
                    datetime.now()
                    .strftime("%Y%m%d_%H%M%S")
                )

                waveform_name = (
                    f"{timestamp}_"
                    f"DIO{dio}_"
                    f"{resistance:.1f}ohm_"
                    f"{pulse_time * 1000:.0f}ms_"
                    f"R{repeat}.csv"
                )

                waveform_path = save_waveform(
                    waveform_name,
                    times,
                    ch1,
                    ch2
                )

                summary = {
                    "timestamp":
                        datetime.now().isoformat(
                            timespec="seconds"
                        ),

                    "repeat":
                        repeat,

                    "dio":
                        dio,

                    "load_resistance_ohm":
                        resistance,

                    "requested_pulse_ms":
                        pulse_time * 1000,

                    "actual_pulse_ms":
                        actual_pulse * 1000,

                    "aborted":
                        aborted,

                    **metrics,

                    "waveform_file":
                        waveform_path
                }

                save_summary(
                    summary
                )

                print(
                    f"VBAT baseline = "
                    f"{metrics['baseline_vbat_V']:.4f} V"
                )

                print(
                    f"VBAT minimum = "
                    f"{metrics['vbat_min_V']:.4f} V"
                )

                print(
                    f"Droop = "
                    f"{metrics['battery_droop_mV']:.1f} mV"
                )

                print(
                    f"Average added current = "
                    f"{metrics['avg_added_current_mA']:.2f} mA"
                )

                print(
                    f"Maximum sampled added current = "
                    f"{metrics['max_sampled_added_current_mA']:.2f} mA"
                )

                print(
                    f"Minimum PCB rail = "
                    f"{metrics['vpcb_min_V']:.4f} V"
                )

                if aborted:
                    print(
                        "*** TEST ABORTED BY "
                        "VBAT SAFETY LIMIT ***"
                    )

                print(
                    f"Waiting {RECOVERY_TIME:.0f} s "
                    "for battery recovery..."
                )

                time.sleep(
                    RECOVERY_TIME
                )

    print(
        "\n================================"
    )

    print(
        "PULSE SWEEP COMPLETE"
    )

    print(
        "================================"
    )

    print(
        f"\nSummary:\n{SUMMARY_CSV}"
    )

    print(
        f"\nWaveforms:\n{WAVEFORM_DIR}"
    )


finally:

    # Always leave fixture safe
    all_loads_off()

    dwf.FDwfDigitalIOOutputEnableSet(
        hdwf,
        c_uint(0)
    )

    dwf.FDwfDigitalIOConfigure(
        hdwf
    )

    dwf.FDwfDeviceClose(
        hdwf
    )

    print(
        "\nAll artificial loads OFF."
    )

    print(
        "AD2 disconnected safely."
    )
