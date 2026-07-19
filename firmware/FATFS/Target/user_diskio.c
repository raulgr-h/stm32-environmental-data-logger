/* Previous code */
/**
 ******************************************************************************
  * @file    user_diskio.c
  * @brief   FatFs user disk I/O driver for SPI microSD.
 ******************************************************************************
  */
/* USER CODE END Header */

#ifdef USE_OBSOLETE_USER_CODE_SECTION_0
/* USER CODE BEGIN 0 */
/* USER CODE END 0 */
#endif

/* Includes ------------------------------------------------------------------*/
#include <string.h>
#include "ff_gen_drv.h"
#include "main.h"

/* External SPI handle from main.c */
extern SPI_HandleTypeDef hspi2;

/* Disk status */
static volatile DSTATUS Stat = STA_NOINIT;

/* 1 = SDHC/SDXC sector addressing, 0 = SDSC byte addressing */
static uint8_t sd_is_sdhc = 1;

/* SD command numbers */
#define SD_CMD0       0
#define SD_CMD8       8
#define SD_CMD17      17
#define SD_CMD24      24
#define SD_CMD55      55
#define SD_CMD58      58
#define SD_ACMD41     41

/* Debug variables visible in CubeIDE Expressions */
volatile uint8_t  dbg_init_ok = 0;
volatile uint8_t  dbg_cmd0 = 0xFF;
volatile uint8_t  dbg_cmd8 = 0xFF;
volatile uint8_t  dbg_cmd55 = 0xFF;
volatile uint8_t  dbg_acmd41 = 0xFF;
volatile uint8_t  dbg_cmd58 = 0xFF;
volatile uint8_t  dbg_ocr[4] = {0};
volatile uint8_t  dbg_cmd8_data[4] = {0};
volatile uint32_t dbg_acmd41_tries = 0;
volatile uint8_t  dbg_init_fail_stage = 0;

volatile DWORD dbg_last_read_sector = 0;
volatile UINT  dbg_last_read_count = 0;
volatile DWORD dbg_last_write_sector = 0;
volatile UINT  dbg_last_write_count = 0;
volatile uint8_t dbg_last_write_resp = 0xFF;
volatile uint8_t dbg_last_read_token = 0xFF;

/* Function prototypes required by FatFs */
DSTATUS USER_initialize(BYTE pdrv);
DSTATUS USER_status(BYTE pdrv);
DRESULT USER_read(BYTE pdrv, BYTE *buff, DWORD sector, UINT count);

#if _USE_WRITE == 1
DRESULT USER_write(BYTE pdrv, const BYTE *buff, DWORD sector, UINT count);
#endif

#if _USE_IOCTL == 1
DRESULT USER_ioctl(BYTE pdrv, BYTE cmd, void *buff);
#endif

Diskio_drvTypeDef USER_Driver =
{
  USER_initialize,
  USER_status,
  USER_read,
#if _USE_WRITE
  USER_write,
#endif
#if _USE_IOCTL == 1
  USER_ioctl,
#endif
};

static void SD_Select(void)
{
    HAL_GPIO_WritePin(SD_CS_N_GPIO_Port, SD_CS_N_Pin, GPIO_PIN_RESET);
}

static void SD_Deselect(void)
{
    HAL_GPIO_WritePin(SD_CS_N_GPIO_Port, SD_CS_N_Pin, GPIO_PIN_SET);
}


static uint8_t SPI_TxRx(uint8_t data)
{
    uint8_t rx = 0xFF;
    HAL_SPI_TransmitReceive(&hspi2, &data, &rx, 1, 100);
    return rx;
}

static void SD_SendDummyClocks(void)
{
    SD_Deselect();

    for (int i = 0; i < 10; i++)
    {
        SPI_TxRx(0xFF);
    }
}

static uint8_t SD_WaitReady(uint32_t timeout)
{
    uint8_t r;

    do
    {
        r = SPI_TxRx(0xFF);

        if (r == 0xFF)
        {
            return 1;
        }
    } while (timeout--);

    return 0;
}

static uint8_t SD_SendCmd(uint8_t cmd, uint32_t arg, uint8_t crc)
{
    uint8_t r1 = 0xFF;

    SD_Select();

    SPI_TxRx(0xFF);

    SPI_TxRx(0x40 | cmd);
    SPI_TxRx((arg >> 24) & 0xFF);
    SPI_TxRx((arg >> 16) & 0xFF);
    SPI_TxRx((arg >> 8) & 0xFF);
    SPI_TxRx(arg & 0xFF);
    SPI_TxRx(crc);

    for (int i = 0; i < 10; i++)
    {
        r1 = SPI_TxRx(0xFF);

        if ((r1 & 0x80) == 0)
        {
            return r1;
        }
    }

    return 0xFF;
}

/* Put debug CMD0 test here */
uint8_t SD_Debug_CMD0_Test(void)
{
    uint8_t r;

    SD_SendDummyClocks();

    r = SD_SendCmd(SD_CMD0, 0x00000000, 0x95);
    SD_Deselect();
    SPI_TxRx(0xFF);

    return r;
}

static uint32_t SD_SectorArg(DWORD sector)
{
    if (sd_is_sdhc)
    {
        return sector;
    }

    return sector * 512U;
}

static uint8_t SD_InitCard(void)
{
    uint8_t r = 0xFF;
    uint8_t ocr[4] = {0};

    dbg_init_ok = 0;
    dbg_init_fail_stage = 0;
    dbg_cmd0 = 0xFF;
    dbg_cmd8 = 0xFF;
    dbg_cmd55 = 0xFF;
    dbg_acmd41 = 0xFF;
    dbg_cmd58 = 0xFF;
    dbg_acmd41_tries = 0;

    SD_Deselect();
    HAL_Delay(10);
    SD_SendDummyClocks();

    r = SD_SendCmd(SD_CMD0, 0x00000000, 0x95);
    dbg_cmd0 = r;
    SD_Deselect();
    SPI_TxRx(0xFF);

    if (r != 0x01)
    {
        dbg_init_fail_stage = 1;
        return 0;
    }

    r = SD_SendCmd(SD_CMD8, 0x000001AA, 0x87);
    dbg_cmd8 = r;

    for (int i = 0; i < 4; i++)
    {
        ocr[i] = SPI_TxRx(0xFF);
        dbg_cmd8_data[i] = ocr[i];
    }

    SD_Deselect();
    SPI_TxRx(0xFF);

    if (r != 0x01)
    {
        dbg_init_fail_stage = 2;
        return 0;
    }

    for (uint32_t i = 0; i < 1000; i++)
    {
        r = SD_SendCmd(SD_CMD55, 0x00000000, 0xFF);
        dbg_cmd55 = r;
        SD_Deselect();
        SPI_TxRx(0xFF);

        if ((r > 0x01) || (r == 0xFF))
        {
            dbg_init_fail_stage = 3;
            return 0;
        }

        r = SD_SendCmd(SD_ACMD41, 0x40000000, 0xFF);
        dbg_acmd41 = r;
        dbg_acmd41_tries = i + 1;
        SD_Deselect();
        SPI_TxRx(0xFF);

        if (r == 0x00)
        {
            break;
        }

        HAL_Delay(1);
    }

    if (r != 0x00)
    {
        dbg_init_fail_stage = 4;
        return 0;
    }

    r = SD_SendCmd(SD_CMD58, 0x00000000, 0xFF);
    dbg_cmd58 = r;

    for (int i = 0; i < 4; i++)
    {
        ocr[i] = SPI_TxRx(0xFF);
        dbg_ocr[i] = ocr[i];
    }

    SD_Deselect();
    SPI_TxRx(0xFF);

    if (r != 0x00)
    {
        dbg_init_fail_stage = 5;
        return 0;
    }

    sd_is_sdhc = (ocr[0] & 0x40) ? 1 : 0;

    dbg_init_ok = 1;
    dbg_init_fail_stage = 0;

    return 1;
}

/**
  * @brief Initializes a Drive
  */
DSTATUS USER_initialize(BYTE pdrv)
{
    (void)pdrv;

    if (SD_InitCard())
    {
        Stat = 0;
        return Stat;
    }

    Stat = STA_NOINIT;
    return Stat;
}

/**
  * @brief Gets Disk Status
  */
DSTATUS USER_status(BYTE pdrv)
{
    (void)pdrv;
    return Stat;
}

/**
  * @brief Reads Sector(s)
  */
DRESULT USER_read(BYTE pdrv, BYTE *buff, DWORD sector, UINT count)
{
    uint8_t r;
    uint8_t token;

    (void)pdrv;

    dbg_last_read_sector = sector;
    dbg_last_read_count = count;
    dbg_last_read_token = 0xFF;

    if (count == 0)
    {
        return RES_PARERR;
    }

    if (Stat & STA_NOINIT)
    {
        return RES_NOTRDY;
    }

    for (UINT c = 0; c < count; c++)
    {
        r = SD_SendCmd(SD_CMD17, SD_SectorArg(sector + c), 0xFF);

        if (r != 0x00)
        {
            SD_Deselect();
            SPI_TxRx(0xFF);
            return RES_ERROR;
        }

        token = 0xFF;

        for (uint32_t t = 0; t < 100000; t++)
        {
            token = SPI_TxRx(0xFF);

            if (token == 0xFE)
            {
                break;
            }
        }

        dbg_last_read_token = token;

        if (token != 0xFE)
        {
            SD_Deselect();
            SPI_TxRx(0xFF);
            return RES_ERROR;
        }

        for (uint32_t i = 0; i < 512; i++)
        {
            buff[(c * 512U) + i] = SPI_TxRx(0xFF);
        }

        SPI_TxRx(0xFF);
        SPI_TxRx(0xFF);

        SD_Deselect();
        SPI_TxRx(0xFF);
    }

    return RES_OK;
}

#if _USE_WRITE == 1
/**
  * @brief Writes Sector(s)
  */
DRESULT USER_write(BYTE pdrv, const BYTE *buff, DWORD sector, UINT count)
{
    uint8_t r;
    uint8_t resp;

    (void)pdrv;

    dbg_last_write_sector = sector;
    dbg_last_write_count = count;
    dbg_last_write_resp = 0xFF;

    if (count == 0)
    {
        return RES_PARERR;
    }

    if (Stat & STA_NOINIT)
    {
        return RES_NOTRDY;
    }

    for (UINT c = 0; c < count; c++)
    {
        r = SD_SendCmd(SD_CMD24, SD_SectorArg(sector + c), 0xFF);

        if (r != 0x00)
        {
            SD_Deselect();
            SPI_TxRx(0xFF);
            return RES_ERROR;
        }

        SPI_TxRx(0xFF);
        SPI_TxRx(0xFE);

        for (uint32_t i = 0; i < 512; i++)
        {
            SPI_TxRx(buff[(c * 512U) + i]);
        }

        SPI_TxRx(0xFF);
        SPI_TxRx(0xFF);

        resp = SPI_TxRx(0xFF);
        dbg_last_write_resp = resp;

        if ((resp & 0x1F) != 0x05)
        {
            SD_Deselect();
            SPI_TxRx(0xFF);
            return RES_ERROR;
        }

        if (!SD_WaitReady(100000))
        {
            SD_Deselect();
            SPI_TxRx(0xFF);
            return RES_ERROR;
        }

        SD_Deselect();
        SPI_TxRx(0xFF);
    }

    return RES_OK;
}
#endif

#if _USE_IOCTL == 1
/**
  * @brief I/O control operation
  */
DRESULT USER_ioctl(BYTE pdrv, BYTE cmd, void *buff)
{
    (void)pdrv;

    if (Stat & STA_NOINIT)
    {
        return RES_NOTRDY;
    }

    switch (cmd)
    {
        case CTRL_SYNC:
            SD_Select();

            if (SD_WaitReady(100000))
            {
                SD_Deselect();
                SPI_TxRx(0xFF);
                return RES_OK;
            }

            SD_Deselect();
            SPI_TxRx(0xFF);
            return RES_ERROR;

        case GET_SECTOR_SIZE:
            *(WORD *)buff = 512;
            return RES_OK;

        case GET_BLOCK_SIZE:
            *(DWORD *)buff = 1;
            return RES_OK;

        case GET_SECTOR_COUNT:
            *(DWORD *)buff = 0x100000;
            return RES_OK;

        default:
            return RES_PARERR;
    }
}
#endif
