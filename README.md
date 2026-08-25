# STM32L431 Environmental Data Logger

A custom embedded environmental data logger built around the STM32L431 microcontroller.

The project began as a hand-assembled Rev A PCB integrating an SHT41 environmental sensor, SPI microSD storage, RTC timestamping, and STM32 firmware. Rev A was brought through board bring-up, firmware integration, protocol debugging, long-duration logging, and electrical characterization.

Development has now progressed to a Rev B redesign informed by measured Rev A behavior, with emphasis on lower-power operation, improved nonvolatile storage, BLE connectivity, and systematic hardware validation.

---

## Project Status

### Rev A — Functional and Characterized

The core Rev A environmental logging path has been successfully brought up and verified.

Verified functionality includes:

- STM32L431 firmware execution and SWD debugging
- SHT41 temperature and relative-humidity measurements over I2C
- SPI-mode microSD initialization and sector access
- FatFs mount, file open, append, write, sync, and close operations
- STM32 RTC initialization and timestamp generation
- RTC-timestamped, PC-readable CSV logging
- Nonblocking push-button-controlled logging
- Multi-hour logging operation
- Zero observed SPI transfer failures during verified long-duration runs
- Logic-analyzer verification of I2C and SPI transactions
- Oscilloscope and Analog Discovery 2 electrical measurements
- Board-level current and supply-transient characterization
- Automated CR2032 pulse-load characterization

Rev A is retained as the verified hardware baseline for continued development.

### Rev B — In Development

Rev B is being developed from Rev A test results and system-level lessons.

Current design changes include:

- Replacement of microSD storage with an ST M95P16 SPI Page EEPROM
- Addition of a 32.768 kHz LSE crystal for RTC and low-power operation
- Addition of a CYBLE-416045-02 BLE module
- STM32-to-BLE UART communication
- Dedicated BLE programming/debug access
- Revised low-power architecture
- Updated user controls and interfaces
- PCB changes informed by measured battery and transient-load behavior

Rev B schematic development is maintained separately from the archived Rev A hardware baseline.

---

## System Architecture

### Rev A

- **Microcontroller:** STM32L431CBT6
- **Environmental Sensor:** Sensirion SHT41
- **Sensor Interface:** I2C
- **Storage:** microSD over SPI
- **Filesystem:** FatFs
- **Timekeeping:** STM32 RTC
- **Firmware:** Embedded C using STM32 HAL
- **PCB Design:** KiCad
- **Development Environment:** STM32CubeIDE
- **Test Equipment:** Digilent Analog Discovery 2, DMM, oscilloscope, and logic analyzer

### Rev B

- **Microcontroller:** STM32L431CBT6
- **Environmental Sensor:** Sensirion SHT41
- **Nonvolatile Storage:** ST M95P16 SPI Page EEPROM
- **Wireless Interface:** Infineon CYBLE-416045-02 BLE module
- **BLE Host Interface:** UART
- **RTC Reference:** External 32.768 kHz LSE crystal
- **PCB Design:** KiCad

---

## Firmware Development

Rev A firmware includes:

- STM32 HAL peripheral configuration
- SHT41 command and measurement handling
- Low-level SPI SD communication
- SD initialization using CMD0, CMD8, CMD55, ACMD41, and CMD58
- Sector-level SD access
- FatFs disk-I/O integration
- RTC initialization and timestamp generation
- Backup-register handling for RTC state
- Timestamped CSV creation and append operations
- Nonblocking push-button debounce and logging-state control
- Reusable sensor-to-storage logging routines
- SPI error instrumentation
- Time-based communication timeout handling

Rev B firmware development will extend the platform with:

- SPI EEPROM storage
- Lower-power operating modes
- BLE coprocessor communication
- Wireless environmental-data transfer

---

## Automated Test and Characterization

A Python-based automated test environment was developed using the Digilent WaveForms SDK and Analog Discovery 2.

The test fixture uses transistor-switched resistive loads and synchronized analog acquisition to characterize battery and PCB supply behavior under controlled transient loads.

Capabilities include:

- Automated selection of multiple load conditions
- Configurable pulse durations
- Repeated transient tests
- Analog acquisition at up to 100 kS/s
- Synchronized battery and shunt-voltage measurement
- Current calculation from calibrated shunt measurements
- Pre-pulse baseline measurement
- Minimum battery-voltage detection
- PCB supply-voltage analysis
- Voltage-droop calculation
- Recovery-voltage analysis
- Pulse-duration validation
- Acquisition-integrity monitoring
- Per-test raw waveform CSV logging
- Reduced summary-metric generation
- Automatic load removal after each test
- Configurable 2.40 V low-voltage safety cutoff

The characterization framework progressed from basic manual load switching and averaged measurements to automated transient waveform capture, focused pulse testing, and repeatability testing.

These measurements are being used to inform Rev B power, storage, and low-power design decisions.

---

## Electrical Characterization

Rev A current and supply behavior were measured during normal environmental logging and controlled load testing.

Verified observations include:

- Approximately **2.1 mA average board current** during 5 s interval logging
- Sampled transient current peaks of approximately **25 mA** at 500 kHz during sensor and microSD activity
- Measurable VDD droop correlated with current transients
- Successful CSV writes despite the observed transient supply behavior
- Repeatable CR2032 transient-load measurements using automated acquisition
- Preservation of raw waveforms for later engineering analysis

The automated test setup enables battery behavior to be compared across different loads, pulse durations, and repeated test runs rather than relying only on static current measurements.

---

## Verification

The system has been verified using:

- STM32CubeIDE debugging
- Runtime firmware instrumentation
- DMM resistance, continuity, and voltage measurements
- Oscilloscope measurements
- Digilent Analog Discovery 2 analog acquisition
- Logic-analyzer protocol captures
- Long-duration CSV logging
- Automated transient-load testing
- Repeatability testing
- Git revision and diff analysis during debugging

Key verified results include:

- `FR_OK` for successful FatFs mount, open, write, sync, and close operations
- `HAL_OK` during verified SHT41 communication
- Successful SPI SD initialization
- Successful CMD17 read transactions
- Verified SHT41 I2C command and response transactions
- RTC-timestamped, PC-readable CSV files
- Button input correlated with subsequent sensor sampling and storage activity
- Multi-hour logging with zero observed SPI transfer failures during verified runs

---

## Debugging Case Studies

### SD Hardware Fault

During Rev A bring-up, the SD card ground connection measured approximately 5 MΩ because of a poor solder joint.

The fault was isolated using resistance and continuity measurements and corrected by reflowing the affected connection.

This restored a valid low-resistance ground connection and allowed SD communication debugging to continue.

### FatFs Write Failure

A later firmware issue caused the first FatFs write operation to appear to hang.

Investigation showed that the SPI peripheral remained at the low initialization clock after SD startup while the disk driver used iteration-count-based ready timeouts.

The corrective actions included:

- Increasing the SPI clock after SD initialization
- Replacing iteration-count polling with `HAL_GetTick()`-based timeouts
- Adding SPI transfer-failure instrumentation

After correction, file open, write, sync, and close operations completed successfully.

### CubeMX Regeneration Regression

A later STM32CubeMX regeneration overwrote the customized `user_diskio.c` implementation, causing FatFs operations to return `FR_NOT_READY`.

The regression was isolated using:

- Runtime return-code instrumentation
- Git revision comparison
- Source diff analysis

Restoring the previously verified disk-I/O implementation recovered normal SD and FatFs operation.

This demonstrated the use of source control not only for version management, but also as a firmware-debugging and regression-analysis tool.

---

## Hardware Revision Strategy

Rev A is retained as a frozen hardware baseline rather than being modified in place.

Rev B development is maintained separately so design changes can be traced back to measured Rev A behavior and validation results.

```text
hardware/kicad/
├── rev-a/          Verified Rev A hardware baseline
├── rev-b/          Rev B hardware development
├── symbols/        Project-specific schematic symbols
├── footprints/     Project-specific PCB footprints
└── 3dmodels/       Component mechanical models
```

The `rev-a-hardware` Git tag preserves the Rev A hardware milestone.

---

## Repository Structure

```text
hardware/
└── kicad/
    ├── rev-a/
    ├── rev-b/
    ├── symbols/
    ├── footprints/
    └── 3dmodels/

firmware/
└── STM32CubeIDE project and embedded firmware

test/
├── scripts/
│   └── ate/
├── raw-data/
├── processed-data/
└── results/

docs/
├── design/
├── bringup/
└── images/

releases/
└── Release and milestone documentation
```

### Automated Test Scripts

The primary automated characterization scripts are maintained under:

```text
test/scripts/ate/
```

They cover:

- Full pulse-load characterization
- Focused pulse testing
- Repeatability testing
- Rev A system-level load testing

Raw acquisition data and processed engineering results are maintained separately to preserve traceability between measurement evidence and reduced summary metrics.

---

## Engineering Scope

This project serves as an end-to-end embedded hardware development platform covering:

- PCB schematic and layout development
- Hardware revision control
- Hand assembly and board bring-up
- STM32 embedded firmware development
- I2C and SPI protocol implementation
- Sensor integration
- Embedded filesystem integration
- RTC and timestamped data acquisition
- Hardware/firmware debugging
- Oscilloscope and logic-analyzer validation
- Automated hardware testing
- Python test automation
- Battery and transient-load characterization
- Root-cause failure analysis
- Design-for-low-power development
- BLE subsystem development
- Git/GitHub engineering workflow

---

## Next Development Steps

Current development is focused on Rev B, including:

- Completing Rev B schematic design review
- PCB layout and design-rule verification
- M95P16 storage-driver development
- BLE subsystem prototyping and UART communication
- Low-power firmware development
- Rev B assembly and bring-up
- Power-consumption comparison between Rev A and Rev B
- Environmental logging validation using the revised architecture
