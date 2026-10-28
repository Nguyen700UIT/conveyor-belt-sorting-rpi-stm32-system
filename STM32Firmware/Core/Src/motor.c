#include "motor.h"

static Motor_State state;

void Motor_Stop(TIM_HandleTypeDef* htim)
{
    if (htim == NULL) return;
    state = 0;
    HAL_GPIO_WritePin(MOTOR_EN_PORT, R_EN | L_EN, GPIO_PIN_RESET);

    __HAL_TIM_SET_COMPARE(htim, RPWM, 0);
    __HAL_TIM_SET_COMPARE(htim, LPWM, 0);
}

void Motor_Set_Duty(TIM_HandleTypeDef *htim, uint32_t channel, uint8_t duty_percent)
{
    if (htim == NULL) return;

    if (duty_percent > 100U)
    {
        duty_percent = 100U;
    }
    
    if (duty_percent == 0)
    {
        Motor_Stop(htim);
        return;
    }

    const uint32_t period_counts = __HAL_TIM_GET_AUTORELOAD(htim) + 1U;
    const uint32_t pulse = (period_counts * duty_percent) / 100U;

    switch(channel)
    {
        case RPWM: 
        {
            if (state == LPWM_RUNNING) return;
            state = RPWM_RUNNING;
            __HAL_TIM_SET_COMPARE(htim, LPWM, pulse);
            __HAL_TIM_SET_COMPARE(htim, RPWM, 0);
        }
        case LPWM:
        {
            if (state == RPWM_RUNNING) return;
            state = LPWM_RUNNING;
            __HAL_TIM_SET_COMPARE(htim, LPWM, pulse);
            __HAL_TIM_SET_COMPARE(htim, RPWM, 0);
            break;
        }
        default: 
        {
            return;
        }
    }

    HAL_GPIO_WritePin(MOTOR_EN_PORT, R_EN | L_EN, GPIO_PIN_SET);
} 
