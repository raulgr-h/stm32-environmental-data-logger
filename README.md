\# STM32L431 Environmental Data Logger



A custom embedded environmental data logger built around the STM32L431 microcontroller. The system measures temperature and relative humidity using an SHT41 sensor over I2C and records timestamped measurements to a microSD card over SPI using FatFs.



The project includes a custom KiCad PCB, STM32CubeIDE firmware, low-level peripheral drivers, board bring-up, protocol verification, long-duration CSV logging, and documented hardware/firmware debugging.



\## Current Status



The assembled PCB has been brought up successfully and the core logging system is operational.



Verified functionality includes:



\- STM32L431 firmware execution and SWD debugging

\- SHT41 temperature and humidity measurements over I2C

\- SPI-mode microSD initialization

\- FatFs mount, file open, write, sync, and close operations

\- Continuous temperature and humidity logging to PC-readable CSV files

\- Multi-hour logging operation

\- Zero observed SPI transfer failures during verified testing



LCD integration, user controls, low-power periodic logging, enclosure development, and battery-life characterization remain future work.



\## System Architecture



\- \*\*Microcontroller:\*\* STM32L431CBT6

\- \*\*Sensor:\*\* Sensirion SHT41 over I2C

\- \*\*Storage:\*\* microSD over SPI

\- \*\*Filesystem:\*\* FatFs

\- \*\*Firmware:\*\* Embedded C using STM32 HAL

\- \*\*PCB design:\*\* KiCad

\- \*\*Development environment:\*\* STM32CubeIDE

\- \*\*Test equipment:\*\* Digilent Analog Discovery 2, DMM, logic analyzer, oscilloscope



\## Firmware



The firmware includes:



\- SHT41 command and measurement handling

\- Low-level SPI communication

\- SD card initialization using CMD0, CMD8, CMD55, ACMD41, and CMD58

\- Single-block sector access using CMD17 and CMD24

\- FatFs disk I/O integration

\- CSV file creation, append, synchronization, and closure

\- SPI error instrumentation and timeout handling



\## Verification



The design was verified using debugger variables, oscilloscope measurements, logic-analyzer captures, resistance measurements, and long-duration CSV logging.



Key verified results:



\- `FR\_OK` returned for mount, open, write, sync, and close operations

\- `HAL\_OK` returned for SHT41 communication

\- Successful CMD17 read transaction with valid response and data token

\- Successful SD write operation

\- Stable 3.3 V rail during startup and SD activity

\- PC-readable CSV output

\- Multi-hour logging without observed SPI failures



\## Debugging Case Study: SD Logging Failure



During bring-up, the SD card ground connection measured approximately 5 MΩ because of a poor solder joint. The issue was isolated using resistance and continuity measurements, then corrected by reflowing the affected connection.



A later firmware issue caused the first FatFs write operation to appear to hang. The root cause was that SPI remained at the slow initialization clock after SD startup, while the driver used iteration-count-based ready timeouts.



The final fix included:



\- Increasing the SPI clock after SD initialization

\- Replacing iteration-based ready polling with `HAL\_GetTick()`-based timeouts

\- Adding SPI transfer failure instrumentation



After the fix, file open, write, sync, and close operations completed successfully.



\## Repository Structure



```text

hardware/       KiCad source, renders, and manufacturing outputs

firmware/       STM32CubeIDE project and embedded firmware

docs/           Bring-up notes, images, and verification documentation

test/           Sample data and test procedures

releases/       Release-related documentation

