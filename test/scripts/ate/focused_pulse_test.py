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

R_SHUNT = 0.530
CH1_OFFSET = 0.000577

SAMPLE_RATE = 100000.0    # 100 kS/s
PRE_TIME = 0.250          # 250 ms before pulse
POST_TIME = 0.500         # 500 ms after pulse

REPEATS = 5
SETTLE_TIME = 5.0
RECOVERY_TIME = 60.0

ABORT_VBAT_MIN = 2.40

# Five focused characterization conditions
TESTS = [
    {
        "name": "996ohm_10ms",
        "dio": 0,
        "resistance": 996.0,
        "pulse_time": 0.010
    },
    {
        "name": "996ohm_100ms",
        "dio": 0,
        "resistance": 996.0,
        "pulse_time": 0.100
    }
]
RESULTS_DIR = "results/focused_pulse"
WAVEFORM_DIR = os.path.join(
    RESULTS_DIR,
    "waveforms"
)

SUMMARY_CSV = os.path.join(
    RESULTS_DIR,
    "focused_pulse_summary.csv"
)

# Enable DIO1, DIO2, DIO3
ALL_LOAD_MASK = (1 << 0)

dwf = cdll.LoadLibrary(DWF_PATH)
hdwf = c_int()


# ============================================================
# DIGITAL CONTROL
# ============================================================

def all_loads_off():

    dwf.FDwfDigitalIOOutputSet(
        hdwf,
        c_uint(0)
    )

    dwf.FDwfDigitalIOConfigure(hdwf)


def load_on(dio):

    dwf.FDwfDigitalIOOutputSet(
        hdwf,
        c_uint(1 << dio)
    )

    dwf.FDwfDigitalIOConfigure(hdwf)


# ============================================================
# WAVEFORM CAPTURE
# ============================================================

def capture_test(dio, pulse_time):

    total_time = (
        PRE_TIME
        + pulse_time
        + POST_TIME
    )

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

    start_time = time.perf_counter()

    load_started = False
    load_finished = False
    aborted = False

    actual_on_time = None
    actual_off_time = None

    while True:

        elapsed = (
            time.perf_counter()
            - start_time
        )

        # ----------------------------------------
        # Turn load ON
        # ----------------------------------------

        if (
            not load_started
            and elapsed >= PRE_TIME
        ):

            load_on(dio)

            load_started = True
            actual_on_time = elapsed

        # ----------------------------------------
        # Turn load OFF normally
        # ----------------------------------------

        if (
            load_started
            and not load_finished
            and elapsed >= PRE_TIME + pulse_time
        ):

            all_loads_off()

            load_finished = True
            actual_off_time = elapsed

        # ----------------------------------------
        # Read acquisition data
        # ----------------------------------------

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

            # ------------------------------------
            # Emergency cutoff
            # ------------------------------------

            if (
                load_started
                and not load_finished
                and min(new_ch2) < ABORT_VBAT_MIN
            ):

                print(
                    "\nWARNING: VBAT below "
                    f"{ABORT_VBAT_MIN:.2f} V"
                )

                print(
                    "Aborting load pulse."
                )

                all_loads_off()

                load_finished = True
                aborted = True

                actual_off_time = (
                    time.perf_counter()
                    - start_time
                )

        if sts.value == DwfStateDone.value:
            break

        time.sleep(0.001)

    all_loads_off()

    if actual_off_time is None:
        actual_off_time = (
            time.perf_counter()
            - start_time
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
        aborted,
        lost.value,
        corrupted.value
    )


# ============================================================
# ANALYSIS
# ============================================================

def analyze(
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
            pulse_start - 0.100
            <= t
            < pulse_start
        )
    ]

    pulse_indices = [
        i
        for i, t in enumerate(times)
        if (
            pulse_start
            <= t
            <= pulse_end
        )
    ]

    post_indices = [
        i
        for i, t in enumerate(times)
        if (
            pulse_end
            < t
            <= pulse_end + 0.250
        )
    ]

    if not pre_indices:
        raise RuntimeError(
            "No pre-pulse samples found."
        )

    if not pulse_indices:
        raise RuntimeError(
            "No pulse samples found."
        )

    # ----------------------------------------
    # Baseline
    # ----------------------------------------

    baseline_vbat = sum(
        ch2[i]
        for i in pre_indices
    ) / len(pre_indices)

    baseline_ch1 = sum(
        ch1[i]
        for i in pre_indices
    ) / len(pre_indices)

    # ----------------------------------------
    # Minimum battery voltage
    # ----------------------------------------

    min_index = min(
        pulse_indices,
        key=lambda i: ch2[i]
    )

    vbat_min = ch2[min_index]

    time_min_after_on = (
        times[min_index]
        - pulse_start
    )

    battery_droop = (
        baseline_vbat
        - vbat_min
    )

    # ----------------------------------------
    # Added current
    # ----------------------------------------

    added_currents = [
        (
            ch1[i]
            - baseline_ch1
        ) / R_SHUNT
        for i in pulse_indices
    ]

    avg_added_current = (
        sum(added_currents)
        / len(added_currents)
    )

    max_added_current = max(
        added_currents
    )

    # ----------------------------------------
    # Absolute total current
    # ----------------------------------------

    total_currents = [
        (
            ch1[i]
            - CH1_OFFSET
        ) / R_SHUNT
        for i in pulse_indices
    ]

    avg_total_current = (
        sum(total_currents)
        / len(total_currents)
    )

    max_total_current = max(
        total_currents
    )

    # ----------------------------------------
    # Minimum PCB rail
    # ----------------------------------------

    vpcb_values = []

    for i in pulse_indices:

        corrected_shunt = (
            ch1[i]
            - CH1_OFFSET
        )

        vpcb_values.append(
            ch2[i]
            - corrected_shunt
        )

    vpcb_min = min(vpcb_values)

    # ----------------------------------------
    # Immediate recovery
    # ----------------------------------------

    if post_indices:

        recent_indices = (
            post_indices[-1000:]
        )

        recovery_vbat = sum(
            ch2[i]
            for i in recent_indices
        ) / len(recent_indices)

    else:

        recovery_vbat = float("nan")

    return {

        "baseline_vbat_V":
            baseline_vbat,

        "vbat_min_V":
            vbat_min,

        "battery_droop_mV":
            battery_droop * 1000,

        "time_min_after_load_on_ms":
            time_min_after_on * 1000,

        "avg_added_current_mA":
            avg_added_current * 1000,

        "max_added_current_mA":
            max_added_current * 1000,

        "avg_total_current_mA":
            avg_total_current * 1000,

        "max_total_current_mA":
            max_total_current * 1000,

        "vpcb_min_V":
            vpcb_min,

        "immediate_recovery_vbat_V":
            recovery_vbat
    }


# ============================================================
# SAVE WAVEFORM
# ============================================================

def save_waveform(
    test_name,
    repeat,
    times,
    ch1,
    ch2,
    pulse_start,
    pulse_end
):

    os.makedirs(
        WAVEFORM_DIR,
        exist_ok=True
    )

    filename = (
        f"{test_name}_"
        f"repeat{repeat}.csv"
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
            "vbat_V",
            "load_state"
        ])

        for t, v1, v2 in zip(
            times,
            ch1,
            ch2
        ):

            load_state = int(
                pulse_start
                <= t
                <= pulse_end
            )

            writer.writerow([
                t,
                v1,
                v2,
                load_state
            ])

    return filepath


# ============================================================
# SAVE SUMMARY
# ============================================================

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
        "test_name",
        "repeat",
        "dio",
        "load_resistance_ohm",

        "pulse_requested_ms",
        "pulse_actual_ms",

        "aborted",
        "lost_samples",
        "corrupted_samples",

        "baseline_vbat_V",
        "vbat_min_V",
        "battery_droop_mV",

        "time_min_after_load_on_ms",

        "avg_added_current_mA",
        "max_added_current_mA",

        "avg_total_current_mA",
        "max_total_current_mA",

        "vpcb_min_V",
        "immediate_recovery_vbat_V",

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
# MAIN
# ============================================================

try:

    # Configure DIO1-DIO3
    dwf.FDwfDigitalIOOutputEnableSet(
        hdwf,
        c_uint(ALL_LOAD_MASK)
    )

    all_loads_off()

    # Enable CH1 and CH2
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

    print("\n================================")
    print("FOCUSED CR2032 PULSE TEST")
    print("================================")

    print(
        f"\n{len(TESTS)} conditions"
    )

    print(
        f"{REPEATS} repeats per condition"
    )

    print(
        f"Total tests = "
        f"{len(TESTS) * REPEATS}"
    )

    for test_index, test in enumerate(
        TESTS,
        start=1
    ):

        print("\n================================")
        print(
            f"CONDITION "
            f"{test_index}/{len(TESTS)}"
        )
        print("================================")

        print(
            f"{test['resistance']} ohm"
        )

        print(
            f"{test['pulse_time'] * 1000:.0f} ms"
        )

        print(
            f"DIO{test['dio']}"
        )

        for repeat in range(
            1,
            REPEATS + 1
        ):

            print("\n--------------------------------")

            print(
                f"Repeat {repeat}/{REPEATS}"
            )

            print("--------------------------------")

            all_loads_off()

            print(
                f"Settling for "
                f"{SETTLE_TIME:.0f} s..."
            )

            time.sleep(
                SETTLE_TIME
            )

            (
                times,
                ch1,
                ch2,
                pulse_start,
                pulse_end,
                aborted,
                lost_samples,
                corrupted_samples
            ) = capture_test(
                test["dio"],
                test["pulse_time"]
            )

            actual_pulse = (
                pulse_end
                - pulse_start
            )

            metrics = analyze(
                times,
                ch1,
                ch2,
                pulse_start,
                pulse_end
            )

            waveform_file = save_waveform(
                test["name"],
                repeat,
                times,
                ch1,
                ch2,
                pulse_start,
                pulse_end
            )

            summary = {

                "timestamp":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),

                "test_name":
                    test["name"],

                "repeat":
                    repeat,

                "dio":
                    test["dio"],

                "load_resistance_ohm":
                    test["resistance"],

                "pulse_requested_ms":
                    test["pulse_time"] * 1000,

                "pulse_actual_ms":
                    actual_pulse * 1000,

                "aborted":
                    aborted,

                "lost_samples":
                    lost_samples,

                "corrupted_samples":
                    corrupted_samples,

                **metrics,

                "waveform_file":
                    waveform_file
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
                f"{metrics['max_added_current_mA']:.2f} mA"
            )

            print(
                f"Minimum PCB rail = "
                f"{metrics['vpcb_min_V']:.4f} V"
            )

            print(
                f"VBAT minimum at "
                f"{metrics['time_min_after_load_on_ms']:.2f} ms"
            )

            print(
                f"Lost samples = "
                f"{lost_samples}"
            )

            print(
                f"Corrupted samples = "
                f"{corrupted_samples}"
            )

            if aborted:

                print(
                    "*** SAFETY ABORT ***"
                )

            # No need to wait after final test
            is_final_test = (
                test_index == len(TESTS)
                and repeat == REPEATS
            )

            if not is_final_test:

                print(
                    f"Waiting "
                    f"{RECOVERY_TIME:.0f} s "
                    "for recovery..."
                )

                time.sleep(
                    RECOVERY_TIME
                )

    print("\n================================")
    print("FOCUSED TEST COMPLETE")
    print("================================")

    print(
        f"\nSummary:\n{SUMMARY_CSV}"
    )

    print(
        f"\nWaveforms:\n{WAVEFORM_DIR}"
    )


finally:

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
