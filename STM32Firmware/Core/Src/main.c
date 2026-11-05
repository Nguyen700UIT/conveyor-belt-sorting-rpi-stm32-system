/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
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
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "uart_link.h"
#include "servo.h"
#include "servo_fsm.h"
#include "system_fsm.h"
#include "uart_protocol.h"
#include "product_queue.h"
#include "stm32f1xx_hal.h"
#include "stm32f1xx_hal_tim.h"
#include "motor.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define MOTOR_RUNNING_DUTY_PERCENT 30U

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */
#define servo_tim_handler htim2
#define motor_tim_handler htim3
/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
TIM_HandleTypeDef htim2;
TIM_HandleTypeDef htim3;
TIM_HandleTypeDef htim4;

UART_HandleTypeDef huart1;

/* USER CODE BEGIN PV */
/* Main-loop use only. Advance only after a product is successfully queued. */
static uint32_t next_product_id = 1U;
/* Last protocol service result, observable in the debugger. HAL_BUSY is retryable. */
static volatile HAL_StatusTypeDef uart_protocol_status = HAL_OK;

static ServoFsm servo_fsms[2];
static const ServoFsmConfig servo_configs[2] = {
  { .rest_angle = 0, .deflect_angle = 45,
    .deflect_ms = 200U, .hold_ms = 2000U, .return_ms = 200U },
  { .rest_angle = 0, .deflect_angle = 45,
    .deflect_ms = 200U, .hold_ms = 2000U, .return_ms = 200U }
};
static volatile uint8_t servo_timer_due;

/* Debugger mailbox: write product ID first, then command.
 * Commands: 1 = servo 1, 2 = servo 2, 3 = Stop both,
 * 4 = Reset (operator must first clear the belt), 5 = Start without a servo test.
 * Results: 0 = none, 1 = accepted, 2 = rejected.
 * Entering RUNNING starts the conveyor motor on LPWM.
 */
volatile uint32_t servo_test_command;
volatile uint32_t servo_test_product_id;
volatile uint32_t servo_test_result;
volatile uint32_t servo_completed_count[2];
volatile uint32_t servo_last_completed_id[2];
/* Timing estimate only; no physical exit confirmation. */
volatile uint32_t ripe_estimated_exit_count;

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_TIM2_Init(void);
static void MX_USART1_UART_Init(void);
static void MX_TIM3_Init(void);
static void MX_TIM4_Init(void);
/* USER CODE BEGIN PFP */
static bool App_StartSystem(void);
static UartProtocol_Status_t App_HandleProductCommand(uint8_t command);
static void ServoTest_Init(void);
static void ServoTest_ApplyOutput(uint32_t index, const ServoFsmOutput *output);
static void ServoTest_ScheduleTimer(void);
static void ServoTest_ProcessCommand(void);
static void ServoTest_ProcessTimeouts(void);
static bool ServoTest_BothIdle(void);

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

static bool App_StartSystem(void)
{
  if (SystemFsm_GetState() == SYSTEM_RUNNING) return true;
  if (!SystemFsm_HandleEvent(SYSTEM_EVENT_START)) return false;

  Motor_Set_Duty(&htim3, LPWM, MOTOR_RUNNING_DUTY_PERCENT);
  return true;
}

//Callback
static UartProtocol_Status_t App_HandleProductCommand(uint8_t command)
{
  if (command == UART_PROTOCOL_CMD_START)
  {
    if (App_StartSystem())
    {
      return UART_PROTOCOL_STATUS_ACK;
    }
    return UART_PROTOCOL_STATUS_NOT_READY;
  }
  if (SystemFsm_GetState() != SYSTEM_RUNNING) return UART_PROTOCOL_STATUS_NOT_READY;
  const uint32_t now = HAL_GetTick();
  Product p;

  /* Temporary travel times for bench testing; measure before running the belt. */
  switch(command)
  {
    case UART_PROTOCOL_CMD_UNRIPE:
    {
      p.type = PRODUCT_UNRIPE;
      p.deadline_ms = now + (1000U - 200U);
      break;
    }
    case UART_PROTOCOL_CMD_RIPE:
    {
      p.type = PRODUCT_RIPE;
      p.deadline_ms = now + 5000U;
      break;
    }
    case UART_PROTOCOL_CMD_SPOILED:
    {
      p.type = PRODUCT_SPOILED;
      p.deadline_ms = now + (2000U - 200U);
      break;
    }
    default:
      return UART_PROTOCOL_STATUS_BAD_CMD;
  }
  p.product_id = next_product_id;

  if(ProductQueue_Push(p))
  {
    next_product_id++;
    ServoTest_ScheduleTimer();
    return UART_PROTOCOL_STATUS_ACK;
  }
  return UART_PROTOCOL_STATUS_FULL;
}


static bool ServoTest_BothIdle(void)
{
  return servo_fsms[0].state == SERVO_FSM_IDLE
      && servo_fsms[1].state == SERVO_FSM_IDLE;
}

static void ServoTest_ApplyOutput(uint32_t index, const ServoFsmOutput *output)
{
  if (output->angle_requested)
  {
    const uint32_t channel = index == 0U ? TIM_CHANNEL_1 : TIM_CHANNEL_2;
    Set_Servo_Angle(&htim2, channel, output->angle);
  }
  if (output->cycle_completed)
  {
    servo_last_completed_id[index] = output->product_id;
    servo_completed_count[index]++;
  }
}

static void ServoTest_Init(void)
{
  ServoFsmOutput outputs[2];
  const uint32_t now = HAL_GetTick();
  for (uint32_t index = 0U; index < 2U; index++)
  {
    if (!ServoFsm_Init(&servo_fsms[index], &servo_configs[index], now, &outputs[index]))
    {
      Error_Handler();
    }
  }
  for (uint32_t index = 0U; index < 2U; index++)
  {
    ServoTest_ApplyOutput(index, &outputs[index]);
  }
  if (HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1) != HAL_OK
      || HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_2) != HAL_OK)
  {
    Error_Handler();
  }
  ServoTest_ScheduleTimer();
}

static void ServoTest_ScheduleTimer(void)
{
  HAL_TIM_Base_Stop_IT(&htim4);
  __HAL_TIM_CLEAR_FLAG(&htim4, TIM_FLAG_UPDATE);
  HAL_NVIC_ClearPendingIRQ(TIM4_IRQn);
  servo_timer_due = 0U;

  const uint32_t now = HAL_GetTick();
  uint32_t next_ms = UINT32_MAX;
  for (uint32_t index = 0U; index < 2U; index++)
  {
    if (servo_fsms[index].state == SERVO_FSM_UNINITIALIZED
        || servo_fsms[index].state == SERVO_FSM_IDLE)
    {
      continue;
    }

    const uint32_t remaining_ms = servo_fsms[index].deadline_ms - now; //Overflow when deadline passed
    if (remaining_ms == 0U || remaining_ms > INT32_MAX)
    {
      servo_timer_due = 1U;
      return;
    }

    if (remaining_ms < next_ms)
    {
      next_ms = remaining_ms; //Set remaining_ms as next for the timer to continue counting the remaining miliseconds
    }
  }

  if (SystemFsm_GetState() == SYSTEM_RUNNING)
  {
    Product p;
    if (ProductQueue_PeekEarliest(&p))
    {
      const uint32_t remaining_ms = p.deadline_ms - now;
      if (remaining_ms == 0 || remaining_ms > INT32_MAX)
      {
        servo_timer_due = 1U;
        return;
      }
      if (remaining_ms < next_ms) next_ms = remaining_ms;
    }
  }


  if (next_ms == UINT32_MAX)
  {
    return;
  }
  /* TIM4 is 16-bit, running at 2 kHz. Long deadlines use bounded chunks. */
  if (next_ms > 32767U)
  {
    next_ms = 32767U;
  }
  __HAL_TIM_SET_AUTORELOAD(&htim4, next_ms * 2U - 1U);
  __HAL_TIM_SET_COUNTER(&htim4, 0U);
  if (HAL_TIM_Base_Start_IT(&htim4) != HAL_OK)
  {
    Error_Handler();
  }
}

static void ServoTest_ProcessCommand(void)
{
  const uint32_t command = servo_test_command;
  const uint32_t product_id = servo_test_product_id;
  servo_test_command = 0U;
  if (command == 0U)
  {
    return;
  }

  ServoFsmOutput output;
  const uint32_t now = HAL_GetTick();
  bool accepted = false;
  if (command == 3U)
  {
    /* Stop is processed before timeout completion in the main loop. */
    Motor_Stop(&htim3);
    accepted = SystemFsm_HandleEvent(SYSTEM_EVENT_STOP);
    for (uint32_t index = 0U; index < 2U; index++)
    {
      ServoFsm_Stop(&servo_fsms[index], now, &output);
      ServoTest_ApplyOutput(index, &output);
    }
  }
  else if (command == 4U)
  {
    if (ServoTest_BothIdle()
        && (SystemFsm_GetState() == SYSTEM_STOPPED
            || SystemFsm_GetState() == SYSTEM_FAULT))
    {
      /* Explicit operator reset confirms the belt has been physically cleared. */
      Product discarded;
      while (ProductQueue_Pop(&discarded))
      {
      }
      accepted = SystemFsm_HandleEvent(SYSTEM_EVENT_RESET_ALLOWED);
    }
  }
  else if (command == 5U)
  {
    accepted = App_StartSystem();
  }
  else if (command == 1U || command == 2U)
  {
    if (SystemFsm_GetState() == SYSTEM_READY)
    {
      App_StartSystem();
    }
    if (SystemFsm_GetState() == SYSTEM_RUNNING)
    {
      const uint32_t index = command - 1U;
      accepted = ServoFsm_Start(&servo_fsms[index], product_id, now, &output);
      ServoTest_ApplyOutput(index, &output);
    }
  }
  servo_test_result = accepted ? 1U : 2U;
  ServoTest_ScheduleTimer();
}

static void ServoTest_ProcessTimeouts(void)
{
  if (servo_timer_due == 0U)
  {
    return;
  }
  servo_timer_due = 0U;
  const uint32_t now = HAL_GetTick();
  ServoFsmOutput output;
  for (uint32_t index = 0U; index < 2U; index++)
  {
    if (ServoFsm_HandleTimeout(&servo_fsms[index], now, &output))
    {
      ServoTest_ApplyOutput(index, &output);
    }
  }

  while (SystemFsm_GetState() == SYSTEM_RUNNING)
  {
    Product p;
    if (!ProductQueue_PeekEarliest(&p))
    {
      break;
    }
    const uint32_t product_now = HAL_GetTick();
    const uint32_t remaining_ms = p.deadline_ms - product_now;
    if (remaining_ms != 0U && remaining_ms <= INT32_MAX)
    {
      break;
    }
    if (p.type == PRODUCT_RIPE)
    {
      ProductQueue_PopEarliest(&p);
      ripe_estimated_exit_count++;
      continue;
    }
    /* Bench mapping: servo 1 = unripe, servo 2 = spoiled. */
    const uint32_t index = p.type == PRODUCT_UNRIPE ? 0U : 1U;
    if ((p.type == PRODUCT_UNRIPE || p.type == PRODUCT_SPOILED)
        && ServoFsm_Start(&servo_fsms[index], p.product_id, product_now, &output))
    {
      ServoTest_ApplyOutput(index, &output);
      ProductQueue_PopEarliest(&p);
      continue;
    }

    /* A busy servo cannot safely sort this product late. Keep its record. */
    Motor_Stop(&htim3);
    SystemFsm_HandleEvent(SYSTEM_EVENT_ERROR);
    for (uint32_t servo = 0U; servo < 2U; servo++)
    {
      ServoFsm_Stop(&servo_fsms[servo], product_now, &output);
      ServoTest_ApplyOutput(servo, &output);
    }
  }

  if (SystemFsm_GetState() == SYSTEM_INIT && ServoTest_BothIdle())
  {
    SystemFsm_HandleEvent(SYSTEM_EVENT_INIT_DONE);
  }
  ServoTest_ScheduleTimer();
}

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
   HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_TIM2_Init();
  MX_USART1_UART_Init();
  MX_TIM3_Init();
  MX_TIM4_Init();
  /* USER CODE BEGIN 2 */
  Motor_Stop(&htim3);
  if (HAL_TIM_PWM_Start(&htim3, RPWM) != HAL_OK
      || HAL_TIM_PWM_Start(&htim3, LPWM) != HAL_OK)
  {
    Error_Handler();
  }
  ServoTest_Init();

  if (UartLink_Init(&huart1) != HAL_OK)
  {
    Error_Handler();
  }
  UartProtocol_Init(App_HandleProductCommand);
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    ServoTest_ProcessCommand();
    uart_protocol_status = UartProtocol_Process();
    ServoTest_ProcessTimeouts();

    /* A pending IRQ wakes WFI even while PRIMASK is set. Masking the final
     * check and sleep prevents losing a deadline between them.
     * SysTick stays enabled for HAL time and debugger mailbox wakeups.
     */
    __disable_irq();
    if (servo_timer_due == 0U && servo_test_command == 0U
        && !UartLink_HasServices())
    {
      __DSB();
      __WFI();
    }
    __enable_irq();
    /* USER CODE END WHILE */
    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief TIM2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM2_Init(void)
{

  /* USER CODE BEGIN TIM2_Init 0 */

  /* USER CODE END TIM2_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  /* USER CODE BEGIN TIM2_Init 1 */

  /* USER CODE END TIM2_Init 1 */
  htim2.Instance = TIM2;
  htim2.Init.Prescaler = 72-1;
  htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim2.Init.Period = 20000-1;
  htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim2) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim2, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_Init(&htim2) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 0;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  if (HAL_TIM_PWM_ConfigChannel(&htim2, &sConfigOC, TIM_CHANNEL_1) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_ConfigChannel(&htim2, &sConfigOC, TIM_CHANNEL_2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM2_Init 2 */

  /* USER CODE END TIM2_Init 2 */
  HAL_TIM_MspPostInit(&htim2);

}

/**
  * @brief TIM3 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM3_Init(void)
{

  /* USER CODE BEGIN TIM3_Init 0 */

  /* USER CODE END TIM3_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  /* USER CODE BEGIN TIM3_Init 1 */

  /* USER CODE END TIM3_Init 1 */
  htim3.Instance = TIM3;
  htim3.Init.Prescaler = 0;
  htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim3.Init.Period = 3600-1;
  htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim3) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim3, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_Init(&htim3) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim3, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 0;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  if (HAL_TIM_PWM_ConfigChannel(&htim3, &sConfigOC, TIM_CHANNEL_3) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_ConfigChannel(&htim3, &sConfigOC, TIM_CHANNEL_4) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM3_Init 2 */

  /* USER CODE END TIM3_Init 2 */
  HAL_TIM_MspPostInit(&htim3);

}

/**
  * @brief USART1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART1_UART_Init(void)
{

  /* USER CODE BEGIN USART1_Init 0 */

  /* USER CODE END USART1_Init 0 */

  /* USER CODE BEGIN USART1_Init 1 */

  /* USER CODE END USART1_Init 1 */
  huart1.Instance = USART1;
  huart1.Init.BaudRate = 115200;
  huart1.Init.WordLength = UART_WORDLENGTH_8B;
  huart1.Init.StopBits = UART_STOPBITS_1;
  huart1.Init.Parity = UART_PARITY_NONE;
  huart1.Init.Mode = UART_MODE_TX_RX;
  huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart1.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART1_Init 2 */

  /* USER CODE END USART1_Init 2 */

}

/**
  * @brief TIM4 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM4_Init(void)
{
  /* USER CODE BEGIN TIM4_Init 0 */

  /* USER CODE END TIM4_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM4_Init 1 */

  /* USER CODE END TIM4_Init 1 */
  htim4.Instance = TIM4;
  htim4.Init.Prescaler = 36000-1;
  htim4.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim4.Init.Period = 2-1;
  htim4.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim4.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim4) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim4, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim4, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM4_Init 2 */

  /* USER CODE END TIM4_Init 2 */
}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOD_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4|GPIO_PIN_5, GPIO_PIN_RESET);

  /*Configure GPIO pins : PA4 PA5 */
  GPIO_InitStruct.Pin = GPIO_PIN_4|GPIO_PIN_5;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
  if (htim->Instance == TIM4)
  {
    /* Stop after one update; the main loop schedules the next deadline. */
    HAL_TIM_Base_Stop_IT(htim);
    servo_timer_due = 1U;
  }
}

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  if (htim3.Instance == TIM3)
  {
    Motor_Stop(&htim3);
  }
  SystemFsm_HandleEvent(SYSTEM_EVENT_ERROR);
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
