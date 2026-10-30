#ifndef SERVO_H
#define SERVO_H

#include "stm32f1xx_hal.h"

#define SERVO_1_PWM_CHANNEL TIM_CHANNEL_1
#define SERVO_2_PWM_CHANNEL TIM_CHANNEL_2
#define MIN_COUNTS 550U
#define MAX_COUNTS 2480U
//263 <  CCR < 2634

/* Requires a 1 MHz timer counter and a 20 ms PWM period.
 * angle: 0..180 degrees; 90 is the middle position (1500 us).
 * Start PWM separately with HAL_TIM_PWM_Start().
 */
void Set_Servo_Angle(TIM_HandleTypeDef* htim, uint32_t channel, int16_t angle);

#endif /* SERVO_H */
