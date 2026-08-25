# STM32L431 Environmental Data Logger

A custom embedded environmental data logger built around the STM32L431 microcontroller.

The project began as a hand-assembled Rev A PCB that measures temperature and relative humidity using an SHT41 sensor over I2C and records RTC-timestamped measurements to removable storage. Rev A was brought through hardware bring-up, firmware integration, long-duration logging, protocol verification, and electrical characterization.

Development has now progressed into a Rev B redesign informed by measured Rev A behavior, with emphasis on lower-power operation, improved storage architecture, BLE connectivity, and more systematic hardware validation.

---

## Current Status

### Rev A — Functional and Characterized

The assembled Rev A PCB has been successfully brought up and the core environmental logging system is operational.

Verified functionality includes:

- STM32L431 firmware execution and SWD debugging
- SHT41 temperature and humidity measurements over I2C
- SPI-mode microSD initialization
- FatFs filesystem integration
- RTC-based timestamp generation
- Timestamped CSV logging
- Button-controlled logging behavior
- Multi-hour logging operation
- PC-readable logged data
- Logic-analyzer and oscilloscope verification of digital interfaces
- Automated power-source and transient-load characterization

Rev A now serves as the validated hardware baseline for the Rev B redesign.

### Rev B — In Development

Rev B is being developed from Rev A test results and system-level lessons.

Planned and in-progress changes include:

- Replacement of the microSD subsystem with SPI nonvolatile memory
- M95P16 serial Page EEPROM integration
- 32.768 kHz LSE crystal for improved low-power RTC operation
- CYBLE-416045-02 BLE module integration
- BLE UART interface to the STM32
- Dedicated BLE programming/debug access
- Improved low-power architecture
- Updated user controls
- PCB changes informed by measured battery and transient-load behavior

Rev B schematic development is maintained separately from the archived Rev A hardware baseline.

---

## System Architecture

### Rev A

- **Microcontroller:** STM32L431CBT6
- **Environmental sensor:** Sensirion SHT41 over I2C
- **Storage:** microSD over SPI
- **Filesystem:** FatFs
- **Timekeeping:** STM32 RTC
- **Firmware:** Embedded C using STM32 HAL
- **PCB design:** KiCad
- **Development environment:** STM32CubeIDE
- **Test equipment:** Digilent Analog Discovery 2, DMM, oscilloscope, and logic analyzer

### Rev B Development

- **Microcontroller:** STM32L431CBT6
- **Environmental sensor:** Sensirion SHT41
- **Nonvolatile storage:** ST M95P16 SPI Page EEPROM
- **Wireless interface:** Infineon CYBLE-416045-02 BLE module
- **BLE host interface:** UART
- **RTC reference:** External 32.768 kHz LSE crystal
- **Hardware design:** KiCad

---

## Firmware

Rev A firmware development includes:

- STM32 HAL peripheral initialization
- SHT41 command and measurement handling
- Low-level SPI communication
- SD card initialization using CMD0, CMD8, CMD55, ACMD41, and CMD58
- Single-block SD sector access using CMD17 and CMD24
- FatFs disk I/O integration
- CSV file creation, append, synchronization, and closure
- RTC initialization and timestamp generation
- Backup-domain handling
- Button input handling and nonblocking control logic
- SPI error instrumentation
- Timeout and failure handling

Rev B firmware development will extend the system with EEPROM storage, additional low-power behavior, and communication with a BLE coprocessor.

---

## Automated Test and Characterization

A Python-based automated test environment was developed using the Digilent WaveForms SDK and Analog Discovery 2.

The test system controls external transistor-switched loads while synchronously capturing battery and PCB voltage behavior.

Capabilities include:

- Automated programmable load selection
- Configurable pulse durations
- Repeated transient tests
- Synchronized analog waveform acquisition
- Battery-voltage monitoring
- Current estimation from shunt measurements
- Minimum-voltage and droop detection
- Recovery-voltage analysis
- Pulse timing validation
- Acquisition-integrity checks
- Per-test waveform CSV generation
- Reduced summary metrics
- Automated low-voltage safety shutdown

Testing was used to characterize the CR2032-powered Rev A system under transient load conditions and provide measured input to Rev B design decisions.

Primary ATE scripts are maintained under:

```text
test/scripts/ate/
