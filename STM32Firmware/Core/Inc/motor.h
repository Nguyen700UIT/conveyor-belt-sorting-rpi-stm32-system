#ifndef MOTOR_DC_H
#define MOTOR_DC_H

#include "stm32f1xx_hal.h"

#define RPWM TIM_CHANNEL_3
#define LPWM TIM_CHANNEL_4
#define R_EN GPIO_PIN_4
#define L_EN GPIO_PIN_5

typedef enum
{
    RPWM_RUNNING, 
    LPWM_RUNNING, 
    MOTOR_STOPPED
} Motor_State;

void Motor_Set_Duty(TIM_HandleTypeDef *htim, uint32_t channel, uint8_t duty_percent); 
void Motor_Stop(TIM_HandleTypeDef* htim);

#define MOTOR_EN_PORT GPIOA
#endif /* MOTOR_DC_H */
