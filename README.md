# STM32L431 Environmental Data Logger

A custom embedded environmental data logger built around the STM32L431
microcontroller. The system measures temperature and relative humidity using
an SHT41 sensor over I2C and records RTC-timestamped measurements to a microSD
card over SPI using FatFs.

The project includes a custom assembled KiCad PCB, STM32CubeIDE firmware,
low-level peripheral drivers, RTC timekeeping, button-controlled logging,
board bring-up, protocol analysis, long-duration CSV logging, current/power
characterization, and documented hardware/firmware debugging.

## Current Status

The custom PCB has been assembled and fully brought up. Power, SWD, GPIO,
clocking, I2C, SPI, sensor communication, microSD storage, RTC timekeeping,
and timestamped CSV logging have been verified.

Verified functionality includes:

- STM32L431 firmware execution and SWD debugging
- SHT41 temperature and humidity measurements over I2C
- SPI-mode microSD initialization and sector access
- FatFs mount, file open, append, write, sync, and close operations
- RTC-based timestamped CSV logging
- Push-button-controlled logging using a nonblocking debounce/state machine
- Long-duration logging to PC-readable CSV files
- Zero observed SPI transfer failures during verified runs
- Board-level current characterization during periodic sensor/SD activity

LCD integration, expanded user-interface controls, low-power/sleep
optimization, CR2032 operation, enclosure development, FRAM integration,
and battery-life characterization remain future work.



Verified functionality includes:



- STM32L431 firmware execution and SWD debugging
- SHT41 temperature and humidity measurements over I2C
- SPI-mode microSD initialization
- FatFs mount, file open, write, sync, and close operations
- Continuous temperature and humidity logging to PC-readable CSV files
- Multi-hour logging operation
- Zero observed SPI transfer failures during verified testing



LCD integration, user controls, low-power periodic logging, enclosure development, and battery-life characterization remain future work.



## System Architecture



- **Microcontroller:** STM32L431CBT6
- **Sensor:** Sensirion SHT41 over I2C
- **Storage:** microSD over SPI
- **Filesystem:** FatFs
- **Firmware:** Embedded C using STM32 HAL
- **PCB design:** KiCad
- **Development environment:** STM32CubeIDE
- **Test equipment:** Digilent Analog Discovery 2, DMM, logic analyzer, oscilloscope



## Firmware

The firmware includes:

- SHT41 command and measurement handling
- Low-level SPI SD card communication
- SD initialization using CMD0, CMD8, CMD55, ACMD41, and CMD58
- Sector-level SD card access
- FatFs disk I/O integration
- RTC initialization and timestamp generation
- Backup-register logic for RTC state handling
- Timestamped CSV file creation and append operations
- Nonblocking push-button debounce and logging-state control
- Reusable sensor-to-storage logging routines
- SPI error instrumentation and timeout handling



## Verification

The system was verified using STM32CubeIDE debugger variables, DMM and
continuity measurements, oscilloscope measurements, Analog Discovery 2
logic/protocol captures, CSV inspection, and board-level current measurement.

Key verified results:

- `FR_OK` for successful FatFs mount, open, write, sync, and close operations
- `HAL_OK` for verified SHT41 communication
- Successful SD initialization and CMD17 read transactions
- Detailed SHT41 I2C transaction verification
- RTC-timestamped, PC-readable CSV output
- Button input correlated with subsequent sensor sampling and microSD activity
- Long-duration logging with zero observed SPI failures during verified runs
- Approximately 2.1 mA average board current during 5 s interval logging
- Sampled transient current peaks of approximately 25 mA at 500 kHz during
  sensor and microSD activity
- Correlated VDD droop during current transients while CSV writes remained
  successful



## Debugging Case Studies: 


### SD Logging Failure

During bring-up, the SD card ground connection measured approximately 5 MΩ because of a poor solder joint. The issue was isolated using resistance and continuity measurements, then corrected by reflowing the affected connection.

A later firmware issue caused the first FatFs write operation to appear to hang. The root cause was that SPI remained at the slow initialization clock after SD startup, while the driver used iteration-count-based ready timeouts.


### CubeMX Regeneration Regression

A later STM32CubeMX regeneration overwrote the custom `user_diskio.c`
implementation, causing FatFs operations to return `FR_NOT_READY`.

The regression was isolated using runtime return-code instrumentation and Git
revision/diff analysis. Restoring the custom disk-I/O implementation recovered
normal SD and FatFs operation.



The final fix included:



- Increasing the SPI clock after SD initialization
- Replacing iteration-based ready polling with `HAL\_GetTick()`-based timeouts
- Adding SPI transfer failure instrumentation



After the fix, file open, write, sync, and close operations completed successfully.



## Repository Structure



```text

hardware/       KiCad source, renders, and manufacturing outputs

firmware/       STM32CubeIDE project and embedded firmware

docs/           Bring-up notes, images, and verification documentation

test/           Sample data and test procedures

releases/       Release-related documentation

