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

# Current calibrated value
R_SHUNT = 0.530

# Previously measured CH1 zero-current offset
CH1_OFFSET = 0.000577

# Test only the 550.4-ohm branch
LOAD_DIO = 1
LOAD_RESISTANCE = 550.4

# Repeatability test
PULSE_TIME = 0.100       # 100 ms
REPEATS = 5

# Give the CR2032 plenty of recovery
RECOVERY_TIME = 60.0

# Waveform capture
SAMPLE_RATE = 100000.0   # 100 kS/s
PRE_TIME = 0.250         # 250 ms before pulse
POST_TIME = 0.500        # 500 ms after pulse

# Emergency cutoff
ABORT_VBAT_MIN = 2.40

RESULTS_DIR = "results/repeatability"
SUMMARY_CSV = os.path.join(
    RESULTS_DIR,
    "550ohm_100ms_repeatability.csv"
)

dwf = cdll.LoadLibrary(DWF_PATH)
hdwf = c_int()

DIO_MASK = 1 << LOAD_DIO


# ============================================================
# DIGITAL CONTROL
# ============================================================

def load_off():
    dwf.FDwfDigitalIOOutputSet(
        hdwf,
        c_uint(0)
    )

    dwf.FDwfDigitalIOConfigure(hdwf)


def load_on():
    dwf.FDwfDigitalIOOutputSet(
        hdwf,
        c_uint(DIO_MASK)
    )

    dwf.FDwfDigitalIOConfigure(hdwf)


# ============================================================
# WAVEFORM CAPTURE
# ============================================================

def capture_test():

    total_time = (
        PRE_TIME
        + PULSE_TIME
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

    # Start recording
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

    load_is_on = False
    load_is_off = False
    aborted = False

    actual_on_time = None
    actual_off_time = None

    while True:

        elapsed = (
            time.perf_counter()
            - start_time
        )

        # ---------------------------------------
        # Turn load ON
        # ---------------------------------------

        if (
            not load_is_on
            and elapsed >= PRE_TIME
        ):

            load_on()

            load_is_on = True
            actual_on_time = elapsed

        # ---------------------------------------
        # Turn load OFF
        # ---------------------------------------

        if (
            load_is_on
            and not load_is_off
            and elapsed >= PRE_TIME + PULSE_TIME
        ):

            load_off()

            load_is_off = True
            actual_off_time = elapsed

        # ---------------------------------------
        # Read ADC data
        # ---------------------------------------

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

            # Emergency cutoff
            if (
                load_is_on
                and not load_is_off
                and min(new_ch2) < ABORT_VBAT_MIN
            ):

                print(
                    "\nWARNING: VBAT below "
                    f"{ABORT_VBAT_MIN:.2f} V"
                )

                print("Aborting pulse.")

                load_off()

                load_is_off = True
                aborted = True

                actual_off_time = (
                    time.perf_counter()
                    - start_time
                )

        if sts.value == DwfStateDone.value:
            break

        time.sleep(0.001)

    load_off()

    count = min(
        len(ch1_all),
        len(ch2_all)
    )

    ch1_all = ch1_all[:count]
    ch2_all = ch2_all[:count]

    times = [
        i / SAMPLE_RATE
        for i in range(count)
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

    # ---------------------------------------
    # Baseline
    # ---------------------------------------

    baseline_vbat = sum(
        ch2[i]
        for i in pre_indices
    ) / len(pre_indices)

    baseline_ch1 = sum(
        ch1[i]
        for i in pre_indices
    ) / len(pre_indices)

    # ---------------------------------------
    # Battery minimum
    # ---------------------------------------

    min_index = min(
        pulse_indices,
        key=lambda i: ch2[i]
    )

    vbat_min = ch2[min_index]

    time_of_min = times[min_index]

    time_min_after_on = (
        time_of_min - pulse_start
    )

    droop = (
        baseline_vbat - vbat_min
    )

    # ---------------------------------------
    # Added current
    # ---------------------------------------

    added_currents = [
        (
            ch1[i] - baseline_ch1
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

    # ---------------------------------------
    # Absolute current estimate
    # ---------------------------------------

    total_currents = [
        (
            ch1[i] - CH1_OFFSET
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

    # ---------------------------------------
    # PCB rail minimum
    # ---------------------------------------

    vpcb_values = []

    for i in pulse_indices:

        corrected_shunt = (
            ch1[i] - CH1_OFFSET
        )

        vpcb_values.append(
            ch2[i] - corrected_shunt
        )

    vpcb_min = min(vpcb_values)

    # ---------------------------------------
    # Immediate recovery
    # ---------------------------------------

    if post_indices:

        last_samples = post_indices[-1000:]

        recovery_vbat = sum(
            ch2[i]
            for i in last_samples
        ) / len(last_samples)

    else:
        recovery_vbat = float("nan")

    return {
        "baseline_vbat_V":
            baseline_vbat,

        "vbat_min_V":
            vbat_min,

        "droop_mV":
            droop * 1000,

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
# SAVE RAW WAVEFORM
# ============================================================

def save_waveform(
    repeat,
    times,
    ch1,
    ch2,
    pulse_start,
    pulse_end
):

    os.makedirs(
        RESULTS_DIR,
        exist_ok=True
    )

    filename = os.path.join(
        RESULTS_DIR,
        f"repeat_{repeat}_waveform.csv"
    )

    with open(
        filename,
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

    return filename


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
        "repeat",
        "load_resistance_ohm",
        "pulse_requested_ms",
        "pulse_actual_ms",
        "aborted",
        "lost_samples",
        "corrupted_samples",

        "baseline_vbat_V",
        "vbat_min_V",
        "droop_mV",

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

print("Opening Analog Discovery 2...")

dwf.FDwfDeviceOpen(
    c_int(-1),
    byref(hdwf)
)

if hdwf.value == 0:

    error = create_string_buffer(512)

    dwf.FDwfGetLastErrorMsg(error)

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

    # DIO1 only
    dwf.FDwfDigitalIOOutputEnableSet(
        hdwf,
        c_uint(DIO_MASK)
    )

    load_off()

    # CH1
    dwf.FDwfAnalogInChannelEnableSet(
        hdwf,
        c_int(0),
        c_bool(True)
    )

    # CH2
    dwf.FDwfAnalogInChannelEnableSet(
        hdwf,
        c_int(1),
        c_bool(True)
    )

    # Shunt input range
    dwf.FDwfAnalogInChannelRangeSet(
        hdwf,
        c_int(0),
        c_double(0.5)
    )

    # Battery input range
    dwf.FDwfAnalogInChannelRangeSet(
        hdwf,
        c_int(1),
        c_double(10.0)
    )

    print("\n================================")
    print("550.4 OHM / 100 ms REPEATABILITY")
    print("================================")

    print(f"\nRepeats: {REPEATS}")
    print(f"Recovery: {RECOVERY_TIME:.0f} s")
    print(
        f"Sample rate: "
        f"{SAMPLE_RATE / 1000:.0f} kS/s"
    )

    for repeat in range(
        1,
        REPEATS + 1
    ):

        print("\n--------------------------------")
        print(
            f"TEST {repeat} OF {REPEATS}"
        )
        print("--------------------------------")

        load_off()

        # Stable idle period before acquisition
        print("Settling for 5 s...")
        time.sleep(5)

        (
            times,
            ch1,
            ch2,
            pulse_start,
            pulse_end,
            aborted,
            lost_samples,
            corrupted_samples
        ) = capture_test()

        actual_pulse = (
            pulse_end - pulse_start
        )

        metrics = analyze(
            times,
            ch1,
            ch2,
            pulse_start,
            pulse_end
        )

        waveform_file = save_waveform(
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

            "repeat":
                repeat,

            "load_resistance_ohm":
                LOAD_RESISTANCE,

            "pulse_requested_ms":
                PULSE_TIME * 1000,

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

        save_summary(summary)

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
            f"{metrics['droop_mV']:.1f} mV"
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
            f"VBAT minimum occurred "
            f"{metrics['time_min_after_load_on_ms']:.2f} ms "
            "after load ON"
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
                "*** SAFETY ABORT OCCURRED ***"
            )

        if repeat < REPEATS:

            print(
                f"\nWaiting {RECOVERY_TIME:.0f} s "
                "for recovery..."
            )

            time.sleep(
                RECOVERY_TIME
            )

    print("\n================================")
    print("REPEATABILITY TEST COMPLETE")
    print("================================")

    print(
        f"\nSummary:\n{SUMMARY_CSV}"
    )


finally:

    load_off()

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

    print("\nLoad OFF.")
    print("AD2 disconnected safely.")
