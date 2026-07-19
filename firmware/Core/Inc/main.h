/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32l4xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define BTN_LCD_WAKE_N_Pin GPIO_PIN_13
#define BTN_LCD_WAKE_N_GPIO_Port GPIOC
#define LCD_DB7_Pin GPIO_PIN_0
#define LCD_DB7_GPIO_Port GPIOA
#define LCD_DB6_Pin GPIO_PIN_1
#define LCD_DB6_GPIO_Port GPIOA
#define LCD_DB5_Pin GPIO_PIN_2
#define LCD_DB5_GPIO_Port GPIOA
#define LCD_DB4_Pin GPIO_PIN_3
#define LCD_DB4_GPIO_Port GPIOA
#define LCD_DB3_Pin GPIO_PIN_4
#define LCD_DB3_GPIO_Port GPIOA
#define LCD_DB2_Pin GPIO_PIN_5
#define LCD_DB2_GPIO_Port GPIOA
#define LCD_DB1_Pin GPIO_PIN_6
#define LCD_DB1_GPIO_Port GPIOA
#define LCD_DB0_Pin GPIO_PIN_7
#define LCD_DB0_GPIO_Port GPIOA
#define LCD_WR_N_Pin GPIO_PIN_0
#define LCD_WR_N_GPIO_Port GPIOB
#define LCD_A0_Pin GPIO_PIN_1
#define LCD_A0_GPIO_Port GPIOB
#define LCD_RESET_N_Pin GPIO_PIN_2
#define LCD_RESET_N_GPIO_Port GPIOB
#define LCD_CS_N_Pin GPIO_PIN_10
#define LCD_CS_N_GPIO_Port GPIOB
#define SD_CS_N_Pin GPIO_PIN_12
#define SD_CS_N_GPIO_Port GPIOB
#define SD_SCK_Pin GPIO_PIN_13
#define SD_SCK_GPIO_Port GPIOB
#define SD_MISO_Pin GPIO_PIN_14
#define SD_MISO_GPIO_Port GPIOB
#define SD_MOSI_Pin GPIO_PIN_15
#define SD_MOSI_GPIO_Port GPIOB

/* USER CODE BEGIN Private defines */

/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
