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

# Calibrated current-sense path
R_SHUNT = 0.700

# Measured artificial load resistor
R_LOAD = 996.0

# CH1 zero-current offset determined previously
# with Rev A physically disconnected.
CH1_OFFSET = 0.000577     # volts = 0.577 mV

SAMPLES = 4096
SAMPLE_RATE = 10000.0

# Current test timing
PULSE_TIME = 10.0
RECOVERY_TIME = 30.0
BASELINE_SETTLE_TIME = 5.0

# DIO0 drives the 2N3904 artificial load
DIO0_MASK = 1 << 0

RESULTS_DIR = "results"
CSV_FILE = os.path.join(
    RESULTS_DIR,
    "cr2032_reva_results.csv"
)


# ============================================================
# DWF INITIALIZATION
# ============================================================

dwf = cdll.LoadLibrary(DWF_PATH)
hdwf = c_int()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def acquire_average():
    """
    Acquire average CH1 and CH2 voltages.

    CH1 = voltage across current-sense shunt
    CH2 = CR2032 battery terminal voltage
    """

    dwf.FDwfAnalogInConfigure(
        hdwf,
        c_bool(False),
        c_bool(True)
    )

    sts = c_byte()

    while True:
        dwf.FDwfAnalogInStatus(
            hdwf,
            c_bool(True),
            byref(sts)
        )

        if sts.value == DwfStateDone.value:
            break

        time.sleep(0.01)

    ch1_data = (c_double * SAMPLES)()
    ch2_data = (c_double * SAMPLES)()

    dwf.FDwfAnalogInStatusData(
        hdwf,
        c_int(0),
        ch1_data,
        c_int(SAMPLES)
    )

    dwf.FDwfAnalogInStatusData(
        hdwf,
        c_int(1),
        ch2_data,
        c_int(SAMPLES)
    )

    ch1_avg = sum(ch1_data) / SAMPLES
    ch2_avg = sum(ch2_data) / SAMPLES

    return ch1_avg, ch2_avg


def set_load(state):
    """
    Turn the DIO0-controlled artificial load ON or OFF.
    """

    if state:
        output_value = DIO0_MASK
    else:
        output_value = 0

    dwf.FDwfDigitalIOOutputSet(
        hdwf,
        c_uint(output_value)
    )

    dwf.FDwfDigitalIOConfigure(hdwf)


def corrected_shunt_voltage(raw_voltage):
    """
    Remove previously measured AD2 CH1 zero-current offset.
    """

    return raw_voltage - CH1_OFFSET


def calculate_current(shunt_voltage):
    """
    Convert corrected shunt voltage to battery current.
    """

    return shunt_voltage / R_SHUNT


def save_to_csv(data):
    """
    Append one Rev A load-test result to CSV.
    """

    os.makedirs(
        RESULTS_DIR,
        exist_ok=True
    )

    file_exists = os.path.isfile(CSV_FILE)

    fieldnames = [
        "timestamp",

        "load_resistance_ohm",
        "shunt_resistance_ohm",
        "ch1_offset_mV",

        "pulse_time_s",
        "recovery_time_s",

        "vbat_baseline_V",
        "vbat_loaded_V",
        "vbat_recovery_V",

        "vpcb_baseline_V",
        "vpcb_loaded_V",
        "vpcb_recovery_V",

        "vshunt_baseline_raw_mV",
        "vshunt_loaded_raw_mV",
        "vshunt_recovery_raw_mV",

        "vshunt_baseline_corrected_mV",
        "vshunt_loaded_corrected_mV",
        "vshunt_recovery_corrected_mV",

        "baseline_current_mA",
        "loaded_total_current_mA",
        "added_load_current_mA",
        "recovery_current_mA",

        "battery_droop_mV",
        "pcb_droop_mV",
        "battery_recovery_error_mV"
    ]

    with open(
        CSV_FILE,
        "a",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(data)


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

    # --------------------------------------------------------
    # Configure DIO0
    # --------------------------------------------------------

    dwf.FDwfDigitalIOOutputEnableSet(
        hdwf,
        c_uint(DIO0_MASK)
    )

    # Always begin with artificial load OFF
    set_load(False)

    # --------------------------------------------------------
    # Configure analog inputs
    # --------------------------------------------------------

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

    # CH1: millivolt-level shunt measurement
    dwf.FDwfAnalogInChannelRangeSet(
        hdwf,
        c_int(0),
        c_double(0.5)
    )

    # CH2: approximately 3 V battery
    dwf.FDwfAnalogInChannelRangeSet(
        hdwf,
        c_int(1),
        c_double(10.0)
    )

    dwf.FDwfAnalogInFrequencySet(
        hdwf,
        c_double(SAMPLE_RATE)
    )

    dwf.FDwfAnalogInBufferSizeSet(
        hdwf,
        c_int(SAMPLES)
    )

    # --------------------------------------------------------
    # STEP 1 - REV A BASELINE
    # --------------------------------------------------------

    print("\nArtificial load OFF.")
    print(
        f"Waiting {BASELINE_SETTLE_TIME:.1f} seconds "
        "for Rev A baseline..."
    )

    time.sleep(BASELINE_SETTLE_TIME)

    base_shunt_raw, base_vbat = acquire_average()

    # --------------------------------------------------------
    # STEP 2 - ARTIFICIAL LOAD ON
    # --------------------------------------------------------

    print(
        f"\nTurning {R_LOAD:.0f} ohm artificial load ON."
    )

    print(
        f"Load will remain ON for "
        f"{PULSE_TIME:.1f} seconds."
    )

    set_load(True)

    time.sleep(PULSE_TIME)

    loaded_shunt_raw, loaded_vbat = acquire_average()

    # --------------------------------------------------------
    # STEP 3 - LOAD OFF / RECOVERY
    # --------------------------------------------------------

    print("\nTurning artificial load OFF.")

    set_load(False)

    print(
        f"Waiting {RECOVERY_TIME:.1f} seconds "
        "for battery recovery..."
    )

    time.sleep(RECOVERY_TIME)

    recovery_shunt_raw, recovery_vbat = acquire_average()

    # --------------------------------------------------------
    # OFFSET CORRECTION
    # --------------------------------------------------------

    base_shunt = corrected_shunt_voltage(
        base_shunt_raw
    )

    loaded_shunt = corrected_shunt_voltage(
        loaded_shunt_raw
    )

    recovery_shunt = corrected_shunt_voltage(
        recovery_shunt_raw
    )

    # --------------------------------------------------------
    # CURRENT CALCULATIONS
    # --------------------------------------------------------

    baseline_current = calculate_current(
        base_shunt
    )

    loaded_total_current = calculate_current(
        loaded_shunt
    )

    recovery_current = calculate_current(
        recovery_shunt
    )

    # Difference does NOT depend on CH1 offset
    added_load_current = (
        loaded_total_current
        - baseline_current
    )

    # --------------------------------------------------------
    # PCB VOLTAGE
    # --------------------------------------------------------

    # PCB rail is downstream of the shunt
    vpcb_baseline = (
        base_vbat - base_shunt
    )

    vpcb_loaded = (
        loaded_vbat - loaded_shunt
    )

    vpcb_recovery = (
        recovery_vbat - recovery_shunt
    )

    # --------------------------------------------------------
    # DROOP / RECOVERY
    # --------------------------------------------------------

    battery_droop = (
        base_vbat - loaded_vbat
    )

    pcb_droop = (
        vpcb_baseline - vpcb_loaded
    )

    battery_recovery_error = (
        base_vbat - recovery_vbat
    )

    # --------------------------------------------------------
    # PRINT RESULTS
    # --------------------------------------------------------

    print("\n================================")
    print("CR2032 + REV A AUTOMATED LOAD TEST")
    print("================================")

    print("\nCONFIGURATION")

    print(
        f"Current shunt = "
        f"{R_SHUNT:.3f} ohm"
    )

    print(
        f"Artificial load = "
        f"{R_LOAD:.1f} ohm"
    )

    print(
        f"CH1 zero offset = "
        f"{CH1_OFFSET * 1000:.4f} mV"
    )

    # ----------------------------

    print("\nREV A BASELINE")

    print(
        f"VBAT = "
        f"{base_vbat:.4f} V"
    )

    print(
        f"PCB rail = "
        f"{vpcb_baseline:.4f} V"
    )

    print(
        f"Raw Vshunt = "
        f"{base_shunt_raw * 1000:.4f} mV"
    )

    print(
        f"Corrected Vshunt = "
        f"{base_shunt * 1000:.4f} mV"
    )

    print(
        f"Baseline battery current = "
        f"{baseline_current * 1000:.3f} mA"
    )

    # ----------------------------

    print("\nREV A + ARTIFICIAL LOAD")

    print(
        f"VBAT = "
        f"{loaded_vbat:.4f} V"
    )

    print(
        f"PCB rail = "
        f"{vpcb_loaded:.4f} V"
    )

    print(
        f"Raw Vshunt = "
        f"{loaded_shunt_raw * 1000:.4f} mV"
    )

    print(
        f"Corrected Vshunt = "
        f"{loaded_shunt * 1000:.4f} mV"
    )

    print(
        f"Total battery current = "
        f"{loaded_total_current * 1000:.3f} mA"
    )

    # ----------------------------

    print("\nLOAD DIFFERENCE")

    print(
        f"Artificial added current = "
        f"{added_load_current * 1000:.3f} mA"
    )

    print(
        f"Battery droop = "
        f"{battery_droop * 1000:.2f} mV"
    )

    print(
        f"PCB rail droop = "
        f"{pcb_droop * 1000:.2f} mV"
    )

    # ----------------------------

    print("\nRECOVERY")

    print(
        f"VBAT = "
        f"{recovery_vbat:.4f} V"
    )

    print(
        f"PCB rail = "
        f"{vpcb_recovery:.4f} V"
    )

    print(
        f"Battery current = "
        f"{recovery_current * 1000:.3f} mA"
    )

    print(
        f"Battery recovery error = "
        f"{battery_recovery_error * 1000:.2f} mV"
    )

    # --------------------------------------------------------
    # SAVE CSV
    # --------------------------------------------------------

    result = {

        "timestamp":
            datetime.now().isoformat(
                timespec="seconds"
            ),

        "load_resistance_ohm":
            R_LOAD,

        "shunt_resistance_ohm":
            R_SHUNT,

        "ch1_offset_mV":
            CH1_OFFSET * 1000,

        "pulse_time_s":
            PULSE_TIME,

        "recovery_time_s":
            RECOVERY_TIME,

        "vbat_baseline_V":
            base_vbat,

        "vbat_loaded_V":
            loaded_vbat,

        "vbat_recovery_V":
            recovery_vbat,

        "vpcb_baseline_V":
            vpcb_baseline,

        "vpcb_loaded_V":
            vpcb_loaded,

        "vpcb_recovery_V":
            vpcb_recovery,

        "vshunt_baseline_raw_mV":
            base_shunt_raw * 1000,

        "vshunt_loaded_raw_mV":
            loaded_shunt_raw * 1000,

        "vshunt_recovery_raw_mV":
            recovery_shunt_raw * 1000,

        "vshunt_baseline_corrected_mV":
            base_shunt * 1000,

        "vshunt_loaded_corrected_mV":
            loaded_shunt * 1000,

        "vshunt_recovery_corrected_mV":
            recovery_shunt * 1000,

        "baseline_current_mA":
            baseline_current * 1000,

        "loaded_total_current_mA":
            loaded_total_current * 1000,

        "added_load_current_mA":
            added_load_current * 1000,

        "recovery_current_mA":
            recovery_current * 1000,

        "battery_droop_mV":
            battery_droop * 1000,

        "pcb_droop_mV":
            pcb_droop * 1000,

        "battery_recovery_error_mV":
            battery_recovery_error * 1000
    }

    save_to_csv(result)

    print(
        f"\nResult saved to:"
        f"\n{CSV_FILE}"
    )


# ============================================================
# SAFE SHUTDOWN
# ============================================================

finally:

    # Always force artificial load OFF
    set_load(False)

    # Return DIO pins to high impedance
    dwf.FDwfDigitalIOOutputEnableSet(
        hdwf,
        c_uint(0)
    )

    dwf.FDwfDigitalIOConfigure(hdwf)

    dwf.FDwfDeviceClose(hdwf)

    print("\nAD2 disconnected safely.")
